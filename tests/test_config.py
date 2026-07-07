import yaml

from weekly_report.config import SummarizerConfig, _parse_branches, _parse_repos


def test_summarizer_defaults_to_claude_cli():
    s = SummarizerConfig()
    assert s.provider == "claude_cli"   # 로컬 구독 CLI 가 기본 (무과금)
    assert s.retrospective is False


def test_parse_repos_single_string():
    # "oiia" 를 문자별로 쪼개면 안 된다.
    assert _parse_repos("oiia") == ["oiia"]


def test_parse_repos_comma_and_list():
    assert _parse_repos("a, b ,c") == ["a", "b", "c"]
    assert _parse_repos(["x", " y "]) == ["x", "y"]


def test_parse_branches_variants():
    assert _parse_branches(None) is None
    assert _parse_branches("") is None
    assert _parse_branches("dev, stg, main") == ["dev", "stg", "main"]
    assert _parse_branches(["dev", "main"]) == ["dev", "main"]


def test_personal_space_key_roundtrips_as_string():
    # 개인 space key 는 '~' 로 시작 — YAML 이 null 로 오해하지 않는지 확인.
    key = "~6318c0df8473817d7d05f9bf"
    dumped = yaml.safe_dump({"space_key": key}, allow_unicode=True)
    loaded = yaml.safe_load(dumped)
    assert loaded["space_key"] == key
    assert isinstance(loaded["space_key"], str)
