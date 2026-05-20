import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import { AuthProvider } from './contexts/AuthContext.jsx'
import { BrandSeasonProvider } from './contexts/BrandSeasonContext.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <BrandSeasonProvider>
        <App />
      </BrandSeasonProvider>
    </AuthProvider>
  </React.StrictMode>,
)
