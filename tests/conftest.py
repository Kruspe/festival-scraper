import os

import pytest


@pytest.fixture
def spotify_envs():
    os.environ["SPOTIFY_CLIENT_ID_PARAMETER_NAME"] = "/spotify/client-id"
    os.environ["SPOTIFY_CLIENT_SECRET_PARAMETER_NAME"] = "/spotify/client-secret"
    os.environ["DEBUG_ARTIST_NAME"] = ""
    yield
    del os.environ["SPOTIFY_CLIENT_ID_PARAMETER_NAME"]
    del os.environ["SPOTIFY_CLIENT_SECRET_PARAMETER_NAME"]
    del os.environ["DEBUG_ARTIST_NAME"]


@pytest.fixture
def github_envs():
    os.environ["GITHUB_TOKEN_PARAMETER_NAME"] = "/github/festival-scraper/pr-token"
    yield
    del os.environ["GITHUB_TOKEN_PARAMETER_NAME"]
