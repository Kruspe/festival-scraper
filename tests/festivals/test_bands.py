from typing import Union
from unittest.mock import Mock, create_autospec

import pytest

from src.adapter.spotify import SpotifyClient, ArtistInformation
from src.adapter.ssm import Ssm
from src.festivals.bands import get_wacken_artists, get_dong_artists, get_rude_artists

wacken_url = "https://www.wacken.com/fileadmin/Json/bandlist-concert.json"
dong_url = "https://www.dongopenair.de/de/bands/index"
rude_url = "https://www.rockunterdeneichen.de/bands/"


@pytest.fixture
def spotify_client(spotify_envs, httpx_mock):
    ssm: Union[Mock, Ssm] = create_autospec(Ssm)
    ssm.get_parameters.return_value = {
        "/spotify/client-id": "client_id",
        "/spotify/client-secret": "client_secret",
    }
    httpx_mock.add_response(
        method="POST",
        url="https://accounts.spotify.com/api/token",
        json={
            "access_token": "token",
            "token_type": "bearer",
            "expires_in": 3600,
        },
        status_code=200,
    )

    yield SpotifyClient(ssm=ssm)


def create_spotify_response(*, artist_name: str, image_url: str = None):
    return {
        "artists": {
            "items": [
                {
                    "genres": ["Swedish Death Metal"],
                    "images": [
                        {
                            "height": 320,
                            "url": image_url,
                            "width": 320,
                        },
                    ],
                    "name": artist_name,
                },
            ],
        }
    }


@pytest.mark.asyncio
async def test_get_wacken_artists(spotify_client, httpx_mock):
    bloodbath = {"artist": {"title": "Bloodbath"}}
    vader = {"artist": {"title": "Vader"}}
    metal_disco = {"artist": {"title": "Metal Disco"}}
    metal_yoga = {"artist": {"title": "Metal Yoga"}}
    artist_response = [bloodbath, vader, metal_disco, metal_yoga]

    image_url = "https://some-image-url.com"
    expected_result = {
        "Bloodbath": ArtistInformation(name="Bloodbath", image_url=image_url),
        "Vader": ArtistInformation(name="Vader", image_url=None),
    }

    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath",
        json=create_spotify_response(artist_name="Bloodbath", image_url=image_url),
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Vader",
        json=create_spotify_response(artist_name="Vader"),
        status_code=200,
    )

    httpx_mock.add_response(
        method="GET", url=wacken_url, json=artist_response, status_code=200
    )

    artist_information = await get_wacken_artists(spotify_client=spotify_client)

    assert artist_information == expected_result
    assert len(httpx_mock.get_requests()) == 4
    assert httpx_mock.get_requests()[1].url == wacken_url


@pytest.mark.asyncio
async def test_get_wacken_artists_when_call_fails(spotify_client, httpx_mock):
    httpx_mock.add_response(method="GET", url=wacken_url, status_code=500)

    artists = await get_wacken_artists(spotify_client=spotify_client)

    assert artists == {}
    assert len(httpx_mock.get_requests()) == 2
    assert httpx_mock.get_requests()[1].url == wacken_url


@pytest.mark.asyncio
async def test_get_dong_artists(spotify_client, httpx_mock):
    image_url = "https://some-image-url.com"
    html_response = """
    <html>
        <body>
            <h1>Some Headline</h1>
            <div>Any Text Here</div>
            <div class="headline">alle bisherigen Bands für das D.O.A 2024>
                <div class="bandteaser">
                    <p> <span class="headline"><a href="">Bloodbath</a></span></p>
                </div>
                <div class="bandteaser">
                    <p> <span class="headline"><a href="">Dawn of Disease</a></span></p>
                </div>
            </div> 
        </body>
    </html>
    """
    httpx_mock.add_response(method="GET", url=dong_url, text=html_response)
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath",
        json=create_spotify_response(artist_name="Bloodbath", image_url=image_url),
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Dawn of Disease",
        json=create_spotify_response(artist_name="Dawn of Disease", image_url=None),
    )
    artists = await get_dong_artists(spotify_client=spotify_client)

    assert artists == {
        "Bloodbath": ArtistInformation(name="Bloodbath", image_url=image_url),
        "Dawn of Disease": ArtistInformation(name="Dawn of Disease", image_url=None),
    }
    assert len(httpx_mock.get_requests()) == 4
    assert httpx_mock.get_requests()[1].url == dong_url


@pytest.mark.asyncio
async def test_get_dong_artists_does_not_return_when_no_a_element_appears(
    spotify_client, httpx_mock
):
    image_url = "https://some-image-url.com"
    html_response = """
        <html>
            <body>
                <h1>Some Headline</h1>
                <div>Any Text Here</div>
                <div class="headline">alle bisherigen Bands für das D.O.A 2024>
                    <div class="bandteaser">
                        <p> <span class="headline"><a href="">Bloodbath</a></span></p>
                    </div>
                    <div class="bandteaser">
                        <p><span style="margin-left: 115px; font-weight:bold; color: #fb4a00 !important;">Party mit DJ Benne</span></p>
                    </div>
                </div> 
            </body>
        </html>
        """
    httpx_mock.add_response(method="GET", url=dong_url, text=html_response)
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath",
        json=create_spotify_response(artist_name="Bloodbath", image_url=image_url),
    )
    artists = await get_dong_artists(spotify_client=spotify_client)

    assert artists == {
        "Bloodbath": ArtistInformation(name="Bloodbath", image_url=image_url)
    }


@pytest.mark.asyncio
async def test_get_dong_artists_when_call_fails(spotify_client, httpx_mock):
    httpx_mock.add_response(method="GET", url=dong_url, status_code=500)

    artists = await get_dong_artists(spotify_client=spotify_client)

    assert artists == {}


@pytest.mark.asyncio
async def test_get_rude_artists(spotify_client, httpx_mock):
    image_url = "https://some-image-url.com"
    html_response = """
    <html>
        <body>
            <div class="cb-article-meta">
                <h2>
                    <a href="">Marduk (SWE)</a>
                </h2>
            </div>
            <div class="cb-article-meta">
                <h2>
                    <a href="">Deserted Fear (D)</a>
                </h2>
            </div>
        </body>
    </html>
    """
    httpx_mock.add_response(method="GET", url=rude_url, text=html_response)
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Marduk",
        json=create_spotify_response(artist_name="Marduk", image_url=image_url),
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Deserted Fear",
        json=create_spotify_response(artist_name="Deserted Fear", image_url=None),
    )
    artists = await get_rude_artists(spotify_client=spotify_client)

    assert artists == {
        "Marduk": ArtistInformation(name="Marduk", image_url=image_url),
        "Deserted Fear": ArtistInformation(name="Deserted Fear", image_url=None),
    }
    assert len(httpx_mock.get_requests()) == 4
    assert httpx_mock.get_requests()[1].url == rude_url


@pytest.mark.asyncio
async def test_get_rude_artists_when_call_fails(spotify_client, httpx_mock):
    httpx_mock.add_response(method="GET", url=rude_url, status_code=500)

    artists = await get_rude_artists(spotify_client=spotify_client)

    assert artists == {}
