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


def test_build_note_frontmatter_and_stats():
    note = build_note(_period(), _commits(), summary_markdown=None)
    assert note.startswith("---\n")
    assert "week: 2026-W27" in note
    assert "commit_count: 3" in note
    # 집계 블록 (API 없이 계산).
    assert "## 🧮 집계" in note
    assert "총 **3** 커밋" in note
    assert "✨ 기능 1" in note
    assert "🐛 버그 수정 1" in note
    assert "🔧 기타 1" in note


def test_build_note_detail_grouped_by_date():
    note = build_note(_period(), _commits(), summary_markdown=None)
    assert "## 📅 상세 (프로젝트·날짜별)" in note
    assert "### repo-a" in note
    assert "### repo-b" in note
    # 날짜(요일) 소제목과 커밋 링크/저자.
    assert "#### 6/25 (" in note
    assert "[`aaaaaaa`](https://x/a)" in note
    assert "_alice_" in note


def test_summary_callout_present_and_prefixed():
    note = build_note(
        _period(), _commits(),
        summary_markdown="## 기능\n- 대시보드 추가",
    )
    assert "> [!summary] 이번 주 요약" in note
    # 콜아웃 본문은 각 줄이 '> ' 로 prefix 된다.
    assert "> ## 기능" in note
    assert "> - 대시보드 추가" in note


def test_no_summary_no_retrospective_callouts():
    note = build_note(_period(), _commits(), summary_markdown=None)
    assert "[!summary]" not in note
    assert "[!note]" not in note


def test_retrospective_callout():
    note = build_note(
        _period(), _commits(),
        summary_markdown=None,
        retrospective="이번 주는 결제 안정화에 집중했다.",
    )
    assert "> [!note] 한 주 회고" in note
    assert "> 이번 주는 결제 안정화에 집중했다." in note


def test_build_note_empty_week():
    note = build_note(_period(), [], summary_markdown=None)
    assert "수집된 커밋이 없습니다" in note
    assert "commit_count: 0" in note
    # 빈 주에는 상세/집계를 만들지 않는다.
    assert "상세" not in note
    assert "집계" not in note
