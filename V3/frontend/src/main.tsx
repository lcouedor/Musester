import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import axios from 'axios'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

async function test(){
  //Faire une requête distante avec axios
  let res = await axios.get('https://api.github.com/users/github')
  console.log(res.data)

  let res2 = await axios.get('https://musester-back.onrender.com')
  console.log(res2.data)
}

test()




