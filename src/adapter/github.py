import logging
import os
import httpx

from src.adapter.ssm import Ssm

logger = logging.getLogger(__name__)


class GitHubClient:
    def __init__(self, *, ssm: Ssm):
        github_pr_token = os.environ.get("GITHUB_PR_TOKEN_PARAMETER_NAME")
        github_pr_secret = ssm.get_parameters(
            parameter_names=[
                github_pr_token,
            ]
        )
        self.token = github_pr_secret[github_pr_token]
        self.created_prs = self._retrieve_bands_with_pr()

    def create_pr(self, *, artist_name: str) -> None:
        response = httpx.post(
            "https://api.github.com/repos/kruspe/festival-scraper/pulls",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "title": f"Search for ArtistInformation manually: {artist_name}",
                "head": f"artistInfo/{artist_name}",
                "base": "main",
                "body": f"Could not find ArtistInformation for {artist_name}. Please look them up manually.",
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

    def _retrieve_bands_with_pr(self) -> list[str]:
        response = httpx.get(
            "https://api.github.com/repos/kruspe/festival-scraper/pulls",
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

        result = []
        for pr in response.json():
            if "Search for ArtistInformation manually" in pr["title"]:
                result.append(pr["title"].split(": ")[1])
        return result


class GitHubException(Exception):
    pass
