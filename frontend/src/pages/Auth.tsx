import { useState } from 'react'
import auth from '../requests'

interface AuthProps {
    setCurrentPage: (currentPage: string) => void
	setGlobalUsername: (username: string) => void
	setGlobalPassword: (password: string) => void
}

function Auth({ setCurrentPage, setGlobalUsername, setGlobalPassword }: AuthProps): JSX.Element {
    const [username, setUsername] = useState('')
	const [password, setPassword] = useState('')
	const [error, setError] = useState('')

	const handleSubmit = async (e: React.FormEvent): Promise<void> => {
		e.preventDefault()

		// let response = await auth(username, password)
		// if(response.status !== 200) {
		// 	setError(response.response.data.message)
		// 	return
		// }

		// setGlobalUsername(username)
		// setGlobalPassword(password)

		let response = await auth()
		if(response.status !== 200) {
			setError(response.response.data.message)
			return
		}

        setCurrentPage('musicListPage')
	}

	return (
		<div className="mainPage" id="authentificationPage">
			<div className="logos">
				<img src="/assets/spotify.png" alt="Logo Spotify" className="logo" />
				<img src="/assets/spotify.png" alt="Logo Spotify" className="logo" />
			</div>
			<form id='formAuthentification' onSubmit={handleSubmit}>
				<label htmlFor="username">Nom d'utilisateur</label>
				<input type="text" id='username' value={username} onChange={(e) => setUsername(e.target.value)} />

				<label htmlFor="password">Mot de passe</label>
				<input type="password" id='password' value={password} onChange={(e) => setPassword(e.target.value)} />

				<p className='error'>{error}</p>

				<button type='submit'>Se connecter</button>
			</form>
			<ul>
				<li><span>1.</span>Synchronisez vos musiques Spotify avec la base de données</li>
				<li><span>2.</span>Affinez les tags associés à vos musiques pour être le plus précis possible</li>
				<li><span>3.</span>Demandez à l'IA votre playlist de rêve</li>
				<li><span>4.</span>Ajustez les tags que vous souhaitez dans votre playlist</li>
				<li><span>5.</span>Créez votre playlist avec les tags que vous avez choisi</li>
			</ul>
		</div>
	)
}

export default Auth