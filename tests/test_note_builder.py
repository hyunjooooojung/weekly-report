from datetime import datetime, timezone

from weekly_report.models import Commit
from weekly_report.note_builder import (
    ReportPeriod,
    build_note,
    note_filename,
)


def _period() -> ReportPeriod:
    return ReportPeriod(
        since=datetime(2026, 6, 24, tzinfo=timezone.utc),
        until=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


def _commits() -> list[Commit]:
    return [
        Commit("repo-a", "a" * 40, "feat: 새 대시보드", "alice",
               datetime(2026, 6, 25, tzinfo=timezone.utc), "https://x/a"),
        Commit("repo-a", "b" * 40, "fix: 널 포인터", "bob",
               datetime(2026, 6, 26, tzinfo=timezone.utc), "https://x/b"),
        Commit("repo-b", "c" * 40, "chore: 의존성 업데이트", "carol",
               datetime(2026, 6, 27, tzinfo=timezone.utc), "https://x/c"),
    ]


def test_week_label_and_filename():
    p = _period()
    # 2026-07-01 은 ISO 27주차.
    assert p.week_label == "2026-W27"
    assert note_filename(p) == "Weekly Report 2026-W27.md"


def test_build_note_contains_frontmatter_and_sections():
    note = build_note(_period(), _commits(), summary_markdown="## 요약\n- 어쩌구")
    assert note.startswith("---\n")
    assert "week: 2026-W27" in note
    assert "commit_count: 3" in note
    # AI 요약을 넘기면 미니 요약 아래에 'AI 요약' 섹션으로 붙는다.
    assert "## 📋 AI 요약" in note
    assert "## 📑 커밋 상세 (원본)" in note
    # repo 별 섹션과 커밋 링크가 있어야 함.
    assert "### repo-a" in note
    assert "### repo-b" in note
    assert "[`aaaaaaa`](https://x/a)" in note
    assert "_alice_" in note


def test_build_note_groups_by_category():
    note = build_note(_period(), _commits(), summary_markdown=None)
    # AI 요약을 안 넘기면 'AI 요약' 섹션은 빠진다.
    assert "## 📋 AI 요약" not in note
    assert "✨ 기능" in note
    assert "🐛 버그 수정" in note
    assert "🔧 기타" in note


def test_mini_summary_present_and_aggregates():
    # AI 요약이 없어도 무료 미니 요약은 항상 들어간다.
    note = build_note(_period(), _commits(), summary_markdown=None)
    assert "## 🧮 이번 주 요약" in note
    assert "총 **3** 커밋" in note
    # 카테고리별 개수 집계 (feat/fix/chore 각 1건).
    assert "✨ 기능 1" in note
    assert "🐛 버그 수정 1" in note
    assert "🔧 기타 1" in note
    # 최근 커밋(최신순) 목록에 sha 링크가 노출된다 (가장 최근 = repo-b chore).
    assert "([`ccccccc`](https://x/c))" in note


def test_build_note_empty_week():
    note = build_note(_period(), [], summary_markdown=None)
    assert "수집된 커밋이 없습니다" in note
    assert "commit_count: 0" in note
    # 빈 주에는 미니 요약도, 상세 부록도 만들지 않는다.
    assert "커밋 상세" not in note
    assert "이번 주 요약" not in note
