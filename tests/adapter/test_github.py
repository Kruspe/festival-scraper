import json
from typing import Union
from unittest.mock import Mock, create_autospec

import pytest

from src.adapter.github import GitHubClient, GitHubException, GitHubIssue
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
    httpx_mock.add_response(
        method="GET",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        status_code=200,
        json=[],
        match_headers={
            "Authorization": "Bearer gh_pr_token",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    yield GitHubClient(ssm=ssm_mock)


def test_github_client_initializes_with_created_prs(github_envs, ssm_mock, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        status_code=200,
        json=[
            {"id": "1", "title": "Search for ArtistInformation manually: Bloodbath"},
            {"id": "2", "title": "Some other PR"},
        ],
        match_headers={
            "Authorization": "Bearer gh_pr_token",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    client = GitHubClient(ssm=ssm_mock)
    assert client.created_issues == {
        "bloodbath": GitHubIssue(id="1", artist_name="bloodbath")
    }


def test_github_client_initializes_raises_and_logs_exception_during_initialization(
    caplog, github_envs, ssm_mock, httpx_mock
):
    error_message = {"error": "error"}
    httpx_mock.add_response(
        method="GET",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        json=error_message,
        status_code=500,
    )

    with pytest.raises(GitHubException):
        GitHubClient(ssm=ssm_mock)

    assert len(httpx_mock.get_requests()) == 1

    assert len(caplog.records) == 1
    for record in caplog.records:
        assert record.levelname == "ERROR"
        assert (
            record.getMessage()
            == "GitHub request to retrieve PRs returned status 500, "
            + str(error_message)
        )


def test_create_issue_calls_correct_endpoint(github_client, httpx_mock):
    artist_name = "Bloodbath"
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        status_code=201,
        match_content=json.dumps(
            {
                "title": f"Search for ArtistInformation manually: {artist_name}",
                "body": f"Could not find ArtistInformation for {artist_name}. Please look them up manually.",
                "assignees": ["kruspe"],
            }
        ).encode("utf-8"),
        match_headers={
            "Authorization": "Bearer gh_pr_token",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    github_client.create_issue(artist_name=artist_name)


def test_create_issue_does_not_create_issue_when_it_already_exists(
    github_client, httpx_mock
):
    github_client.created_issues = ["hypocrisy"]
    github_client.create_issue(artist_name="Hypocrisy")

    assert len(httpx_mock.get_requests()) == 1


def test_create_issue_raises_and_logs_exception_when_search_fails(
    caplog, github_client, httpx_mock
):
    error_message = {"error": "error"}
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        json=error_message,
        status_code=500,
    )

    with pytest.raises(GitHubException):
        github_client.create_issue(artist_name="Bloodbath")

    assert len(httpx_mock.get_requests()) == 2

    assert len(caplog.records) == 1
    for record in caplog.records:
        assert record.levelname == "ERROR"
        assert (
            record.getMessage()
            == "GitHub request to create PR returned status 500, " + str(error_message)
        )


def test_close_issue_calls_correct_endpoint(github_client, httpx_mock):
    issue_number = "123"
    httpx_mock.add_response(
        method="PATCH",
        url=f"https://api.github.com/repos/kruspe/festival-scraper/issues/{issue_number}",
        status_code=200,
        match_content=json.dumps(
            {"state": "closed", "state_reason": "completed"}
        ).encode("utf-8"),
        match_headers={
            "Authorization": "Bearer gh_pr_token",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    github_client.close_issue(issue_id=issue_number)


def test_close_issue_raises_and_logs_exception_when_search_fails(
    caplog, github_client, httpx_mock
):
    issue_number = "123"
    error_message = {"error": "error"}
    httpx_mock.add_response(
        method="PATCH",
        url=f"https://api.github.com/repos/kruspe/festival-scraper/issues/{issue_number}",
        json=error_message,
        status_code=500,
    )

    with pytest.raises(GitHubException):
        github_client.close_issue(issue_id=issue_number)

    assert len(httpx_mock.get_requests()) == 2

    assert len(caplog.records) == 1
    for record in caplog.records:
        assert record.levelname == "ERROR"
        assert (
            record.getMessage()
            == "GitHub request to close PR returned status 500, " + str(error_message)
        )
