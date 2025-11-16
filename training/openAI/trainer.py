import csv
import json
import tempfile

from pathlib import Path
from openai import OpenAI

from django.conf import settings

# Initialize client (reads key from OPENAI_API_KEY env variable)
client = OpenAI(api_key=settings.OPENAI_KEY)

def csv_to_jsonl(csv_path: str) -> Path:
    """
    Convert a CSV file of quotes into a JSONL file suitable for fine-tuning.
    Each row becomes a mini chat example.
    """
    csv_path = Path(csv_path)
    jsonl_path = Path(tempfile.gettempdir()) / f"{csv_path.stem}.jsonl"

    with open(csv_path, "r", encoding="utf-8") as csvfile, open(jsonl_path, "w", encoding="utf-8") as jsonlfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            quote = row.get("quote", "").strip()
            if not quote:
                continue
            # Each line is a chat training example
            data = {
                "messages": [
                    {"role": "system", "content": "You are a helpful AI assistant that speaks like a specific anime character."},
                    {"role": "user", "content": "Say something in the tone of how the character would speak."},
                    {"role": "assistant", "content": quote}
                ]
            }
            jsonlfile.write(json.dumps(data) + "\n")

    return jsonl_path

def train(csv_path: str, character_name: str):
    """
    Fine-tune gpt-3.5-turbo using data from a CSV file.
    """

    jsonl_path = csv_to_jsonl(csv_path)

    file_obj = client.files.create(file=open(jsonl_path, "rb"), purpose="fine-tune")

    job = client.fine_tuning.jobs.create(
        training_file=file_obj.id,
        model="gpt-3.5-turbo",
        suffix=character_name.lower().replace(" ", "_")
    )

    return job