from django.db import models

# Create your models here.

class Character(models.Model):
    name = models.CharField(max_length=100, unique=True)
    dataset_path = models.CharField(max_length=255, null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name