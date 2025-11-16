from . import scraper

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

    def character_has_model(self, character_name):
        # Look up the character by name (case-insensitive)
        character = Character.objects.filter(name__iexact=character_name.strip()).first()

        # Return True only if the character exists AND has a related model
        if character and character.model is not None:
            return True
        else:
            return False

    def scrape(self):
        ''' Check If Dataset Exists to Avoid Double Scraping '''
        ''' Check if Character has Model or not to Avoid Double Scraping '''
        base_dir = Path(__file__).resolve().parent.parent
        csv_path = base_dir / "datasets" / f"{self.character_name}.csv"
        if csv_path.exists() or self.character_has_model(self.character_name):
            return None

        ''' Start Scrape Timer '''
        t0 = time.time()
        urls = scraper.discover_urls(self.character_name, max_urls=12)

        ''' Parallel Scraping '''
        quotes = scraper.scrape_many(
            urls,
            character=self.character_name,
            max_workers=8,
            use_browser_fallback=False
        )

        ''' Remove Duplicate Quotes '''
        uniq = scraper.dedupe(quotes)

        ''' Save Quote Dataset '''
        base_dir = Path(__file__).resolve().parent.parent
        file_path = base_dir / "datasets" / f"{self.character_name}.csv"
        scraper.save_csv(uniq, file_path)

        ''' Create Character Model in DB '''
        self.create_character_model(self.character_name, file_path)

        ''' Stop Scrape Timer '''
        t1 = time.time()
        scrape_time = t1 - t0

        return scrape_time