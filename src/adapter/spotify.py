import logging
import os
from base64 import b64encode
from dataclasses import dataclass

import httpx

from src.adapter.ssm import Ssm

logger = logging.getLogger(__name__)


@dataclass
class ArtistInformation:
    id: str | None
    name: str
    image_url: str | None


class SpotifyClient:
    def __init__(self, *, ssm: Ssm):
        client_id_parameter_name = os.environ.get("SPOTIFY_CLIENT_ID_PARAMETER_NAME")
        client_secret_parameter_name = os.environ.get(
            "SPOTIFY_CLIENT_SECRET_PARAMETER_NAME"
        )
        spotify_secrets = ssm.get_parameters(
            parameter_names=[
                client_id_parameter_name,
                client_secret_parameter_name,
            ]
        )
        self.client_id = spotify_secrets[client_id_parameter_name]
        self.client_secret = spotify_secrets[client_secret_parameter_name]
        self.token = self._get_token()
        self.client = httpx.AsyncClient()
        self.exception_map = {
            "ATTIC": ArtistInformation(
                id="5z9ci33r73qjiOqk1wmuY9",
                name="Attic",
                image_url="https://i.scdn.co/image/ab67616100005174cc1a1ab23574e34fc7693f24",
            ),
            "Boomtown Rats": ArtistInformation(
                id="40oYPr305MsT2lsiXr9fX9",
                name="Boomtown Rats",
                image_url="https://i.scdn"
            ),
            "Hanabie": ArtistInformation(
                id="4N2I7VsF86h59tbsvVoB1h",
                name="Hanabie",
                image_url="https://i.scdn.co/image/ab6761610000e5ebde4fabc8a9d57b304c23706a",
            ),
            "Kissin’ Dynamite": ArtistInformation(
                id="2wSP2cFfkqg4LKu1pmkTWx",
                name="Kissin' Dynamite",
                image_url="https://i.scdn.co/image/ab6761610000e5eb650a6331f62d5671e3f8192c",
            ),
            "POWERSLAVE": ArtistInformation(
                id="POWERSLAVE", name="POWERSLAVE", image_url=None
            ),
            "Tarja & Marko Hietela": ArtistInformation(
                id="Tarja & Marko Hietela",
                name="Tarja & Marko Hietela",
                image_url=None,
            ),
            "Weckörhead": ArtistInformation(
                id="44pq4JEhpX9dg5BbZlJGZg",
                name="Weckörhead",
                image_url=None,
            ),
        }

    def _get_token(self) -> str:
        encoded_credentials = b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        )
        encoded_spotify_basic_auth = f"Basic {encoded_credentials.decode("utf-8")}"
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
            logger.error(
                "Spotify token endpoint returned status "
                + str(token_response_status_code)
                + ", "
                + str(token_response_json)
            )
            raise SpotifyException("Spotify token response is invalid")

        return token_response_json["access_token"]

    async def search_artist(self, *, name: str, genres: list[str]) -> ArtistInformation:
        if name in self.exception_map:
            return self.exception_map[name]
        search_response = await self.client.get(
            "https://api.spotify.com/v1/search",
            params={"type": "artist", "limit": 5, "q": name, "market": "DE"},
            headers={"Authorization": "Bearer " + self.token},
        )
        search_response_status_code = search_response.status_code
        search_response_json = search_response.json()
        if search_response_status_code != 200:
            logger.error(
                "Spotify search returned status "
                + str(search_response_status_code)
                + ", "
                + str(search_response_json)
            )
            raise SpotifyException("Spotify search response is invalid")

        found_artists = search_response_json["artists"]["items"]
        if len(found_artists) == 0:
            logger.error(
                f"Unable to find information for {name}! Here are the spotify search results: {search_response_json}"
            )
            return ArtistInformation(id=None, name=name, image_url=None)

        best_matches = []
        for artist in found_artists:
            if artist["name"].lower() != name.lower():
                continue
            if len(artist["genres"]) > 0:
                for genre in genres:
                    for artist_genre in artist["genres"]:
                        if genre.lower() in artist_genre.lower():
                            best_matches.append(artist)
                            break
            else:
                best_matches.append(artist)

        if len(best_matches) == 0:
            logger.error(
                f"Unable to find information for {name}! Here are the spotify search results: {search_response_json}"
            )
            return ArtistInformation(id=None, name=name, image_url=None)

        matching_information: list[ArtistInformation] = []
        for match in best_matches:
            if len(match["images"]) > 0:
                for image in reversed(match["images"]):
                    if image["width"] >= 300 or image["height"] >= 300:
                        matching_information.append(
                            ArtistInformation(
                                id=match["id"],
                                name=match["name"],
                                image_url=image["url"],
                            )
                        )
                        break

        if len(matching_information) == 0:
            logger.error(
                f"Unable to find information for {name}! Here are the spotify search results: {search_response_json}"
            )
            return ArtistInformation(id=None, name=name, image_url=None)

        return ArtistInformation(
            id=matching_information[0].id,
            name=matching_information[0].name,
            image_url=matching_information[0].image_url,
        )


class SpotifyException(Exception):
    pass
