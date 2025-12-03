from django.db import models

# Create your models here.
class ScrapeMetrics(models.Model):
    character = models.OneToOneField("scraper.Character", on_delete=models.CASCADE, related_name="scrape_metrics")
    total_urls_discovered = models.IntegerField(default=0)
    unsafe_quotes_extracted = models.IntegerField(default=0)
    safe_quotes_extracted = models.IntegerField(default=0)
    unique_quotes = models.IntegerField(default=0)
    scrape_duration = models.FloatField(default=0.0)
    timestamp = models.DateTimeField(auto_now_add=True)

class ScrapedQuote(models.Model):
    character = models.ForeignKey("scraper.Character", on_delete=models.CASCADE, related_name="scraped_quotes")
    source_url = models.URLField()
    quote = models.TextField()

    is_safe = models.BooleanField(default=True)  # Passed moderation
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

class TrainingMetrics(models.Model):
    trained_model = models.OneToOneField("training.TrainedModel", on_delete=models.CASCADE, related_name="metrics")
    total_quotes_used = models.IntegerField(default=0)
    dataset_size_kb = models.FloatField(default=0.0)
    fine_tune_start = models.DateTimeField(null=True, blank=True)
    fine_tune_end = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.FloatField(default=0.0)
    job_status = models.CharField(max_length=50, default="pending")
    final_model_name = models.CharField(max_length=255, null=True, blank=True)