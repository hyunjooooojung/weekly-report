"""[1] GitHub 커밋 수집.

organization 내 지정된 repo 들을 순회하며 주어진 기간(since~until) 안의
커밋을 모아 Commit 리스트로 돌려준다. PyGithub 를 사용해 페이지네이션을
자동 처리한다.
"""

from __future__ import annotations

import logging
from datetime import datetime

from github import Auth, Github
from github.GithubException import GithubException

from .config import GitHubConfig
from .models import Commit

logger = logging.getLogger(__name__)


def collect_commits(
    gh_config: GitHubConfig,
    token: str,
    since: datetime,
    until: datetime,
) -> list[Commit]:
    """[since, until] 기간의 커밋을 모든 대상 repo 에서 수집한다.

    Args:
        gh_config: org/repos/branch 설정.
        token: repo read 권한을 가진 PAT.
        since, until: 수집 기간 (timezone-aware 권장).

    Returns:
        날짜 오름차순으로 정렬된 Commit 리스트.
    """
    auth = Auth.Token(token)
    client = Github(auth=auth)
    commits: list[Commit] = []

    try:
        for repo_name in gh_config.repos:
            full_name = f"{gh_config.org}/{repo_name}"
            logger.info("커밋 수집 중: %s", full_name)
            try:
                repo = client.get_repo(full_name)
            except GithubException as exc:
                # 한 repo 접근 실패가 전체를 막지 않도록 경고 후 계속.
                logger.warning("repo 접근 실패 (%s): %s", full_name, exc)
                continue

            # 브랜치가 지정되면 각 브랜치를 순회하며 합집합을 구하고 sha 로
            # 중복 제거한다 (dev→stg→main 처럼 겹치는 커밋 방지). 미지정 시
            # None 하나만 돌려 repo 기본 브랜치를 사용한다.
            branches = gh_config.branches or [None]
            seen: set[str] = set()

            for branch in branches:
                # PyGithub 의 get_commits 는 since/until 과 sha(브랜치) 를 지원.
                kwargs: dict = {"since": since, "until": until}
                if branch:
                    kwargs["sha"] = branch
                try:
                    for c in repo.get_commits(**kwargs):
                        if c.sha in seen:
                            continue
                        seen.add(c.sha)
                        gc = c.commit  # git 수준 커밋 (author/message)
                        commits.append(
                            Commit(
                                repo=repo_name,
                                sha=c.sha,
                                message=gc.message or "",
                                author=_resolve_author(c, gc),
                                date=gc.author.date if gc.author else gc.committer.date,
                                url=c.html_url,
                            )
                        )
                except GithubException as exc:
                    # 존재하지 않는 브랜치 등은 경고 후 다음 브랜치로.
                    logger.warning(
                        "브랜치 수집 실패 (%s@%s): %s", full_name, branch, exc
                    )
    finally:
        client.close()

    commits.sort(key=lambda x: x.date)
    logger.info("총 %d 개 커밋 수집 완료", len(commits))
    return commits


def _resolve_author(commit, git_commit) -> str:
    """표시용 author 이름. GitHub 계정 login 을 우선, 없으면 git author name."""
    if commit.author and commit.author.login:
        return commit.author.login
    if git_commit.author and git_commit.author.name:
        return git_commit.author.name
    return "unknown"
