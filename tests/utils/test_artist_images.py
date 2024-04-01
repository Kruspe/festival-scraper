import copy
import json
import os
from base64 import b64encode
from typing import Union
from unittest.mock import Mock, create_autospec

import pytest

from src.adapter.s3 import S3
from src.adapter.ssm import Ssm
from src.utils.artist_images import Helper, SpotifyException

url = spotify_token_endpoint = "https://accounts.spotify.com/api/token"
spotify_token_response = {
    "access_token": "token",
    "token_type": "bearer",
    "expires_in": 3600,
}
expected_bloodbath_image_url = "https://bloodbath_image.com"
bloodbath_search_response = {
    "artists": {
        "items": [
            {
                "images": [
                    {"height": 640, "url": expected_bloodbath_image_url, "width": 640},
                ],
                "name": "Bloodbath",
            },
        ],
    }
}


@pytest.fixture
def artist_images():
    ssm: Union[Mock, Ssm] = create_autospec(Ssm)
    ssm.get_parameters.return_value = {
        "/spotify/client-id": "client_id",
        "/spotify/client-secret": "client_secret",
    }
    s3: S3 = create_autospec(S3)

    yield Helper(ssm=ssm, s3=s3)


@pytest.fixture
def spotify_envs():
    os.environ["SPOTIFY_CLIENT_ID_PARAMETER_NAME"] = "/spotify/client-id"
    os.environ["SPOTIFY_CLIENT_SECRET_PARAMETER_NAME"] = "/spotify/client-secret"
    yield
    del os.environ["SPOTIFY_CLIENT_ID_PARAMETER_NAME"]
    del os.environ["SPOTIFY_CLIENT_SECRET_PARAMETER_NAME"]


@pytest.fixture
def bucket_env():
    os.environ["FESTIVAL_ARTISTS_BUCKET"] = "MockedBucket"
    yield
    del os.environ["FESTIVAL_ARTISTS_BUCKET"]


@pytest.mark.asyncio
async def test_get_images_with_empty_list_empty_dict(artist_images, httpx_mock):
    images = await artist_images.get_images(artist_names=[])
    assert images == {}
    assert len(httpx_mock.get_requests()) == 0


@pytest.mark.asyncio
async def test_get_images_raises_and_logs_exception_when_getting_token_fails(
    caplog, artist_images, spotify_envs, httpx_mock
):
    error_message = {"error": "error"}
    httpx_mock.add_response(
        method="POST", url=spotify_token_endpoint, json=error_message, status_code=500
    )

    with pytest.raises(SpotifyException):
        await artist_images.get_images(artist_names=["Bloodbath"])

    assert len(httpx_mock.get_requests()) == 1
    assert httpx_mock.get_requests()[0].url == spotify_token_endpoint

    assert len(caplog.records) == 1
    for record in caplog.records:
        assert record.levelname == "ERROR"
        expected_log_message = "Spotify token endpoint returned status 500, " + str(
            error_message
        )
        assert record.getMessage() == expected_log_message


@pytest.mark.asyncio
async def test_get_images_raises_and_logs_exception_when_search_fails(
    caplog, artist_images, spotify_envs, httpx_mock
):
    error_message = {"error": "error"}
    httpx_mock.add_response(
        method="POST",
        url=spotify_token_endpoint,
        json=spotify_token_response,
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath",
        json=error_message,
        status_code=500,
    )

    with pytest.raises(SpotifyException):
        await artist_images.get_images(artist_names=["Bloodbath"])

    assert len(httpx_mock.get_requests()) == 2
    print(httpx_mock.get_requests()[0].url)
    assert httpx_mock.get_requests()[0].url == spotify_token_endpoint
    assert (
        httpx_mock.get_requests()[1].url
        == "https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath"
    )

    assert len(caplog.records) == 1
    for record in caplog.records:
        assert record.levelname == "ERROR"
        assert record.getMessage() == "Spotify search returned status 500, " + str(
            error_message
        )


@pytest.mark.asyncio
async def test_get_images_endpoints_get_called_correctly(
    artist_images, spotify_envs, httpx_mock
):
    authorization_header_key = "Authorization"
    authorization_header_value = (
        f"Basic {b64encode(b'client_id:client_secret').decode('utf-8')}"
    )
    content_type_header_key = "Content-Type"
    content_type_header_value = "application/x-www-form-urlencoded"
    expected_body = b'"grant_type=client_credentials"'

    httpx_mock.add_response(
        method="POST",
        url=spotify_token_endpoint,
        json=spotify_token_response,
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath",
        json=bloodbath_search_response,
        status_code=200,
    )

    await artist_images.get_images(artist_names=["Bloodbath"])

    assert len(httpx_mock.get_requests()) == 2
    assert httpx_mock.get_requests()[0].url == spotify_token_endpoint
    assert (
        httpx_mock.get_requests()[1].url
        == "https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath"
    )

    assert httpx_mock.get_requests()[0].content == expected_body
    assert authorization_header_key in httpx_mock.get_requests()[0].headers
    assert content_type_header_key in httpx_mock.get_requests()[0].headers
    assert (
        httpx_mock.get_requests()[0].headers[authorization_header_key]
        == authorization_header_value
    )
    assert (
        httpx_mock.get_requests()[0].headers[content_type_header_key]
        == content_type_header_value
    )

    assert authorization_header_key in httpx_mock.get_requests()[1].headers
    assert (
        httpx_mock.get_requests()[1].headers[authorization_header_key] == "Bearer token"
    )


@pytest.mark.asyncio
async def test_get_images_returns_correct_images_for_two_bands(
    artist_images, spotify_envs, httpx_mock
):
    expected_megadeth_image_url = "https://megadeth_image.com"
    megadeth_search_response = copy.deepcopy(bloodbath_search_response)
    megadeth_search_response["artists"]["items"][0]["name"] = "Megadeth"
    megadeth_search_response["artists"]["items"][0]["images"][0]["url"] = (
        expected_megadeth_image_url
    )

    httpx_mock.add_response(
        method="POST",
        url=spotify_token_endpoint,
        json=spotify_token_response,
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath",
        json=bloodbath_search_response,
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Megadeth",
        json=megadeth_search_response,
        status_code=200,
    )

    images = await artist_images.get_images(artist_names=["Bloodbath", "Megadeth"])

    assert len(httpx_mock.get_requests()) == 3

    assert images == {
        "Bloodbath": expected_bloodbath_image_url,
        "Megadeth": expected_megadeth_image_url,
    }


@pytest.mark.asyncio
async def test_get_images_returns_none_when_no_artist_was_found(
    artist_images, spotify_envs, httpx_mock
):
    search_response = {
        "artists": {
            "items": [],
        }
    }
    httpx_mock.add_response(
        method="POST",
        url=spotify_token_endpoint,
        json=spotify_token_response,
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath",
        json=search_response,
        status_code=200,
    )

    images = await artist_images.get_images(artist_names=["Bloodbath"])

    assert len(httpx_mock.get_requests()) == 2
    assert images == {"Bloodbath": None}


@pytest.mark.asyncio
async def test_get_images_returns_none_when_no_name_matches_search(
    artist_images, spotify_envs, httpx_mock
):
    search_response = {
        "artists": {
            "items": [
                {
                    "images": [],
                    "name": "NoMatch",
                },
            ],
        }
    }
    httpx_mock.add_response(
        method="POST",
        url=spotify_token_endpoint,
        json=spotify_token_response,
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Attic",
        json=search_response,
        status_code=200,
    )

    images = await artist_images.get_images(artist_names=["Attic"])

    assert len(httpx_mock.get_requests()) == 2
    assert images == {"Attic": None}


@pytest.mark.asyncio
async def test_get_images_returns_first_image_for_matching_name(
    artist_images, spotify_envs, httpx_mock
):
    expected_image_url = "https://expected_image.com"
    search_response_with_two_name_matches = copy.deepcopy(bloodbath_search_response)
    search_response_with_two_name_matches["artists"]["items"][0]["images"][0]["url"] = (
        expected_image_url
    )
    search_response_with_two_name_matches["artists"]["items"].append(
        {
            "images": [
                {"height": 300, "url": "https://different_image.com", "width": 300},
            ],
            "name": "Bloodbath",
        }
    )

    httpx_mock.add_response(
        method="POST",
        url=spotify_token_endpoint,
        json=spotify_token_response,
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath",
        json=search_response_with_two_name_matches,
        status_code=200,
    )

    images = await artist_images.get_images(artist_names=["Bloodbath"])

    assert len(httpx_mock.get_requests()) == 2

    assert images == {"Bloodbath": expected_image_url}


@pytest.mark.asyncio
async def test_get_images_returns_first_image_that_is_greater_than_400_in_width_and_height(
    artist_images, spotify_envs, httpx_mock
):
    search_response = {
        "artists": {
            "items": [
                {
                    "images": [
                        {
                            "height": 1000,
                            "url": "https://too_big_image.com",
                            "width": 1000,
                        },
                        {
                            "height": 300,
                            "url": expected_bloodbath_image_url,
                            "width": 300,
                        },
                        {
                            "height": 420,
                            "url": "https://width_too_small.com",
                            "width": 120,
                        },
                        {
                            "height": 120,
                            "url": "https://too_small_image.com",
                            "width": 120,
                        },
                    ],
                    "name": "Bloodbath",
                }
            ]
        }
    }

    httpx_mock.add_response(
        method="POST",
        url=spotify_token_endpoint,
        json=spotify_token_response,
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath",
        json=search_response,
        status_code=200,
    )

    images = await artist_images.get_images(artist_names=["Bloodbath"])

    assert len(httpx_mock.get_requests()) == 2
    assert images == {"Bloodbath": expected_bloodbath_image_url}


@pytest.mark.asyncio
async def test_get_images_returns_none_when_no_image_bigger_than_299_was_found(
    artist_images, spotify_envs, httpx_mock
):
    search_response = {
        "artists": {
            "items": [
                {
                    "images": [
                        {
                            "height": 299,
                            "url": "https://too_small_image.com",
                            "width": 299,
                        }
                    ],
                    "name": "Bloodbath",
                },
            ],
        }
    }
    httpx_mock.add_response(
        method="POST",
        url=spotify_token_endpoint,
        json=spotify_token_response,
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath",
        json=search_response,
        status_code=200,
    )

    images = await artist_images.get_images(artist_names=["Bloodbath"])

    assert len(httpx_mock.get_requests()) == 2
    assert images == {"Bloodbath": None}


@pytest.mark.asyncio
async def test_get_images_returns_none_when_no_images_were_found(
    artist_images, spotify_envs, httpx_mock
):
    search_response = {
        "artists": {
            "items": [
                {
                    "images": [],
                    "name": "Bloodbath",
                },
            ],
        }
    }
    httpx_mock.add_response(
        method="POST",
        url=spotify_token_endpoint,
        json=spotify_token_response,
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath",
        json=search_response,
        status_code=200,
    )

    images = await artist_images.get_images(artist_names=["Bloodbath"])

    assert len(httpx_mock.get_requests()) == 2
    assert images == {"Bloodbath": None}


@pytest.mark.asyncio
async def test_get_images_returns_image_only_for_matching_name(
    artist_images, spotify_envs, httpx_mock
):
    expected_image_url = "https://attic_image.com"
    search_response = {
        "artists": {
            "items": [
                {
                    "images": [],
                    "name": "Atticus Ross",
                },
                {
                    "images": [],
                    "name": "Attic109",
                },
                {
                    "images": [
                        {"height": 640, "url": expected_image_url, "width": 640},
                    ],
                    "name": "Attic",
                },
                {
                    "images": [],
                    "name": "Atticus",
                },
                {
                    "images": [],
                    "name": "Attica Bars",
                },
            ],
        }
    }
    httpx_mock.add_response(
        method="POST",
        url=spotify_token_endpoint,
        json=spotify_token_response,
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Attic",
        json=search_response,
        status_code=200,
    )

    images = await artist_images.get_images(artist_names=["Attic"])

    assert len(httpx_mock.get_requests()) == 2
    assert images == {"Attic": expected_image_url}


def test_upload_uploads_list_of_bands(artist_images, bucket_env):
    festival_name = "wacken"
    artist_images.upload(
        artist_images={
            "Bloodbath": "https://0image_320.com",
            "Megadeth": "https://1image_320.com",
            "Vader": "https://2image_320.com",
        },
        festival_name=festival_name,
    )
    artists = [
        {"artist": "Bloodbath", "image": "https://0image_320.com"},
        {"artist": "Megadeth", "image": "https://1image_320.com"},
        {"artist": "Vader", "image": "https://2image_320.com"},
    ]

    _, args = artist_images.s3.upload.call_args_list[0]
    assert args["bucket_name"] == "MockedBucket"
    assert args["key"] == f"{festival_name}.json"
    assert args["json"] == json.dumps(artists)


def test_upload_to_s3_without_empty_list_does_not_upload(artist_images, bucket_env):
    artist_images.upload(artist_images={}, festival_name="wacken")

    assert artist_images.s3.upload.called is False
