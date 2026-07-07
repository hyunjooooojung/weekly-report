"""[3] Obsidian 노트(Markdown) 생성.

부작용이 없는 순수 문자열 조립이라 단위 테스트가 쉽다. 최종 노트 구조:
YAML frontmatter → (AI 요약 콜아웃) → 집계 → 프로젝트·날짜별 상세 → (회고 콜아웃).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from .models import CATEGORY_ORDER, Commit, category_label

_WEEKDAY_KO = "월화수목금토일"  # date.weekday(): 월=0 … 일=6


@dataclass
class ReportPeriod:
    """리포트가 다루는 기간과 ISO 주차 라벨."""

    since: datetime
    until: datetime

    @property
    def week_label(self) -> str:
        """ISO 주차 라벨 (예: 2026-W27). until 기준."""
        iso = self.until.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    @property
    def range_label(self) -> str:
        return f"{self.since.date().isoformat()} ~ {self.until.date().isoformat()}"


def note_filename(period: ReportPeriod) -> str:
    """vault 에 저장될 파일명."""
    return f"Weekly Report {period.week_label}.md"


def build_note(
    period: ReportPeriod,
    commits: list[Commit],
    summary_markdown: str | None,
    *,
    retrospective: str | None = None,
    created: date | None = None,
) -> str:
    """완성된 Obsidian 노트 Markdown 을 반환한다.

    Args:
        period: 리포트 기간.
        commits: 수집된 커밋 (정렬 여부 무관, 내부에서 그룹화).
        summary_markdown: AI 요약. None 이면 요약 콜아웃 생략.
        retrospective: AI 회고. None 이면 회고 콜아웃 생략.
        created: frontmatter 의 생성일. 기본은 period.until 날짜.
    """
    created = created or period.until.date()
    repos = sorted({c.repo for c in commits})

    parts: list[str] = []
    parts.append(_frontmatter(period, repos, created, len(commits)))
    parts.append(f"# 주간 개발 리포트 {period.week_label}\n")
    parts.append(f"**기간**: {period.range_label}  ")
    parts.append(f"**대상 리포지토리**: {', '.join(repos) if repos else '없음'}  ")
    parts.append(f"**총 커밋 수**: {len(commits)}\n")

    if not commits:
        parts.append("> 이번 주에는 수집된 커밋이 없습니다.\n")
        return "\n".join(parts)

    # AI 요약 (있을 때만) — Obsidian summary 콜아웃으로 강조.
    if summary_markdown:
        parts.append(_callout("summary", "이번 주 요약", summary_markdown))

    # 무료(집계형) 통계 — API 없이 커밋을 세어 항상 노출.
    parts.append(_stats(commits))

    parts.append("---\n")
    parts.append("## 📅 상세 (프로젝트·날짜별, 머지 제외)\n")
    parts.append(_detail(commits))

    # AI 회고 (있을 때만) — Obsidian note 콜아웃.
    if retrospective:
        parts.append(_callout("note", "한 주 회고", retrospective))

    return "\n".join(parts)


def _callout(kind: str, title: str, body: str) -> str:
    """Obsidian 콜아웃(`> [!kind] title`) 으로 본문을 감싼다."""
    lines = [f"> [!{kind}] {title}"]
    for ln in body.strip().splitlines():
        lines.append(f"> {ln}" if ln.strip() else ">")
    return "\n".join(lines) + "\n"


def _stats(commits: list[Commit]) -> str:
    """총 커밋수 + 카테고리별 개수(집계). API 없이 계산."""
    repos = sorted({c.repo for c in commits})
    counts: dict[str, int] = defaultdict(int)
    for c in commits:
        counts[c.category] += 1
    count_parts = [
        f"{category_label(cat)} {counts[cat]}"
        for cat in CATEGORY_ORDER
        if counts.get(cat)
    ]

    lines = ["## 🧮 집계\n", f"- 총 **{len(commits)}** 커밋 · {', '.join(repos)}"]
    if count_parts:
        lines.append(f"- {' · '.join(count_parts)}")
    return "\n".join(lines) + "\n"


def _weekday_ko(d: date) -> str:
    return _WEEKDAY_KO[d.weekday()]


def _detail(commits: list[Commit]) -> str:
    """repo → 날짜(요일) 순으로 그룹화한 커밋 목록.

    머지/브랜치동기 커밋은 노이즈라 상세에서 제외한다 (집계 수치에는 포함).
    """
    commits = [c for c in commits if not c.is_merge]
    by_repo: dict[str, list[Commit]] = defaultdict(list)
    for c in commits:
        by_repo[c.repo].append(c)

    lines: list[str] = []
    for repo in sorted(by_repo):
        lines.append(f"### {repo}\n")
        by_day: dict[date, list[Commit]] = defaultdict(list)
        for c in by_repo[repo]:
            by_day[c.date.date()].append(c)

        for day in sorted(by_day):
            lines.append(f"#### {day.month}/{day.day} ({_weekday_ko(day)})\n")
            for c in sorted(by_day[day], key=lambda x: x.date):
                emoji = category_label(c.category).split(" ", 1)[0]  # 라벨 앞 이모지
                subject = c.subject.replace("\n", " ")
                lines.append(
                    f"- {emoji} {subject} "
                    f"([`{c.short_sha}`]({c.url})) — _{c.author}_"
                )
            lines.append("")  # 날짜 그룹 사이 빈 줄

    return "\n".join(lines)


def _frontmatter(
    period: ReportPeriod, repos: list[str], created: date, total: int
) -> str:
    """Obsidian YAML frontmatter."""
    repo_lines = "\n".join(f"  - {r}" for r in repos) or "  []"
    return (
        "---\n"
        "tags:\n"
        "  - weekly-report\n"
        "  - dev\n"
        f"week: {period.week_label}\n"
        f"period_start: {period.since.date().isoformat()}\n"
        f"period_end: {period.until.date().isoformat()}\n"
        f"created: {created.isoformat()}\n"
        f"commit_count: {total}\n"
        "repos:\n"
        f"{repo_lines}\n"
        "---\n"
    )
