"""[5] Confluence Cloud 발행 (REST API v2).

Markdown → HTML(storage format) 변환 후, 같은 제목의 페이지가 있으면
업데이트(version+1), 없으면 생성한다. 동일 주차 재실행 시 중복 페이지가
생기지 않도록 제목으로 멱등성을 보장한다.
"""

from __future__ import annotations

import logging

import markdown as md
import requests

from .config import ConfluenceConfig, Secrets

logger = logging.getLogger(__name__)

_TIMEOUT = 30


class ConfluenceError(Exception):
    pass


class ConfluencePublisher:
    def __init__(self, config: ConfluenceConfig, secrets: Secrets):
        self.config = config
        self.session = requests.Session()
        # Confluence Cloud 는 이메일:API토큰 의 HTTP Basic 인증.
        self.session.auth = (secrets.confluence_email, secrets.confluence_api_token)
        self.session.headers.update({"Accept": "application/json"})
        self._api = f"{config.base_url}/api/v2"

    # --- public ----------------------------------------------------------

    def publish(self, title: str, note_markdown: str) -> dict:
        """제목/본문으로 페이지를 생성 또는 업데이트하고 결과 dict 반환."""
        storage = markdown_to_storage(note_markdown)
        space_id = self._resolve_space_id(self.config.space_key)
        existing = self._find_page(space_id, title)

        if existing:
            logger.info("기존 페이지 업데이트: id=%s", existing["id"])
            return self._update_page(existing, title, storage)
        logger.info("새 페이지 생성: %s", title)
        return self._create_page(space_id, title, storage)

    # --- REST helpers ----------------------------------------------------

    def _resolve_space_id(self, space_key: str) -> str:
        """space key → 숫자 space id (v2 create/update 는 id 를 요구)."""
        resp = self.session.get(
            f"{self._api}/spaces",
            params={"keys": space_key, "limit": 1},
            timeout=_TIMEOUT,
        )
        _raise_for_status(resp, "space 조회 실패")
        results = resp.json().get("results", [])
        if not results:
            raise ConfluenceError(f"space key 를 찾을 수 없습니다: {space_key}")
        return results[0]["id"]

    def _find_page(self, space_id: str, title: str) -> dict | None:
        """같은 space 안에서 제목이 정확히 일치하는 current 페이지를 찾는다."""
        cursor: str | None = None
        while True:
            params = {"space-id": space_id, "title": title, "status": "current", "limit": 50}
            if cursor:
                params["cursor"] = cursor
            resp = self.session.get(
                f"{self._api}/pages", params=params, timeout=_TIMEOUT
            )
            _raise_for_status(resp, "페이지 조회 실패")
            data = resp.json()
            for page in data.get("results", []):
                if page.get("title") == title:
                    return page
            cursor = _next_cursor(data)
            if not cursor:
                return None

    def _create_page(self, space_id: str, title: str, storage: str) -> dict:
        body = {
            "spaceId": space_id,
            "status": "current",
            "title": title,
            "body": {"representation": "storage", "value": storage},
        }
        if self.config.parent_page_id:
            body["parentId"] = self.config.parent_page_id
        resp = self.session.post(
            f"{self._api}/pages", json=body, timeout=_TIMEOUT
        )
        _raise_for_status(resp, "페이지 생성 실패")
        return resp.json()

    def _update_page(self, existing: dict, title: str, storage: str) -> dict:
        page_id = existing["id"]
        current_version = existing.get("version", {}).get("number")
        if current_version is None:
            # 목록 응답에 version 이 없으면 상세 조회로 보강.
            current_version = self._current_version(page_id)
        body = {
            "id": page_id,
            "status": "current",
            "title": title,
            "body": {"representation": "storage", "value": storage},
            "version": {
                "number": current_version + 1,
                "message": "주간 리포트 자동 업데이트",
            },
        }
        resp = self.session.put(
            f"{self._api}/pages/{page_id}", json=body, timeout=_TIMEOUT
        )
        _raise_for_status(resp, "페이지 업데이트 실패")
        return resp.json()

    def _current_version(self, page_id: str) -> int:
        resp = self.session.get(
            f"{self._api}/pages/{page_id}", timeout=_TIMEOUT
        )
        _raise_for_status(resp, "페이지 버전 조회 실패")
        return resp.json()["version"]["number"]


# --- 변환/유틸 ------------------------------------------------------------


def markdown_to_storage(note_markdown: str) -> str:
    """Markdown → Confluence storage(XHTML) 문자열.

    storage format 은 XHTML 기반이라 표준 HTML 대부분을 그대로 받는다.
    표/코드블록/펜스 지원을 위해 확장을 활성화한다.
    """
    return md.markdown(
        note_markdown,
        extensions=["fenced_code", "tables", "sane_lists"],
    )


def _next_cursor(data: dict) -> str | None:
    """v2 페이지네이션: _links.next 의 cursor 쿼리값 추출."""
    next_link = data.get("_links", {}).get("next")
    if not next_link or "cursor=" not in next_link:
        return None
    # next_link 예: "/wiki/api/v2/pages?...&cursor=ABC123"
    from urllib.parse import parse_qs, urlparse

    qs = parse_qs(urlparse(next_link).query)
    values = qs.get("cursor")
    return values[0] if values else None


def _raise_for_status(resp: requests.Response, context: str) -> None:
    if resp.status_code >= 400:
        raise ConfluenceError(
            f"{context}: HTTP {resp.status_code} - {resp.text[:500]}"
        )
