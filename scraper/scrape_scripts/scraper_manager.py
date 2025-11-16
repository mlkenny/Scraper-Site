from . import scraper as sc

import time
import csv
from pathlib import Path

from scraper.models import Character
from django.conf import settings

class ScraperManager:
    def __init__(self, character_name):
        self.character_name = character_name.strip()

    def create_character_model(self, character_name, file_path):
        # Create the Character Object
        Character.objects.get_or_create(name=character_name, dataset_path=str(file_path))

    def scrape(self):
        ''' Start Scrape Timer '''
        t0 = time.time()
        urls = sc.discover_urls(self.character_name, max_urls=12)

        ''' Parallel Scraping '''
        quotes = sc.scrape_many(urls, character=self.character_name,
                            max_workers=8,
                            use_browser_fallback=False)

        ''' Remove Duplicate Quotes '''
        uniq = sc.dedupe(quotes)

        ''' Save Quote Dataset '''
        base_dir = Path(__file__).resolve().parent.parent
        file_path = base_dir / "datasets" / f"{self.character_name}.csv"
        sc.save_csv(uniq, file_path)

        ''' Create Character Model in DB '''
        self.create_character_model(self.character_name, file_path)

        ''' Stop Scrape Timer '''
        t1 = time.time()
        scrape_time = t1 - t0

        return scrape_time