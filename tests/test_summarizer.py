from datetime import datetime, timezone

from weekly_report.models import Commit
from weekly_report.summarizer import (
    _RETRO_MARKER,
    _build_data_prompt,
    _split_result,
)


def _commits() -> list[Commit]:
    return [
        Commit("repo-a", "a" * 40, "feat: x", "alice",
               datetime(2026, 6, 25, tzinfo=timezone.utc), "https://x/a"),
    ]


def test_split_result_with_marker():
    text = f"요약 본문입니다.\n{_RETRO_MARKER}\n회고 본문입니다."
    r = _split_result(text, retrospective=True)
    assert r.body == "요약 본문입니다."
    assert r.retrospective == "회고 본문입니다."


def test_split_result_no_marker():
    r = _split_result("요약만 있습니다.", retrospective=True)
    assert r.body == "요약만 있습니다."
    assert r.retrospective == ""


def test_split_result_retro_disabled_keeps_whole_body():
    # retrospective=False 면 구분선이 있어도 분리하지 않는다.
    text = f"요약\n{_RETRO_MARKER}\n회고"
    r = _split_result(text, retrospective=False)
    assert _RETRO_MARKER in r.body
    assert r.retrospective == ""


def test_build_prompt_marker_toggles_with_retrospective():
    with_retro = _build_data_prompt(_commits(), "ko", retrospective=True)
    without = _build_data_prompt(_commits(), "ko", retrospective=False)
    assert _RETRO_MARKER in with_retro
    assert _RETRO_MARKER not in without
    # 커밋 제목이 프롬프트에 직렬화된다.
    assert "feat: x" in with_retro
