import itertools
import json
import logging
import os
from base64 import b64encode
from dataclasses import dataclass
from typing import List, Dict

import httpx

from src.adapter.s3 import S3
from src.adapter.ssm import Ssm


@dataclass
class ArtistInformation:
    name: str
    image_url: str | None


def _find_artists_with_matching_name(search_result, name):
    return list(
        itertools.filterfalse(
            lambda found_artist: found_artist.get("name").lower() != name.lower(),
            search_result,
        )
    )


def _find_artists_with_images(artists):
    return list(
        itertools.filterfalse(lambda artist: len(artist["images"]) == 0, artists)
    )


def _get_images_with_size_greater_300(artist):
    return list(
        itertools.filterfalse(
            lambda image: image["width"] < 300 or image["height"] < 300,
            artist["images"],
        )
    )


class Helper:
    def __init__(self, *, ssm: Ssm, s3: S3) -> None:
        self.ssm = ssm
        self.s3 = s3

    async def get_images(self, *, artist_names: List[str]) -> Dict:
        if len(artist_names) == 0:
            return {}

        spotify_token = self._get_spotify_token()
        artist_images = {}

        async with httpx.AsyncClient() as client:
            for artist in artist_names:
                artist_information = await self._retrieve_information(
                    client=client, artist=artist, spotify_token=spotify_token
                )
                if artist_information is None:
                    artist_images[artist] = None
                else:
                    artist_images[artist_information.name] = (
                        artist_information.image_url
                    )

        return artist_images

    async def _retrieve_information(
        self, *, client: httpx.AsyncClient, artist: str, spotify_token: str
    ) -> ArtistInformation | None:
        search_response = await client.get(
            "https://api.spotify.com/v1/search",
            params={"type": "artist", "limit": 5, "q": artist},
            headers={"Authorization": "Bearer " + spotify_token},
        )
        search_response_status_code = search_response.status_code
        search_response_json = search_response.json()

        if search_response_status_code != 200:
            logging.error(
                "Spotify search returned status "
                + str(search_response_status_code)
                + ", "
                + str(search_response_json)
            )
            raise SpotifyException("Spotify search response is invalid")

        found_artists = search_response_json["artists"]["items"]
        if len(found_artists) == 0:
            return None

        matching_artists = _find_artists_with_matching_name(found_artists, artist)
        if len(matching_artists) == 0:
            return None
        spotify_artist_name = matching_artists[0]["name"]
        matching_artists_with_images = _find_artists_with_images(matching_artists)
        if len(matching_artists_with_images) == 0:
            return ArtistInformation(name=spotify_artist_name, image_url=None)

        artist_images_with_correct_size = _get_images_with_size_greater_300(
            matching_artists_with_images[0]
        )
        amount_of_images = len(artist_images_with_correct_size)
        if amount_of_images == 0:
            return ArtistInformation(name=spotify_artist_name, image_url=None)

        return ArtistInformation(
            name=spotify_artist_name,
            image_url=artist_images_with_correct_size[amount_of_images - 1]["url"],
        )

    def upload(self, *, artist_images: Dict[str, str], festival_name: str):
        if artist_images:
            result = []
            for artist, image in artist_images.items():
                result.append({"artist": artist, "image": image})
            self.s3.upload(
                bucket_name=os.getenv("FESTIVAL_ARTISTS_BUCKET"),
                key=f"{festival_name}.json",
                json=json.dumps(result),
            )

    def _get_spotify_token(self) -> str:
        spotify_client_id_parameter_name = os.environ[
            "SPOTIFY_CLIENT_ID_PARAMETER_NAME"
        ]
        spotify_client_secret_parameter_name = os.environ[
            "SPOTIFY_CLIENT_SECRET_PARAMETER_NAME"
        ]
        spotify_secrets = self.ssm.get_parameters(
            parameter_names=[
                spotify_client_id_parameter_name,
                spotify_client_secret_parameter_name,
            ]
        )
        encoded_spotify_basic_auth = "Basic " + b64encode(
            (
                spotify_secrets[spotify_client_id_parameter_name]
                + ":"
                + spotify_secrets[spotify_client_secret_parameter_name]
            ).encode()
        ).decode("utf-8")
        spotify_token_response = httpx.post(
            "https://accounts.spotify.com/api/token",
            data="grant_type=client_credentials",
            headers={
                "Authorization": encoded_spotify_basic_auth,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        token_response_status_code = spotify_token_response.status_code
        token_response_json = spotify_token_response.json()

        if token_response_status_code != 200:
            logging.error(
                "Spotify token endpoint returned status "
                + str(token_response_status_code)
                + ", "
                + str(token_response_json)
            )
            raise SpotifyException("Spotify token response is invalid")
        return token_response_json.get("access_token")


class SpotifyException(Exception):
    pass
