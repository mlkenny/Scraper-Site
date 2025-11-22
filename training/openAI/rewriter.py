import json
from pathlib import Path
from openai import OpenAI
from django.conf import settings
'''
    The objective of this script is to allow an openai model to read my json quotes and create
    converational dialogue that the model will interpret as a speaking pattern. This speaking
    pattern should resemble roughly the character the quotes are from which will allow us
    to "talk" to the character.
'''
client = OpenAI(api_key=settings.OPENAI_KEY)

def rewrite_dataset(input_path: str, output_path: str = None) -> Path:
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path.with_name(f"{input_path.stem}_rewritten.jsonl")

    system_prompt = (
        "You rewrite scraped quote data into natural chat form. "
        "Keep the character's tone and remove all article or narration text. "
        "Make each assistant reply sound like real dialogue."
    )

    with open(input_path, "r", encoding="utf-8") as infile, \
         open(output_path, "w", encoding="utf-8") as outfile:
        for i, line in enumerate(infile, 1):
            data = json.loads(line)
            quote_text = " ".join(m["content"] for m in data["messages"])
            char_name = data["messages"][0]["content"].split(",")[0]
            prompt = f"Convert this into a realistic dialogue between a user and {char_name}:\n\n{quote_text}"

            try:
                resp = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=200,
                )
                rewritten = resp.choices[0].message.content.strip()
                new_entry = {
                    "messages": [
                        {"role": "system", "content": data["messages"][0]["content"]},
                        {"role": "user", "content": "Let's talk!"},
                        {"role": "assistant", "content": rewritten},
                    ]
                }
                outfile.write(json.dumps(new_entry, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"⚠️ Skipped line {i} ({e})")

    print(f"\n✅ Rewriting complete → {output_path}")
    return output_path
