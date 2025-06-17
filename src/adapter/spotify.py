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
    search_name: str
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
                search_name="ATTIC",
                image_url="https://i.scdn.co/image/ab67616100005174cc1a1ab23574e34fc7693f24",
            ),
            "BAP": ArtistInformation(
                id="39ukKqQOSUFJDAM9OLKQZg",
                name="BAP",
                search_name="BAP",
                image_url="https://i.scdn.co/image/ab6761610000517494f434977e3dc06d3565a975",
            ),
            "Boomtown Rats": ArtistInformation(
                id="40oYPr305MsT2lsiXr9fX9",
                name="Boomtown Rats",
                search_name="Boomtown Rats",
                image_url="https://i.scdn.co/image/ab67616100005174650a6331f62d5671e3f8192c",
            ),
            "Eihwar": ArtistInformation(
                id="2VFxoCJQPfQauZujESPjQK",
                name="Eihwar",
                search_name="Eihwar",
                image_url="https://i.scdn.co/image/ab676161000051742a9ed2dbd3745cc93f48b51c",
            ),
            "Guns N’ Roses": ArtistInformation(
                id="3qm84nBOXUEQ2vnTfUTTFC",
                name="Guns N' Roses",
                search_name="Guns N’ Roses",
                image_url="https://i.scdn.co/image/ab6761610000517450defaf9fc059a1efc541f4c",
            ),
            "Hanabie": ArtistInformation(
                id="4N2I7VsF86h59tbsvVoB1h",
                name="Hanabie",
                search_name="Hanabie",
                image_url="https://i.scdn.co/image/ab67616100005174de4fabc8a9d57b304c23706a",
            ),
            "Kissin’ Dynamite": ArtistInformation(
                id="2wSP2cFfkqg4LKu1pmkTWx",
                name="Kissin' Dynamite",
                search_name="Kissin’ Dynamite",
                image_url="https://i.scdn.co/image/ab67616100005174f8e1f25d44ea876f05d70c46",
            ),
            "Jack & Cöke": ArtistInformation(
                id="Jack & Cöke",
                name="Jack & Cöke",
                search_name="Jack & Cöke",
                image_url=None,
            ),
            "Metal Worx": ArtistInformation(
                id="Metal Worx",
                name="Metal Worx",
                search_name="Metal Worx",
                image_url=None,
            ),
            "Pentagram (Chile)": ArtistInformation(
                id="0xin7cSeEjVSsvNsKPHaJc",
                name="Pentagram Chile",
                search_name="Pentagram (Chile)",
                image_url="https://i.scdn.co/image/ab67616100005174f662e3011e3f5487dccb6227",
            ),
            "POWERSLAVE": ArtistInformation(
                id="POWERSLAVE",
                name="POWERSLAVE",
                search_name="POWERSLAVE",
                image_url=None,
            ),
            "Setyoursails": ArtistInformation(
                id="01AynfThIqLCNevTuPSoYk",
                name="SETYØURSAILS",
                search_name="Setyoursails",
                image_url="https://i.scdn.co/image/ab67616100005174e09b5b36b45b76f91016cfbd",
            ),
            "Tarja & Marko Hietela": ArtistInformation(
                id="Tarja & Marko Hietela",
                name="Tarja & Marko Hietela",
                search_name="Tarja & Marko Hietela",
                image_url=None,
            ),
            "UK Subs": ArtistInformation(
                id="4wsg78KGu80m8Xk37PY2uG",
                name="U.K. Subs",
                search_name="UK Subs",
                image_url="https://i.scdn.co/image/ab67616100005174cb869ec7836df71825714e48",
            ),
            "Weckörhead": ArtistInformation(
                id="44pq4JEhpX9dg5BbZlJGZg",
                name="Weckörhead",
                search_name="Weckörhead",
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
            params={"type": "artist", "q": name, "market": "DE"},
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
            logger.error(f"No artists found for {name}")
            return ArtistInformation(
                id=None, name=name, search_name=name, image_url=None
            )

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
            return self._handle_not_found_artist(
                name=name, spotify_response=search_response_json
            )

        matching_information: list[ArtistInformation] = []
        for match in best_matches:
            if len(match["images"]) > 0:
                for image in reversed(match["images"]):
                    if image["width"] >= 300 or image["height"] >= 300:
                        matching_information.append(
                            ArtistInformation(
                                id=match["id"],
                                name=match["name"],
                                search_name=name,
                                image_url=image["url"],
                            )
                        )
                        break

        if len(matching_information) == 0:
            return self._handle_not_found_artist(
                name=name, spotify_response=search_response_json
            )

        return ArtistInformation(
            id=matching_information[0].id,
            name=matching_information[0].name,
            search_name=name,
            image_url=matching_information[0].image_url,
        )

    def _handle_not_found_artist(
        self, *, name: str, spotify_response
    ) -> ArtistInformation:
        logger.error(
            f"Unable to find information for '{name}'! Here are the interesting parts of the search result"
        )
        for item in spotify_response["artists"]["items"]:
            logger.error(
                f"SpotifyName {item['name']}, Id: {item['id']}, Genres: {item['genres']}', Image URL: {item['images']}"
            )
        return ArtistInformation(id=None, name=name, search_name=name, image_url=None)


class SpotifyException(Exception):
    pass
