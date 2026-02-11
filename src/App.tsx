import React, { useState, useEffect } from 'react'
import Dashboard from './components/Dashboard'
import WalletSetup from './components/WalletSetup'
import { StatusProvider } from './context/StatusContext'
import './App.css'

function App() {
  const [hasWallet, setHasWallet] = useState<boolean | null>(null)

  useEffect(() => {
    checkWallet()
    const interval = setInterval(checkWallet, 5000)
    return () => clearInterval(interval)
  }, [])

  const checkWallet = async () => {
    try {
      const response = await fetch('/api/account')
      const data = await response.json()
      setHasWallet(data.wallet_loaded)
    } catch (error) {
      console.error('Error checking wallet:', error)
      setHasWallet(false)
    }
  }

  if (hasWallet === null) {
    return (
      <div className="app-loading">
        <div className="spinner"></div>
        <p>Loading...</p>
      </div>
    )
  }

  return (
    <StatusProvider>
      <div className="app">
        <header className="app-header">
          <h1>🚀 Solana Market Maker</h1>
          <p>Professional Trading Bot</p>
        </header>
        {hasWallet ? <Dashboard /> : <WalletSetup onWalletCreated={checkWallet} />}
      </div>
    </StatusProvider>
  )
}

export default App
