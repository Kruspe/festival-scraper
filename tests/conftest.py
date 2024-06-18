import os

import pytest


@pytest.fixture
def spotify_envs():
    os.environ["SPOTIFY_CLIENT_ID_PARAMETER_NAME"] = "/spotify/client-id"
    os.environ["SPOTIFY_CLIENT_SECRET_PARAMETER_NAME"] = "/spotify/client-secret"
    yield
    del os.environ["SPOTIFY_CLIENT_ID_PARAMETER_NAME"]
    del os.environ["SPOTIFY_CLIENT_SECRET_PARAMETER_NAME"]
