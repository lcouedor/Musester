from openai import OpenAI
from services_bdd import getAllTagsNames
from utils import getSecret
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=getSecret('GPT_KEY'))

def getSongAutomaticTags(song_name, artists):
    tags = getAllTagsNames()

    tags = ', '.join(tags)

    preprompt = "You are a music tagging assistant. Your task is to determine relevant tags for a song based on its title and artists."
    preprompt += "Here are the rules you must follow:"
    preprompt += "1. If you don't know the song, respond only with 'unknown', but you should know most of the songs."
    preprompt += "2. Tags must :"
    preprompt += "- Be in English."
    preprompt += "- Be general and widely understandable (avoid overly specific or niche tags, e.g., series names,artists names, highly obscure terms like 'surfy', ...)."
    preprompt += "- Represent broad categories like genres, language, emotions, listening moods, or other significant aspects of the song, but it must add meaningful value to the filtering process coming next."
    preprompt += "- If you feel like multiple tags fill the same role, add them all."
    preprompt += "3. Use the provided list of pre-existing tags as a huge priority. Try to align with them whenever applicable. However, if absolutely essential tags are missing, you are allowed to create new ones. Avoid generating too many new tags."
    preprompt += "4. Respond only with a list of tags, each separated by a hyphen (-). Do not add any explanations or additional text."
    preprompt += "Input format:"
    preprompt += "- Song title: <song_title>"
    preprompt += "- Artists: <artist_names>"
    preprompt += "- Existing tags: <list_of_existing_tags>"
    preprompt += "Output format: tag1 - tag2 - tag3 - ..."

    prompt = "Titre : " + song_name
    prompt += "\nArtiste(s) : " + artists
    prompt += "\nAExisting tags: " + tags
  
    response = client.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        messages=[
            {"role": "system", "content": preprompt},
            {"role": "user", "content": prompt},
        ]
    )

    result = response.choices[0].message.content
    #Je fais un tableau à partir des tags
    result = result.split('-')
    #Je supprime les espaces et les tags vides
    result = [tag.strip() for tag in result if tag.strip()]

    return result

def getTagListForPrompt(prompt):
    tags = getAllTagsNames()

    tags = ', '.join(tags)

    preprompt = "You are a playlist filtering assistant. Your task is to analyze a human-written playlist description and categorize tags into three groups:"
    preprompt += "- Included tags: Tags that must all be present for a song to qualify. Use this sparingly, ideally 1 or 2 maximum, as it's rare for many songs to have all the same tags."
    preprompt += "- Excluded tags: Tags that must not be present in any qualifying songs."
    preprompt += "- Or tags: Tags where songs must have at least one to qualify, allowing for more flexibility."
    preprompt += "Here are the rules you must follow:"
    preprompt += "1. Use only the provided list of tags. Do not invent or add any new tags."
    preprompt += "2. If no tags from the existing list fit the description, or only a few are relevant, do not force tags into the output. Prioritize quality over quantity."
    preprompt += "3. Interpret the description creatively but align with the tag list provided."
    preprompt += "4. Respond in the following format, separating categories with hyphens (-): included_tag1, included_tag2 - excluded_tag1, excluded_tag2 - or_tag1, or_tag2"
    preprompt += "If a category has no tags, leave it empty, but ensure the two hyphens remain."
    preprompt += "Input format:"
    preprompt += "- Description: <user_prompt>"
    preprompt += "- Existing tags: <list_of_existing_tags>"
    preprompt += "Output format:"
    preprompt += "included_tag1, included_tag2 - excluded_tag1, excluded_tag2 - or_tag1, or_tag2"
    
    prompt = "Description : " + prompt
    prompt += "\nExisting tags: " + tags

    response = client.chat.completions.create(
        model="chatgpt-4o-latest",
        messages=[
            {"role": "system", "content": preprompt},
            {"role": "user", "content": prompt},
        ]
    )

    result = response.choices[0].message.content

    return result