from typing import Union
from unittest.mock import Mock, create_autospec

import pytest

from src.adapter.github import GitHubClient
from src.adapter.spotify import SpotifyClient, ArtistInformation
from src.adapter.ssm import Ssm
from src.festivals.bands import get_wacken_artists, get_dong_artists, get_rude_artists

wacken_url = "https://www.wacken.com/fileadmin/Json/bandlist-concert.json"
dong_url = "https://www.dongopenair.de/bands/"
rude_url = "https://www.rockunterdeneichen.de/bands/"
artist_that_has_issue = "hypocrisy"


@pytest.fixture
def spotify_client(spotify_envs, httpx_mock):
    ssm: Union[Mock, Ssm] = create_autospec(Ssm)
    ssm.get_parameters.return_value = {
        "/spotify/client-id": "client_id",
        "/spotify/client-secret": "client_secret",
    }
    httpx_mock.add_response(
        method="POST",
        url="https://accounts.spotify.com/api/token",
        json={
            "access_token": "token",
            "token_type": "bearer",
            "expires_in": 3600,
        },
        status_code=200,
    )

    yield SpotifyClient(ssm=ssm)


@pytest.fixture
def github_client(github_envs, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        status_code=200,
        json=[
            {
                "number": "1",
                "title": f"Search for ArtistInformation manually: {artist_that_has_issue}",
            },
        ],
        match_headers={
            "Authorization": "Bearer gh_pr_token",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    ssm: Union[Mock, Ssm] = create_autospec(Ssm)
    ssm.get_parameters.return_value = {
        "/github/festival-scraper/pr-token": "gh_pr_token",
    }

    yield GitHubClient(ssm=ssm)


def create_spotify_response(
    *, artist_id: str = None, artist_name: str, image_url: str = None
):
    return {
        "artists": {
            "items": [
                {
                    "id": artist_id,
                    "genres": ["Swedish Death Metal"],
                    "images": [
                        {
                            "height": 320,
                            "url": image_url,
                            "width": 320,
                        },
                    ],
                    "name": artist_name,
                },
            ],
        }
    }


@pytest.mark.asyncio
async def test_get_wacken_artists(spotify_client, github_client, httpx_mock):
    bloodbath = {"artist": {"title": "Bloodbath"}}
    vader = {"artist": {"title": "Vader"}}
    hypocrisy = {"artist": {"title": artist_that_has_issue}}
    metal_disco = {"artist": {"title": "Metal Disco"}}
    metal_yoga = {"artist": {"title": "Metal Yoga"}}
    artist_response = [bloodbath, vader, hypocrisy, metal_disco, metal_yoga]

    image_url = "https://some-image-url.com"
    expected_result = [
        ArtistInformation(id="RandomSpotifyId", name="Bloodbath", image_url=image_url)
    ]

    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath&market=DE",
        json=create_spotify_response(
            artist_id="RandomSpotifyId", artist_name="Bloodbath", image_url=image_url
        ),
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Vader&market=DE",
        json=create_spotify_response(artist_name="Vader"),
        status_code=200,
    )
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.spotify.com/v1/search?type=artist&limit=5&q={artist_that_has_issue}&market=DE",
        json=create_spotify_response(artist_name=artist_that_has_issue),
        status_code=200,
    )

    httpx_mock.add_response(
        method="GET", url=wacken_url, json=artist_response, status_code=200
    )

    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        status_code=201,
    )

    artist_information = await get_wacken_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artist_information == expected_result
    assert len(httpx_mock.get_requests()) == 7
    assert httpx_mock.get_requests()[2].url == wacken_url


@pytest.mark.asyncio
async def test_get_wacken_artists_when_call_fails(
    spotify_client, github_client, httpx_mock
):
    httpx_mock.add_response(method="GET", url=wacken_url, status_code=500)

    artists = await get_wacken_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artists == []
    assert len(httpx_mock.get_requests()) == 3
    assert httpx_mock.get_requests()[2].url == wacken_url


@pytest.mark.asyncio
async def test_get_wacken_artists_closes_opened_issues(
    spotify_client, github_client, httpx_mock
):
    hypocrisy = {"artist": {"title": artist_that_has_issue}}
    artist_response = [hypocrisy]

    image_url = "https://some-image-url.com"
    expected_result = [
        ArtistInformation(
            id="RandomSpotifyId", name=artist_that_has_issue, image_url=image_url
        )
    ]

    httpx_mock.add_response(
        method="GET",
        url=f"https://api.spotify.com/v1/search?type=artist&limit=5&q={artist_that_has_issue}&market=DE",
        json=create_spotify_response(
            artist_id="RandomSpotifyId",
            artist_name=artist_that_has_issue,
            image_url=image_url,
        ),
        status_code=200,
    )

    httpx_mock.add_response(
        method="GET", url=wacken_url, json=artist_response, status_code=200
    )

    httpx_mock.add_response(
        method="PATCH",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues/1",
        status_code=200,
    )

    artist_information = await get_wacken_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artist_information == expected_result
    assert httpx_mock.get_requests()[4].method == "PATCH"
    assert len(httpx_mock.get_requests()) == 5


@pytest.mark.asyncio
async def test_get_dong_artists(spotify_client, github_client, httpx_mock):
    image_url = "https://some-image-url.com"
    html_response = f"""
    <html>
        <body data-cmplz="1" class="page-template page-template-page-no-title page page-id-292 wp-custom-logo wp-embed-responsive theme-twentytwentyfour woocommerce-uses-block-theme woocommerce-block-theme-has-button-styles woocommerce-js cmplz-functional cmplz-eu cmplz-optin"><div id="cmplz-cookiebanner-container"><div class="cmplz-cookiebanner banner-1 bottom-right-view-preferences optin cmplz-bottom-right cmplz-categories-type-view-preferences cmplz-dismissed" aria-modal="true" data-nosnippet="true" role="dialog" aria-live="polite" aria-labelledby="cmplz-header-1-optin" aria-describedby="cmplz-message-1-optin">
	<div class="cmplz-header">
		<div class="cmplz-logo"></div>
		<div class="cmplz-title" id="cmplz-header-1-optin">Cookie-Zustimmung verwalten</div>
		<div class="cmplz-close" tabindex="0" role="button" aria-label="Dialog schließen">
			<svg aria-hidden="true" focusable="false" data-prefix="fas" data-icon="times" class="svg-inline--fa fa-times fa-w-11" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 352 512"><path fill="currentColor" d="M242.72 256l100.07-100.07c12.28-12.28 12.28-32.19 0-44.48l-22.24-22.24c-12.28-12.28-32.19-12.28-44.48 0L176 189.28 75.93 89.21c-12.28-12.28-32.19-12.28-44.48 0L9.21 111.45c-12.28 12.28-12.28 32.19 0 44.48L109.28 256 9.21 356.07c-12.28 12.28-12.28 32.19 0 44.48l22.24 22.24c12.28 12.28 32.2 12.28 44.48 0L176 322.72l100.07 100.07c12.28 12.28 32.2 12.28 44.48 0l22.24-22.24c12.28-12.28 12.28-32.19 0-44.48L242.72 256z"></path></svg>
		</div>
	</div>

	<div class="cmplz-divider cmplz-divider-header"></div>
	<div class="cmplz-body">
		<div class="cmplz-message" id="cmplz-message-1-optin">Um dir ein optimales Erlebnis zu bieten, verwenden wir Technologien wie Cookies, um Geräteinformationen zu speichern und/oder darauf zuzugreifen. Wenn du diesen Technologien zustimmst, können wir Daten wie das Surfverhalten oder eindeutige IDs auf dieser Website verarbeiten. Wenn du deine Zustimmung nicht erteilst oder zurückziehst, können bestimmte Merkmale und Funktionen beeinträchtigt werden.</div>
		<!-- categories start -->
		<div class="cmplz-categories">
			<details class="cmplz-category cmplz-functional">
				<summary>
						<span class="cmplz-category-header">
							<span class="cmplz-category-title">Funktional</span>
							<span class="cmplz-always-active">
								<span class="cmplz-banner-checkbox">
									<input type="checkbox" id="cmplz-functional-optin" data-category="cmplz_functional" class="cmplz-consent-checkbox cmplz-functional" size="40" value="1">
									<label class="cmplz-label" for="cmplz-functional-optin" tabindex="0"><span class="screen-reader-text">Funktional</span></label>
								</span>
								Immer aktiv							</span>
							<span class="cmplz-icon cmplz-open">
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512" height="18"><path d="M224 416c-8.188 0-16.38-3.125-22.62-9.375l-192-192c-12.5-12.5-12.5-32.75 0-45.25s32.75-12.5 45.25 0L224 338.8l169.4-169.4c12.5-12.5 32.75-12.5 45.25 0s12.5 32.75 0 45.25l-192 192C240.4 412.9 232.2 416 224 416z"></path></svg>
							</span>
						</span>
				</summary>
				<div class="cmplz-description">
					<span class="cmplz-description-functional">Die technische Speicherung oder der Zugang ist unbedingt erforderlich für den rechtmäßigen Zweck, die Nutzung eines bestimmten Dienstes zu ermöglichen, der vom Teilnehmer oder Nutzer ausdrücklich gewünscht wird, oder für den alleinigen Zweck, die Übertragung einer Nachricht über ein elektronisches Kommunikationsnetz durchzuführen.</span>
				</div>
			</details>

			<details class="cmplz-category cmplz-preferences">
				<summary>
						<span class="cmplz-category-header">
							<span class="cmplz-category-title">Vorlieben</span>
							<span class="cmplz-banner-checkbox">
								<input type="checkbox" id="cmplz-preferences-optin" data-category="cmplz_preferences" class="cmplz-consent-checkbox cmplz-preferences" size="40" value="1">
								<label class="cmplz-label" for="cmplz-preferences-optin" tabindex="0"><span class="screen-reader-text">Vorlieben</span></label>
							</span>
							<span class="cmplz-icon cmplz-open">
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512" height="18"><path d="M224 416c-8.188 0-16.38-3.125-22.62-9.375l-192-192c-12.5-12.5-12.5-32.75 0-45.25s32.75-12.5 45.25 0L224 338.8l169.4-169.4c12.5-12.5 32.75-12.5 45.25 0s12.5 32.75 0 45.25l-192 192C240.4 412.9 232.2 416 224 416z"></path></svg>
							</span>
						</span>
				</summary>
				<div class="cmplz-description">
					<span class="cmplz-description-preferences">Die technische Speicherung oder der Zugriff ist für den rechtmäßigen Zweck der Speicherung von Präferenzen erforderlich, die nicht vom Abonnenten oder Benutzer angefordert wurden.</span>
				</div>
			</details>

			<details class="cmplz-category cmplz-statistics">
				<summary>
						<span class="cmplz-category-header">
							<span class="cmplz-category-title">Statistiken</span>
							<span class="cmplz-banner-checkbox">
								<input type="checkbox" id="cmplz-statistics-optin" data-category="cmplz_statistics" class="cmplz-consent-checkbox cmplz-statistics" size="40" value="1">
								<label class="cmplz-label" for="cmplz-statistics-optin" tabindex="0"><span class="screen-reader-text">Statistiken</span></label>
							</span>
							<span class="cmplz-icon cmplz-open">
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512" height="18"><path d="M224 416c-8.188 0-16.38-3.125-22.62-9.375l-192-192c-12.5-12.5-12.5-32.75 0-45.25s32.75-12.5 45.25 0L224 338.8l169.4-169.4c12.5-12.5 32.75-12.5 45.25 0s12.5 32.75 0 45.25l-192 192C240.4 412.9 232.2 416 224 416z"></path></svg>
							</span>
						</span>
				</summary>
				<div class="cmplz-description">
					<span class="cmplz-description-statistics">Die technische Speicherung oder der Zugriff, der ausschließlich zu statistischen Zwecken erfolgt.</span>
					<span class="cmplz-description-statistics-anonymous">Die technische Speicherung oder der Zugriff, der ausschließlich zu anonymen statistischen Zwecken verwendet wird. Ohne eine Vorladung, die freiwillige Zustimmung deines Internetdienstanbieters oder zusätzliche Aufzeichnungen von Dritten können die zu diesem Zweck gespeicherten oder abgerufenen Informationen allein in der Regel nicht dazu verwendet werden, dich zu identifizieren.</span>
				</div>
			</details>
			<details class="cmplz-category cmplz-marketing">
				<summary>
						<span class="cmplz-category-header">
							<span class="cmplz-category-title">Marketing</span>
							<span class="cmplz-banner-checkbox">
								<input type="checkbox" id="cmplz-marketing-optin" data-category="cmplz_marketing" class="cmplz-consent-checkbox cmplz-marketing" size="40" value="1">
								<label class="cmplz-label" for="cmplz-marketing-optin" tabindex="0"><span class="screen-reader-text">Marketing</span></label>
							</span>
							<span class="cmplz-icon cmplz-open">
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512" height="18"><path d="M224 416c-8.188 0-16.38-3.125-22.62-9.375l-192-192c-12.5-12.5-12.5-32.75 0-45.25s32.75-12.5 45.25 0L224 338.8l169.4-169.4c12.5-12.5 32.75-12.5 45.25 0s12.5 32.75 0 45.25l-192 192C240.4 412.9 232.2 416 224 416z"></path></svg>
							</span>
						</span>
				</summary>
				<div class="cmplz-description">
					<span class="cmplz-description-marketing">Die technische Speicherung oder der Zugriff ist erforderlich, um Nutzerprofile zu erstellen, um Werbung zu versenden oder um den Nutzer auf einer Website oder über mehrere Websites hinweg zu ähnlichen Marketingzwecken zu verfolgen.</span>
				</div>
			</details>
		</div><!-- categories end -->
			</div>

	<div class="cmplz-links cmplz-information">
		<a class="cmplz-link cmplz-manage-options cookie-statement" href="https://www.dongopenair.de/cookie-richtlinie-eu/#cmplz-manage-consent-container" data-relative_url="#cmplz-manage-consent-container">Optionen verwalten</a>
		<a class="cmplz-link cmplz-manage-third-parties cookie-statement" href="https://www.dongopenair.de/cookie-richtlinie-eu/#cmplz-cookies-overview" data-relative_url="#cmplz-cookies-overview">Dienste verwalten</a>
		<a class="cmplz-link cmplz-manage-vendors tcf cookie-statement" href="https://www.dongopenair.de/cookie-richtlinie-eu/#cmplz-tcf-wrapper" data-relative_url="#cmplz-tcf-wrapper">Verwalten von -Lieferanten</a>
		<a class="cmplz-link cmplz-external cmplz-read-more-purposes tcf" target="_blank" rel="noopener noreferrer nofollow" href="https://cookiedatabase.org/tcf/purposes/">Lese mehr über diese Zwecke</a>
			</div>

	<div class="cmplz-divider cmplz-footer"></div>

	<div class="cmplz-buttons">
		<button class="cmplz-btn cmplz-accept">Akzeptieren</button>
		<button class="cmplz-btn cmplz-deny">Ablehnen</button>
		<button class="cmplz-btn cmplz-view-preferences">Einstellungen ansehen</button>
		<button class="cmplz-btn cmplz-save-preferences">Einstellungen speichern</button>
		<a class="cmplz-btn cmplz-manage-options tcf cookie-statement" href="https://www.dongopenair.de/cookie-richtlinie-eu/#cmplz-manage-consent-container" data-relative_url="#cmplz-manage-consent-container">Einstellungen ansehen</a>
			</div>

	<div class="cmplz-links cmplz-documents">
		<a class="cmplz-link cookie-statement" href="https://www.dongopenair.de/cookie-richtlinie-eu/" data-relative_url="">Cookie-Richtlinie </a>
		<a class="cmplz-link privacy-statement" href="https://www.dongopenair.de/privacy-policy/" data-relative_url="">Datenschutzerklärung</a>
		<a class="cmplz-link impressum" href="https://www.dongopenair.de/impressum/" data-relative_url="">Impressum</a>
			</div>

</div>
</div>

<a class="skip-link screen-reader-text" href="#wp--skip-link--target">Direkt zum Inhalt wechseln</a><div class="wp-site-blocks"><header class="wp-block-template-part"><div class="wp-block-group alignwide has-base-background-color has-background is-layout-flow wp-block-group-is-layout-flow" style="padding-top:0px;padding-bottom:0px"><div class="wp-block-group is-content-justification-space-between is-nowrap is-layout-flex wp-container-core-group-is-layout-3 wp-block-group-is-layout-flex"><div class="wp-block-group is-nowrap is-layout-flex wp-container-core-group-is-layout-1 wp-block-group-is-layout-flex"><ul class="wp-block-social-links has-small-icon-size has-icon-background-color is-style-default is-layout-flex wp-container-core-social-links-is-layout-1 wp-block-social-links-is-layout-flex" style="margin-top:0;margin-right:1.2rem;margin-bottom:0;margin-left:1.2rem"><li style="background-color: #000; " class="wp-social-link wp-social-link-facebook  wp-block-social-link"><a rel="noopener nofollow" target="_blank" href="https://www.facebook.com/DongOpenAir" class="wp-block-social-link-anchor"><svg width="24" height="24" viewBox="0 0 24 24" version="1.1" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"><path d="M12 2C6.5 2 2 6.5 2 12c0 5 3.7 9.1 8.4 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9 3.8-3.9 1.1 0 2.2.2 2.2.2v2.5h-1.3c-1.2 0-1.6.8-1.6 1.6V12h2.8l-.4 2.9h-2.3v7C18.3 21.1 22 17 22 12c0-5.5-4.5-10-10-10z"></path></svg><span class="wp-block-social-link-label screen-reader-text">Facebook</span></a></li>

<li style="background-color: #000; " class="wp-social-link wp-social-link-x  wp-block-social-link"><a rel="noopener nofollow" target="_blank" href="https://x.com/i/flow/login?redirect_after_login=%2FDongOpenAir" class="wp-block-social-link-anchor"><svg width="24" height="24" viewBox="0 0 24 24" version="1.1" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"><path d="M13.982 10.622 20.54 3h-1.554l-5.693 6.618L8.745 3H3.5l6.876 10.007L3.5 21h1.554l6.012-6.989L15.868 21h5.245l-7.131-10.378Zm-2.128 2.474-.697-.997-5.543-7.93H8l4.474 6.4.697.996 5.815 8.318h-2.387l-4.745-6.787Z"></path></svg><span class="wp-block-social-link-label screen-reader-text">X</span></a></li>

<li style="background-color: #000; " class="wp-social-link wp-social-link-instagram  wp-block-social-link"><a rel="noopener nofollow" target="_blank" href="https://www.instagram.com/dong_open_air" class="wp-block-social-link-anchor"><svg width="24" height="24" viewBox="0 0 24 24" version="1.1" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"><path d="M12,4.622c2.403,0,2.688,0.009,3.637,0.052c0.877,0.04,1.354,0.187,1.671,0.31c0.42,0.163,0.72,0.358,1.035,0.673 c0.315,0.315,0.51,0.615,0.673,1.035c0.123,0.317,0.27,0.794,0.31,1.671c0.043,0.949,0.052,1.234,0.052,3.637 s-0.009,2.688-0.052,3.637c-0.04,0.877-0.187,1.354-0.31,1.671c-0.163,0.42-0.358,0.72-0.673,1.035 c-0.315,0.315-0.615,0.51-1.035,0.673c-0.317,0.123-0.794,0.27-1.671,0.31c-0.949,0.043-1.233,0.052-3.637,0.052 s-2.688-0.009-3.637-0.052c-0.877-0.04-1.354-0.187-1.671-0.31c-0.42-0.163-0.72-0.358-1.035-0.673 c-0.315-0.315-0.51-0.615-0.673-1.035c-0.123-0.317-0.27-0.794-0.31-1.671C4.631,14.688,4.622,14.403,4.622,12 s0.009-2.688,0.052-3.637c0.04-0.877,0.187-1.354,0.31-1.671c0.163-0.42,0.358-0.72,0.673-1.035 c0.315-0.315,0.615-0.51,1.035-0.673c0.317-0.123,0.794-0.27,1.671-0.31C9.312,4.631,9.597,4.622,12,4.622 M12,3 C9.556,3,9.249,3.01,8.289,3.054C7.331,3.098,6.677,3.25,6.105,3.472C5.513,3.702,5.011,4.01,4.511,4.511 c-0.5,0.5-0.808,1.002-1.038,1.594C3.25,6.677,3.098,7.331,3.054,8.289C3.01,9.249,3,9.556,3,12c0,2.444,0.01,2.751,0.054,3.711 c0.044,0.958,0.196,1.612,0.418,2.185c0.23,0.592,0.538,1.094,1.038,1.594c0.5,0.5,1.002,0.808,1.594,1.038 c0.572,0.222,1.227,0.375,2.185,0.418C9.249,20.99,9.556,21,12,21s2.751-0.01,3.711-0.054c0.958-0.044,1.612-0.196,2.185-0.418 c0.592-0.23,1.094-0.538,1.594-1.038c0.5-0.5,0.808-1.002,1.038-1.594c0.222-0.572,0.375-1.227,0.418-2.185 C20.99,14.751,21,14.444,21,12s-0.01-2.751-0.054-3.711c-0.044-0.958-0.196-1.612-0.418-2.185c-0.23-0.592-0.538-1.094-1.038-1.594 c-0.5-0.5-1.002-0.808-1.594-1.038c-0.572-0.222-1.227-0.375-2.185-0.418C14.751,3.01,14.444,3,12,3L12,3z M12,7.378 c-2.552,0-4.622,2.069-4.622,4.622S9.448,16.622,12,16.622s4.622-2.069,4.622-4.622S14.552,7.378,12,7.378z M12,15 c-1.657,0-3-1.343-3-3s1.343-3,3-3s3,1.343,3,3S13.657,15,12,15z M16.804,6.116c-0.596,0-1.08,0.484-1.08,1.08 s0.484,1.08,1.08,1.08c0.596,0,1.08-0.484,1.08-1.08S17.401,6.116,16.804,6.116z"></path></svg><span class="wp-block-social-link-label screen-reader-text">Instagram</span></a></li>

<li style="background-color: #000; " class="wp-social-link wp-social-link-youtube  wp-block-social-link"><a rel="noopener nofollow" target="_blank" href="https://www.youtube.com/channel/UCVB8z9NTK526Xsl6E6xTGGA" class="wp-block-social-link-anchor"><svg width="24" height="24" viewBox="0 0 24 24" version="1.1" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"><path d="M21.8,8.001c0,0-0.195-1.378-0.795-1.985c-0.76-0.797-1.613-0.801-2.004-0.847c-2.799-0.202-6.997-0.202-6.997-0.202 h-0.009c0,0-4.198,0-6.997,0.202C4.608,5.216,3.756,5.22,2.995,6.016C2.395,6.623,2.2,8.001,2.2,8.001S2,9.62,2,11.238v1.517 c0,1.618,0.2,3.237,0.2,3.237s0.195,1.378,0.795,1.985c0.761,0.797,1.76,0.771,2.205,0.855c1.6,0.153,6.8,0.201,6.8,0.201 s4.203-0.006,7.001-0.209c0.391-0.047,1.243-0.051,2.004-0.847c0.6-0.607,0.795-1.985,0.795-1.985s0.2-1.618,0.2-3.237v-1.517 C22,9.62,21.8,8.001,21.8,8.001z M9.935,14.594l-0.001-5.62l5.404,2.82L9.935,14.594z"></path></svg><span class="wp-block-social-link-label screen-reader-text">YouTube</span></a></li></ul></div>

<header class="wp-block-group is-content-justification-right is-nowrap is-layout-flex wp-container-core-group-is-layout-2 wp-block-group-is-layout-flex" style="padding-right:var(--wp--preset--spacing--10);padding-left:var(--wp--preset--spacing--10);text-transform:uppercase"><nav style="font-size:0.8rem;" class="is-responsive wp-block-navigation is-layout-flex wp-container-core-navigation-is-layout-1 wp-block-navigation-is-layout-flex" aria-label="Top Menu" data-wp-interactive="core/navigation" data-wp-context=""><button aria-haspopup="dialog" aria-label="Menü öffnen" class="wp-block-navigation__responsive-container-open " data-wp-on-async--click="actions.openMenuOnClick" data-wp-on--keydown="actions.handleMenuKeydown"><svg width="24" height="24" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="4" y="7.5" width="16" height="1.5"></rect><rect x="4" y="15" width="16" height="1.5"></rect></svg></button>
				<div class="wp-block-navigation__responsive-container" id="modal-1" data-wp-class--has-modal-open="state.isMenuOpen" data-wp-class--is-menu-open="state.isMenuOpen" data-wp-watch="callbacks.initMenu" data-wp-on--keydown="actions.handleMenuKeydown" data-wp-on-async--focusout="actions.handleMenuFocusout" tabindex="-1">
					<div class="wp-block-navigation__responsive-close" tabindex="-1">
						<div class="wp-block-navigation__responsive-dialog" data-wp-bind--aria-modal="state.ariaModal" data-wp-bind--aria-label="state.ariaLabel" data-wp-bind--role="state.roleAttribute">
							<button aria-label="Menü schließen" class="wp-block-navigation__responsive-container-close" data-wp-on-async--click="actions.closeMenuOnClick"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false"><path d="m13.06 12 6.47-6.47-1.06-1.06L12 10.94 5.53 4.47 4.47 5.53 10.94 12l-6.47 6.47 1.06 1.06L12 13.06l6.47 6.47 1.06-1.06L13.06 12Z"></path></svg></button>
							<div class="wp-block-navigation__responsive-container-content" data-wp-watch="callbacks.focusFirstElement" id="modal-1-content">
								<ul style="font-size:0.8rem;" class="wp-block-navigation__container is-responsive wp-block-navigation"><li style="font-size: 0.8rem;" class=" wp-block-navigation-item wp-block-navigation-link"><a class="wp-block-navigation-item__content" href="https://devweb.dongopenair.de/index.php/presseinformationen/"><span class="wp-block-navigation-item__label">Presse</span></a></li><li style="font-size: 0.8rem;" class=" wp-block-navigation-item wp-block-navigation-link"><a class="wp-block-navigation-item__content" href="https://devweb.dongopenair.de/index.php/kontakt/"><span class="wp-block-navigation-item__label">Kontakt</span></a></li><li style="font-size: 0.8rem;" class=" wp-block-navigation-item wp-block-navigation-link"><a class="wp-block-navigation-item__content" href="https://devweb.dongopenair.de/index.php/impressum/"><span class="wp-block-navigation-item__label">Impressum</span></a></li><li style="font-size: 0.8rem;" class=" wp-block-navigation-item wp-block-navigation-link"><a class="wp-block-navigation-item__content" href="https://devweb.dongopenair.de/index.php/datenschutzerklaerung/"><span class="wp-block-navigation-item__label">Datenschutz</span></a></li></ul>
							</div>
						</div>
					</div>
				</div></nav>

<div data-block-name="woocommerce/customer-account" data-display-style="icon_only" data-icon-style="line" data-style="" class="wp-block-woocommerce-customer-account " style="margin-left:0.5em;">
			<a aria-label="Anmelden" href="https://www.dongopenair.de/my-account/">
				<svg class="icon" viewBox="5 5 22 22" xmlns="http://www.w3.org/2000/svg">
				<circle cx="16" cy="10.5" r="3.5" stroke="currentColor" stroke-width="2" fill="none"></circle>
				<path fill-rule="evenodd" clip-rule="evenodd" d="M11.5 18.5H20.5C21.8807 18.5 23 19.6193 23 21V25.5H25V21C25 18.5147 22.9853 16.5 20.5 16.5H11.5C9.01472 16.5 7 18.5147 7 21V25.5H9V21C9 19.6193 10.1193 18.5 11.5 18.5Z" fill="currentColor"></path>
			</svg>
			</a>
		</div></header></div>

<div class="wp-block-group alignwide has-base-color has-contrast-background-color has-text-color has-background has-link-color wp-elements-9fa495563fe57488a4c062bf25502d34 is-content-justification-space-between is-layout-flex wp-container-core-group-is-layout-6 wp-block-group-is-layout-flex" style="margin-top:0em;margin-bottom:0em;padding-top:0.4em;padding-right:var(--wp--preset--spacing--20);padding-bottom:0.4em;padding-left:var(--wp--preset--spacing--20);text-transform:uppercase"><div class="wp-block-group is-layout-flex wp-container-core-group-is-layout-4 wp-block-group-is-layout-flex"><div class="wp-block-site-logo"><a href="https://www.dongopenair.de/" class="custom-logo-link" rel="home"><img width="270" height="32" src="https://www.dongopenair.de/wp-content/uploads/2024/10/Logo_25_Datum.png" class="custom-logo" alt="Dong Open Air 2025" decoding="async" srcset="https://www.dongopenair.de/wp-content/uploads/2024/10/Logo_25_Datum.png 340w, https://www.dongopenair.de/wp-content/uploads/2024/10/Logo_25_Datum-300x36.png 300w" sizes="(max-width: 270px) 100vw, 270px"></a></div></div>

<div class="wp-block-group is-content-justification-left is-layout-flex wp-container-core-group-is-layout-5 wp-block-group-is-layout-flex" style="padding-right:0;padding-left:0"><nav style="font-size:clamp(0.984rem, 0.984rem + ((1vw - 0.2rem) * 0.86), 1.5rem);font-style:normal;font-weight:700;" class="has-text-color has-contrast-color items-justified-left ticket-menu-background wp-block-navigation is-content-justification-left is-layout-flex wp-container-core-navigation-is-layout-2 wp-block-navigation-is-layout-flex" aria-label="Ticket Link"><ul style="font-size:clamp(0.984rem, 0.984rem + ((1vw - 0.2rem) * 0.86), 1.5rem);font-style:normal;font-weight:700;" class="wp-block-navigation__container has-text-color has-contrast-color items-justified-left ticket-menu-background wp-block-navigation"><li style="font-size: clamp(0.984rem, 0.984rem + ((1vw - 0.2rem) * 0.86), 1.5rem);" class=" wp-block-navigation-item wp-block-navigation-link"><a class="wp-block-navigation-item__content" href="https://devweb.dongopenair.de/tickets/"><span class="wp-block-navigation-item__label">Tickets</span></a></li></ul></nav>

<nav style="font-style:normal;font-weight:700;" class="is-responsive items-justified-right wp-block-navigation is-horizontal is-content-justification-right is-layout-flex wp-container-core-navigation-is-layout-3 wp-block-navigation-is-layout-flex" aria-label="Main Menu" data-wp-interactive="core/navigation" data-wp-context=""><button aria-haspopup="dialog" aria-label="Menü öffnen" class="wp-block-navigation__responsive-container-open " data-wp-on-async--click="actions.openMenuOnClick" data-wp-on--keydown="actions.handleMenuKeydown"><svg width="24" height="24" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M5 5v1.5h14V5H5zm0 7.8h14v-1.5H5v1.5zM5 19h14v-1.5H5V19z"></path></svg></button>
				<div class="wp-block-navigation__responsive-container" id="modal-2" data-wp-class--has-modal-open="state.isMenuOpen" data-wp-class--is-menu-open="state.isMenuOpen" data-wp-watch="callbacks.initMenu" data-wp-on--keydown="actions.handleMenuKeydown" data-wp-on-async--focusout="actions.handleMenuFocusout" tabindex="-1">
					<div class="wp-block-navigation__responsive-close" tabindex="-1">
						<div class="wp-block-navigation__responsive-dialog" data-wp-bind--aria-modal="state.ariaModal" data-wp-bind--aria-label="state.ariaLabel" data-wp-bind--role="state.roleAttribute">
							<button aria-label="Menü schließen" class="wp-block-navigation__responsive-container-close" data-wp-on-async--click="actions.closeMenuOnClick"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false"><path d="m13.06 12 6.47-6.47-1.06-1.06L12 10.94 5.53 4.47 4.47 5.53 10.94 12l-6.47 6.47 1.06 1.06L12 13.06l6.47 6.47 1.06-1.06L13.06 12Z"></path></svg></button>
							<div class="wp-block-navigation__responsive-container-content" data-wp-watch="callbacks.focusFirstElement" id="modal-2-content">
								<ul style="font-style:normal;font-weight:700;" class="wp-block-navigation__container is-responsive items-justified-right wp-block-navigation"><li class=" wp-block-navigation-item current-menu-item wp-block-navigation-link"><a class="wp-block-navigation-item__content" href="https://devweb.dongopenair.de/index.php/bands/" aria-current="page"><span class="wp-block-navigation-item__label">Bands</span></a></li><li class=" wp-block-navigation-item wp-block-navigation-link"><a class="wp-block-navigation-item__content" href="https://devweb.dongopenair.de/de/neuste-news/"><span class="wp-block-navigation-item__label">News</span></a></li><li data-wp-context="" data-wp-interactive="core/navigation" data-wp-on--focusout="actions.handleMenuFocusout" data-wp-on--keydown="actions.handleMenuKeydown" data-wp-on-async--mouseenter="actions.openMenuOnHover" data-wp-on-async--mouseleave="actions.closeMenuOnHover" data-wp-watch="callbacks.initMenu" tabindex="-1" class=" wp-block-navigation-item has-child open-on-hover-click wp-block-navigation-submenu"><a class="wp-block-navigation-item__content" href="https://devweb.dongopenair.de/de/infos/">Infos</a><button data-wp-bind--aria-expanded="state.isMenuOpen" data-wp-on-async--click="actions.toggleMenuOnClick" aria-label="Untermenü von Infos" class="wp-block-navigation__submenu-icon wp-block-navigation-submenu__toggle" aria-expanded="false"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true" focusable="false"><path d="M1.50002 4L6.00002 8L10.5 4" stroke-width="1.5"></path></svg></button><ul data-wp-on-async--focus="actions.openMenuOnFocus" class="wp-block-navigation__submenu-container wp-block-navigation-submenu"><li class=" wp-block-navigation-item wp-block-navigation-link"><a class="wp-block-navigation-item__content" href="https://devweb.dongopenair.de/de/infos/"><span class="wp-block-navigation-item__label">FAQ</span></a></li><li class=" wp-block-navigation-item wp-block-navigation-link"><a class="wp-block-navigation-item__content" href="https://devweb.dongopenair.de/de/anfahrt/"><span class="wp-block-navigation-item__label">Anfahrt</span></a></li></ul></li></ul>
							</div>
						</div>
					</div>
				</div></nav></div></div></div></header><main class="wp-block-group is-layout-flow wp-block-group-is-layout-flow" style="margin-top:0" id="wp--skip-link--target">
	<div class="entry-content wp-block-post-content has-global-padding is-layout-constrained wp-block-post-content-is-layout-constrained"><div class="wp-block-group alignfull has-global-padding is-layout-constrained wp-block-group-is-layout-constrained"><figure class="wp-block-image alignfull size-full"><img fetchpriority="high" decoding="async" width="1920" height="323" src="https://www.dongopenair.de/wp-content/uploads/2024/11/Bandheader_25.jpg" alt="Eine Band lässt sich auf der Bühne des Dong Open Air vom Publikum feiern. " class="wp-image-1746" srcset="https://www.dongopenair.de/wp-content/uploads/2024/11/Bandheader_25.jpg 1920w, https://www.dongopenair.de/wp-content/uploads/2024/11/Bandheader_25-300x50.jpg 300w, https://www.dongopenair.de/wp-content/uploads/2024/11/Bandheader_25-1024x172.jpg 1024w, https://www.dongopenair.de/wp-content/uploads/2024/11/Bandheader_25-768x129.jpg 768w, https://www.dongopenair.de/wp-content/uploads/2024/11/Bandheader_25-1536x258.jpg 1536w, https://www.dongopenair.de/wp-content/uploads/2024/11/Bandheader_25-600x101.jpg 600w" sizes="(max-width: 1920px) 100vw, 1920px"></figure>

<hr class="wp-block-separator has-text-color has-base-color has-alpha-channel-opacity has-base-background-color has-background is-style-wide" style="margin-top:10px;margin-bottom:10px">

<div class="wp-block-group alignfull has-base-background-color has-background has-global-padding is-layout-constrained wp-block-group-is-layout-constrained"><div class="wp-block-group alignfull is-content-justification-center is-layout-flex wp-block-group-is-layout-flex" style="margin-left: auto !important; margin-right: auto !important; justify-content: center;  column-count: 3;">
<div style="position: relative; margin: 0.5em 1.5em;"><a href="https://www.dongopenair.de/band-details/?band=Bloodbath&amp;doa_year=2025"><img decoding="async" src="/wp-content/plugins/dong_magic/files/doa_2025/bands/destruction.jpg" style="z-index: 0; max-width: 25em; min-width: 10em;  aspect-ratio: 2/1; object-fit: cover;"></a><a style="color: #ffffff; text-shadow: 2px 2px black; font-size: 1.5em; z-index: 1; position: absolute; left: 0; top: 40%; width: 100%; text-align: center;" href="https://www.dongopenair.de/band-details/?band=Bloodbath&amp;doa_year=2025">Bloodbath</a></div>
<div style="position: relative; margin: 0.5em 1.5em;"><a href="https://www.dongopenair.de/band-details/?band=Dawn of Disease&amp;doa_year=2025"><img decoding="async" src="/wp-content/plugins/dong_magic/files/doa_2025/bands/doomcrusher.jpg" style="z-index: 0; max-width: 25em; min-width: 10em;  aspect-ratio: 2/1; object-fit: cover;"></a><a style="color: #ffffff; text-shadow: 2px 2px black; font-size: 1.5em; z-index: 1; position: absolute; left: 0; top: 40%; width: 100%; text-align: center;" href="https://www.dongopenair.de/band-details/?band=Dawn of Disease&amp;doa_year=2025">Dawn of Disease</a></div>
<div style="position: relative; margin: 0.5em 1.5em;"><a href="https://www.dongopenair.de/band-details/?band={artist_that_has_issue}&amp;doa_year=2025"><img decoding="async" src="/wp-content/plugins/dong_magic/files/doa_2025/bands/kissin_dynamite.jpg" style="z-index: 0; max-width: 25em; min-width: 10em;  aspect-ratio: 2/1; object-fit: cover;"></a><a style="color: #ffffff; text-shadow: 2px 2px black; font-size: 1.5em; z-index: 1; position: absolute; left: 0; top: 40%; width: 100%; text-align: center;" href="https://www.dongopenair.de/band-details/?band={artist_that_has_issue}&amp;doa_year=2025">{artist_that_has_issue}</a></div>
</div>
</div></div><p></p></div>
</main><footer class="wp-block-template-part"><div class="wp-block-group is-layout-flow wp-block-group-is-layout-flow"><hr class="wp-block-separator has-alpha-channel-opacity is-style-wide">

<div class="wp-block-group is-content-justification-center is-layout-flex wp-container-core-group-is-layout-11 wp-block-group-is-layout-flex"><figure class="wp-block-image size-full is-resized"><img decoding="async" width="1074" height="112" src="https://devweb.dongopenair.de/wp-content/uploads/2024/10/sponsors.jpg" alt="" class="wp-image-1372" style="width:500px" srcset="https://www.dongopenair.de/wp-content/uploads/2024/10/sponsors.jpg 1074w, https://www.dongopenair.de/wp-content/uploads/2024/10/sponsors-300x31.jpg 300w, https://www.dongopenair.de/wp-content/uploads/2024/10/sponsors-1024x107.jpg 1024w, https://www.dongopenair.de/wp-content/uploads/2024/10/sponsors-768x80.jpg 768w, https://www.dongopenair.de/wp-content/uploads/2024/10/sponsors-600x63.jpg 600w" sizes="(max-width: 1074px) 100vw, 1074px"></figure></div>

<div style="height:12px" aria-hidden="true" class="wp-block-spacer"></div></div></footer></div>

<!-- Consent Management powered by Complianz | GDPR/CCPA Cookie Consent https://wordpress.org/plugins/complianz-gdpr -->

					<div id="cmplz-manage-consent" data-nosnippet="true"><button class="cmplz-btn cmplz-manage-consent manage-consent-1 cmplz-show">Zustimmung verwalten</button>

</div>
</body>
    </html>
    """
    httpx_mock.add_response(method="GET", url=dong_url, text=html_response)
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath&market=DE",
        json=create_spotify_response(
            artist_id="RandomSpotifyId", artist_name="Bloodbath", image_url=image_url
        ),
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Dawn of Disease&market=DE",
        json=create_spotify_response(artist_name="Dawn of Disease"),
    )
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.spotify.com/v1/search?type=artist&limit=5&q={artist_that_has_issue}&market=DE",
        json=create_spotify_response(artist_name=artist_that_has_issue),
    )

    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        status_code=201,
    )

    artists = await get_dong_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artists == [
        ArtistInformation(id="RandomSpotifyId", name="Bloodbath", image_url=image_url),
    ]
    assert len(httpx_mock.get_requests()) == 7
    assert httpx_mock.get_requests()[2].url == dong_url


@pytest.mark.asyncio
async def test_get_dong_artists_does_not_return_when_no_a_element_appears(
    spotify_client, github_client, httpx_mock
):
    image_url = "https://some-image-url.com"
    html_response = """
        <html>
            <body>
                <a href="https://www.dongopenair.de/band-details/?band=Bloodbath"></a>
                <a href="https://www.dongopenair.de/band-details/?band=Bloodbath" style="color: #ffffff" z-index="1">Bloodbath</a>
                <a></a>
                <a style="color: #ffffff" z-index="1">Party mit DJ Benne</a>
            </body>
        </html>
        """
    httpx_mock.add_response(method="GET", url=dong_url, text=html_response)
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Bloodbath&market=DE",
        json=create_spotify_response(
            artist_id="RandomSpotifyId", artist_name="Bloodbath", image_url=image_url
        ),
    )
    artists = await get_dong_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artists == [
        ArtistInformation(id="RandomSpotifyId", name="Bloodbath", image_url=image_url)
    ]


@pytest.mark.asyncio
async def test_get_dong_artists_when_call_fails(
    spotify_client, github_client, httpx_mock
):
    httpx_mock.add_response(method="GET", url=dong_url, status_code=500)

    artists = await get_dong_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artists == []


@pytest.mark.asyncio
async def test_get_dong_artists_closes_opened_issues(
    spotify_client, github_client, httpx_mock
):
    image_url = "https://some-image-url.com"
    html_response = f"""
        <html>
            <body>
                <a href="https://www.dongopenair.de/band-details/?band={artist_that_has_issue}"></a>
                <a href="https://www.dongopenair.de/band-details/?band={artist_that_has_issue}" style="color: #ffffff" z-index="1">{artist_that_has_issue}</a>
            </body>
        </html>
        """
    httpx_mock.add_response(method="GET", url=dong_url, text=html_response)
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.spotify.com/v1/search?type=artist&limit=5&q={artist_that_has_issue}&market=DE",
        json=create_spotify_response(
            artist_id="RandomSpotifyId",
            artist_name=artist_that_has_issue,
            image_url=image_url,
        ),
    )

    httpx_mock.add_response(
        method="PATCH",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues/1",
        status_code=200,
    )

    artists = await get_dong_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artists == [
        ArtistInformation(
            id="RandomSpotifyId", name=artist_that_has_issue, image_url=image_url
        ),
    ]
    assert len(httpx_mock.get_requests()) == 5
    assert httpx_mock.get_requests()[4].method == "PATCH"


@pytest.mark.asyncio
async def test_get_rude_artists(spotify_client, github_client, httpx_mock):
    image_url = "https://some-image-url.com"
    html_response = f"""
    <html>
        <body>
            <div class="cb-article-meta">
                <h2>
                    <a href="">RUNNING ORDER 2024</a>
                </h2>
            </div>
            <div class="cb-article-meta">
                <h2>
                    <a href="">Marduk (SWE)</a>
                </h2>
            </div>
            <div class="cb-article-meta">
                <h2>
                    <a href="">Deserted Fear (D)</a>
                </h2>
            </div>
            <div class="cb-article-meta">
                <h2>
                    <a href="">{artist_that_has_issue} (SWE)</a>
                </h2>
            </div>
        </body>
    </html>
    """
    httpx_mock.add_response(method="GET", url=rude_url, text=html_response)
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Marduk&market=DE",
        json=create_spotify_response(
            artist_id="RandomSpotifyId", artist_name="Marduk", image_url=image_url
        ),
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Deserted Fear&market=DE",
        json=create_spotify_response(artist_name="Deserted Fear"),
    )
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.spotify.com/v1/search?type=artist&limit=5&q={artist_that_has_issue}&market=DE",
        json=create_spotify_response(artist_name=artist_that_has_issue),
    )

    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        status_code=201,
    )

    artists = await get_rude_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artists == [
        ArtistInformation(id="RandomSpotifyId", name="Marduk", image_url=image_url),
    ]
    assert len(httpx_mock.get_requests()) == 7
    assert httpx_mock.get_requests()[2].url == rude_url


@pytest.mark.asyncio
async def test_get_rude_artists_uses_predefined_artist_names(
    spotify_client, github_client, httpx_mock
):
    image_url = "https://some-image-url.com"
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Marduk&market=DE",
        json=create_spotify_response(
            artist_id="RandomSpotifyId", artist_name="Marduk", image_url=image_url
        ),
    )
    httpx_mock.add_response(
        method="GET",
        url="https://api.spotify.com/v1/search?type=artist&limit=5&q=Deserted Fear&market=DE",
        json=create_spotify_response(artist_name="Deserted Fear"),
    )
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.spotify.com/v1/search?type=artist&limit=5&q={artist_that_has_issue}&market=DE",
        json=create_spotify_response(artist_name=artist_that_has_issue),
    )

    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues",
        status_code=201,
    )

    artists = await get_rude_artists(
        spotify_client=spotify_client,
        github_client=github_client,
        artists=["Marduk", "Deserted Fear", artist_that_has_issue],
    )

    assert artists == [
        ArtistInformation(id="RandomSpotifyId", name="Marduk", image_url=image_url),
    ]
    assert len(httpx_mock.get_requests()) == 6


@pytest.mark.asyncio
async def test_get_rude_artists_when_call_fails(
    spotify_client, github_client, httpx_mock
):
    httpx_mock.add_response(method="GET", url=rude_url, status_code=500)

    artists = await get_rude_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artists == []


@pytest.mark.asyncio
async def test_get_rude_artists_closes_opened_issues(
    spotify_client, github_client, httpx_mock
):
    image_url = "https://some-image-url.com"
    html_response = f"""
    <html>
        <body>
            <div class="cb-article-meta">
                <h2>
                    <a href="">{artist_that_has_issue} (SWE)</a>
                </h2>
            </div>
        </body>
    </html>
    """
    httpx_mock.add_response(method="GET", url=rude_url, text=html_response)
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.spotify.com/v1/search?type=artist&limit=5&q={artist_that_has_issue}&market=DE",
        json=create_spotify_response(
            artist_id="RandomSpotifyId",
            artist_name=artist_that_has_issue,
            image_url=image_url,
        ),
    )

    httpx_mock.add_response(
        method="PATCH",
        url="https://api.github.com/repos/kruspe/festival-scraper/issues/1",
        status_code=200,
    )

    artists = await get_rude_artists(
        spotify_client=spotify_client, github_client=github_client
    )

    assert artists == [
        ArtistInformation(
            id="RandomSpotifyId", name=artist_that_has_issue, image_url=image_url
        ),
    ]
    assert len(httpx_mock.get_requests()) == 5
    assert httpx_mock.get_requests()[4].method == "PATCH"
