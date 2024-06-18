import asyncio
import json
import logging
import os
from typing import Mapping

import boto3

from src.adapter.s3 import S3
from src.adapter.ssm import Ssm
from src.adapter.spotify import SpotifyClient, ArtistInformation
from src.festivals.bands import get_wacken_artists, get_dong_artists, get_rude_artists

logger = logging.getLogger(__name__)


def _configure_logger():
    log_level_name = os.environ.get("LOG_LEVEL", "INFO")
    logging.root.setLevel(level=logging.getLevelName(log_level_name))


async def _handle(*, s3: S3, spotify_client: SpotifyClient):
    logger.info("getting all festivals")
    async with asyncio.TaskGroup() as tg:
        wacken_task = tg.create_task(get_wacken_artists(spotify_client=spotify_client))
        dong_task = tg.create_task(get_dong_artists(spotify_client=spotify_client))
        rude_task = tg.create_task(get_rude_artists(spotify_client=spotify_client))
    logger.info("finished getting all festivals")

    wacken_artists: Mapping[str, ArtistInformation] = wacken_task.result()
    logger.info("retrieved artists for wacken:", wacken_artists)
    wacken_body = []
    for artist in wacken_artists.values():
        wacken_body.append({"artist": artist.name, "image": artist.image_url})
    s3.upload(
        bucket_name=os.getenv("FESTIVAL_ARTISTS_BUCKET"),
        key="wacken.json",
        json=json.dumps(wacken_body),
    )

    dong_artists: Mapping[str, ArtistInformation] = dong_task.result()
    dong_body = []
    for artist in dong_artists.values():
        dong_body.append({"artist": artist.name, "image": artist.image_url})
    s3.upload(
        bucket_name=os.getenv("FESTIVAL_ARTISTS_BUCKET"),
        key="dong.json",
        json=json.dumps(dong_body),
    )

    rude_artists: Mapping[str, ArtistInformation] = rude_task.result()
    rude_body = []
    for artist in rude_artists.values():
        rude_body.append({"artist": artist.name, "image": artist.image_url})
    s3.upload(
        bucket_name=os.getenv("FESTIVAL_ARTISTS_BUCKET"),
        key="rude.json",
        json=json.dumps(rude_body),
    )


def handler(event, context):
    _configure_logger()
    s3 = S3(s3_client=(boto3.client("s3")))
    ssm = Ssm(ssm_client=(boto3.client("ssm", "eu-west-1")))
    spotify_client = SpotifyClient(ssm=ssm)

    asyncio.run(_handle(s3=s3, spotify_client=spotify_client))
