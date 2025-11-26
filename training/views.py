import json
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from scraper.models import Character
from chat.models import ChatSession

from training.models import TrainedModel
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

@csrf_exempt
def openai_webhook(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
        event_type = payload.get("type", "")
        data = payload.get("data", {})

        # 🔍 Only handle fine-tune job events
        if not event_type.startswith("fine_tuning.job"):
            print(f"🔕 Ignored non fine-tuning event: {event_type}")
            return JsonResponse({"ignored": True})

        # 🔍 Fine-tune events always wrap the job in data.object
        obj = data.get("object", {})

        job_id = obj.get("id")
        status = obj.get("status")
        model_name = obj.get("fine_tuned_model")
        metadata = obj.get("metadata", {})
        character_name = metadata.get("character") or metadata.get("character_name")

        print("\n===== FINE-TUNE WEBHOOK =====")
        print("Event Type:", event_type)
        print("Job ID:", job_id)
        print("Status:", status)
        print("Model Returned:", model_name)
        print("Metadata:", metadata)
        print("==============================\n")

        # 🔍 Validate job_id
        if not job_id:
            print("❌ Webhook missing job_id (data.object.id)")
            return JsonResponse({"error": "Missing job_id"}, status=400)

        # 🔍 Find TrainedModel by job_id
        trained = TrainedModel.objects.filter(job_id=job_id).select_related("character").first()

        if not trained:
            print(f"⚠️ No TrainedModel found for job_id={job_id}")
            return JsonResponse({"warning": "No TrainedModel found"}, status=404)

        # Update training status always
        trained.training_status = status

        # Handle success state
        if status == "succeeded" and model_name:
            trained.model_id = model_name
            print(f"🎉 Fine-tuned model linked: {model_name}")

            # Link chat sessions that were waiting
            sessions = ChatSession.objects.filter(
                model__isnull=True,
                character=trained.character
            )

            for session in sessions:
                session.model = trained  # assign FK properly
                session.save(update_fields=["model"])
                print(f"💬 Session {session.id} linked to trained model")

        # Save trained model
        trained.save(update_fields=["training_status", "model_id"])

        print(f"✅ Trained model saved for character={character_name} job_id={job_id}")
        return JsonResponse({"success": True})

    except Exception as e:
        print("❌ Webhook error:", e)
        return JsonResponse({"error": str(e)}, status=400)
