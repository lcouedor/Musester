import { useEffect, useState } from 'react';
import { get } from '../requests';

interface AuthProps {
    setCurrentPage: (currentPage: string) => void
    username: string
    password: string
}

function MusicList({ setCurrentPage, username, password }: AuthProps): JSX.Element {
    const [musicList, setMusicList] = useState([])
    const [musicListCall, setMusicListCall] = useState({})
    username = 'leoco'
    password = "LeSeDeAn"

    useEffect(() => {
        const fetchMusicList = async () => {
            let musics = await get('songs/1', username, password)
            console.log(musics)
            setMusicList(musics.data.songs)
            setMusicListCall(musics.data)
        }
        fetchMusicList()
    }, [])

    return (
        <div>
            <h1>Music List</h1>
            <button onClick={() => setCurrentPage('playlistCreatePage')}>go to playlistCreate</button>
        
            {/* {musicList.map((music: any) => {
                return (
                    <div key={music.id}>
                        <h2>{music.title}</h2>
                        <p>{music.artist}</p>
                        <p>{music.album}</p>
                    </div>
                )
            })} */}
        </div>
    )
}

export default MusicList