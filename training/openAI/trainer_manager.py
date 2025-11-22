from scraper.models import Character
from training.models import TrainedModel
from . import trainer

class TrainerManager:
    def __init__(self, character):
        self.character = character

    def train_model(self):
        csv_path = self.character.dataset_path
        character_name = self.character.name

        existing_character = Character.objects.filter(
            name__iexact=character_name,
            model__isnull=False
        ).first()
        if existing_character:
            return None
        
        job = trainer.train(csv_path, character_name)

        trained_model  = self.create_trained_model(job)

        trained_model.character = self.character
        trained_model.save()

        return trained_model
    
    def create_trained_model(self, job):
        # Create the TrainedModel Object
        trained_model, created = TrainedModel.objects.get_or_create(
            job_id=job.id,
            defaults={
                "training_status": job.status,
                "notes": f"{job.model} trained on {self.character.name} quotes."
            }
        )
        if not created:
            trained_model.training_status = job.status
            trained_model.notes = f"{job.model} re-trained on {self.character.name} quotes."
            trained_model.save()

        return trained_model 