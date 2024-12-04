from cred import chatGptKey
from openai import OpenAI
from services_bdd import getAllTagsNames

client = OpenAI(api_key=chatGptKey)

def getSongAutomaticTags(song_name, artists):
    tags = getAllTagsNames()

    tags = ', '.join(tags)

    preprompt = "Tu es chargé de déterminer des tags pour des musiques"
    preprompt += "Tu reçois un titre de musique, et le(s) artiste(s) associé(s)"
    preprompt += "Tu me donne les tags que tu attribuerais à la musique"
    preprompt += "Les tags actuellement disponibles sont : " + tags
    preprompt += "Tu peux en ajouter un nouveau si besoin"
    preprompt += "Chaque musique a entre 2 et 10 tags"
    preprompt += "Un tag peut être plusieurs choses : genre de la musique, nationalité, mood, émotion, ..."
    preprompt += "Si tu ne connais pas la musique, réponds uniquement 'unknown'"
    preprompt += "réponds uniquement par la liste des tags séparés par des tirets"

    prompt = "Titre : " + song_name
    prompt += "\nArtiste(s) : " + artists
  
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
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

