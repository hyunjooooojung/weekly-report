# Weekly Report Pipeline

GitHub organization 내 지정 리포지토리들의 커밋을 매주 자동 수집하여,
**Claude 로 요약/분류**하고 날짜별 커밋 상세를 붙인 **Obsidian 노트**를 만들고,
별도 **Obsidian vault 레포**에 push + **Confluence Cloud**에 발행하는 파이프라인.

**실행 방식은 두 가지**:
- **로컬 crontab (권장, 주간 자동 실행)** — AI 요약을 **Claude Code CLI(구독 인증)**로
  생성하므로 Anthropic API 추가 과금이 **없다**. 맥이 켜져 있어야 한다.
- **GitHub Actions (수동/백업)** — 클라우드엔 구독 CLI 가 없어 AI 요약은 꺼진 채
  (집계 요약만) 실행된다. 주간 cron 은 비활성, 수동 `Run workflow` 로만 사용.

## 파이프라인 구조

```
[1] GitHub 수집 → [2] Claude 요약 → [3] 노트 생성
                                        ├─→ [4] Obsidian vault 레포 push
                                        └─→ [5] Confluence 발행
```

| 모듈 | 역할 |
|------|------|
| `github_collector.py` | 기간 내 커밋 수집 (PyGithub) |
| `summarizer.py` | 주간 요약/회고 생성 — provider `claude_cli`(구독, 무과금) 또는 `api`(유료) |
| `note_builder.py` | Obsidian 노트 생성 (요약 콜아웃 + 집계 + 날짜별 상세 + 회고 콜아웃) |
| `vault_writer.py` | vault 레포 clone → 노트 커밋 → push |
| `confluence_publisher.py` | Markdown→storage 변환 후 페이지 생성/업데이트 |
| `cli.py` | 전체 오케스트레이션 |

## 설정

민감정보는 **GitHub Secrets**, 식별 설정은 **GitHub Actions Variables** 로 분리한다.
`config.yaml` 은 git 에 커밋하지 않고(개인정보 보호), 워크플로가 Variables 로부터
`scripts/gen_config.py` 로 생성한다. → 나중에 레포를 public 으로 바꿔도 히스토리에
개인정보가 남지 않는다.

**Secrets** (Settings → Secrets and variables → Actions → *Secrets*):

| Secret | 용도 |
|--------|------|
| `GH_API_TOKEN` | org 내 repo read 권한 PAT (⚠️ 기본 `GITHUB_TOKEN` 으론 크로스-레포 불가) |
| `CONFLUENCE_EMAIL` / `CONFLUENCE_API_TOKEN` | Confluence Cloud 인증 |
| `VAULT_REPO_TOKEN` | Obsidian vault 레포 write 권한 PAT |
| `ANTHROPIC_API_KEY` | (선택) provider=`api` 일 때만. 로컬 crontab(=`claude_cli`)엔 **불필요** |

> **요약 provider** (`config.yaml` 의 `summarizer.provider`):
> - `claude_cli` (로컬 기본) — 로컬 `claude` CLI 를 headless 호출. claude.ai
>   **구독으로 인증**되어 API 유료 과금이 없다. `ANTHROPIC_API_KEY` 불필요.
> - `api` — Anthropic SDK 직접 호출(유료). 구독 로그인이 없는 GitHub Actions 용.
> - GitHub Actions 경로는 `gen_config.py` 가 `enabled: false` 로 생성 → 클라우드
>   에선 AI 요약 없이 **집계 요약만** 나온다. AI 요약은 로컬 실행에서만.

**Variables** (같은 화면 → *Variables*):

| Variable | 예시 |
|----------|------|
| `GH_ORG` | `flunti` |
| `GH_REPOS` | `oiia` (여러 개면 콤마) |
| `GH_BRANCHES` | `dev,stg,main` (생략 시 기본 브랜치) |
| `VAULT_REPO` | `owner/name` (⚠️ URL 아님) |
| `VAULT_BRANCH` | `main` (선택) |
| `NOTES_DIR` | `Weekly Reports` (선택, 중첩 경로 가능. 미지정 시 기본값) |
| `CONFLUENCE_BASE_URL` | `https://xxx.atlassian.net/wiki` |
| `CONFLUENCE_SPACE_KEY` | `~6318...` |
| `CONFLUENCE_PARENT_PAGE_ID` | (선택) |

로컬 실행 시에는 `config.example.yaml` 을 복사해 직접 `config.yaml` 을 만든다:
```bash
cp config.example.yaml config.yaml   # 값 채우기 (gitignore 됨)
```

## 로컬 실행

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .            # 패키지 설치 (python -m weekly_report 사용 가능)

cp config.example.yaml config.yaml        # 값 채우기 (gitignore 됨)
cp scripts/secrets.env.example scripts/secrets.env   # 토큰 채우기 (gitignore 됨)

# 발행/푸시 없이 노트 Markdown 만 출력 (안전한 미리보기; AI 요약은 claude CLI 호출)
python -m weekly_report --dry-run --since 2026-06-24 --until 2026-07-01

python -m weekly_report --no-publish   # vault push 까지만
python -m weekly_report --no-vault     # Confluence 발행만
python -m weekly_report --no-summary   # AI 요약 생략(집계만)
```

## 로컬 자동 실행 (crontab, 권장)

주간 실행은 `scripts/run_local.sh` 래퍼로 돈다. 시크릿을 `scripts/secrets.env`
에서 읽고, AI 요약은 `claude` CLI(구독)로 생성한다 (`ANTHROPIC_API_KEY` 불필요).

```bash
cp scripts/secrets.env.example scripts/secrets.env   # 토큰 값 채우기
scripts/run_local.sh --dry-run                       # 먼저 미리보기로 확인

# crontab 등록 — 매주 월요일 09:00 KST 에 '지난주(월~금)' 를 정리. 로그는 scripts/logs/ 에.
crontab -e
# 아래 한 줄 추가 (경로는 프로젝트 절대경로로):
# 0 9 * * 1  cd /path/to/weekly-report && mkdir -p scripts/logs && \
#   scripts/run_local.sh --last-week >> "scripts/logs/$(date +\%Y-\%m-\%d).log" 2>&1
```

> `--last-week` 는 실행 시점 기준 **직전 주 월~금** 을 대상으로 한다 (backfill 과
> 동일한 주 경계). 과거 특정 주를 다시 만들려면 `--since/--until` 을 직접 준다.
> 과거 여러 주 일괄 생성은 `scripts/backfill.sh` 참고.

> **놓친 주 보정**: cron 은 맥이 꺼져 있던 시각의 작업을 나중에 실행하지 않는다.
> 월요일에 맥이 꺼져 있었다면, 아무 날이나 `scripts/run_local.sh` 를 직접 실행하면
> 된다. 특정 주를 정확히 지정하려면 `--since/--until` 을 준다.

## 테스트

```bash
pip install pytest
pytest
```

## 수동/백업 실행 (GitHub Actions)

- 주간 cron 은 **비활성화**됨 (AI 요약이 로컬 전용이라). 워크플로는 수동
  `Run workflow` (기간/dry-run 지정) 로만 사용한다.
- 이 경로는 AI 요약 없이 **집계 요약만** 생성한다 (클라우드엔 claude CLI 없음).
- Repo Settings → Secrets/Variables 값 필요 (위 표 참고).

## 멱등성

- Confluence: 제목(`주간 개발 리포트 YYYY-Www`)이 같으면 새로 만들지 않고
  **버전만 올려 업데이트**합니다.
- Vault: 같은 파일명이면 덮어쓰고, 내용 변화가 없으면 커밋을 건너뜁니다.
