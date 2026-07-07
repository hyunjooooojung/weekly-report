#!/usr/bin/env bash
# 로컬 주간 리포트 실행 래퍼 (crontab / 수동 실행 공용).
#
# - 시크릿을 scripts/secrets.env(gitignore)에서 읽는다.
# - AI 요약은 claude CLI(구독 인증)를 쓰므로 ANTHROPIC_API_KEY 불필요.
# - 추가 인자는 파이프라인에 그대로 전달된다.
#     예) scripts/run_local.sh --dry-run
#         scripts/run_local.sh --since 2026-06-30 --until 2026-07-06
#
# 월요일 자동 실행을 놓쳤다면(맥이 꺼져 있었다면) 아무 날이나 이 스크립트를
# 직접 실행하면 된다. 인자 없이 실행하면 "최근 7일"을 정리한다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

# crontab 은 최소 PATH 로 실행되므로 claude/git 위치를 보강한다.
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"

# 시크릿 로드.
SECRETS="$SCRIPT_DIR/secrets.env"
if [ ! -f "$SECRETS" ]; then
  echo "[run_local] 시크릿 파일이 없습니다: $SECRETS" >&2
  echo "  cp scripts/secrets.env.example scripts/secrets.env 후 값을 채우세요." >&2
  exit 1
fi
set -a
# shellcheck disable=SC1090
. "$SECRETS"
set +a

# 가상환경 파이썬 우선.
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

exec "$PY" -m weekly_report "$@"
