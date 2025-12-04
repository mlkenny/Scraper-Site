from django.contrib import admin
from django.utils.html import format_html
from .models import Character
from analytics.admin import ScrapeMetricsInline

@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "linked_model", "dataset_path")
    inlines = [ScrapeMetricsInline]

    def linked_model(self, obj):
        if obj.model:
            return format_html(
                '<a href="/admin/training/trainedmodel/{}/change/">{}</a>',
                obj.model.id,
                obj.model.model_id
            )
        return "No trained model"