from django.shortcuts import get_object_or_404, redirect, render

from scraper.models import Character

# Create your views here.

def character_select(request):
    # Load all characters and their linked model efficiently
    characters = Character.objects.all().select_related("model")
    return render(request, "character_select.html", {"characters": characters})

def delete_character(request, name):
    character = get_object_or_404(Character, name=name)
    character.delete()
    return redirect('character_select')