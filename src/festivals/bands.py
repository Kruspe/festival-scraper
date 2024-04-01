import httpx
from bs4 import BeautifulSoup


def get_wacken_artists():
    artist_names = []
    response = httpx.get("https://www.wacken.com/fileadmin/Json/bandlist-concert.json")

    if response.status_code == 200:
        artists = response.json()
        for artist in artists:
            if (
                artist["artist"]["title"] != "Metal Disco"
                and artist["artist"]["title"] != "Metal Yoga"
            ):
                artist_names.append(artist["artist"]["title"])
    return artist_names


def get_dong_artists():
    artist_names = []
    response = httpx.get("https://www.dongopenair.de/de/bands/index")

    if response.status_code == 200:
        parsed_html = BeautifulSoup(response.text)
        artist_html_list = parsed_html.find_all("div", attrs={"class": "bandteaser"})
        for element in artist_html_list:
            artist_names.append(element.find_next("a").text)

    return artist_names
