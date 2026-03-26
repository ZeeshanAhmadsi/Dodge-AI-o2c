import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// NOTE: StrictMode removed — it double-fires effects in dev, causing duplicate sessions
ReactDOM.createRoot(document.getElementById('root')).render(
  <App />
)
