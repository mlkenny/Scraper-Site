from django.db import models

# Create your models here.

class Character(models.Model):
    name = models.CharField(max_length=100, unique=True)
    dataset_path = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    model = models.OneToOneField(
        'training.TrainedModel',
        on_delete=models.CASCADE,
        related_name='character',
        null=True,
        blank=True
    )

    def __str__(self):
        return self.name