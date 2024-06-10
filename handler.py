import asyncio
import logging
import os

import boto3

from src.adapter.s3 import S3
from src.adapter.ssm import Ssm
from src.festivals.bands import get_wacken_artists, get_dong_artists, get_rude_artists
from src.utils.artist_images import Helper


def _configure_logger():
    log_level_name = os.environ.get("LOG_LEVEL", "INFO")
    logging.Logger.setLevel(level=logging.getLevelName(log_level_name))


def handler(event, context):
    _configure_logger()
    s3_client = boto3.client("s3")
    ssm_client = boto3.client("ssm", "eu-west-1")

    helper = Helper(ssm=Ssm(ssm_client=ssm_client), s3=S3(s3_client=s3_client))

    wacken_artists = asyncio.run(helper.get_images(artist_names=get_wacken_artists()))
    helper.upload(artist_images=wacken_artists, festival_name="wacken")

    dong_artists = asyncio.run(helper.get_images(artist_names=get_dong_artists()))
    helper.upload(artist_images=dong_artists, festival_name="dong")

    rude_artists = asyncio.run(helper.get_images(artist_names=get_rude_artists()))
    helper.upload(artist_images=rude_artists, festival_name="rude")
