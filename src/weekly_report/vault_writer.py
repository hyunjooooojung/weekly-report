"""[4] Obsidian vault 레포에 노트 push.

GitHub Actions 러너는 휘발성이므로, 생성한 노트를 별도 vault git 레포에
커밋/푸시해야 영구 보관된다. 임시 디렉터리에 shallow clone → 노트 파일
쓰기 → commit → push 순으로 동작한다. 동일 파일명이면 덮어써서 멱등.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from .config import ObsidianConfig, Secrets

logger = logging.getLogger(__name__)

_BOT_NAME = "github-actions[bot]"
_BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"


class VaultError(Exception):
    pass


def push_note(
    obsidian: ObsidianConfig,
    secrets: Secrets,
    filename: str,
    content: str,
) -> None:
    """노트를 vault 레포의 notes_dir 에 커밋/푸시한다."""
    token = secrets.vault_repo_token
    # 토큰을 URL 에 삽입해 HTTPS 인증. 로그에는 절대 남기지 않는다.
    clone_url = f"https://x-access-token:{token}@github.com/{obsidian.vault_repo}.git"
    safe_url = f"https://github.com/{obsidian.vault_repo}.git"

    with tempfile.TemporaryDirectory(prefix="vault-") as tmp:
        workdir = Path(tmp) / "vault"
        logger.info("vault 레포 clone: %s (branch=%s)", safe_url, obsidian.vault_branch)
        _git(
            [
                "clone", "--depth", "1",
                "--branch", obsidian.vault_branch,
                clone_url, str(workdir),
            ],
            cwd=Path(tmp),
            redact=token,
        )

        notes_dir = workdir / obsidian.notes_dir
        notes_dir.mkdir(parents=True, exist_ok=True)
        note_path = notes_dir / filename
        note_path.write_text(content, encoding="utf-8")

        _git(["config", "user.name", _BOT_NAME], cwd=workdir)
        _git(["config", "user.email", _BOT_EMAIL], cwd=workdir)
        _git(["add", "--", str(note_path.relative_to(workdir))], cwd=workdir)

        # 변경이 없으면 (동일 내용 재실행) 커밋을 건너뛴다.
        if not _has_staged_changes(workdir):
            logger.info("vault 변경 없음 — push 생략")
            return

        _git(
            ["commit", "-m", f"docs: 주간 리포트 {filename}"],
            cwd=workdir,
        )
        _git(["push", "origin", obsidian.vault_branch], cwd=workdir, redact=token)
        logger.info("vault push 완료: %s", filename)


def _has_staged_changes(cwd: Path) -> bool:
    """스테이징된 변경이 있는지 (git diff --cached --quiet 는 변경 시 exit 1)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=cwd,
        capture_output=True,
    )
    return result.returncode != 0


def _git(args: list[str], cwd: Path, redact: str | None = None) -> None:
    """git 명령 실행. 실패 시 토큰을 가린 메시지로 VaultError."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr
        if redact:
            stderr = stderr.replace(redact, "***")
        raise VaultError(f"git {args[0]} 실패: {stderr.strip()}")
