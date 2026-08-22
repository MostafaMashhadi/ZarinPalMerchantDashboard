import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'samim-font/dist/font-face.css'
import App from './App.tsx'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
