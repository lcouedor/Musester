import { useState } from 'react'
import Auth from './pages/Auth'
import MusicList from './pages/MusicListPage'
import PlaylistCreatePage from './pages/PlaylistCreatePage'

function App() {
	const [currentPage, setCurrentPage] = useState('auth')
	const [globalUsername, setGlobalUsername] = useState('')
	const [globalPassword, setGlobalPassword] = useState('')

	return (
		<div className="App">
			{currentPage === 'auth' && <Auth setCurrentPage={setCurrentPage} setGlobalPassword={setGlobalPassword} setGlobalUsername={setGlobalUsername} />}
			{currentPage === 'musicListPage' && <MusicList setCurrentPage={setCurrentPage} password={globalPassword} username={globalUsername} />}
			{currentPage === 'playlistCreatePage' && <PlaylistCreatePage setCurrentPage={setCurrentPage} password={globalPassword} username={globalUsername} />}
		</div>
	)
}

export default App
