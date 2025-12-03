from django.contrib import admin
from analytics.models import ScrapeMetrics, TrainingMetrics
from scraper.models import Character
from training.models import TrainedModel

class ScrapeMetricsInline(admin.StackedInline):
    model = ScrapeMetrics
    can_delete = False
    extra = 0

    readonly_fields = (
        "total_urls_discovered",
        "unsafe_quotes_extracted",
        "safe_quotes_extracted",
        "unique_quotes",
        "scrape_duration",
        "timestamp",
    )


class TrainingMetricsInline(admin.StackedInline):
    model = TrainingMetrics
    can_delete = False
    extra = 0

    readonly_fields = (
        "total_quotes_used",
        "quotes_removed",
        "dataset_size_kb",
        "fine_tune_start",
        "fine_tune_end",
        "duration_minutes",
        "job_status",
        "final_model_name",
    )
