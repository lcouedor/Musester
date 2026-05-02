from openai import OpenAI
from utils import getSecret
from dotenv import load_dotenv
import time
import json
from config import batch_size, gpt_model, max_workers
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

client = OpenAI(api_key=getSecret('GPT_KEY'))

PREPROMPT = """
You are a music classification assistant.

You will receive:
- A textual description of a musical mood, theme, or intent.
- A list of songs, each with an ID, title, and artist(s).

Your task:
For each song, decide if it matches the given description by affecting a % of matching to the given description.

You can rely on:
- The song title
- The artist(s) and their general musical style
- The lyrics (if you know them)
- The album or any other reliable musical information you know

You must be as accurate as possible.
If you are not familiar with a song, do not try to guess — return match: "0".

Your answer must be in **JSON format EXACTLY** as follows:
[
{"id": "id1", "title": "title1", "match": "10"},
{"id": "id2", "title": "title2", "match": "7"},
...
]

Do not include any explanations, extra text, or commentary — only the JSON array.
"""


def _build_prompt(description: str, batch: list) -> str:
    lines = "\n".join(
        f"- ID: {t['id']}, Title: {t['title']}, Artist(s): {t['artists']}, Album: {t['album']}"
        for t in batch
    )
    return f"Description: {description}\nSongs:\n{lines}"


def _process_batch(description: str, batch: list, batch_index: int, total: int) -> list:
    prompt = _build_prompt(description, batch)
    retries = 5

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=gpt_model,
                messages=[
                    {"role": "system", "content": PREPROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            result = json.loads(response.choices[0].message.content)
            print(f"✅ Batch {batch_index}/{total}")
            return result
        except json.JSONDecodeError as e:
            print(f"JSON parse error on batch {batch_index}: {e}")
            if attempt == retries - 1:
                raise
            time.sleep(1)
        except Exception as e:
            if "rate_limit" in str(e).lower():
                delay = 2 ** attempt
                print(f"Rate limit. Retry in {delay}s…")
                time.sleep(delay)
            elif attempt < retries - 1:
                print(f"API error: {e}. Retry {attempt + 1}/{retries}…")
                time.sleep(1)
            else:
                raise

    return []


def decision_handler_parallel(description: str, music_infos: list) -> list:
    batches = [music_infos[i:i + batch_size] for i in range(0, len(music_infos), batch_size)]
    total = len(batches)
    all_results = [None] * total

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_batch, description, batch, i + 1, total): i
            for i, batch in enumerate(batches)
        }
        for future in as_completed(futures):
            idx = futures[future]
            all_results[idx] = future.result()

    # Aplatir en préservant l'ordre
    return [item for batch in all_results if batch for item in batch]
