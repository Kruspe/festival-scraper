import boto3

from src.adapter.s3 import S3
from src.adapter.ssm import Ssm
from src.festivals.bands import get_wacken_artists, get_dong_artists
from src.utils.artist_images import Helper


def handler(event, context):
    s3_client = boto3.client("s3")
    ssm_client = boto3.client("ssm", "eu-west-1")

    helper = Helper(ssm=Ssm(ssm_client=ssm_client), s3=S3(s3_client=s3_client))

    wacken_artists = helper.get_images(artist_names=get_wacken_artists())
    helper.upload(artist_images=wacken_artists, festival_name="wacken")

    dong_artists = helper.get_images(artist_names=get_dong_artists())
    helper.upload(artist_images=dong_artists, festival_name="dong")
