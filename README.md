# Weekly Report Pipeline

GitHub organization 내 지정 리포지토리들의 커밋을 매주 자동 수집하여,
**Claude 로 요약/분류**하고 원본 커밋 부록을 붙인 **Obsidian 노트**를 만들고,
별도 **Obsidian vault 레포**에 push + **Confluence Cloud**에 발행하는 파이프라인.

매주 GitHub Actions cron 으로 자동 실행됩니다.

## 파이프라인 구조

```
[1] GitHub 수집 → [2] Claude 요약 → [3] 노트 생성
                                        ├─→ [4] Obsidian vault 레포 push
                                        └─→ [5] Confluence 발행
```

| 모듈 | 역할 |
|------|------|
| `github_collector.py` | 기간 내 커밋 수집 (PyGithub) |
| `summarizer.py` | Claude 로 카테고리별 주간 요약 |
| `note_builder.py` | Obsidian 노트(frontmatter + 요약 + 원본 부록) 생성 |
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
| `ANTHROPIC_API_KEY` | (선택) AI 요약을 켤 때만. 기본 off 라 **등록 불필요** |

> **요약 방식**: 기본적으로 AI 요약은 **꺼져 있다**(`summarizer.enabled: false`).
> Anthropic API 는 claude.ai 구독과 별개로 유료 과금되기 때문. 대신 노트 상단에
> **API 없이 커밋을 집계한 무료 "미니 요약"**(카테고리별 개수 + 최근 커밋)이
> 들어간다. 서술형 AI 요약을 원하면 `enabled: true` + `ANTHROPIC_API_KEY` 를 추가.

**Variables** (같은 화면 → *Variables*):

| Variable | 예시 |
|----------|------|
| `GH_ORG` | `flunti` |
| `GH_REPOS` | `oiia` (여러 개면 콤마) |
| `GH_BRANCHES` | `dev,stg,main` (생략 시 기본 브랜치) |
| `VAULT_REPO` | `owner/name` (⚠️ URL 아님) |
| `VAULT_BRANCH` | `main` (선택) |
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

# 발행/푸시 없이 노트 Markdown 만 출력 (안전한 미리보기)
python -m weekly_report --dry-run --since 2026-06-24 --until 2026-07-01

python -m weekly_report --no-publish   # vault push 까지만
python -m weekly_report --no-vault     # Confluence 발행만
python -m weekly_report --no-summary   # AI 요약 생략
```

## 테스트

```bash
pip install pytest
pytest
```

## 자동 실행 (GitHub Actions)

- `.github/workflows/weekly-report.yml`: 매주 월요일 00:00 UTC(=09:00 KST) 실행.
- Repo Settings → Secrets 에 위 5개 값을 등록.
- 수동 테스트는 Actions 탭에서 **Run workflow** (기간/dry-run 지정 가능).

## 멱등성

- Confluence: 제목(`주간 개발 리포트 YYYY-Www`)이 같으면 새로 만들지 않고
  **버전만 올려 업데이트**합니다.
- Vault: 같은 파일명이면 덮어쓰고, 내용 변화가 없으면 커밋을 건너뜁니다.
