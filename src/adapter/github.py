import logging
import os
from dataclasses import dataclass
from typing import Mapping

import httpx

from src.adapter.ssm import Ssm

logger = logging.getLogger(__name__)


@dataclass
class GitHubIssue:
    id: str
    artist_name: str


class GitHubClient:
    def __init__(self, *, ssm: Ssm):
        github_token = os.environ.get("GITHUB_TOKEN_PARAMETER_NAME")
        github_secret = ssm.get_parameters(
            parameter_names=[
                github_token,
            ]
        )
        self.token = github_secret[github_token]
        self.created_issues = self._retrieve_bands_with_created_issues()

    def create_issue(self, *, artist_name: str) -> None:
        if artist_name.lower() in self.created_issues:
            logger.info(f"PR for {artist_name} already exists")
            return
        response = httpx.post(
            "https://api.github.com/repos/kruspe/festival-scraper/issues",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "title": f"Search for ArtistInformation manually: {artist_name}",
                "body": f"Could not find ArtistInformation for {artist_name}. Please look them up manually.",
                "assignees": ["kruspe"],
            },
        )
        if response.status_code != 201:
            logger.error(
                "GitHub request to create PR returned status "
                + str(response.status_code)
                + ", "
                + str(response.json())
            )
            raise GitHubException("Failed to create PR")

    def close_issue(self, *, artist_name: str) -> None:
        if artist_name.lower() not in self.created_issues.keys():
            return
        response = httpx.patch(
            f"https://api.github.com/repos/kruspe/festival-scraper/issues/{self.created_issues[artist_name.lower()].id}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"state": "closed", "state_reason": "completed"},
        )

        if response.status_code != 200:
            logger.error(
                "GitHub request to close issue returned status "
                + str(response.status_code)
                + ", "
                + str(response.json())
                + f" https://api.github.com/repos/kruspe/festival-scraper/issues/{self.created_issues[artist_name.lower()].id}"
            )
            raise GitHubException("Failed to close PR")

    def _retrieve_bands_with_created_issues(self) -> Mapping[str, GitHubIssue]:
        response = httpx.get(
            "https://api.github.com/repos/kruspe/festival-scraper/issues",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

        if response.status_code != 200:
            logger.error(
                "GitHub request to retrieve PRs returned status "
                + str(response.status_code)
                + ", "
                + str(response.json())
            )
            raise GitHubException("Failed to retrieve PRs")

        result = {}
        for issue in response.json():
            if "Search for ArtistInformation manually" in issue["title"]:
                artist_name = issue["title"].split(": ")[1].lower()
                result[artist_name] = GitHubIssue(
                    id=issue["id"],
                    artist_name=artist_name,
                )
        return result


class GitHubException(Exception):
    pass
