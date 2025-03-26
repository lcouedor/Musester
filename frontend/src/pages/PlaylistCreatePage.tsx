interface AuthProps {
    setCurrentPage: (currentPage: string) => void
    username: string
    password: string
}

function PlaylistCreatePage({ setCurrentPage, username, password }: AuthProps): JSX.Element {
    return (
        <div>
            <h1>Playlist Create</h1>
            <button onClick={() => setCurrentPage('musicListPage')}>go to musicListPage</button>
        </div>
    )
}

export default PlaylistCreatePage