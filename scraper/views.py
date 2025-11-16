from django.shortcuts import redirect, render

from scraper.scrape_scripts.scraper_manager import ScraperManager

# Create your views here.

def scrape_character(request):
    if request.method == "POST":
        character_name = request.POST.get("character")
        manager = ScraperManager(character_name=character_name)
        time_taken = manager.scrape()

        return render(request, "scrape_results.html", {
            "character": character_name,
            "scrape_time": time_taken,
        })
    
    return render(request, "scrape_results.html")