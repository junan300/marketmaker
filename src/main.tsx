import React from 'react'
import ReactDOM from 'react-dom/client'
import axios from 'axios'
import App from './App'
import './index.css'

// In dev, call backend directly so we don't rely on proxy (avoids 404 on POST /api/v2/wallets/reset-all etc.)
if (import.meta.env.DEV) {
  axios.defaults.baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
