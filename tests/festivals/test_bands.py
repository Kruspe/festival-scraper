from src.festivals.bands import get_wacken_artists, get_dong_artists, get_rude_artists

wacken_url = "https://www.wacken.com/fileadmin/Json/bandlist-concert.json"
dong_url = "https://www.dongopenair.de/de/bands/index"
rude_url = "https://www.rockunterdeneichen.de/bands/"


def test_get_wacken_artists(httpx_mock):
    bloodbath = {"artist": {"title": "Bloodbath"}}
    megadeth = {"artist": {"title": "Megadeth"}}
    vader = {"artist": {"title": "Vader"}}
    metal_disco = {"artist": {"title": "Metal Disco"}}
    metal_yoga = {"artist": {"title": "Metal Yoga"}}
    artists = [bloodbath, megadeth, vader, metal_disco, metal_yoga]
    expected_artist_names = [
        bloodbath["artist"]["title"],
        megadeth["artist"]["title"],
        vader["artist"]["title"],
    ]

    httpx_mock.add_response(method="GET", url=wacken_url, json=artists, status_code=200)

    artists = get_wacken_artists()

    assert artists == expected_artist_names
    assert len(httpx_mock.get_requests()) == 1
    assert httpx_mock.get_requests()[0].url == wacken_url


def test_get_wacken_artists_when_call_fails(httpx_mock):
    httpx_mock.add_response(method="GET", url=wacken_url, status_code=500)

    artists = get_wacken_artists()

    assert artists == []
    assert len(httpx_mock.get_requests()) == 1
    assert httpx_mock.get_requests()[0].url == wacken_url


def test_get_dong_artists(httpx_mock):
    html_response = """
    <html>
        <body>
            <h1>Some Headline</h1>
            <div>Any Text Here</div>
            <div class="headline">alle bisherigen Bands für das D.O.A 2024>
                <div class="bandteaser">
                    <p> <span class="headline"><a href="">Bloodbath</a></span></p>
                </div>
                <div class="bandteaser">
                    <p> <span class="headline"><a href="">Dawn of Disease</a></span></p>
                </div>
                <div class="bandteaser">
                    <p> <span class="headline"><a href="">Hypocrisy</a></span></p>
                </div>
                <div class="bandteaser">
                    <p> <span class="headline"><a href="">Grave</a></span></p>
                </div>
            </div> 
        </body>
    </html>
    """
    httpx_mock.add_response(method="GET", url=dong_url, text=html_response)
    artists = get_dong_artists()

    assert artists == ["Bloodbath", "Dawn of Disease", "Hypocrisy", "Grave"]
    assert len(httpx_mock.get_requests()) == 1
    assert httpx_mock.get_requests()[0].url == dong_url


def test_get_dong_artists_when_call_fails(httpx_mock):
    httpx_mock.add_response(method="GET", url=dong_url, status_code=500)

    artists = get_dong_artists()

    assert artists == []
    assert len(httpx_mock.get_requests()) == 1
    assert httpx_mock.get_requests()[0].url == dong_url


def test_get_rude_artists(httpx_mock):
    html_response = """
    <html>
        <body>
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
                    <a href="">Legion of the Damned (NL)</a>
                </h2>
            </div>
        </body>
    </html>
    """
    httpx_mock.add_response(method="GET", url=rude_url, text=html_response)
    artists = get_rude_artists()

    assert artists == ["Marduk", "Deserted Fear", "Legion of the Damned"]
    assert len(httpx_mock.get_requests()) == 1
    assert httpx_mock.get_requests()[0].url == rude_url


def test_get_rude_artists_when_call_fails(httpx_mock):
    httpx_mock.add_response(method="GET", url=rude_url, status_code=500)

    artists = get_rude_artists()

    assert artists == []
    assert len(httpx_mock.get_requests()) == 1
    assert httpx_mock.get_requests()[0].url == rude_url
