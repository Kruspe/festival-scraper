from base64 import b64encode
from typing import Union
from unittest.mock import Mock, create_autospec

import pytest

from src.adapter.spotify import SpotifyClient, SpotifyException, ArtistInformation
from src.adapter.ssm import Ssm

spotify_token_endpoint = "https://accounts.spotify.com/api/token"
spotify_token_response = {
    "access_token": "token",
    "token_type": "bearer",
    "expires_in": 3600,
}
expected_bloodbath_image_url = "https://bloodbath_image.com"


@pytest.fixture
def ssm_mock():
    ssm: Union[Mock, Ssm] = create_autospec(Ssm)
    ssm.get_parameters.return_value = {
        "/spotify/client-id": "client_id",
        "/spotify/client-secret": "client_secret",
    }
    yield ssm


@pytest.fixture
def spotify_client(spotify_envs, ssm_mock, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=spotify_token_endpoint,
        json=spotify_token_response,
        status_code=200,
    )

    yield SpotifyClient(ssm=ssm_mock)


@pytest.mark.asyncio
async def test_spotify_client_retrieves_token(spotify_envs, ssm_mock, httpx_mock):
    authorization_header_key = "Authorization"
    authorization_header_value = (
        f"Basic {b64encode(b"client_id:client_secret").decode('utf-8')}"
    )
    content_type_header_key = "Content-Type"
    content_type_header_value = "application/x-www-form-urlencoded"
    expected_body = b"grant_type=client_credentials"

    httpx_mock.add_response(
        method="POST",
        url=spotify_token_endpoint,
        json=spotify_token_response,
        status_code=200,
    )

    SpotifyClient(ssm=ssm_mock)

    assert len(httpx_mock.get_requests()) == 1
    assert httpx_mock.get_requests()[0].url == spotify_token_endpoint
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


@pytest.mark.asyncio
async def test_spotify_client_raises_and_logs_exception_when_getting_token_fails(
    caplog, spotify_envs, ssm_mock, httpx_mock
):
    error_message = {"error": "error"}
    httpx_mock.add_response(
        method="POST", url=spotify_token_endpoint, json=error_message, status_code=500
    )

    with pytest.raises(SpotifyException):
        SpotifyClient(ssm=ssm_mock)

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
async def test_search_artist_calls_correct_endpoint(spotify_client, httpx_mock):
    authorization_header_key = "Authorization"
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&q=Bloodbath&market=DE",
        json={
            "artists": {
                "items": [
                    {
                        "id": "RandomSpotifyId",
                        "genres": ["Swedish Death Metal"],
                        "images": [
                            {
                                "height": 640,
                                "url": expected_bloodbath_image_url,
                                "width": 640,
                            },
                        ],
                        "name": "Bloodbath",
                    },
                ],
            }
        },
        status_code=200,
    )

    await spotify_client.search_artist(name="Bloodbath", genres=["Metal"])
    assert authorization_header_key in httpx_mock.get_requests()[1].headers
    assert (
        httpx_mock.get_requests()[1].headers[authorization_header_key] == "Bearer token"
    )


@pytest.mark.asyncio
async def test_search_artist_raises_and_logs_exception_when_search_fails(
    caplog, spotify_client, httpx_mock
):
    error_message = {"error": "error"}
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&q=Bloodbath&market=DE",
        json=error_message,
        status_code=500,
    )

    with pytest.raises(SpotifyException):
        await spotify_client.search_artist(name="Bloodbath", genres=["Metal"])

    assert len(httpx_mock.get_requests()) == 2

    assert len(caplog.records) == 1
    for record in caplog.records:
        assert record.levelname == "ERROR"
        assert record.getMessage() == "Spotify search returned status 500, " + str(
            error_message
        )


@pytest.mark.asyncio
async def test_search_artist_returns_artist_information(spotify_client, httpx_mock):
    artist_name = "Bloodbath"
    artist_id = "RandomSpotifyId"
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&q=Bloodbath&market=DE",
        json={
            "artists": {
                "items": [
                    {
                        "id": artist_id,
                        "genres": ["Heavy Rock", "Swedish Death Metal"],
                        "images": [
                            {
                                "height": 640,
                                "url": expected_bloodbath_image_url,
                                "width": 640,
                            },
                        ],
                        "name": artist_name,
                    },
                ],
            }
        },
        status_code=200,
    )

    artist_information = await spotify_client.search_artist(
        name=artist_name, genres=["metal"]
    )
    assert artist_information == ArtistInformation(
        id=artist_id,
        name=artist_name,
        search_name=artist_name,
        image_url=expected_bloodbath_image_url,
    )


@pytest.mark.asyncio
async def test_search_artist_returns_no_image_url_when_name_does_not_match_exactly(
    spotify_client, httpx_mock
):
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&q=Bloodbath&market=DE",
        json={
            "artists": {
                "items": [
                    {
                        "id": "RandomSpotifyId",
                        "genres": ["Swedish Death Metal"],
                        "images": [
                            {
                                "height": 640,
                                "url": expected_bloodbath_image_url,
                                "width": 640,
                            },
                        ],
                        "name": "NotBloodbath",
                    },
                ],
            }
        },
        status_code=200,
    )

    artist_information = await spotify_client.search_artist(
        name="Bloodbath", genres=["Metal"]
    )
    assert artist_information == ArtistInformation(
        id=None, name="Bloodbath", search_name="Bloodbath", image_url=None
    )


@pytest.mark.asyncio
async def test_search_artist_returns_no_image_url_when_no_artists_are_found(
    spotify_client, httpx_mock
):
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&q=Bloodbath&market=DE",
        json={
            "artists": {
                "items": [],
            }
        },
        status_code=200,
    )

    artist_information = await spotify_client.search_artist(
        name="Bloodbath", genres=["Metal"]
    )
    assert artist_information == ArtistInformation(
        id=None, name="Bloodbath", search_name="Bloodbath", image_url=None
    )


@pytest.mark.asyncio
async def test_search_artist_returns_no_image_url_when_genre_does_not_match(
    spotify_client, httpx_mock
):
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&q=Bloodbath&market=DE",
        json={
            "artists": {
                "items": [
                    {
                        "id": "RandomSpotifyId",
                        "genres": ["Indie Pop"],
                        "images": [
                            {
                                "height": 640,
                                "url": expected_bloodbath_image_url,
                                "width": 640,
                            },
                        ],
                        "name": "Bloodbath",
                    },
                ],
            }
        },
        status_code=200,
    )

    artist_information = await spotify_client.search_artist(
        name="Bloodbath", genres=["Metal"]
    )
    assert artist_information == ArtistInformation(
        id=None, name="Bloodbath", search_name="Bloodbath", image_url=None
    )


@pytest.mark.asyncio
async def test_search_artist_returns_no_image_url_when_no_images_are_found(
    spotify_client, httpx_mock
):
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&q=Bloodbath&market=DE",
        json={
            "artists": {
                "items": [
                    {
                        "id": "RandomSpotifyId",
                        "genres": ["Swedish Death Metal"],
                        "images": [],
                        "name": "Bloodbath",
                    },
                ],
            }
        },
        status_code=200,
    )

    artist_information = await spotify_client.search_artist(
        name="Bloodbath", genres=["Metal"]
    )
    assert artist_information == ArtistInformation(
        id=None, name="Bloodbath", search_name="Bloodbath", image_url=None
    )


@pytest.mark.asyncio
async def test_search_artist_returns_first_match_when_more_are_available(
    spotify_client, httpx_mock
):
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&q=Bloodbath&market=DE",
        json={
            "artists": {
                "items": [
                    {
                        "id": "RandomSpotifyId",
                        "genres": ["Indie Pop"],
                        "images": [
                            {
                                "height": 640,
                                "url": "https://image-from-indie-pop-band.com",
                                "width": 640,
                            },
                        ],
                        "name": "Bloodbath",
                    },
                    {
                        "id": "CorrectSpotifyId",
                        "genres": ["Swedish Death Metal"],
                        "images": [
                            {
                                "height": 640,
                                "url": expected_bloodbath_image_url,
                                "width": 640,
                            },
                        ],
                        "name": "Bloodbath",
                    },
                    {
                        "id": "YetAnotherRandomSpotifyId",
                        "genres": ["Heavy Metal"],
                        "images": [
                            {
                                "height": 640,
                                "url": "https://some-image-url.com",
                                "width": 640,
                            },
                        ],
                        "name": "Bloodbath",
                    },
                ],
            }
        },
        status_code=200,
    )

    artist_information = await spotify_client.search_artist(
        name="Bloodbath", genres=["Metal"]
    )
    assert artist_information == ArtistInformation(
        id="CorrectSpotifyId",
        name="Bloodbath",
        search_name="Bloodbath",
        image_url=expected_bloodbath_image_url,
    )


@pytest.mark.asyncio
async def test_search_artist_returns_no_image_url_when_available_images_are_to_small(
    spotify_client, httpx_mock
):
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&q=Bloodbath&market=DE",
        json={
            "artists": {
                "items": [
                    {
                        "id": "RandomSpotifyId",
                        "genres": ["Swedish Death Metal"],
                        "images": [
                            {
                                "height": 200,
                                "url": expected_bloodbath_image_url,
                                "width": 200,
                            },
                        ],
                        "name": "Bloodbath",
                    },
                ],
            }
        },
        status_code=200,
    )

    artist_information = await spotify_client.search_artist(
        name="Bloodbath", genres=["Metal"]
    )
    assert artist_information == ArtistInformation(
        id=None, name="Bloodbath", search_name="Bloodbath", image_url=None
    )


@pytest.mark.asyncio
async def test_search_artist_returns_smallest_possible_image_bigger_than_300_width_and_height(
    spotify_client, httpx_mock
):
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&q=Bloodbath&market=DE",
        json={
            "artists": {
                "items": [
                    {
                        "id": "RandomSpotifyId",
                        "genres": ["Swedish Death Metal"],
                        "images": [
                            {
                                "height": 640,
                                "url": "https://too_large_image.com",
                                "width": 640,
                            },
                            {
                                "height": 320,
                                "url": expected_bloodbath_image_url,
                                "width": 320,
                            },
                            {
                                "height": 120,
                                "url": "https://too_small_image",
                                "width": 120,
                            },
                        ],
                        "name": "Bloodbath",
                    },
                ],
            }
        },
        status_code=200,
    )

    artist_information = await spotify_client.search_artist(
        name="Bloodbath", genres=["Metal"]
    )
    assert artist_information == ArtistInformation(
        id="RandomSpotifyId",
        name="Bloodbath",
        search_name="Bloodbath",
        image_url=expected_bloodbath_image_url,
    )


@pytest.mark.asyncio
async def test_search_artist_returns_matching_artist_if_one_genre_matches(
    spotify_client, httpx_mock
):
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&q=Bloodbath&market=DE",
        json={
            "artists": {
                "items": [
                    {
                        "id": "RandomSpotifyId",
                        "genres": ["Heavy Rock", "Swedish Death", "Death Metal"],
                        "images": [
                            {
                                "height": 320,
                                "url": expected_bloodbath_image_url,
                                "width": 320,
                            },
                        ],
                        "name": "Bloodbath",
                    },
                ],
            }
        },
        status_code=200,
    )

    artist_information = await spotify_client.search_artist(
        name="Bloodbath", genres=["NonExistingGenre", "Metal"]
    )
    assert artist_information == ArtistInformation(
        id="RandomSpotifyId",
        name="Bloodbath",
        search_name="Bloodbath",
        image_url=expected_bloodbath_image_url,
    )


@pytest.mark.asyncio
async def test_search_artist_returns_artists_from_exception_map(
    spotify_client, httpx_mock
):
    expected_artist_information = ArtistInformation(
        id="RandomSpotifyId",
        name="Bloodbath",
        search_name="Bloodbath",
        image_url=expected_bloodbath_image_url,
    )
    spotify_client.exception_map = {"Bloodbath": expected_artist_information}
    artist_information = await spotify_client.search_artist(
        name="Bloodbath", genres=["Metal"]
    )

    assert len(httpx_mock.get_requests()) == 1
    assert artist_information == expected_artist_information
