from datetime import datetime, timezone

from weekly_report.models import Commit, category_label


def _commit(message: str) -> Commit:
    return Commit(
        repo="repo-a",
        sha="abcdef1234567890",
        message=message,
        author="alice",
        date=datetime(2026, 6, 30, tzinfo=timezone.utc),
        url="https://example.com/c/abcdef1",
    )


def test_short_sha():
    assert _commit("feat: x").short_sha == "abcdef1"


def test_subject_is_first_line():
    c = _commit("fix: bug\n\n본문 설명")
    assert c.subject == "fix: bug"


def test_conventional_category_detection():
    assert _commit("feat: 새 기능").category == "feat"
    assert _commit("fix(auth): 로그인").category == "fix"
    assert _commit("refactor!: 구조 변경").category == "refactor"
    assert _commit("FEAT: 대문자도").category == "feat"


def test_non_conventional_is_other():
    assert _commit("그냥 커밋 메시지").category == "other"
    assert _commit("Merge branch 'main'").category == "other"


def test_category_label_fallback():
    assert category_label("feat") == "✨ 기능"
    assert category_label("unknown-key") == category_label("other")
