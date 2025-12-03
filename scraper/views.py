from django.shortcuts import redirect, render

from scraper.models import Character
from scraper.scrape_scripts.scraper_manager import ScraperManager

# Create your views here.

def scrape_character(request):
    if request.method == "POST":
        character_name = request.POST.get("character")

        manager = ScraperManager(character_name=character_name)
        scrape_time = manager.scrape()

        character = Character.objects.get(name__iexact=character_name)
        
        quotes = character.scraped_quotes.all()

        metrics = getattr(character, "scrape_metrics", None)

        return render(request, "scrape_results.html", {
            "character": character,
            "quotes": quotes,
            "metrics": metrics,
            "scrape_time": scrape_time,
        })
