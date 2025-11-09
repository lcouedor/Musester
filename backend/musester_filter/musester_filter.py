from common.services_chatgpt import getSongAutomaticTagsBatch
from common.services_spotify import get_spotify_client, get_playlist_tracks
from common.services_bdd import isPlaylistSongInDb, getTagIdByNameForSpotify, addSongsBatch
import asyncio

async def syncService(sourcePlaylistId):
    # Je récupère les pistes de la playlist source
    playlist_tracks = get_playlist_tracks(sourcePlaylistId)
    total_songs = len(playlist_tracks)

    songs_to_tag = [
        song for song in playlist_tracks
        if not isPlaylistSongInDb(song['song_spotify_id'])
    ]

    prepared_songs = []

    # Par paquet, je fais une requête à chatGPT pour récupérer les tags
    batch_size = 12

    async def process_batch(batch, start_index):
        print(f"Batch {start_index // batch_size + 1}/{len(songs_to_tag) // batch_size + 1}")
        # Je prépare une variable data qui m'affiche une ligne par chanson, avec le titre et les artistes
        data = ''
        for song in batch:
            data += 'Titre : ' + song['song_name'] + '\nArtiste(s) : ' + song['song_artists'] + '\n\n'
        
        song_tags = getSongAutomaticTagsBatch(data)  # Appel synchrone

        #Pour chaque chanson, je récupère les tags
        for song in batch:
            song_tags_ids = getTagIdByNameForSpotify(song_tags[batch.index(song)])
            song['tag_ids'] = song_tags_ids
            prepared_songs.append(song)

    # Traitement en parallèle des lots
    tasks = [
        process_batch(songs_to_tag[i:i + batch_size], start_index=i)
        for i in range(0, len(songs_to_tag), batch_size)
    ]
    
    await asyncio.gather(*tasks)

    # Je les ajoute à la base de données par batchs de 100
    for i in range(0, len(prepared_songs), 100):
        addSongsBatch(prepared_songs[i:i + 100])

    return {"success": "Synchronization successful"}
