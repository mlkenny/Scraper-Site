from django.db import models

# Create your models here.

class Character(models.Model):
    name = models.CharField(max_length=100, unique=True)
    dataset_path = models.FilePathField(path="scraper/datasets/", null=True, blank=True)
    model_id = models.CharField(max_length=255, null=True, blank=True)  # fine-tuned model ID
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name