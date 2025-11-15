from django.shortcuts import render

from scraper.scrape_scripts.scraper_manager import ScraperManager

# Create your views here.

def train_character(request):
    if request.method == "POST":
        character_name = request.POST.get("character")
        manager = ScraperManager(character_name=character_name)
        time_taken = manager.scrape()

    return render(request, 'train_results.html', {
        "character": character_name,
        "train_time" : time_taken,
    })