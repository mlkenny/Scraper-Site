from django.shortcuts import redirect, render

from scraper.models import Character

from training.openAI.trainer_manager import TrainerManager

# Create your views here.

def train_model(request):
    character_name = request.GET.get("character")
    scrape_time = request.GET.get("scrape_time")
    try:
        character = Character.objects.get(name=character_name)

        if character.model is not None:
            model = character.model
        else:
            manager = TrainerManager(character)
            model = manager.train_model()
    
        context = {
            "character": character_name,
            "scrape_time": scrape_time,
            "model_id": model.id
        }

        return render(request, "model.html", context)

    except Character.DoesNotExist:
        print(f"No character found with the name: {character_name}")
        return redirect("scrape_character")