import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './WalletManagement.css'

interface Wallet {
  address: string
  role: string
  health: string
  balance_sol: number
  current_exposure: number
  label: string
}

interface WalletManagementProps {
  onBack: () => void
  onWalletSelected: () => void
}

const WalletManagement: React.FC<WalletManagementProps> = ({ onBack, onWalletSelected }) => {
  const [wallets, setWallets] = useState<Wallet[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showImport, setShowImport] = useState(false)
  const [privateKey, setPrivateKey] = useState('')
  const [importLoading, setImportLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [activeWallets, setActiveWallets] = useState<string[]>([])

  const loadWallets = async () => {
    try {
      const response = await axios.get('/api/v2/wallets')
      setWallets(response.data.wallets || [])
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load wallets')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadWallets()
    loadActiveWallets()
  }, [])

  const loadActiveWallets = async () => {
    try {
      const response = await axios.get('/api/v2/wallets/active')
      setActiveWallets(response.data.active_wallets || [])
    } catch (error) {
      console.error('Failed to load active wallets:', error)
    }
  }

  const toggleActiveWallet = async (address: string) => {
    try {
      await axios.post(`/api/v2/wallets/${address}/active`)
      await loadActiveWallets()
      await loadWallets()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to toggle active wallet')
    }
  }

  const refreshBalances = async () => {
    setRefreshing(true)
    try {
      await axios.post('/api/wallet/refresh-balance')
      await loadWallets()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to refresh balances')
    } finally {
      setRefreshing(false)
    }
  }

  const importWallet = async () => {
    if (!privateKey.trim()) {
      setError('Please enter a private key')
      return
    }

    setImportLoading(true)
    setError(null)

    try {
      await axios.post('/api/wallet/import', {
        private_key: privateKey.trim()
      })
      setPrivateKey('')
      setShowImport(false)
      await loadWallets()
      onWalletSelected()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to import wallet')
    } finally {
      setImportLoading(false)
    }
  }

  const createWallet = async () => {
    setImportLoading(true)
    setError(null)

    try {
      await axios.post('/api/wallet/create')
      await loadWallets()
      onWalletSelected()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create wallet')
    } finally {
      setImportLoading(false)
    }
  }

  const toggleWallet = async (address: string, currentHealth: string) => {
    try {
      if (currentHealth === 'disabled') {
        await axios.post(`/api/v2/wallets/${address}/enable`)
      } else {
        await axios.post(`/api/v2/wallets/${address}/disable`)
      }
      await loadWallets()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to toggle wallet')
    }
  }

  const deleteWallet = async (address: string) => {
    if (!window.confirm(`Remove wallet ${address.slice(0, 8)}...? The key will be deleted from this app. Export the key first if you need a backup.`)) return
    try {
      await axios.post(`/api/v2/wallets/${encodeURIComponent(address)}/delete`)
      await loadWallets()
      await loadActiveWallets()
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to remove wallet')
    }
  }

  const resetAllWallets = async () => {
    if (!window.confirm('Remove ALL wallets and start from a blank slate? Take-profit targets will be cleared. This cannot be undone.')) return
    try {
      await axios.post('/api/v2/wallets/reset-all')
      await loadWallets()
      await loadActiveWallets()
      onWalletSelected()
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset wallets')
    }
  }

  const formatAddress = (address: string) => {
    return `${address.slice(0, 8)}...${address.slice(-8)}`
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    alert('Copied to clipboard!')
  }

  if (loading) {
    return (
      <div className="wallet-management-loading">
        <div className="spinner"></div>
        <p>Loading wallets...</p>
      </div>
    )
  }

  return (
    <div className="wallet-management">
      <div className="wallet-management-header">
        <button className="btn-back" onClick={onBack}>
          ← Back to Dashboard
        </button>
        <h2>🔐 Wallet Management</h2>
        <div className="wallet-actions-top">
          <button 
            className="btn btn-secondary"
            onClick={refreshBalances}
            disabled={refreshing}
          >
            {refreshing ? 'Refreshing...' : '🔄 Refresh Balances'}
          </button>
          {wallets.length > 0 && (
            <button
              className="btn btn-danger"
              onClick={resetAllWallets}
              title="Remove all wallets and start from scratch"
            >
              🗑️ Reset All Wallets
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      <div className="add-wallet-section">
        <h3>Add New Wallet</h3>
        <div className="add-wallet-buttons">
          <button 
            className="btn btn-primary"
            onClick={createWallet}
            disabled={importLoading}
          >
            {importLoading ? 'Creating...' : '➕ Create New Wallet'}
          </button>
          <button 
            className="btn btn-secondary"
            onClick={() => setShowImport(!showImport)}
            disabled={importLoading}
          >
            {showImport ? 'Cancel Import' : '📥 Import Existing Wallet'}
          </button>
        </div>

        {showImport && (
          <div className="import-form">
            <textarea
              className="private-key-input"
              placeholder="Paste your private key (base58, hex, or array format)"
              value={privateKey}
              onChange={(e) => setPrivateKey(e.target.value)}
              rows={3}
            />
            <button 
              className="btn btn-primary"
              onClick={importWallet}
              disabled={importLoading || !privateKey.trim()}
            >
              {importLoading ? 'Importing...' : 'Import Wallet'}
            </button>
          </div>
        )}
      </div>

      <div className="wallets-list">
        <h3>Your Wallets ({wallets.length})</h3>
        {wallets.length === 0 ? (
          <div className="no-wallets">
            <p>No wallets found. Create or import a wallet to get started.</p>
          </div>
        ) : (
          <div className="wallets-grid">
            {wallets.map((wallet) => (
              <div 
                key={wallet.address} 
                className={`wallet-card ${wallet.health === 'disabled' ? 'disabled' : ''}`}
              >
                <div className="wallet-card-header">
                  <div className="wallet-address-section">
                    <code className="wallet-address">{formatAddress(wallet.address)}</code>
                    <button 
                      className="btn-copy-small"
                      onClick={() => copyToClipboard(wallet.address)}
                      title="Copy full address"
                    >
                      📋
                    </button>
                  </div>
                  <button
                    className={`btn-toggle ${wallet.health === 'disabled' ? 'enable' : 'disable'}`}
                    onClick={() => toggleWallet(wallet.address, wallet.health)}
                    title={wallet.health === 'disabled' ? 'Enable wallet' : 'Disable wallet'}
                  >
                    {wallet.health === 'disabled' ? '▶️' : '⏸️'}
                  </button>
                </div>
                
                <div className="wallet-card-body">
                  {wallet.label && (
                    <div className="wallet-label">
                      <strong>Label:</strong> {wallet.label}
                    </div>
                  )}
                  <div className="wallet-info-row">
                    <span className="info-label">Balance:</span>
                    <span className="info-value">{wallet.balance_sol.toFixed(4)} SOL</span>
                  </div>
                  <div className="wallet-info-row">
                    <span className="info-label">Role:</span>
                    <span className="info-value badge-role">{wallet.role}</span>
                  </div>
                  <div className="wallet-info-row">
                    <span className="info-label">Health:</span>
                    <span className={`info-value badge-health ${wallet.health}`}>
                      {wallet.health}
                    </span>
                  </div>
                  {wallet.current_exposure > 0 && (
                    <div className="wallet-info-row">
                      <span className="info-label">Exposure:</span>
                      <span className="info-value">{wallet.current_exposure.toFixed(4)} SOL</span>
                    </div>
                  )}
                </div>
                
                <div className="wallet-card-footer">
                  <div className="wallet-footer-actions">
                    <button
                      className={`btn-active ${activeWallets.includes(wallet.address) ? 'active' : ''}`}
                      onClick={() => toggleActiveWallet(wallet.address)}
                      title={activeWallets.includes(wallet.address) ? 'Remove from active wallets' : 'Add to active wallets'}
                    >
                      {activeWallets.includes(wallet.address) ? '⭐ Active' : '☆ Set Active'}
                    </button>
                    <button
                      className="btn-remove"
                      onClick={() => deleteWallet(wallet.address)}
                      title="Remove wallet (delete key from app)"
                    >
                      🗑️ Remove
                    </button>
                  </div>
                  <small className="full-address">{wallet.address}</small>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="wallet-management-info">
        <h3>ℹ️ About Wallet Management</h3>
        <ul>
          <li><strong>Total Balance:</strong> Sum of all enabled wallet balances</li>
          <li><strong>Disabled Wallets:</strong> Won't be used for trading but remain in keystore</li>
          <li><strong>Health Status:</strong> Indicates wallet availability for trading</li>
          <li><strong>Role:</strong> Defines wallet purpose (trading, accumulation, distribution, treasury)</li>
        </ul>
      </div>
    </div>
  )
}

export default WalletManagement
