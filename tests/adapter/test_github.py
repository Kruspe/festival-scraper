import json
from typing import Union
from unittest.mock import Mock, create_autospec

import pytest

from src.adapter.github import GitHubClient, GitHubException
from src.adapter.ssm import Ssm

github_token_endpoint = "https://accounts.spotify.com/api/token"
github_token_response = {
    "access_token": "token",
    "token_type": "bearer",
    "expires_in": 3600,
}


@pytest.fixture
def ssm_mock():
    ssm: Union[Mock, Ssm] = create_autospec(Ssm)
    ssm.get_parameters.return_value = {
        "/github/festival-scraper/pr-token": "gh_pr_token",
    }
    yield ssm


@pytest.fixture
def github_client(github_envs, ssm_mock, httpx_mock):
    yield GitHubClient(ssm=ssm_mock)


def test_search_artist_calls_correct_endpoint(github_client, httpx_mock):
    artist_name = "Bloodbath"
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/repos/kruspe/festival-scraper/pulls",
        status_code=201,
        match_content=json.dumps(
            {
                "title": f"Search for ArtistInformation manually: {artist_name}",
                "head": f"artistInfo/{artist_name}",
                "base": "main",
                "body": f"Could not find ArtistInformation for {artist_name}. Please look them up manually.",
            }
        ).encode("utf-8"),
        match_headers={
            "Authorization": "Bearer gh_pr_token",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    github_client.create_pr(artist_name=artist_name)


def test_search_artist_raises_and_logs_exception_when_search_fails(
    caplog, github_client, httpx_mock
):
    error_message = {"error": "error"}
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/repos/kruspe/festival-scraper/pulls",
        json=error_message,
        status_code=500,
    )

    with pytest.raises(GitHubException):
        github_client.create_pr(artist_name="Bloodbath")

    assert len(httpx_mock.get_requests()) == 1

    assert len(caplog.records) == 1
    for record in caplog.records:
        assert record.levelname == "ERROR"
        assert (
            record.getMessage()
            == "GitHub request to create PR returned status 500, " + str(error_message)
        )
