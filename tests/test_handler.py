import json
import os
import re

import boto3
import pytest
from moto import mock_aws
from mypy_boto3_s3 import S3Client

from handler import handler


@pytest.fixture
def setup_env():
    os.environ["FESTIVAL_ARTISTS_BUCKET"] = "bucket-name"
    yield
    del os.environ["FESTIVAL_ARTISTS_BUCKET"]


@mock_aws
def test_get_bands_handler_gets_artists_and_images_and_uploads_them(
    spotify_envs, github_envs, setup_env, httpx_mock
):
    wacken_bloodbath_response = [{"artist": {"title": "Bloodbath"}}]
    spotify_token_endpoint = "https://accounts.spotify.com/api/token"
    spotify_token_response = {
        "access_token": "token",
        "token_type": "bearer",
        "expires_in": 3600,
    }
    # spotify_search_bloodbath_url = (
    #     "https://api.spotify.com/v1/search?type=artist&q=Bloodbath&market=DE"
    # )
    spotify_wildcard_search_url = (
        "https:\/\/api\.spotify\.com\/v1\/search\?type=artist&q=.*&market=DE"
    )
    github_issue_url = "https://api.github.com/repos/kruspe/festival-scraper/issues"
    spotify_search_bloodbath_response = {
        "artists": {
            "items": [
                {
                    "id": "RandomSpotifyId",
                    "genres": ["Swedish Death Metal"],
                    "images": [
                        {"height": 640, "url": "https://image_640.com", "width": 640},
                        {"height": 320, "url": "https://image_320.com", "width": 320},
                        {"height": 160, "url": "https://image_160.com", "width": 160},
                    ],
                    "name": "Bloodbath",
                }
            ]
        }
    }
    httpx_mock.add_response(
        method="GET",
        url="https://www.wacken.com/fileadmin/Json/bandlist-concert.json",
        json=wacken_bloodbath_response,
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://www.dongopenair.de/bands/",
        status_code=200,
        text="<a href='https://www.dongopenair.de/band-details/?band=Bloodbath' style='color: #ffffff' z-index='1'>Bloodbath</a>",
    )
    # httpx_mock.add_response(
    #     method="GET",
    #     url="https://www.rockunterdeneichen.de/bands/",
    #     status_code=200,
    #     text="<div class='cb-article-meta'><h2><a>Bloodbath (SWE)</a></h2></div>",
    # )
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        status_code=201,
        is_reusable=True,
    )
    httpx_mock.add_response(
        method="POST",
        url=spotify_token_endpoint,
        json=spotify_token_response,
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url=re.compile(spotify_wildcard_search_url),
        json=spotify_search_bloodbath_response,
        status_code=200,
        is_reusable=True,
    )
    httpx_mock.add_response(
        method="GET",
        url=github_issue_url,
        json=[],
        status_code=200,
    )

    s3_client: S3Client = boto3.client("s3")
    s3_client.create_bucket(
        Bucket="bucket-name",
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )

    ssm_client = boto3.client("ssm", "eu-west-1")
    ssm_client.put_parameter(
        Name="/spotify/client-id", Value="value1", Type="SecureString"
    )
    ssm_client.put_parameter(
        Name="/spotify/client-secret", Value="value2", Type="SecureString"
    )
    ssm_client.put_parameter(
        Name="/github/festival-scraper/pr-token", Value="value3", Type="SecureString"
    )

    wacken_expected_result = [
        {
            "id": "RandomSpotifyId",
            "artist": "Bloodbath",
            "image": "https://image_320.com",
        }
    ]
    dong_expected_result = [
        {
            "id": "RandomSpotifyId",
            "artist": "Bloodbath",
            "image": "https://image_320.com",
        }
    ]
    rude_expected_result = []

    handler(None, None)

    wacken_file = s3_client.get_object(Bucket="bucket-name", Key="wacken.json")
    dong_file = s3_client.get_object(Bucket="bucket-name", Key="dong.json")
    rude_file = s3_client.get_object(Bucket="bucket-name", Key="rude.json")

    assert wacken_expected_result == json.load(wacken_file.get("Body"))
    assert dong_expected_result == json.load(dong_file.get("Body"))
    assert rude_expected_result == json.load(rude_file.get("Body"))
