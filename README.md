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

1. 예시 복사 후 값 채우기 (`config.yaml` 은 gitignore 됨):
   ```bash
   cp config.example.yaml config.yaml
   ```
2. 비민감 설정은 `config.yaml`, 민감정보는 환경변수/GitHub Secrets 로:

   | 환경변수 | 용도 |
   |----------|------|
   | `GH_API_TOKEN` | org 내 repo read 권한 PAT (⚠️ 기본 `GITHUB_TOKEN` 으론 크로스-레포 불가) |
   | `ANTHROPIC_API_KEY` | Claude 요약 |
   | `CONFLUENCE_EMAIL` / `CONFLUENCE_API_TOKEN` | Confluence Cloud 인증 |
   | `VAULT_REPO_TOKEN` | Obsidian vault 레포 push 권한 PAT |

## 로컬 실행

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

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
