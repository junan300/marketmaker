import React, { useState } from 'react'
import axios from 'axios'
import './AccountPanel.css'

interface AccountPanelProps {
  account: {
    wallet_loaded: boolean
    public_key: string | null
    balance: number
    network: string
  }
}

const AccountPanel: React.FC<AccountPanelProps> = ({ account }) => {
  const [refreshing, setRefreshing] = useState(false)
  const [showExport, setShowExport] = useState(false)
  const [passphrase, setPassphrase] = useState('')
  const [exportData, setExportData] = useState<any>(null)
  const [exportError, setExportError] = useState<string | null>(null)

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    alert('Copied to clipboard!')
  }

  const formatAddress = (address: string | null) => {
    if (!address) return 'N/A'
    return `${address.slice(0, 8)}...${address.slice(-8)}`
  }

  const refreshBalance = async () => {
    setRefreshing(true)
    try {
      await axios.post('/api/wallet/refresh-balance')
      // Trigger a page refresh to show updated balance
      setTimeout(() => window.location.reload(), 500)
    } catch (error: any) {
      alert('Failed to refresh balance: ' + (error.response?.data?.detail || error.message))
    } finally {
      setRefreshing(false)
    }
  }

  const exportWallet = async () => {
    if (!account.public_key) return
    
    setExportError(null)
    try {
      const response = await axios.get(`/api/wallet/export/${account.public_key}`, {
        params: { passphrase }
      })
      setExportData(response.data)
    } catch (error: any) {
      setExportError(error.response?.data?.detail || 'Failed to export wallet')
    }
  }

  return (
    <div className="account-panel">
      <h2>💼 Wallet Account</h2>
      
      <div className="account-info">
        <div className="info-row">
          <span className="label">Network:</span>
          <span className={`value network-badge ${account.network}`}>
            {account.network}
          </span>
        </div>
        
        <div className="info-row">
          <span className="label">Balance:</span>
          <div className="balance-container">
            <span className="value balance-amount">
              {account.balance.toFixed(4)} SOL
            </span>
            <button 
              className="refresh-btn"
              onClick={refreshBalance}
              disabled={refreshing}
              title="Refresh balance from blockchain"
            >
              {refreshing ? '⏳' : '🔄'}
            </button>
          </div>
        </div>
        
        <div className="info-row address-row">
          <span className="label">Public Key:</span>
          <div className="address-container">
            <code className="address-value">{formatAddress(account.public_key)}</code>
            {account.public_key && (
              <button 
                className="copy-btn"
                onClick={() => copyToClipboard(account.public_key!)}
                title="Copy full address"
              >
                📋
              </button>
            )}
          </div>
        </div>
        
        {account.public_key && (
          <div className="full-address">
            <small>{account.public_key}</small>
          </div>
        )}
      </div>

      {account.public_key && (
        <div className="wallet-actions-section">
          <button 
            className="btn-export"
            onClick={() => setShowExport(!showExport)}
          >
            {showExport ? 'Hide' : 'Export'} Private Key
          </button>

          {showExport && (
            <div className="export-form">
              <p className="export-warning">
                ⚠️ WARNING: Exporting your private key exposes it. Keep it secure!
              </p>
              <input
                type="password"
                className="passphrase-input"
                placeholder="Enter keystore passphrase (from .env MM_KEYSTORE_PASSPHRASE)"
                value={passphrase}
                onChange={(e) => setPassphrase(e.target.value)}
              />
              <button 
                className="btn-export-confirm"
                onClick={exportWallet}
                disabled={!passphrase}
              >
                Export Key
              </button>

              {exportError && (
                <div className="export-error">{exportError}</div>
              )}

              {exportData && (
                <div className="export-results">
                  <h4>Private Key (Base58):</h4>
                  <code className="export-key" onClick={() => copyToClipboard(exportData.private_key_base58)}>
                    {exportData.private_key_base58}
                  </code>
                  <button onClick={() => copyToClipboard(exportData.private_key_base58)}>
                    Copy Base58
                  </button>

                  <h4>Private Key (Hex):</h4>
                  <code className="export-key" onClick={() => copyToClipboard(exportData.private_key_hex)}>
                    {exportData.private_key_hex}
                  </code>
                  <button onClick={() => copyToClipboard(exportData.private_key_hex)}>
                    Copy Hex
                  </button>

                  <p className="export-warning">
                    {exportData.warning}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default AccountPanel
