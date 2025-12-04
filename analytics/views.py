from django.shortcuts import get_object_or_404, render

from analytics.models import RewrittenQuote
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

    character = trained_model.character

    rewritten_quotes = RewrittenQuote.objects.filter(
        trained_model=trained_model
    ).order_by('-created_at')

    length_short = 0
    length_medium = 0
    length_long = 0

    for rq in rewritten_quotes:
        text = rq.original_quote or ""
        l = len(text)
        if l < 50:
            length_short += 1
        elif l < 120:
            length_medium += 1
        else:
            length_long += 1

    return render(request, "train_results.html", {
        "model": trained_model,
        "character": character,
        "metrics": getattr(trained_model, "metrics", None),
        "rewritten_quotes": rewritten_quotes,
        "length_short": length_short,
        "length_medium": length_medium,
        "length_long": length_long,
    })
