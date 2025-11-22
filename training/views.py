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
        event_type = payload.get("type")
        data = payload.get("data", {})
        job_id = data.get("id")
        status = data.get("status") or event_type.split(".")[-1]
        model_name = data.get("fine_tuned_model")

        print(f"📩 Webhook event={event_type} job_id={job_id} status={status}")

        print(f"🔎 Incoming job_id from webhook: {job_id!r}")
        print(f"📦 Existing job_ids in DB:", list(TrainedModel.objects.values_list("job_id", flat=True)))
        trained = TrainedModel.objects.filter(job_id=job_id).select_related("character").first()
        if not trained:
            print(f"⚠️ No TrainedModel found for job_id={job_id}")
            return JsonResponse({"warning": "No TrainedModel found"}, status=404)

        trained.training_status = status

        if status == "succeeded" and model_name:
            trained.model_id = model_name
            print(f"🎉 Fine-tuned model linked: {model_name}")

            if trained.character:
                trained.character.model = trained
                trained.character.save(update_fields=["model"])
                print(f"🔗 Linked character {trained.character.name} to model {model_name}")

            sessions = ChatSession.objects.filter(model__isnull=True, character=trained.character)
            for session in sessions:
                session.model = model_name
                session.save(update_fields=["model"])
                print(f"💬 Linked chat session {session.id} to model {model_name}")

        trained.save(update_fields=["training_status", "model_id"])
        print(f"✅ Updated TrainedModel {trained.id}: {status}")

        return JsonResponse({"success": True})

    except Exception as e:
        print("❌ Webhook error:", e)
        return JsonResponse({"error": str(e)}, status=400)