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
        logger.info(
            f"Searching artist: {name}; https://api.spotify.com/v1/search?type=artist&limit=5&q={name}"
        )
        search_response = await self.client.get(
            "https://api.spotify.com/v1/search",
            params={"type": "artist", "limit": 5, "q": name},
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
        logger.info("Spotify returned these results")
        logger.info(found_artists)
        if len(found_artists) == 0:
            logger.info(f"Not results for {name}")
            return ArtistInformation(id=None, name=name, image_url=None)

        best_matches = []
        for artist in found_artists:
            if artist["name"].lower() != name.lower():
                logger.info(
                    f"Skipping artist because of name mismatch, {artist['name']} != {name}"
                )
                continue
            if len(artist["genres"]) > 0:
                logger.info(f"Checking genres: found {artist['genres']}")
                for genre in genres:
                    for artist_genre in artist["genres"]:
                        if genre.lower() in artist_genre.lower():
                            logger.info(f"FOUND! Adding {artist}")
                            best_matches.append(artist)
                            break
            else:
                logger.info(f"Adding artist {artist} because no genres were found")
                best_matches.append(artist)

        if len(best_matches) == 0:
            logger.info(f"No match for {name}")
            return ArtistInformation(id=None, name=name, image_url=None)

        matching_information: list[ArtistInformation] = []
        logger.info("Searching for a good image size")
        for match in best_matches:
            if len(match["images"]) > 0:
                for image in reversed(match["images"]):
                    if image["width"] >= 300 or image["height"] >= 300:
                        logger.info(
                            f"Found image {image['url']} with size {image['width']}x{image['height']}"
                        )
                        matching_information.append(
                            ArtistInformation(
                                id=match["id"],
                                name=match["name"],
                                image_url=image["url"],
                            )
                        )
                        break

        if len(matching_information) == 0:
            logger.info(f"No images for {name}")
            return ArtistInformation(id=None, name=name, image_url=None)

        return ArtistInformation(
            id=matching_information[0].id,
            name=matching_information[0].name,
            image_url=matching_information[0].image_url,
        )


class SpotifyException(Exception):
    pass
