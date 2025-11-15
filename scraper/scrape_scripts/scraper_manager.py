from . import scraper as sc

import time
from pathlib import Path

from django.conf import settings

class ScraperManager:
    def __init__(self, character_name):
        self.character_name = character_name.strip()

    def scrape(self):
        urls = sc.discover_urls(self.character_name, max_urls=12)

        ''' Parallel Scraping '''
        t0 = time.time()
        quotes = sc.scrape_many(urls, character=self.character_name,
                            max_workers=8,
                            use_browser_fallback=False)
        t1 = time.time()
        scrape_time = t1 - t0

        ''' Remove Duplicate Quotes '''
        uniq = sc.dedupe(quotes)

        ''' Save Quote Dataset '''
        base_dir = Path(__file__).resolve().parent.parent
        file_path = base_dir / "test_output" / f"{self.character_name}.csv"
        sc.save_csv(uniq, file_path)

        return scrape_time
