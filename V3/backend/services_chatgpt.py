from openai import OpenAI
from services_bdd import getAllTagsNames
from utils import getSecret
from dotenv import load_dotenv
import time

load_dotenv()

client = OpenAI(api_key=getSecret('GPT_KEY'))

def getSongAutomaticTagsBatch(batch):
    tags = getAllTagsNames()

    tags = ', '.join(tags)

    preprompt = "You are a music tagging assistant. Your task is to determine relevant tags for a song based on its title and artists."
    preprompt += "Here are the rules you must follow:"
    preprompt += "1. If you don't know the song, respond only with 'unknown' and nothing else on the row, but you should know most of the songs."
    preprompt += "2. If you feel like multiple tags fill the same role, add them all. Don’t hold back."
    preprompt += "3. Unless you don't know the song, you must provide **as many tags as possible**. Continue until you have covered all relevant dimensions of the song. Think about the song’s genre, origin, mood, tempo, themes, and any other attributes that could apply."
    preprompt += "4. Include at least one tag from every significant dimension of the song (genre, mood, tempo, language, ambiance, period, etc.), unless you feel it’s irrelevant or no tag is available to describe the point."
    preprompt += "5. Each song should have his individual tags"
    preprompt += "6. Only available tags are those from the provided list. If no tag is present for a specific dimension, either take the closest one if existent or leave it blank. (Ideally, each song should have at least 6 tags)"
    preprompt += "7. Respond only with a list of tags, each separated by a vertical bar |. Do not add any explanations or additional text."
    preprompt += "Input format: Multiple songs at once, for each song:"
    preprompt += "- Song title: <song_title>"
    preprompt += "- Artists: <artist_names>"
    preprompt += "Output format: "
    preprompt += "All tags separated by a vertical bar |. Don't rewrite the song title or artist name"
    preprompt += "Add a dollar after each song to separate them, for example :"
    preprompt += "tag1Song1 | tag2Song1 | tag3Song1 $ tag1Song2 | tag2Song2 | tag3Song2"

    prompt = "Existing tags: " + tags
    prompt += "\n"+batch

    try:
        response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": preprompt},
            {"role": "user", "content": prompt},
        ])
    except Exception as e:
        retries = 3
        for i in range(retries):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
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

    print(result)


    #Je découpe les réponses pour chaque chanson
    result = result.split('$')
    #Et pour chaque chanson, je découpe les tags
    result = [song.split('|') for song in result]
    #Je supprime les espaces et les tags vides
    result = [[tag.strip() for tag in song if tag.strip()] for song in result]
    
    return result

# def getSongAutomaticTags(song_name, artists):
#     tags = getAllTagsNames()

#     tags = ', '.join(tags)

#     preprompt = "You are a music tagging assistant. Your task is to determine relevant tags for a song based on its title and artists."
#     preprompt += "Here are the rules you must follow:"
#     preprompt += "1. If you don't know the song, respond only with 'unknown', but you should know most of the songs."
#     preprompt += "2. Tags must :"
#     preprompt += "- Be in English."
#     preprompt += "- Be general and widely understandable (avoid overly specific or niche tags, e.g., series names,artists names, highly obscure terms like 'surfy', ...)."
#     preprompt += "- Represent broad categories like genres, language, emotions, listening moods, or other significant aspects of the song, but it must add meaningful value to the filtering process coming next."
#     preprompt += "- If you feel like multiple tags fill the same role, add them all."
#     preprompt += "3. Use the provided list of pre-existing tags as a huge priority. Try to align with them whenever applicable. However, if absolutely essential tags are missing, you are allowed to create new ones. Avoid generating too many new tags."
#     preprompt += "4. Respond only with a list of tags, each separated by a hyphen (-). Do not add any explanations or additional text."
#     preprompt += "Input format:"
#     preprompt += "- Song title: <song_title>"
#     preprompt += "- Artists: <artist_names>"
#     preprompt += "- Existing tags: <list_of_existing_tags>"
#     preprompt += "Output format: tag1 - tag2 - tag3 - ..."

#     prompt = "Titre : " + song_name
#     prompt += "\nArtiste(s) : " + artists
#     prompt += "\nAExisting tags: " + tags
  
#     response = client.chat.completions.create(
#         model="gpt-3.5-turbo-1106",
#         messages=[
#             {"role": "system", "content": preprompt},
#             {"role": "user", "content": prompt},
#         ]
#     )

#     result = response.choices[0].message.content
#     #Je fais un tableau à partir des tags
#     result = result.split('-')
#     #Je supprime les espaces et les tags vides
#     result = [tag.strip() for tag in result if tag.strip()]

#     return result

def getTagListForPrompt(prompt):
    tags = getAllTagsNames()

    tags = ', '.join(tags)

    preprompt = "You are a playlist filtering assistant. Your task is to analyze a human-written playlist objective and categorize tags into three groups:"
    preprompt += "- Included tags: Tags that must all be present for a song to qualify."
    preprompt += "- Excluded tags: Tags that must not be present in any qualifying songs."
    preprompt += "- Or tags: Tags where songs must have at least one to qualify."
    preprompt += "Key rules to follow:"
    preprompt += "1. Use ONLY the provided list of tags and nothing else, do not invent any tag."
    preprompt += "2. 0 to 1 tag for included tags."
    preprompt += "3. Use 'or tags' a lot a lot a lot if you can, without any limit, it's by far the MOST important. "
    preprompt += "4. Use 'excluded tags' frequently, even more than 'or tags' sometimes, especially for genre tags that don't fit the description. (Ex : a chill playlist, I don't want any rock songs)"
    preprompt += "5. Interpret the description creatively, but focus on ensuring that the tags fit the essence of the description."
    preprompt += "6. Flexibility is the MOST important, if the playlist description is vague or describes a broad mood or genre, put all the tags in 'Or tags', and none in 'Included'."
    preprompt += "7. Respond in the following format, separating categories with vertical bar  : |"
    preprompt += "Input format:"
    preprompt += "- Description: <user_prompt>"
    preprompt += "- Existing tags: <list_of_existing_tags>"
    preprompt += "Output format:"
    preprompt += "included_tag1, included_tag2 | excluded_tag1, excluded_tag2 | or_tag1, or_tag2"
    preprompt += "8. You can leave empty a category, espacially included tags, but ensure the two hyphens remain."
    
    prompt = "Description : " + prompt
    prompt += "\nExisting tags: " + tags

    try:
        response = client.chat.completions.create(
        model="chatgpt-4o-latest",
        messages=[
            {"role": "system", "content": preprompt},
            {"role": "user", "content": prompt},
        ]
    )
    except Exception as e:
        retries = 3
        for i in range(retries):
            try:
                response = client.chat.completions.create(
                model="chatgpt-4o-latest",
                messages=[
                    {"role": "system", "content": preprompt},
                    {"role": "user", "content": prompt},
                ])
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