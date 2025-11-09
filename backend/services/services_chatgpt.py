from openai import OpenAI
from utils import getSecret
from dotenv import load_dotenv
import time
import json
from config import batch_size, gptModel
from concurrent.futures import ThreadPoolExecutor, as_completed
import itertools

load_dotenv()

client = OpenAI(api_key=getSecret('GPT_KEY'))

counter = itertools.count(1)  # compteur global

def process_batch(preprompt, description, batch, batch_index, number_of_batches):
    prompt = f"Description: {description}\nSongs:\n"
    for info in batch:
        prompt += f"- ID: {info['id']}, Title: {info['title']}, Artist(s): {info['artists']}, Album: {info['album']}\n"

    retries = 5
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=gptModel,
                messages=[
                    {"role": "system", "content": preprompt},
                    {"role": "user", "content": prompt},
                ]
            )
            break
        except Exception as e:
            if "rate_limit" in str(e).lower():
                delay = 2 ** attempt
                print(f"Rate limit reached. Waiting {delay}s before retry...")
                time.sleep(delay)
            elif attempt < retries - 1:
                print(f"API error: {e}. Retrying ({attempt+1}/{retries})...")
                time.sleep(1)
            else:
                raise

    text_result = response.choices[0].message.content
    batch_result = json.loads(text_result)

    batch_number = next(counter)
    print(f"✅ Processed batch {batch_number}/{number_of_batches}")
    
    return batch_result

def decisionHandler_parallel(description, musicInfos, max_workers=3):
    global counter
    counter = itertools.count(1)

    preprompt = """
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

        If you are not familiar with a song do not try to guess, just say it does not match.

        Your answer must be in **JSON format EXACTLY** as follows:
        [
        {"id": "id1", "title": "title1", "match": "10"},
        {"id": "id2", "title": "title1", "match": "7"},
        ...
        ]

        Do not include any explanations, extra text, or commentary — only the JSON array.
    """

    batches = [musicInfos[i:i+batch_size] for i in range(0, len(musicInfos), batch_size)]
    number_of_batches = len(batches)

    all_results = []

    # parallélisation
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_batch, preprompt, description, batch, i+1, number_of_batches)
            for i, batch in enumerate(batches)
        ]

        for future in as_completed(futures):
            batch_result = future.result()
            all_results.extend(batch_result)

    return all_results