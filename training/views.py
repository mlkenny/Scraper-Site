import json
from django.utils import timezone
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from openai import InvalidWebhookSignatureError, OpenAI

from analytics.models import RewrittenQuote
from scraper.models import Character
from chat.models import ChatSession

from training.models import TrainedModel
from training.openAI.trainer_manager import TrainerManager

# Create your views here.

def train_model(request):
    character_name = request.GET.get("character")

    try:
        character = Character.objects.get(name=character_name)

        # Always run training (same structure, just cleaned)
        manager = TrainerManager(character)
        model, metrics = manager.train_model()

        # NEW: rewritten quotes must always come from DB
        rewritten_quotes = RewrittenQuote.objects.filter(
            character=character
        ).order_by('-created_at')

        return render(request, "model.html", {
            "character": character,
            "model": model,
            "metrics": metrics,
            "rewritten_quotes": rewritten_quotes,
        })

    except Character.DoesNotExist:
        print(f"No character found with the name: {character_name}")
        return redirect("character_select")

client = OpenAI(
    api_key=settings.OPENAI_KEY,
    webhook_secret=settings.OPENAI_WEBHOOK_SECRET,
)

@csrf_exempt
def openai_webhook(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        # 1. Unwrap & verify signature
        event = client.webhooks.unwrap(request.body, request.headers)

        print("\n===== RAW UNWRAPPED EVENT =====")
        print(event)  # prints structured object
        print("================================\n")

        # Ignore non fine-tune events
        if not event.type.startswith("fine_tuning.job"):
            print(f"🔕 Ignored non fine-tuning event: {event.type}")
            return JsonResponse({"ignored": True})

        # 2. Event.data is a Data object, not a dict
        job_id = event.data.id
        print(f"Fine-tune job ID extracted: {job_id}")

        # 3. Fetch full job details from API
        job = client.fine_tuning.jobs.retrieve(job_id)

        print("\n===== FULL FINE-TUNE JOB OBJECT =====")
        print(job)
        print("=====================================\n")

        status = job.status
        model_name = job.fine_tuned_model
        metadata = job.metadata or {}

        character_name = (
            metadata.get("character") or
            metadata.get("character_name")
        )

        print("Status:", status)
        print("Model Name:", model_name)
        print("Metadata:", metadata)
        print("Character Name:", character_name)

        # 4. Find the TrainedModel from DB
        trained = TrainedModel.objects.filter(job_id=job_id).select_related("character").first()
        if not trained:
            print(f"⚠️ No TrainedModel found for job_id={job_id}")
            return JsonResponse({"warning": "Not found"}, status=404)

        trained.training_status = status

        # Save to training metrics
        metrics = trained.metrics
        metrics.job_status = status

        if status == "succeeded":
            metrics.final_model_name = model_name

        metrics.fine_tune_end = timezone.now()
        metrics.duration_minutes = (
            (metrics.fine_tune_end - metrics.fine_tune_start).total_seconds() / 60
        )

        metrics.save()

        # 5. Update model_id on success
        if status == "succeeded":
            trained.model_id = model_name
            print(f"🎉 Linked model_id: {model_name}")

            # Link chat sessions that were waiting
            sessions = ChatSession.objects.filter(
                model__isnull=True,
                character=trained.character
            )
            for session in sessions:
                session.model = trained
                session.save(update_fields=["model"])
                print(f"💬 Linked ChatSession {session.id}")

        trained.save(update_fields=["training_status", "model_id"])

        print(f"✅ Updated TrainedModel for {character_name} ({job_id})")

        return JsonResponse({"success": True})

    except InvalidWebhookSignatureError:
        print("❌ Invalid webhook signature")
        return JsonResponse({"error": "Invalid signature"}, status=400)

    except Exception as e:
        print("❌ Webhook error:", e)
        return JsonResponse({"error": str(e)}, status=500)