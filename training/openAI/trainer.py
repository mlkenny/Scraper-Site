import csv
import json
import random
import tempfile

from pathlib import Path
from openai import OpenAI

from django.conf import settings

from training.models import TrainedModel

from . import rewriter

APP_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = APP_DIR / "datasets"
DATASET_DIR.mkdir(exist_ok=True)

# Initialize client (reads key from OPENAI_API_KEY env variable)
client = OpenAI(api_key=settings.OPENAI_KEY)


def generate_user_prompt(character: str, quote: str) -> str:
    """
    Use GPT to generate a realistic user message that would lead
    to the given quote as a natural reply.
    """
    prompt = (
        f"Generate one short, natural user message that would make the following "
        f"quote a natural reply from {character}. "
        f"Keep it conversational and under 20 words.\n\nQuote: \"{quote}\""
    )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # or gpt-3.5-turbo if you prefer
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=50,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ Generation failed: {e}")
        return "What do you think about that?"
    
def csv_to_jsonl(csv_path: str, character_name: str) -> Path:
    """
    Convert a cleaned CSV file of quotes into a conversational JSONL file
    suitable for OpenAI chat fine-tuning.
    Each line becomes one training example.
    """
    csv_path = Path(csv_path)
    jsonl_path = Path(tempfile.gettempdir()) / f"{character_name.lower().replace(' ', '_')}_auto.jsonl"

    # Simple, generic user prompts to make conversations natural
    user_prompts = [
        "What would you say about that?",
        "Tell me something in your own words.",
        "Share your thoughts about life or adventure.",
        "What would you tell your friends?",
        "Say something that shows your spirit.",
        "How do you feel about challenges?",
        "What's something you live by?"
    ]

    with open(csv_path, "r", encoding="utf-8") as csvfile, \
         open(jsonl_path, "w", encoding="utf-8") as jsonlfile:

        reader = csv.DictReader(csvfile)
        for row in reader:
            quote = row.get("quote", "").strip()
            if not quote:
                continue

            # Pick a random generic user prompt
            user_prompt = random.choice(user_prompts)

            # Build a proper conversational message object
            data = {
                "messages": [
                    {
                        "role": "system",
                        "content": f"You are {character_name}, an anime character. "
                                   f"Respond naturally in your signature tone and style."
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    },
                    {
                        "role": "assistant",
                        "content": quote
                    }
                ]
            }

            jsonlfile.write(json.dumps(data, ensure_ascii=False) + "\n")

    print(f"✅ Generated conversational JSONL for {character_name}: {jsonl_path}")
    return jsonl_path

def moderation_check(jsonl_path: str, safe_jsonl: str):
    ''' MODERATION CHECK '''
    print(f"\n⏳ Performing OpenAI moderation check")

    with open(jsonl_path, "r", encoding="utf-8") as infile, \
         open(safe_jsonl, "w", encoding="utf-8") as outfile:
        for i, line in enumerate(infile, 1):
            data = json.loads(line)
            text = " ".join(m["content"] for m in data["messages"])
            result = client.moderations.create(
                model="omni-moderation-latest",
                input=text
            )
            if not result.results[0].flagged:
                outfile.write(line)
            else:
                cats = result.results[0].categories
                print(f"⚠️ Line {i} removed due to moderation flag:")
                print("   sexual:", cats.sexual, " sexual_minors:", cats.sexual_minors,
                    " violence:", cats.violence, "\n")
    # Create fine tuning job file.
    with open(safe_jsonl, "rb") as f:
        return client.files.create(file=f, purpose="fine-tune")

def train(csv_path: str, character_name: str):
    """
    Fine-tune gpt-3.5-turbo using data from a CSV file.
    """
    base_name = character_name.lower().replace(" ", "_")

    jsonl_path = DATASET_DIR / f"{base_name}_auto.jsonl"
    safe_jsonl = DATASET_DIR / f"{base_name}_auto_safe.jsonl"

    # ---- ALWAYS initialize metrics ----
    safe_count = 0
    rewritten_count = 0
    removed_count = 0
    dataset_size_kb = 0
    rewritten_preview = []

    # ---- CASE 1: Already has a safe dataset ----
    if safe_jsonl.exists():
        print(f"🛑 Character already has moderated dataset")
        print(f"🛑 Moderated dataset exists at {safe_jsonl}\n")

        # Count safe lines
        with open(safe_jsonl, "r", encoding="utf-8") as f:
            safe_lines = [line for line in f if line.strip()]
        safe_count = len(safe_lines)

        # In this case, rewritten_count == safe_count (we don't have the raw rewritten file)
        rewritten_count = safe_count
        removed_count = 0

        # Get size of safe jsonl
        dataset_size_kb = round(safe_jsonl.stat().st_size / 1024, 2)

        # Upload file
        file_obj = client.files.create(file=open(safe_jsonl, "rb"), purpose="fine-tune")

    else:
        # ---- CASE 2: Need to build + moderate dataset ----
        jsonl_path = csv_to_jsonl(csv_path, character_name)

        rewritten_jsonl = rewriter.rewrite_dataset(jsonl_path)
        

        # Count rewritten lines BEFORE moderation
        with open(rewritten_jsonl, "r", encoding="utf-8") as f:
            rewritten_lines = [line for line in f if line.strip()]
        rewritten_count = len(rewritten_lines)

        # Moderate → produce safe_jsonl
        file_obj = moderation_check(jsonl_path=rewritten_jsonl, safe_jsonl=safe_jsonl)

        # Collect rewritten quotes for preview

        with open(safe_jsonl, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                # Extract assistant reply (the rewritten quote)
                assistant_msg = next(m["content"] for m in data["messages"] if m["role"] == "assistant")
                rewritten_preview.append(assistant_msg)

        # Count safe lines AFTER moderation
        with open(safe_jsonl, "r", encoding="utf-8") as f:
            safe_lines = [line for line in f if line.strip()]
        safe_count = len(safe_lines)

        removed_count = rewritten_count - safe_count
        dataset_size_kb = round(Path(safe_jsonl).stat().st_size / 1024, 2)

    # ---- Same for both branches below ----

    job = client.fine_tuning.jobs.create(
        training_file=file_obj.id,
        model="gpt-3.5-turbo",
        suffix=character_name.lower().replace(" ", "_"),
        metadata={
            "character": character_name
        }
    )

    trained_model = TrainedModel.objects.filter(character__name__iexact=character_name).first()
    if trained_model:
        trained_model.job_id = job.id
        trained_model.training_status = job.status
        trained_model.save(update_fields=["job_id", "training_status"])

    return {
        "job": job,
        "total_quotes_used": safe_count,
        "quotes_removed": removed_count,
        "dataset_size_kb": dataset_size_kb,
        "rewritten_preview": rewritten_preview[:200],
    }