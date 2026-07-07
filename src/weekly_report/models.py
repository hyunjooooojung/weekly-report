"""파이프라인 단계 간에 주고받는 공용 데이터 구조."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

# Conventional Commits prefix → 사람이 읽는 카테고리 라벨.
_CATEGORY_LABELS: dict[str, str] = {
    "feat": "✨ 기능",
    "fix": "🐛 버그 수정",
    "refactor": "♻️ 리팩터링",
    "perf": "⚡ 성능",
    "docs": "📝 문서",
    "test": "✅ 테스트",
    "build": "📦 빌드",
    "ci": "🤖 CI",
    "style": "💄 스타일",
    "chore": "🔧 기타",
    "revert": "⏪ 되돌림",
    "other": "🗂 미분류",  # Conventional Commits prefix 가 없는 커밋 (chore='🔧 기타' 와 구분)
}

_CONVENTIONAL_RE = re.compile(r"^(?P<type>[a-z]+)(\([^)]*\))?!?:", re.IGNORECASE)

# Conventional 표준은 아니지만 실무에서 흔한 prefix → 표준 카테고리로 정규화.
_CATEGORY_ALIASES: dict[str, str] = {
    "hotfix": "fix",
    "bugfix": "fix",
}


@dataclass
class Commit:
    """수집된 커밋 하나."""

    repo: str
    sha: str            # full sha
    message: str        # 전체 메시지 (첫 줄 + 본문)
    author: str
    date: datetime
    url: str

    @property
    def short_sha(self) -> str:
        return self.sha[:7]

    @property
    def subject(self) -> str:
        """커밋 메시지 첫 줄."""
        return self.message.strip().splitlines()[0] if self.message.strip() else ""

    @property
    def is_merge(self) -> bool:
        """머지 커밋 추정. GitHub 기본 머지 메시지는 'Merge ' 로 시작한다.

        (예: 'Merge pull request #1 ...', 'Merge branch ...') 집계에는 포함하되
        요약의 '최근 커밋' 목록에서 걸러내는 용도.
        """
        return self.subject.startswith("Merge ")

    @property
    def category(self) -> str:
        """Conventional Commits prefix 로 추론한 카테고리 키 (없으면 'other')."""
        m = _CONVENTIONAL_RE.match(self.subject)
        if m:
            t = m.group("type").lower()
            t = _CATEGORY_ALIASES.get(t, t)   # hotfix→fix 등 별칭 정규화
            if t in _CATEGORY_LABELS:
                return t
        return "other"


def category_label(key: str) -> str:
    """카테고리 키를 사람이 읽는 라벨로."""
    return _CATEGORY_LABELS.get(key, _CATEGORY_LABELS["other"])


# note_builder / summarizer 가 카테고리를 일관된 순서로 노출하기 위한 정렬 기준.
CATEGORY_ORDER: list[str] = list(_CATEGORY_LABELS.keys())
