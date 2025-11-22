from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from training.models import TrainedModel
from .models import ChatSession, ChatMessage
from openai import OpenAI
import os

client = OpenAI(api_key=settings.OPENAI_KEY)

def start_chat(request, model_id):
    model = get_object_or_404(TrainedModel, id=model_id)
    character = model.character

    if not request.session.session_key:
        request.session.create()

    chat_session, created = ChatSession.objects.get_or_create(
        character=character,
        session_key=request.session.session_key,
        defaults={"model": model}
    )

    return redirect('chat_window', session_id=chat_session.id)


def chat_window(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id)

    if session.session_key != request.session.session_key:
        return HttpResponseForbidden("This chat session is not yours.")

    messages = session.messages.all().order_by('timestamp')
    return render(request, 'chat_window.html', {'session': session, 'messages': messages})


def send_message(request, session_id):
    if request.method == 'POST':
        session = get_object_or_404(ChatSession, id=session_id)
        if session.session_key != request.session.session_key:
            return HttpResponseForbidden("This chat session is not yours.")

        user_input = request.POST.get('message')
        ChatMessage.objects.create(session=session, sender='user', text=user_input)

        model_name = _resolve_model_name(session.model.model_id)

        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": f"You are {session.character.name}."},
                {"role": "user", "content": user_input},
            ],
        )
        reply = resp.choices[0].message.content.strip()

        ChatMessage.objects.create(session=session, sender='model', text=reply)
        return JsonResponse({'reply': reply})

@require_POST
def clear_chat(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id)
    if session.session_key != request.session.session_key:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    # Delete all messages for this session
    ChatMessage.objects.filter(session=session).delete()
    return JsonResponse({'success': True})

def _resolve_model_name(model_ref):
    """
    Accepts either a TrainedModel instance or a model_id string
    and returns the usable fine-tuned model name.
    """
    # If we were given a TrainedModel object
    if hasattr(model_ref, "model_id"):
        mid = model_ref.model_id
    else:
        mid = model_ref  # it's already a string

    if not mid:
        raise ValueError("No model reference provided.")

    # Handle job IDs (ftjob-) by retrieving the completed model if necessary
    if mid.startswith("ftjob-"):
        job = client.fine_tuning.jobs.retrieve(mid)
        if job.status == "succeeded" and job.fine_tuned_model:
            return job.fine_tuned_model
        raise ValueError(f"Model {mid} not ready (status={job.status})")

    return mid