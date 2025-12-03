from . import scraper

import time
import csv
import requests
from pathlib import Path

from scraper.models import Character
from analytics.models import ScrapeMetrics
from django.conf import settings

class ScraperManager:
    def __init__(self, character_name):
        self.character_name = character_name.strip()

    def create_character_model(self, character_name, file_path):
        # 1. Create character FIRST
        character, _ = Character.objects.get_or_create(
            name=character_name,
            defaults={
                "dataset_path": str(file_path),
                "image_url": self.find_character_image(character_name)
            }
        )

        # Count before moderation
        with open(file_path, "r", encoding="utf-8") as f:
            num_of_lines = len([line for line in f if line.strip()])
        print(f"\n⏳ Cleaning dataset with openai moderation check for {num_of_lines} lines")
        # 2. Clean dataset (now character exists)
        csv_path, kept, removed = scraper.clean_dataset(file_path, character)
        
        print(f"\n⏳ Update new path to {str(csv_path)}")
        # 3. Update dataset path AFTER cleaning
        character.dataset_path = str(csv_path)
        character.save()

        return character, kept, removed


    def character_has_model(self, character_name):
        # Look up the character by name (case-insensitive)
        character = Character.objects.filter(name__iexact=character_name.strip()).first()

        # Return True only if the character exists AND has a related model
        if character and character.model is not None:
            return True
        else:
            return False
    
    def find_character_image(self, character_name):
        """
        Fetch the first image for a given anime character name using the Jikan API.
        Returns the image URL or None if not found.
        """
        try:
            resp = requests.get(
                f"https://api.jikan.moe/v4/characters",
                params={"q": character_name, "limit": 1}
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("data"):
                return data["data"][0]["images"]["jpg"]["image_url"]
        except Exception as e:
            print(f"⚠️ Failed to fetch image for {character_name}: {e}")
        return None
    
    def scrape(self):
        ''' Check if Character has Model or not to Avoid Double Scraping '''
        if self.character_has_model(self.character_name):
            print(f"🛑 Character Has Existing Model")
            return None
        
        ''' Check If Dataset Exists to Avoid Double Scraping '''
        base_dir = Path(__file__).resolve().parent.parent
        csv_path = base_dir / "datasets" / f"{self.character_name}.csv"
        if csv_path.exists() and not self.character_has_model(self.character_name):
            print(f"🛑 Character Has Existing CSV File")
            self.create_character_model(self.character_name, csv_path)
            return -1
        
        print(f"\n⏳ Starting dynamic google scrape for: {self.character_name}")
        
        ''' Start Scrape Timer '''
        t0 = time.time()

        urls = scraper.discover_urls(self.character_name, max_urls=12)

        print(f"\n⏳ Parallel scraping {min(len(urls), 12)} urls")

        ''' Parallel Scraping '''
        quotes = scraper.scrape_many(
            urls,
            character=self.character_name,
            max_workers=8,
            use_browser_fallback=False
        )

        print(f"\n⏳ Removing duplicate quotes")

        ''' Remove Duplicate Quotes '''
        uniq = scraper.dedupe(quotes)

        ''' Save Quote Dataset '''
        base_dir = Path(__file__).resolve().parent.parent
        file_path = base_dir / "datasets" / f"{self.character_name}.csv"
        print(f"\n⏳ Saving quotes to: {file_path}")
        scraper.save_csv(uniq, file_path)

        ''' Create Character Model in DB '''
        print(f"\n⏳ Creating character model in DB")
        character, kept, removed = self.create_character_model(self.character_name, file_path)

        ''' Stop Scrape Timer '''
        t1 = time.time()
        scrape_time = t1 - t0

        print(f"\n✅ Saving metrics for {character.name} scraping")

        metrics, _ = ScrapeMetrics.objects.get_or_create(character=character)

        metrics.total_urls_discovered = len(urls)
        metrics.unsafe_quotes_extracted = removed
        metrics.safe_quotes_extracted = kept
        metrics.unique_quotes = len(uniq)
        metrics.scrape_duration = round(scrape_time, 2)

        metrics.save()

        print(f"✅ Dynamic scrape completed for: {character.name} in {scrape_time}ms")

        return scrape_time