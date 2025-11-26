from django.db import models
from scraper.models import Character
from training.models import TrainedModel
from django.contrib.auth.models import User


# Create your models here.

class ChatSession(models.Model):
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name="chat_sessions", null=True)
    model = models.ForeignKey(TrainedModel, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.model.character.name if self.model.character else self.model.model_id}"
    
class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=10, choices=[('user', 'User'), ('model', 'Model')])
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.title()}: {self.text[:40]}"
