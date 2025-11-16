from django.db import models

# Create your models here.

class TrainedModel(models.Model):
    model_id = models.CharField(max_length=255, unique=True)
    training_status = models.CharField(max_length=50, default='pending')
    trained_on = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.model_id}"