from typing import Union
from unittest.mock import Mock, create_autospec

import pytest

from src.adapter.github import GitHubClient
from src.adapter.spotify import SpotifyClient, ArtistInformation
from src.adapter.ssm import Ssm
from src.festivals.bands import get_wacken_artists, get_dong_artists, get_rude_artists

wacken_url = "https://www.wacken.com/fileadmin/Json/bandlist-concert.json"
dong_url = "https://www.dongopenair.de/de/bands/index"
rude_url = "https://www.rockunterdeneichen.de/bands/"
artist_that_has_pr = "Hypocrisy"


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


@pytest.fixture
def github_client(github_envs, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        status_code=200,
        json=[
            {"title": f"Search for ArtistInformation manually: {artist_that_has_pr}"},
        ],
        match_headers={
            "Authorization": "Bearer gh_pr_token",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    ssm: Union[Mock, Ssm] = create_autospec(Ssm)
    ssm.get_parameters.return_value = {
        "/github/festival-scraper/pr-token": "gh_pr_token",
    }

    yield GitHubClient(ssm=ssm)


def create_spotify_response(
    *, artist_id: str = None, artist_name: str, image_url: str = None
):
    return {
        "artists": {
            "items": [
                {
                    "id": artist_id,
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
async def test_get_wacken_artists(spotify_client, github_client, httpx_mock):
    bloodbath = {"artist": {"title": "Bloodbath"}}
    vader = {"artist": {"title": "Vader"}}
    hypocrisy = {"artist": {"title": artist_that_has_pr}}
    metal_disco = {"artist": {"title": "Metal Disco"}}
    metal_yoga = {"artist": {"title": "Metal Yoga"}}
    artist_response = [bloodbath, vader, hypocrisy, metal_disco, metal_yoga]

    image_url = "https://some-image-url.com"
    expected_result = [
        ArtistInformation(id="RandomSpotifyId", name="Bloodbath", image_url=image_url)
    ]

    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath&market=DE",
        json=create_spotify_response(
            artist_id="RandomSpotifyId", artist_name="Bloodbath", image_url=image_url
        ),
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Vader&market=DE",
        json=create_spotify_response(artist_name="Vader"),
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.spotify.com/v1/search?type=artist&limit=5&q={artist_that_has_pr}&market=DE",
        json=create_spotify_response(artist_name=artist_that_has_pr),
        status_code=200,
    )

    httpx_mock.add_response(
        method="GET", url=wacken_url, json=artist_response, status_code=200
    )

    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        status_code=201,
    )

    artist_information = await get_wacken_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artist_information == expected_result
    assert len(httpx_mock.get_requests()) == 7
    assert httpx_mock.get_requests()[2].url == wacken_url


@pytest.mark.asyncio
async def test_get_wacken_artists_when_call_fails(
    spotify_client, github_client, httpx_mock
):
    httpx_mock.add_response(method="GET", url=wacken_url, status_code=500)

    artists = await get_wacken_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artists == []
    assert len(httpx_mock.get_requests()) == 3
    assert httpx_mock.get_requests()[2].url == wacken_url


@pytest.mark.asyncio
async def test_get_dong_artists(spotify_client, github_client, httpx_mock):
    image_url = "https://some-image-url.com"
    html_response = f"""
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
                <div class="bandteaser">
                    <p> <span class="headline"><a href="">{artist_that_has_pr}</a></span></p>
                </div>
            </div> 
        </body>
    </html>
    """
    httpx_mock.add_response(method="GET", url=dong_url, text=html_response)
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath&market=DE",
        json=create_spotify_response(
            artist_id="RandomSpotifyId", artist_name="Bloodbath", image_url=image_url
        ),
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Dawn of Disease&market=DE",
        json=create_spotify_response(artist_name="Dawn of Disease"),
    )
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.spotify.com/v1/search?type=artist&limit=5&q={artist_that_has_pr}&market=DE",
        json=create_spotify_response(artist_name=artist_that_has_pr),
    )

    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        status_code=201,
    )

    artists = await get_dong_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artists == [
        ArtistInformation(id="RandomSpotifyId", name="Bloodbath", image_url=image_url),
    ]
    assert len(httpx_mock.get_requests()) == 7
    assert httpx_mock.get_requests()[2].url == dong_url


@pytest.mark.asyncio
async def test_get_dong_artists_does_not_return_when_no_a_element_appears(
    spotify_client, github_client, httpx_mock
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
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath&market=DE",
        json=create_spotify_response(
            artist_id="RandomSpotifyId", artist_name="Bloodbath", image_url=image_url
        ),
    )
    artists = await get_dong_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artists == [
        ArtistInformation(id="RandomSpotifyId", name="Bloodbath", image_url=image_url)
    ]


@pytest.mark.asyncio
async def test_get_dong_artists_when_call_fails(
    spotify_client, github_client, httpx_mock
):
    httpx_mock.add_response(method="GET", url=dong_url, status_code=500)

    artists = await get_dong_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artists == []


@pytest.mark.asyncio
async def test_get_rude_artists(spotify_client, github_client, httpx_mock):
    image_url = "https://some-image-url.com"
    html_response = f"""
    <html>
        <body>
            <div class="cb-article-meta">
                <h2>
                    <a href="">RUNNING ORDER 2024</a>
                </h2>
            </div>
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
            <div class="cb-article-meta">
                <h2>
                    <a href="">{artist_that_has_pr} (SWE)</a>
                </h2>
            </div>
        </body>
    </html>
    """
    httpx_mock.add_response(method="GET", url=rude_url, text=html_response)
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Marduk&market=DE",
        json=create_spotify_response(
            artist_id="RandomSpotifyId", artist_name="Marduk", image_url=image_url
        ),
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Deserted Fear&market=DE",
        json=create_spotify_response(artist_name="Deserted Fear"),
    )
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.spotify.com/v1/search?type=artist&limit=5&q={artist_that_has_pr}&market=DE",
        json=create_spotify_response(artist_name=artist_that_has_pr),
    )

    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        status_code=201,
    )

    artists = await get_rude_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artists == [
        ArtistInformation(id="RandomSpotifyId", name="Marduk", image_url=image_url),
    ]
    assert len(httpx_mock.get_requests()) == 7
    assert httpx_mock.get_requests()[2].url == rude_url


@pytest.mark.asyncio
async def test_get_rude_artists_when_call_fails(
    spotify_client, github_client, httpx_mock
):
    httpx_mock.add_response(method="GET", url=rude_url, status_code=500)

    artists = await get_rude_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artists == []
