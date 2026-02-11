import React, { useState, useEffect } from 'react'
import Dashboard from './components/Dashboard'
import WalletSetup from './components/WalletSetup'
import WalletManagement from './components/WalletManagement'
import { StatusProvider } from './context/StatusContext'
import './App.css'

type View = 'dashboard' | 'wallet-setup' | 'wallet-management'

function App() {
  const [hasWallet, setHasWallet] = useState<boolean | null>(null)
  const [currentView, setCurrentView] = useState<View>('dashboard')

  useEffect(() => {
    checkWallet()
    const interval = setInterval(checkWallet, 5000)
    return () => clearInterval(interval)
  }, [])

  const checkWallet = async () => {
    try {
      const response = await fetch('/api/account')
      const data = await response.json()
      const walletLoaded = data.wallet_loaded
      setHasWallet(walletLoaded)
      
      // If wallet is loaded and we're on wallet-setup, go to dashboard
      if (walletLoaded && currentView === 'wallet-setup') {
        setCurrentView('dashboard')
      }
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

  // Determine view based on wallet status and current view
  let activeView: View = currentView
  if (!hasWallet && currentView !== 'wallet-setup') {
    activeView = 'wallet-setup'
  } else if (hasWallet && currentView === 'wallet-setup') {
    activeView = 'dashboard'
  }

  return (
    <StatusProvider>
      <div className="app">
        <header className="app-header">
          <h1>🚀 Solana Market Maker</h1>
          <p>Professional Trading Bot</p>
        </header>
        {activeView === 'wallet-setup' && (
          <WalletSetup onWalletCreated={() => {
            checkWallet()
            setCurrentView('dashboard')
          }} />
        )}
        {activeView === 'wallet-management' && (
          <WalletManagement 
            onBack={() => setCurrentView('dashboard')}
            onWalletSelected={() => {
              checkWallet()
              setCurrentView('dashboard')
            }}
          />
        )}
        {activeView === 'dashboard' && hasWallet && (
          <Dashboard onShowWalletManagement={() => setCurrentView('wallet-management')} />
        )}
      </div>
    </StatusProvider>
  )
}

export default App
