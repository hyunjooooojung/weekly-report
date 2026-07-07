"""[2] 커밋 요약/분류.

두 가지 provider 를 지원한다:
- "claude_cli": 로컬 Claude Code CLI(`claude -p`)를 headless 로 호출. claude.ai
  구독으로 인증되므로 Anthropic API 유료 과금이 없다. (로컬 실행 전용)
- "api": Anthropic SDK 직접 호출. ANTHROPIC_API_KEY 필요(유료). GitHub Actions
  같은 구독 로그인이 없는 환경용.

요약 본문과 (옵션) "한 주 회고" 를 생성한다. 커밋이 없으면 호출하지 않는다.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

from .config import Secrets, SummarizerConfig
from .models import Commit, category_label

logger = logging.getLogger(__name__)

# 요약과 회고를 한 번의 호출로 받고 이 구분선으로 분리한다.
_RETRO_MARKER = "===회고==="

_SYSTEM_PROMPT = """\
당신은 개발팀의 주간 활동을 정리하는 테크니컬 라이터입니다.
주어진 Git 커밋 목록을 바탕으로 이해관계자(팀 리더, 기획자 등)가 한눈에
파악할 수 있는 주간 요약을 작성하세요.

규칙:
- 인사말이나 "작성하겠습니다" 같은 서두·메타 문장 없이, 첫 줄부터 곧바로
  요약 Markdown 만 출력하세요. (설명·맺음말 금지)
- 출력은 순수 Markdown 조각으로만 (최상위 제목 #, frontmatter, 코드펜스 없이).
- 카테고리별(기능/버그 수정/리팩터링/문서/기타 등)로 묶어 소제목(##)과
  불릿으로 정리하세요.
- 커밋 메시지를 그대로 나열하지 말고, 관련된 변경을 묶어 의미 단위로
  요약하세요. 중요한 변화는 앞쪽에 배치하세요.
- 커밋 해시나 저자를 본문에 나열할 필요는 없습니다 (원본은 별도 첨부됨).
- 머지 커밋(Merge ...)은 요약에서 제외하세요.
- 과장 없이 사실 기반으로, 간결하게 작성하세요.
"""


class SummarizerError(Exception):
    pass


@dataclass
class SummaryResult:
    """요약 결과. 둘 다 Markdown 조각(콜아웃 본문으로 들어감)."""

    body: str = ""            # 주간 요약
    retrospective: str = ""   # 한 주 회고 (retrospective=False 면 빈 문자열)


def generate(
    commits: list[Commit],
    config: SummarizerConfig,
    secrets: Secrets,
) -> SummaryResult:
    """provider 에 맞춰 요약을 생성한다. 커밋이 없으면 빈 결과."""
    if not commits:
        return SummaryResult()

    if config.provider == "claude_cli":
        return _summarize_via_cli(commits, config)
    if config.provider == "api":
        secrets.require("anthropic_api_key")
        body = _summarize_via_api(commits, config, secrets.anthropic_api_key)
        return SummaryResult(body=body)
    raise SummarizerError(f"알 수 없는 summarizer provider: {config.provider}")


# --- Claude Code CLI (구독, 무과금) --------------------------------------


def _summarize_via_cli(commits: list[Commit], config: SummarizerConfig) -> SummaryResult:
    prompt = _build_prompt(commits, config.language, config.retrospective)
    logger.info("Claude CLI(%s) 요약 요청: 커밋 %d개", config.model, len(commits))
    text = _run_claude_cli(prompt, config.model)
    return _split_result(text, config.retrospective)


def _run_claude_cli(prompt: str, model: str) -> str:
    """`claude -p` 를 headless 로 실행해 응답 텍스트를 반환한다."""
    try:
        result = subprocess.run(
            ["claude", "-p", "--model", model],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError as exc:
        raise SummarizerError(
            "claude CLI 를 찾을 수 없습니다. 로컬에 Claude Code 가 설치·로그인되어 "
            "있어야 provider=claude_cli 를 쓸 수 있습니다."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise SummarizerError("claude CLI 응답 시간 초과(300s).") from exc

    if result.returncode != 0:
        raise SummarizerError(
            f"claude CLI 실패(exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _split_result(text: str, retrospective: bool) -> SummaryResult:
    """요약/회고 구분선으로 결과를 나눈다."""
    if retrospective and _RETRO_MARKER in text:
        body, _, retro = text.partition(_RETRO_MARKER)
        return SummaryResult(body=body.strip(), retrospective=retro.strip())
    return SummaryResult(body=text.strip())


# --- Anthropic SDK (API, 유료) -------------------------------------------


def _summarize_via_api(
    commits: list[Commit], config: SummarizerConfig, api_key: str
) -> str:
    from anthropic import Anthropic  # 지연 import: CLI provider 만 쓸 땐 불필요.

    client = Anthropic(api_key=api_key)
    prompt = _build_prompt(commits, config.language, retrospective=False)

    logger.info("Claude API(%s) 요약 요청: 커밋 %d개", config.model, len(commits))
    message = client.messages.create(
        model=config.model,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(
        block.text for block in message.content if block.type == "text"
    ).strip()


# --- 공용 프롬프트 --------------------------------------------------------


def _build_prompt(commits: list[Commit], language: str, retrospective: bool) -> str:
    """커밋들을 repo/카테고리 힌트와 함께 프롬프트 문자열로 직렬화."""
    lines: list[str] = [
        _SYSTEM_PROMPT,
        "",
        f"아래는 이번 주 커밋 목록입니다. {language} 로 요약해 주세요.",
        "각 줄 형식: [repo] (추정 카테고리) 커밋 제목",
        "",
    ]
    for c in commits:
        lines.append(f"- [{c.repo}] ({category_label(c.category)}) {c.subject}")

    if retrospective:
        lines += [
            "",
            f"요약을 먼저 작성한 뒤, 반드시 아래 구분선을 한 줄로 출력하세요:",
            _RETRO_MARKER,
            "그 다음 이번 주 작업에 대한 '한 주 회고'를 2~4문장으로 작성하세요 "
            "(잘된 점/아쉬운 점/다음 주 관점). 구분선 위에는 회고를 쓰지 마세요.",
        ]
    return "\n".join(lines)
