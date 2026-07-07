"""GitHub Actions Variables 로부터 config.yaml 을 생성한다.

config.yaml 은 개인정보(org/repo/Confluence 주소 등)를 담을 수 있어 git 에
커밋하지 않는다. 대신 워크플로 실행 시 Actions Variables(vars.*) 에서 값을
읽어 이 스크립트가 config.yaml 을 만든다. 덕분에 나중에 레포를 public 으로
바꿔도 git 히스토리에 개인정보가 남지 않는다.

로컬 실행에는 사용하지 않는다 (로컬은 config.yaml 을 직접 만들어 쓴다).
"""

from __future__ import annotations

import os
import sys

import yaml


def _split(value: str | None) -> list[str]:
    """콤마 구분 문자열 → 공백 제거된 리스트."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"[gen_config] 필수 Actions Variable 이 없습니다: {name}")
    return value


def main() -> None:
    branches = _split(os.environ.get("GH_BRANCHES"))

    config = {
        "github": {
            "org": _require_env("GH_ORG"),
            "repos": _split(_require_env("GH_REPOS")),
            # 미지정 시 키를 생략해 각 repo 기본 브랜치를 사용.
            **({"branches": branches} if branches else {}),
        },
        "schedule": {"lookback_days": 7},
        "obsidian": {
            "vault_repo": _require_env("VAULT_REPO"),         # "owner/name" 형식
            "vault_branch": os.environ.get("VAULT_BRANCH", "").strip() or "main",
            # 저장 폴더 (vault 내 상대경로, 중첩 가능). 미지정 시 "Weekly Reports".
            "notes_dir": os.environ.get("NOTES_DIR", "").strip() or "Weekly Reports",
        },
        "confluence": {
            "base_url": _require_env("CONFLUENCE_BASE_URL"),
            "space_key": _require_env("CONFLUENCE_SPACE_KEY"),
            "parent_page_id": os.environ.get("CONFLUENCE_PARENT_PAGE_ID", "").strip(),
            "title_template": "주간 개발 리포트 {week}",
        },
        "summarizer": {
            # 기본 off — AI 요약은 Anthropic API 유료 과금이 발생하므로 끈다.
            # 대신 note_builder 가 API 없는 무료 집계 요약을 넣는다.
            # 개인 키가 생겨 켜려면 true 로 바꾸고 ANTHROPIC_API_KEY Secret 추가.
            "enabled": False,
            "model": "claude-opus-4-8",
            "language": "ko",
        },
    }

    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)

    print("[gen_config] config.yaml 생성 완료")


if __name__ == "__main__":
    main()
