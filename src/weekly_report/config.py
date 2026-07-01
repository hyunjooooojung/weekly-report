"""설정 로딩/검증.

비민감 설정은 YAML(config.yaml)에서, 민감정보(토큰류)는 환경변수에서 읽는다.
dataclass 로 구조화해 이후 모듈들이 오타 없이 안전하게 접근하도록 한다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ConfigError(Exception):
    """설정이 없거나 필수 값이 빠졌을 때 발생."""


# --- 비민감 설정 (YAML) ---------------------------------------------------


@dataclass
class GitHubConfig:
    org: str
    repos: list[str]
    branches: list[str] | None = None  # None 이면 각 repo 기본 브랜치


@dataclass
class ScheduleConfig:
    lookback_days: int = 7


@dataclass
class ObsidianConfig:
    vault_repo: str            # "owner/name"
    vault_branch: str = "main"
    notes_dir: str = "Weekly Reports"


@dataclass
class ConfluenceConfig:
    base_url: str              # ".../wiki" 까지 포함
    space_key: str
    parent_page_id: str = ""
    title_template: str = "주간 개발 리포트 {week}"


@dataclass
class SummarizerConfig:
    enabled: bool = True
    model: str = "claude-opus-4-8"
    language: str = "ko"


# --- 민감 설정 (환경변수) -------------------------------------------------


@dataclass
class Secrets:
    """환경변수에서 읽는 민감정보. 없는 값은 빈 문자열로 두고, 실제로

    필요한 단계에서 require_* 로 검증한다 (--dry-run 시엔 없어도 되게).
    """

    github_token: str = ""
    anthropic_api_key: str = ""
    confluence_email: str = ""
    confluence_api_token: str = ""
    vault_repo_token: str = ""

    @classmethod
    def from_env(cls) -> "Secrets":
        return cls(
            github_token=os.environ.get("GH_API_TOKEN", ""),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            confluence_email=os.environ.get("CONFLUENCE_EMAIL", ""),
            confluence_api_token=os.environ.get("CONFLUENCE_API_TOKEN", ""),
            vault_repo_token=os.environ.get("VAULT_REPO_TOKEN", ""),
        )

    def require(self, *names: str) -> None:
        """지정한 secret 들이 채워져 있는지 확인. 하나라도 없으면 ConfigError."""
        missing = [n for n in names if not getattr(self, n)]
        if missing:
            env_names = {
                "github_token": "GH_API_TOKEN",
                "anthropic_api_key": "ANTHROPIC_API_KEY",
                "confluence_email": "CONFLUENCE_EMAIL",
                "confluence_api_token": "CONFLUENCE_API_TOKEN",
                "vault_repo_token": "VAULT_REPO_TOKEN",
            }
            pretty = ", ".join(env_names.get(n, n) for n in missing)
            raise ConfigError(f"필수 환경변수가 없습니다: {pretty}")


# --- 통합 설정 ------------------------------------------------------------


@dataclass
class Config:
    github: GitHubConfig
    schedule: ScheduleConfig
    obsidian: ObsidianConfig
    confluence: ConfluenceConfig
    summarizer: SummarizerConfig
    secrets: Secrets = field(default_factory=Secrets)


def _require(section: dict, key: str, where: str):
    if key not in section or section[key] in (None, ""):
        raise ConfigError(f"config.yaml 의 [{where}] 에 '{key}' 값이 필요합니다.")
    return section[key]


def _parse_repos(raw) -> list[str]:
    """repos 값을 list[str] 로 정규화. 단일 문자열/콤마구분/YAML 리스트 모두 허용."""
    if isinstance(raw, str):
        items = [r.strip() for r in raw.split(",")]
    else:
        items = [str(r).strip() for r in raw]
    return [r for r in items if r]


def _parse_branches(raw) -> list[str] | None:
    """branches 값을 list[str] 로 정규화.

    - None / 빈 값 → None (각 repo 기본 브랜치 사용)
    - "dev, stg, main" 같은 콤마 구분 문자열 → ["dev", "stg", "main"]
    - YAML 리스트 → 그대로 (공백 제거)
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, str):
        items = [b.strip() for b in raw.split(",")]
    else:
        items = [str(b).strip() for b in raw]
    items = [b for b in items if b]
    return items or None


def load_config(path: str | os.PathLike = "config.yaml") -> Config:
    """YAML 파일 + 환경변수를 읽어 Config 를 만든다."""
    p = Path(path)
    if not p.exists():
        raise ConfigError(
            f"설정 파일을 찾을 수 없습니다: {p}. "
            "config.example.yaml 을 복사해 config.yaml 을 만드세요."
        )

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    gh = raw.get("github", {})
    github = GitHubConfig(
        org=_require(gh, "org", "github"),
        repos=_parse_repos(_require(gh, "repos", "github")),
        branches=_parse_branches(gh.get("branches") or gh.get("branch")),
    )
    if not github.repos:
        raise ConfigError("config.yaml 의 [github].repos 가 비어 있습니다.")

    sch = raw.get("schedule", {})
    schedule = ScheduleConfig(lookback_days=int(sch.get("lookback_days", 7)))

    ob = raw.get("obsidian", {})
    obsidian = ObsidianConfig(
        vault_repo=_require(ob, "vault_repo", "obsidian"),
        vault_branch=ob.get("vault_branch", "main"),
        notes_dir=ob.get("notes_dir", "Weekly Reports"),
    )

    cf = raw.get("confluence", {})
    confluence = ConfluenceConfig(
        base_url=str(_require(cf, "base_url", "confluence")).rstrip("/"),
        space_key=_require(cf, "space_key", "confluence"),
        parent_page_id=str(cf.get("parent_page_id", "") or ""),
        title_template=cf.get("title_template", "주간 개발 리포트 {week}"),
    )

    sm = raw.get("summarizer", {})
    summarizer = SummarizerConfig(
        enabled=bool(sm.get("enabled", True)),
        model=sm.get("model", "claude-opus-4-8"),
        language=sm.get("language", "ko"),
    )

    return Config(
        github=github,
        schedule=schedule,
        obsidian=obsidian,
        confluence=confluence,
        summarizer=summarizer,
        secrets=Secrets.from_env(),
    )
