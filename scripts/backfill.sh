#!/usr/bin/env bash
# 과거 주간 리포트 일괄 생성(백필). 각 주를 월~금 범위로 파이프라인 실행한다.
#
# 사용:
#   scripts/backfill.sh            # 실제 발행 (vault push + Confluence)
#   scripts/backfill.sh --dry-run  # 발행 없이 미리보기 (로그로만)
#
# 한 주가 실패해도 다음 주로 계속 진행하고, 마지막에 요약을 출력한다.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTRA="${1:-}"

# 생성할 주의 '월요일' 목록 (월~금). 2026-01-05 ~ 2026-06-29.
mondays=(
  2026-01-05 2026-01-12 2026-01-19 2026-01-26
  2026-02-02 2026-02-09 2026-02-16 2026-02-23
  2026-03-02 2026-03-09 2026-03-16 2026-03-23 2026-03-30
  2026-04-06 2026-04-13 2026-04-20 2026-04-27
  2026-05-04 2026-05-11 2026-05-18 2026-05-25
  2026-06-01 2026-06-08 2026-06-15 2026-06-22 2026-06-29
)

ok=0; fail=0; failed_weeks=""
for mon in "${mondays[@]}"; do
  # 금요일 = 월 + 4일 (macOS/BSD date).
  fri="$(date -j -v+4d -f "%Y-%m-%d" "$mon" "+%Y-%m-%d")"
  echo "======== ${mon} ~ ${fri} ========"
  if "$SCRIPT_DIR/run_local.sh" --since "$mon" --until "$fri" $EXTRA; then
    echo "  [OK] ${mon} ~ ${fri}"
    ok=$((ok+1))
  else
    echo "  [FAIL] ${mon} ~ ${fri} (exit $?)"
    fail=$((fail+1))
    failed_weeks="${failed_weeks} ${mon}"
  fi
done

echo "======== 백필 완료: 성공 ${ok}, 실패 ${fail} ========"
[ -n "$failed_weeks" ] && echo "실패한 주(월요일):${failed_weeks}"
exit 0
