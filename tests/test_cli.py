from types import SimpleNamespace

from weekly_report.cli import _resolve_period


def _args(since=None, until=None):
    return SimpleNamespace(since=since, until=until)


def _cfg(lookback=7):
    return SimpleNamespace(schedule=SimpleNamespace(lookback_days=lookback))


def test_until_date_is_inclusive_end_of_day():
    p = _resolve_period(_cfg(), _args(since="2026-01-05", until="2026-01-09"))
    assert p.since.date().isoformat() == "2026-01-05"
    assert p.until.date().isoformat() == "2026-01-09"          # 표시는 금요일 그대로
    assert (p.until.hour, p.until.minute) == (23, 59)          # 하루 끝까지 포함
    assert p.week_label == "2026-W02"


def test_since_only_uses_lookback_for_until_now():
    # until 미지정이면 now 기준 (시각 성분 있음) — 하루끝 보정 대상 아님.
    p = _resolve_period(_cfg(), _args(since="2026-01-05"))
    assert p.since.date().isoformat() == "2026-01-05"
