from django.shortcuts import redirect, render

from scraper.models import Character
from scraper.scrape_scripts.scraper_manager import ScraperManager

# Create your views here.

def scrape_character(request):
    if request.method == "POST":
        character_name = request.POST.get("character")

        manager = ScraperManager(character_name=character_name)
        scrape_time = manager.scrape()

        # Fetch character instance AFTER scraping created it
        character = Character.objects.select_related("scrape_metrics").get(name__iexact=character_name)
        quotes = character.scraped_quotes.all()

        return render(request, "scrape_results.html", {
            "character": character,
            "scrape_time": scrape_time,
            "quotes": quotes,
            "metrics": character.scrape_metrics,
        })
    
    # GET request fallback
    return render(request, "scrape_results.html")
