import React, { useState } from 'react'
import axios from 'axios'
import './WalletSetup.css'

interface WalletSetupProps {
  onWalletCreated: () => void
}

const WalletSetup: React.FC<WalletSetupProps> = ({ onWalletCreated }) => {
  const [loading, setLoading] = useState(false)
  const [importLoading, setImportLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [showImport, setShowImport] = useState(false)
  const [privateKey, setPrivateKey] = useState('')

  const createWallet = async () => {
    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await axios.post('/api/wallet/create')
      setSuccess(`Wallet created! Public Key: ${response.data.public_key}`)
      setTimeout(() => {
        onWalletCreated()
      }, 2000)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create wallet')
    } finally {
      setLoading(false)
    }
  }

  const importWallet = async () => {
    if (!privateKey.trim()) {
      setError('Please enter a private key')
      return
    }

    setImportLoading(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await axios.post('/api/wallet/import', {
        private_key: privateKey.trim()
      })
      setSuccess(`Wallet imported! Public Key: ${response.data.public_key}`)
      setPrivateKey('')
      setShowImport(false)
      setTimeout(() => {
        onWalletCreated()
      }, 2000)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to import wallet')
    } finally {
      setImportLoading(false)
    }
  }

  return (
    <div className="wallet-setup">
      <div className="wallet-setup-card">
        <h2>🔐 Wallet Setup</h2>
        <p>You need a wallet to start market making. Create a new one or import an existing wallet.</p>
        
        <div className="wallet-actions">
          <button 
            onClick={createWallet} 
            disabled={loading}
            className="btn btn-primary"
          >
            {loading ? 'Creating...' : 'Create New Wallet'}
          </button>
          
          <div className="divider">
            <span>OR</span>
          </div>
          
          {!showImport ? (
            <button 
              className="btn btn-secondary"
              onClick={() => setShowImport(true)}
            >
              Import Existing Wallet
            </button>
          ) : (
            <div className="import-form">
              <textarea
                className="private-key-input"
                placeholder="Paste your private key (base58, hex, or array format)"
                value={privateKey}
                onChange={(e) => setPrivateKey(e.target.value)}
                rows={3}
              />
              <div className="import-actions">
                <button 
                  className="btn btn-primary"
                  onClick={importWallet}
                  disabled={importLoading}
                >
                  {importLoading ? 'Importing...' : 'Import Wallet'}
                </button>
                <button 
                  className="btn btn-secondary"
                  onClick={() => {
                    setShowImport(false)
                    setPrivateKey('')
                    setError(null)
                  }}
                  disabled={importLoading}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="alert alert-error">
            {error}
          </div>
        )}

        {success && (
          <div className="alert alert-success">
            {success}
          </div>
        )}

        <div className="wallet-info">
          <h3>⚠️ Important Security Notes:</h3>
          <ul>
            <li>Your wallet keypair will be stored locally in <code>wallet.json</code></li>
            <li>Never share your private key with anyone</li>
            <li>Always test on devnet first</li>
            <li>Keep backups of your wallet file in a secure location</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

export default WalletSetup
