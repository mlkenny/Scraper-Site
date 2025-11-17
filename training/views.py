from django.shortcuts import redirect, render

from scraper.models import Character

from training.openAI.trainer_manager import TrainerManager

# Create your views here.

def train_model(request):
    character_name = request.GET.get("character")
    try:
        character = Character.objects.get(name=character_name)

        if hasattr(character, "model"):
            model = character.model
        else:
            manager = TrainerManager(character)
            model = manager.train_model()

        return render(request, "model.html", {
            "character": character,
        })

    except Character.DoesNotExist:
        print(f"No character found with the name: {character_name}")
        return redirect("scrape_character")