import responses

from src.festivals.bands import get_wacken_artists, get_dong_artists

wacken_url = "https://www.wacken.com/fileadmin/Json/bandlist-concert.json"
dong_url = "https://www.dongopenair.de/de/bands/index"


@responses.activate
def test_get_wacken_artists():
    bloodbath = {"artist": {"title": "Bloodbath"}}
    megadeth = {"artist": {"title": "Megadeth"}}
    vader = {"artist": {"title": "Vader"}}
    metal_disco = {"artist": {"title": "Metal Disco"}}
    metal_yoga = {"artist": {"title": "Metal Yoga"}}
    artists = [bloodbath, megadeth, vader, metal_disco, metal_yoga]
    expected_artist_names = [bloodbath["artist"]["title"], megadeth["artist"]["title"], vader["artist"]["title"]]

    responses.add(responses.GET, wacken_url, json=artists, status=200)

    artists = get_wacken_artists()

    assert artists == expected_artist_names
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == wacken_url


@responses.activate
def test_get_wacken_artists_when_call_fails():
    responses.add(responses.GET, wacken_url, status=500)

    artists = get_wacken_artists()

    assert artists == []
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == wacken_url


@responses.activate
def test_get_dong_artists():
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
    responses.add(responses.GET, dong_url, body=html_response)
    artists = get_dong_artists()

    assert artists == ["Bloodbath", "Dawn of Disease", "Hypocrisy", "Grave"]
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == dong_url


@responses.activate
def test_get_dong_artists_when_call_fails():
    responses.add(responses.GET, dong_url, status=500)

    artists = get_dong_artists()

    assert artists == []
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == dong_url
