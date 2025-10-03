import requests
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class Episode:
    season: int
    episode: int
    name: str
    link: str

@dataclass
class SeriesItem:
    name: str
    key: str
    poster: Optional[str]
    banner: Optional[str]
    year: Optional[int]
    description: Optional[str]
    info: Optional[str]
    rating: Optional[float]
    episodes: List[Episode]

class StreamFlixSeries:
    def __init__(self):
        self.main_url = "https://api.streamflix.app"
        self.config = None
        self.tv_urls = []

    def load_config(self):
        if not self.config:
            try:
                resp = requests.get(f"{self.main_url}/config/config-streamflixapp.json", timeout=15)
                self.config = resp.json()
                self.tv_urls = self.config.get("tv", [])
            except Exception as e:
                print(f"[!] Failed to fetch config: {e}")
                self.config = {"tv": ["https://example.com/fallback/"]}
                self.tv_urls = self.config["tv"]

    def get_series(self) -> List[SeriesItem]:
        series_list = []
        try:
            resp = requests.get(f"{self.main_url}/data.json", timeout=15)
            data = resp.json().get("data", [])
            for item in data:
                if item.get("isTV") and item.get("moviename"):
                    series_list.append(
                        SeriesItem(
                            name=item["moviename"],
                            key=item["moviekey"],
                            poster=item.get("movieposter"),
                            banner=item.get("moviebanner"),
                            year=int(item["movieyear"]) if item.get("movieyear") else None,
                            description=item.get("moviedesc"),
                            info=item.get("movieinfo"),
                            rating=item.get("movierating"),
                            episodes=[]
                        )
                    )
        except Exception as e:
            print(f"[!] Failed to fetch series data: {e}")
        return series_list

    def generate_episode_links(self, series: SeriesItem, seasons: int = 2, episodes_per_season: int = 6):
        """
        Generate real episode links using TV base URLs from config.json.
        """
        episodes = []
        for season in range(1, seasons + 1):
            for ep in range(1, episodes_per_season + 1):
                for base_url in self.tv_urls:
                    url = f"{base_url.rstrip('/')}/tv/{series.key}/s{season}/episode{ep}.mkv"
                    episodes.append(Episode(
                        season=season,
                        episode=ep,
                        name=f"Episode {ep}",
                        link=url
                    ))
        series.episodes = episodes

# --- Example Usage ---
if __name__ == "__main__":
    sf = StreamFlixSeries()
    sf.load_config()
    series_list = sf.get_series()

    for s in series_list[:3]:  # first 3 series for demo
        print(f"Series: {s.name} ({s.year})")
        sf.generate_episode_links(s, seasons=3, episodes_per_season=5)  # adjust seasons/episodes
        for ep in s.episodes[:5]:  # first 5 episodes
            print(f" S{ep.season}E{ep.episode}: {ep.name} -> {ep.link}")
        print("-" * 50)
