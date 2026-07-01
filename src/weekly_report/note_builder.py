"""[3] Obsidian 노트(Markdown) 생성.

부작용이 없는 순수 문자열 조립이라 단위 테스트가 쉽다. 최종 노트는
YAML frontmatter + AI 요약(있으면) + 원본 커밋 부록으로 구성된다.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from .models import CATEGORY_ORDER, Commit, category_label


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
    created: date | None = None,
) -> str:
    """완성된 Obsidian 노트 Markdown 을 반환한다.

    Args:
        period: 리포트 기간.
        commits: 수집된 커밋 (정렬 여부 무관, 내부에서 그룹화).
        summary_markdown: AI 요약 조각. None 이면 요약 섹션 생략.
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

    if summary_markdown:
        parts.append("## 📋 요약\n")
        parts.append(summary_markdown.strip() + "\n")

    parts.append("---\n")
    parts.append("## 📑 커밋 상세 (원본)\n")
    parts.append(_appendix(commits))

    return "\n".join(parts)


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


def _appendix(commits: list[Commit]) -> str:
    """repo → 카테고리 순으로 그룹화한 원본 커밋 목록."""
    by_repo: dict[str, list[Commit]] = defaultdict(list)
    for c in commits:
        by_repo[c.repo].append(c)

    lines: list[str] = []
    for repo in sorted(by_repo):
        lines.append(f"### {repo}\n")
        by_cat: dict[str, list[Commit]] = defaultdict(list)
        for c in by_repo[repo]:
            by_cat[c.category].append(c)

        # 정의된 카테고리 순서대로, 해당 repo 에 존재하는 것만 출력.
        for cat in CATEGORY_ORDER:
            group = by_cat.get(cat)
            if not group:
                continue
            lines.append(f"**{category_label(cat)}**\n")
            for c in sorted(group, key=lambda x: x.date):
                subject = c.subject.replace("\n", " ")
                lines.append(
                    f"- [`{c.short_sha}`]({c.url}) {subject} "
                    f"— _{c.author}_"
                )
            lines.append("")  # 그룹 사이 빈 줄

    return "\n".join(lines)
