from openai import OpenAI
from utils import getSecret
from dotenv import load_dotenv
import time
import json
from config import batch_size

load_dotenv()

client = OpenAI(api_key=getSecret('GPT_KEY'))

def decisionHandler(description, musicInfos):
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

    number_of_batches = (len(musicInfos) + batch_size - 1) // batch_size

    all_results = []

    for i in range(0, len(musicInfos), batch_size):
        batch = musicInfos[i:i+batch_size]

        prompt = f"Description: {description}\nSongs:\n"
        for info in batch:
            prompt += f"- ID: {info['id']}, Title: {info['title']}, Artist(s): {info['artists']}, Album: {info['album']}\n"

        # retry simple
        retries = 3
        for attempt in range(retries):
            try:
                response = client.chat.completions.create(
                    model="chatgpt-4o-latest",
                    messages=[
                        {"role": "system", "content": preprompt},
                        {"role": "user", "content": prompt},
                    ]
                )
                break
            except Exception as e:
                if attempt < retries - 1:
                    print(f"API error: {e}. Retrying ({attempt+1}/{retries})...")
                    time.sleep(1)
                else:
                    print(f"API error: {e}. All retries failed.")
                    raise

        text_result = response.choices[0].message.content
        batch_result = json.loads(text_result)
        all_results.extend(batch_result)
        print(f"Processed batch {i//batch_size + 1}/{number_of_batches}")

    return all_results
