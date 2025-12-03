from django.contrib import admin
from django.utils.html import format_html
from .models import TrainedModel
from analytics.admin import TrainingMetricsInline

@admin.register(TrainedModel)
class TrainedModelAdmin(admin.ModelAdmin):
    list_display = ("model_id", "training_status", "trained_on", "linked_character")
    readonly_fields = ("character", "trained_on", "updated_at")
    search_fields = ("model_id", "character__name")
    list_filter = ("training_status",)
    inlines = [TrainingMetricsInline]

    def linked_character(self, obj):
        if hasattr(obj, "character") and obj.character:
            return format_html(
                '<a href="/admin/scraper/character/{}/change/">{}</a>',
                obj.character.id,
                obj.character.name
            )
        return "No linked character"