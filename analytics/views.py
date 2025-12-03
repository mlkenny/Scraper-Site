from django.shortcuts import get_object_or_404, render

from scraper.models import Character
from training.models import TrainedModel

# Create your views here.
def scrape_results(request, character_name):
    # Fetch character
    character = get_object_or_404(Character, name__iexact=character_name)

    # Fetch quotes
    quotes = character.scraped_quotes.all().order_by('-timestamp')

    # Fetch metrics (OneToOne)
    metrics = getattr(character, "scrape_metrics", None)

    return render(request, "scrape_results.html", {
        "character": character,
        "quotes": quotes,
        "metrics": metrics,
    })

def train_results(request, model_id):
    trained_model = get_object_or_404(TrainedModel, id=model_id)

    character_name = request.GET.get("character")
    character = None
    if character_name:
        character = Character.objects.filter(name__iexact=character_name).first()

    return render(request, "train_results.html", {
        "model": trained_model,
        "character": character,
        "metrics": getattr(trained_model, "metrics", None)
    })