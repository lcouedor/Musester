from openai import OpenAI
from utils import getSecret
from dotenv import load_dotenv
import time
import asyncio

load_dotenv()

client = OpenAI(api_key=getSecret('GPT_KEY'))

def decisionHandler(description, musicInfos, batch_size=50):
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

    prompt = f"Description: {description}\nSongs:\n"
    for info in musicInfos:
        prompt += f"- ID: {info['id']}, Title: {info['title']}, Artist(s): {info['artists']}, , Album: {info['album']}\n"

    try:
        response = client.chat.completions.create(
        model="chatgpt-4o-latest",
        messages=[
            {"role": "system", "content": preprompt},
            {"role": "user", "content": prompt},
        ])
    except Exception as e:
        retries = 3
        for i in range(retries):
            try:
                response = client.chat.completions.create(
                    model="chatgpt-4o-latest",
                    messages=[
                    {"role": "system", "content": preprompt},
                    {"role": "user", "content": prompt},
                    ]
                )
                break  # If successful, break out of the loop
            except Exception as e:
                if i < retries - 1:
                    print(f"API error: {e}. Retrying ({i+1}/{retries})...")
                    time.sleep(1)  # Optional: Pause before retrying
                else:
                    print(f"API error: {e}. All retries failed.")
                    raise  # Re-raise the exception if all retries fail


    result = response.choices[0].message.content
    
    return result
