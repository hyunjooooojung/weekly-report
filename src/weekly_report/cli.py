"""엔트리포인트 / 오케스트레이션.

config·기간 계산 → 커밋 수집 → (요약) → 노트 생성 → vault push + Confluence
발행 순으로 실행한다. 개발/검증용 플래그로 각 부작용 단계를 끌 수 있다.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

from . import github_collector, note_builder, summarizer
from .config import Config, ConfigError, load_config
from .confluence_publisher import ConfluencePublisher
from .note_builder import ReportPeriod
from .vault_writer import push_note

logger = logging.getLogger("weekly_report")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="weekly-report",
        description="GitHub 커밋 → Obsidian 노트 → Confluence 주간 리포트 파이프라인",
    )
    p.add_argument("-c", "--config", default="config.yaml", help="설정 파일 경로")
    p.add_argument("--since", help="수집 시작일 (YYYY-MM-DD). 생략 시 lookback_days 로 계산")
    p.add_argument("--until", help="수집 종료일 (YYYY-MM-DD). 생략 시 오늘")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="발행/push 없이 노트 Markdown 만 출력 (요약 API 는 설정에 따름)",
    )
    p.add_argument("--no-publish", action="store_true", help="Confluence 발행 생략")
    p.add_argument("--no-vault", action="store_true", help="vault push 생략")
    p.add_argument("--no-summary", action="store_true", help="AI 요약 생략")
    p.add_argument("-v", "--verbose", action="store_true", help="디버그 로그")
    return p.parse_args(argv)


def _resolve_period(cfg: Config, args: argparse.Namespace) -> ReportPeriod:
    """--since/--until 또는 lookback_days 로 기간을 계산 (UTC, tz-aware)."""
    if args.until:
        until = datetime.fromisoformat(args.until).replace(tzinfo=timezone.utc)
        # 'YYYY-MM-DD' 처럼 자정으로 들어오면 그 날 전체를 포함하도록 하루 끝으로.
        # (예: --until 2026-01-09 → 금요일 커밋까지 온전히 수집)
        if (until.hour, until.minute, until.second) == (0, 0, 0):
            until = until + timedelta(days=1) - timedelta(microseconds=1)
    else:
        until = datetime.now(timezone.utc)

    if args.since:
        since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    else:
        since = until - timedelta(days=cfg.schedule.lookback_days)

    return ReportPeriod(since=since, until=until)


def run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    period = _resolve_period(cfg, args)
    logger.info("리포트 기간: %s", period.range_label)

    # [1] 커밋 수집 (항상 토큰 필요)
    cfg.secrets.require("github_token")
    commits = github_collector.collect_commits(
        cfg.github, cfg.secrets.github_token, period.since, period.until
    )

    # [2] 요약 (선택). provider 에 따라 Claude CLI(구독) 또는 API 사용.
    summary = None
    retrospective = None
    want_summary = cfg.summarizer.enabled and not args.no_summary
    if want_summary and commits:
        result = summarizer.generate(commits, cfg.summarizer, cfg.secrets)
        summary = result.body or None
        retrospective = result.retrospective or None

    # [3] 노트 생성
    note_md = note_builder.build_note(
        period, commits, summary, retrospective=retrospective
    )
    filename = note_builder.note_filename(period)

    if args.dry_run:
        logger.info("dry-run: 발행/푸시 생략, 노트만 출력합니다.\n")
        print(note_md)
        return 0

    # [4] vault push (선택)
    if not args.no_vault:
        cfg.secrets.require("vault_repo_token")
        push_note(cfg.obsidian, cfg.secrets, filename, note_md)
    else:
        logger.info("--no-vault: vault push 생략")

    # [5] Confluence 발행 (선택)
    if not args.no_publish:
        cfg.secrets.require("confluence_email", "confluence_api_token")
        title = cfg.confluence.title_template.format(week=period.week_label)
        publisher = ConfluencePublisher(cfg.confluence, cfg.secrets)
        result = publisher.publish(title, note_md)
        page_id = result.get("id", "?")
        logger.info("Confluence 발행 완료: '%s' (id=%s)", title, page_id)
    else:
        logger.info("--no-publish: Confluence 발행 생략")

    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        return run(args)
    except ConfigError as exc:
        logger.error("설정 오류: %s", exc)
        return 2
    except Exception as exc:  # 파이프라인 실패를 명확히 노출
        logger.exception("파이프라인 실패: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
