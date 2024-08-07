import functools
from typing import Mapping

import aiometer
import httpx
from bs4 import BeautifulSoup

from src.adapter.spotify import ArtistInformation, SpotifyClient


async def get_wacken_artists(
    *, spotify_client: SpotifyClient
) -> Mapping[str, ArtistInformation]:
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

    artist_information = await _retrieve_images(
        spotify_client=spotify_client, artist_names=artist_names
    )
    return artist_information


async def get_dong_artists(
    *, spotify_client: SpotifyClient
) -> Mapping[str, ArtistInformation]:
    artist_names = []
    response = httpx.get("https://www.dongopenair.de/de/bands/index")

    if response.status_code == 200:
        parsed_html = BeautifulSoup(response.text, features="html.parser")
        artist_html_list = parsed_html.find_all("div", attrs={"class": "bandteaser"})
        for element in artist_html_list:
            band_link = element.a
            if band_link is None:
                continue
            artist_names.append(band_link.text)

    artist_information = await _retrieve_images(
        spotify_client=spotify_client, artist_names=artist_names
    )
    return artist_information


async def get_rude_artists(
    *, spotify_client: SpotifyClient
) -> Mapping[str, ArtistInformation]:
    artist_names = []
    response = httpx.get("https://www.rockunterdeneichen.de/bands/")

    if response.status_code == 200:
        parsed_html = BeautifulSoup(response.text, features="html.parser")
        artist_html_list = parsed_html.find_all(
            "div", attrs={"class": "cb-article-meta"}
        )
        for element in artist_html_list:
            artist_names.append(
                element.find_next("h2").find_next("a").text.split(" (")[0]
            )

    artist_information = await _retrieve_images(
        spotify_client=spotify_client, artist_names=artist_names
    )
    return artist_information


async def _retrieve_images(
    *, spotify_client: SpotifyClient, artist_names: list[str]
) -> Mapping[str, ArtistInformation]:
    artist_information = await aiometer.run_all(
        [
            functools.partial(
                spotify_client.search_artist,
                name=artist_name,
                genres=["Metal", "Rock", "Core", "Heavy"],
            )
            for artist_name in artist_names
        ],
        max_at_once=100,
        max_per_second=5,
    )

    result = {}
    for artist_info in artist_information:
        result[artist_info.name] = artist_info
    return result
