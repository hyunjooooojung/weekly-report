"""[2] Claude 를 사용한 커밋 요약/분류.

수집된 커밋 메시지를 묶어 Claude 에 넘기고, 사람이 읽기 좋은 카테고리별
주간 요약(Markdown 조각)을 받는다. 커밋이 없으면 API 를 호출하지 않는다.
"""

from __future__ import annotations

import logging

from anthropic import Anthropic

from .config import SummarizerConfig
from .models import Commit, category_label

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
당신은 개발팀의 주간 활동을 정리하는 테크니컬 라이터입니다.
주어진 Git 커밋 목록을 바탕으로 이해관계자(팀 리더, 기획자 등)가 한눈에
파악할 수 있는 주간 요약을 작성하세요.

규칙:
- 출력은 순수 Markdown 조각으로만 (최상위 제목 #, frontmatter 없이).
- 카테고리별(기능/버그 수정/리팩터링/문서/기타 등)로 묶어 소제목(##)과
  불릿으로 정리하세요.
- 커밋 메시지를 그대로 나열하지 말고, 관련된 변경을 묶어 의미 단위로
  요약하세요. 중요한 변화는 앞쪽에 배치하세요.
- 커밋 해시나 저자를 본문에 나열할 필요는 없습니다 (원본은 별도 첨부됨).
- 과장 없이 사실 기반으로, 간결하게 작성하세요.
"""


def summarize(
    commits: list[Commit],
    config: SummarizerConfig,
    api_key: str,
) -> str:
    """커밋 목록의 Markdown 요약을 반환한다. 커밋이 없으면 빈 문자열."""
    if not commits:
        return ""

    client = Anthropic(api_key=api_key)
    prompt = _build_prompt(commits, config.language)

    logger.info("Claude(%s) 요약 요청: 커밋 %d개", config.model, len(commits))
    message = client.messages.create(
        model=config.model,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(
        block.text for block in message.content if block.type == "text"
    ).strip()
    return text


def _build_prompt(commits: list[Commit], language: str) -> str:
    """커밋들을 repo/카테고리 힌트와 함께 프롬프트 문자열로 직렬화."""
    lines: list[str] = [
        f"아래는 이번 주 커밋 목록입니다. {language} 로 요약해 주세요.",
        "각 줄 형식: [repo] (추정 카테고리) 커밋 제목",
        "",
    ]
    for c in commits:
        lines.append(f"- [{c.repo}] ({category_label(c.category)}) {c.subject}")
    return "\n".join(lines)
