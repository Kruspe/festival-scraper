import functools
import logging
import re

import aiometer
import httpx
from bs4 import BeautifulSoup

from src.adapter.github import GitHubClient
from src.adapter.spotify import ArtistInformation, SpotifyClient

logger = logging.getLogger(__name__)


async def get_wacken_artists(
    *, spotify_client: SpotifyClient, github_client: GitHubClient
) -> list[ArtistInformation]:
    artist_names = []
    response = httpx.get("https://www.wacken.com/fileadmin/Json/bandlist-concert.json")

    if response.status_code == 200:
        artists = response.json()
        for artist in artists:
            if (
                artist["artist"]["title"] != "Metal Disco"
                and artist["artist"]["title"] != "Metal Yoga"
            ):
                artist_names.append(artist["artist"]["title"])

    logger.info("Wacken Artists %s", artist_names)
    artist_information = await _retrieve_images(
        spotify_client=spotify_client,
        github_client=github_client,
        artist_names=artist_names,
    )
    return artist_information


async def get_dong_artists(
    *, spotify_client: SpotifyClient, github_client: GitHubClient
) -> list[ArtistInformation]:
    artist_names = []
    response = httpx.get("https://www.dongopenair.de/bands/")

    if response.status_code == 200:
        parsed_html = BeautifulSoup(response.text, features="html.parser")
        artist_links = parsed_html.find_all("a")
        for artist_link in artist_links:
            if (
                artist_link.get("href") is not None
                and artist_link.get("href").startswith(
                    "https://www.dongopenair.de/band-details/?band="
                )
                and not re.match("^\\d\\d:\\d\\d", artist_link.text.strip())
                and artist_link.text.strip() != ""
            ):
                artist_names.append(artist_link.text.strip())

    logger.info("DONG Artists %s", artist_names)
    artist_information = await _retrieve_images(
        spotify_client=spotify_client,
        github_client=github_client,
        artist_names=artist_names,
    )
    return artist_information


async def get_rude_artists(
    *,
    spotify_client: SpotifyClient,
    github_client: GitHubClient,
    artists: list[str] = None,
) -> list[ArtistInformation]:
    artist_names = []

    if artists is not None:
        artist_names = artists
    else:
        response = httpx.get("https://www.rockunterdeneichen.de/bands/")

        if response.status_code == 200:
            parsed_html = BeautifulSoup(response.text, features="html.parser")
            artist_html_list = parsed_html.find_all(
                "div", attrs={"class": "cb-article-meta"}
            )
            for element in artist_html_list:
                found_artist = (
                    element.find_next("h2").find_next("a").text.split(" (")[0]
                )
                if found_artist == "RUNNING ORDER 2024":
                    continue
                artist_names.append(found_artist)

    logger.info("RUDE Artists %s", artist_names)
    artist_information = await _retrieve_images(
        spotify_client=spotify_client,
        github_client=github_client,
        artist_names=artist_names,
    )
    return artist_information


async def _retrieve_images(
    *,
    spotify_client: SpotifyClient,
    github_client: GitHubClient,
    artist_names: list[str],
) -> list[ArtistInformation]:
    artist_information = await aiometer.run_all(
        [
            functools.partial(
                spotify_client.search_artist,
                name=artist_name,
                genres=[
                    "Metal",
                    "Rock",
                    "Core",
                    "Heavy",
                    "MetalCore",
                    "Thrash",
                    "Punk",
                    "Medieval",
                ],
            )
            for artist_name in artist_names
            if artist_name != ""
        ],
        max_at_once=100,
        max_per_second=5,
    )

    result = []
    for artist_info in artist_information:
        if artist_info.id is None:
            github_client.create_issue(artist_name=artist_info.search_name)
            continue
        github_client.close_issue(artist_name=artist_info.search_name)
        result.append(artist_info)
    return result
