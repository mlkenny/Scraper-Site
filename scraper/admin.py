from django.contrib import admin
from django.utils.html import format_html
from .models import Character

# Register your models here.

@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "linked_model", "dataset_path")

    def linked_model(self, obj):
        if obj.model:
            # Creates a clickable link to the TrainedModel admin page
            return format_html(
                '<a href="/admin/training/trainedmodel/{}/change/">{}</a>',
                obj.model.id,
                obj.model.model_id
            )
        return "No trained model"
    linked_model.short_description = "Model"