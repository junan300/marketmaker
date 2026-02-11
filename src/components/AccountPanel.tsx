import React, { useState } from 'react'
import axios from 'axios'
import './AccountPanel.css'

interface AccountPanelProps {
  account: {
    wallet_loaded: boolean
    public_key: string | null
    balance: number
    network: string
    total_wallets?: number
    enabled_wallets?: number
    all_wallets?: Array<{
      address: string
      balance_sol: number
      health: string
      label?: string
    }>
  }
  onManageWallets?: () => void
}

const AccountPanel: React.FC<AccountPanelProps> = ({ account, onManageWallets }) => {
  const [refreshing, setRefreshing] = useState(false)
  const [showExport, setShowExport] = useState(false)
  const [passphrase, setPassphrase] = useState('')
  const [exportData, setExportData] = useState<any>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const [selectedWallet, setSelectedWallet] = useState<string | null>(account.public_key)
  const [activeWallets, setActiveWallets] = useState<string[]>([])
  const [trading, setTrading] = useState(false)
  const [tokenMint, setTokenMint] = useState('')
  const [showTrading, setShowTrading] = useState(false)
  const [showTakeProfit, setShowTakeProfit] = useState(false)
  const [profitPercentage, setProfitPercentage] = useState('10')
  const [takeProfitStatus, setTakeProfitStatus] = useState<any>(null)

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    alert('Copied to clipboard!')
  }

  const formatAddress = (address: string | null) => {
    if (!address) return 'N/A'
    return `${address.slice(0, 8)}...${address.slice(-8)}`
  }

  // Load active wallets on mount
  React.useEffect(() => {
    const loadActiveWallets = async () => {
      try {
        const response = await axios.get('/api/v2/wallets/active')
        const wallets = response.data.active_wallets || []
        setActiveWallets(wallets)
        // If no active wallet selected, use the first active or primary wallet
        if (!selectedWallet && wallets.length > 0) {
          setSelectedWallet(wallets[0])
        } else if (!selectedWallet && account.public_key) {
          setSelectedWallet(account.public_key)
        }
      } catch (error) {
        console.error('Failed to load active wallets:', error)
      }
    }
    loadActiveWallets()
  }, [])

  // Update selected wallet when account changes
  React.useEffect(() => {
    if (account.public_key && !selectedWallet) {
      setSelectedWallet(account.public_key)
    }
  }, [account.public_key])

  const handleWalletSelect = async (address: string) => {
    setSelectedWallet(address)
    // Add to active wallets if not already active
    if (!activeWallets.includes(address)) {
      try {
        await axios.post(`/api/v2/wallets/${address}/active`)
        setActiveWallets([...activeWallets, address])
      } catch (error) {
        console.error('Failed to set wallet as active:', error)
      }
    }
  }

  const displayWallet = selectedWallet || account.public_key

  // Load take profit status
  React.useEffect(() => {
    if (displayWallet) {
      loadTakeProfitStatus()
    }
  }, [displayWallet])

  const loadTakeProfitStatus = async () => {
    if (!displayWallet) return
    try {
      const response = await axios.get(`/api/v2/wallets/${displayWallet}/take-profit`)
      setTakeProfitStatus(response.data)
    } catch (error) {
      setTakeProfitStatus(null)
    }
  }

  const setTakeProfit = async () => {
    if (!displayWallet || !tokenMint.trim() || !profitPercentage) {
      alert('Please enter token mint and profit percentage')
      return
    }

    try {
      await axios.post(`/api/v2/wallets/${displayWallet}/take-profit`, {
        wallet_address: displayWallet,
        token_mint: tokenMint.trim(),
        profit_percentage: parseFloat(profitPercentage),
        auto_sell: true
      })
      alert('Take profit target set!')
      await loadTakeProfitStatus()
    } catch (error: any) {
      alert(`Failed to set take profit: ${error.response?.data?.detail || error.message}`)
    }
  }

  const removeTakeProfit = async () => {
    if (!displayWallet) return
    try {
      await axios.delete(`/api/v2/wallets/${displayWallet}/take-profit`)
      setTakeProfitStatus(null)
      alert('Take profit target removed')
    } catch (error: any) {
      alert(`Failed to remove take profit: ${error.response?.data?.detail || error.message}`)
    }
  }

  const executeWalletTrade = async (side: 'buy' | 'sell') => {
    if (!displayWallet || !tokenMint.trim()) {
      alert('Please enter a token mint address')
      return
    }

    setTrading(true)
    try {
      const response = await axios.post(`/api/v2/wallets/${displayWallet}/trade`, {
        token_mint: tokenMint.trim(),
        side: side,
        percentage: 5.0,
        max_slippage: 2.0
      })
      alert(`Trade ${side} executed successfully! Transaction: ${response.data.transaction}`)
      // Refresh balance
      await refreshBalance()
    } catch (error: any) {
      alert(`Trade failed: ${error.response?.data?.detail || error.message}`)
    } finally {
      setTrading(false)
    }
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
      const response = await axios.post(`/api/wallet/export/${account.public_key}`, {
        passphrase
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
          <span className="label">Total Balance:</span>
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

        {account.total_wallets !== undefined && account.total_wallets > 1 && (
          <div className="info-row wallets-summary">
            <span className="label">Wallets:</span>
            <div className="wallets-info">
              <span className="value">
                {account.enabled_wallets || account.total_wallets} of {account.total_wallets} enabled
              </span>
              {onManageWallets && (
                <button 
                  className="btn-manage-link"
                  onClick={onManageWallets}
                  title="Manage all wallets"
                >
                  Manage →
                </button>
              )}
            </div>
          </div>
        )}
        
        <div className="info-row address-row">
          <span className="label">Active Wallet:</span>
          <div className="address-container">
            {account.all_wallets && account.all_wallets.length > 1 ? (
              <select
                className="wallet-select"
                value={displayWallet || ''}
                onChange={(e) => handleWalletSelect(e.target.value)}
                title="Select wallet to display"
              >
                {account.all_wallets.map((wallet) => (
                  <option key={wallet.address} value={wallet.address}>
                    {wallet.label || formatAddress(wallet.address)} - {wallet.balance_sol.toFixed(4)} SOL
                  </option>
                ))}
              </select>
            ) : (
              <code className="address-value">{formatAddress(displayWallet)}</code>
            )}
            {displayWallet && (
              <button 
                className="copy-btn"
                onClick={() => copyToClipboard(displayWallet)}
                title="Copy full address"
              >
                📋
              </button>
            )}
          </div>
        </div>
        
        {displayWallet && (
          <div className="info-row">
            <span className="label">Full Address:</span>
            <code className="address-value-full">{displayWallet}</code>
          </div>
        )}

        {displayWallet && (
          <div className="wallet-trading-section">
            <button 
              className="btn-trading-toggle"
              onClick={() => setShowTrading(!showTrading)}
            >
              {showTrading ? '▼' : '▶'} Wallet Trading
            </button>
            
            {showTrading && (
              <div className="trading-controls">
                <div className="trading-input-group">
                  <label>Token Mint Address:</label>
                  <input
                    type="text"
                    className="token-mint-input"
                    placeholder="Enter token mint address (e.g., EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v)"
                    value={tokenMint}
                    onChange={(e) => setTokenMint(e.target.value)}
                  />
                </div>
                <div className="trading-buttons">
                  <button
                    className="btn-trade btn-trade-buy"
                    onClick={() => executeWalletTrade('buy')}
                    disabled={trading || !tokenMint.trim()}
                  >
                    {trading ? 'Trading...' : '🔼 Small Buy (5%)'}
                  </button>
                  <button
                    className="btn-trade btn-trade-sell"
                    onClick={() => executeWalletTrade('sell')}
                    disabled={trading || !tokenMint.trim()}
                  >
                    {trading ? 'Trading...' : '🔽 Small Sell (5%)'}
                  </button>
                </div>
                <p className="trading-note">
                  ⚠️ Small buy/sell uses 5% of wallet balance. Make sure you have the token mint address correct.
                </p>
              </div>
            )}
          </div>
        )}

        {displayWallet && (
          <div className="wallet-take-profit-section">
            <button 
              className="btn-trading-toggle"
              onClick={() => setShowTakeProfit(!showTakeProfit)}
            >
              {showTakeProfit ? '▼' : '▶'} Take Profit Monitoring
            </button>
            
            {showTakeProfit && (
              <div className="take-profit-controls">
                {takeProfitStatus && takeProfitStatus.status === 'active' ? (
                  <div className="take-profit-status">
                    <h4>Active Take Profit Target</h4>
                    <div className="profit-info">
                      <p><strong>Token:</strong> {formatAddress(takeProfitStatus.token_mint)}</p>
                      <p><strong>Initial Price:</strong> {takeProfitStatus.initial_price.toFixed(6)} SOL</p>
                      <p><strong>Current Price:</strong> {takeProfitStatus.current_price.toFixed(6)} SOL</p>
                      <p><strong>Target Price:</strong> {takeProfitStatus.target_price.toFixed(6)} SOL</p>
                      <p><strong>Target Profit:</strong> {takeProfitStatus.profit_percentage}%</p>
                      <p className={takeProfitStatus.current_profit_pct >= 0 ? 'profit-positive' : 'profit-negative'}>
                        <strong>Current Profit:</strong> {takeProfitStatus.current_profit_pct.toFixed(2)}%
                      </p>
                      {takeProfitStatus.target_reached && (
                        <p className="target-reached">🎯 Target Reached! Auto-sell will execute.</p>
                      )}
                    </div>
                    <button
                      className="btn-remove-profit"
                      onClick={removeTakeProfit}
                    >
                      Remove Take Profit
                    </button>
                  </div>
                ) : (
                  <div className="take-profit-setup">
                    <div className="trading-input-group">
                      <label>Token Mint Address:</label>
                      <input
                        type="text"
                        className="token-mint-input"
                        placeholder="Enter token mint address"
                        value={tokenMint}
                        onChange={(e) => setTokenMint(e.target.value)}
                      />
                    </div>
                    <div className="trading-input-group">
                      <label>Profit Percentage (%):</label>
                      <input
                        type="number"
                        className="profit-percentage-input"
                        placeholder="10"
                        value={profitPercentage}
                        onChange={(e) => setProfitPercentage(e.target.value)}
                        min="1"
                        max="100"
                      />
                    </div>
                    <button
                      className="btn-set-profit"
                      onClick={setTakeProfit}
                      disabled={!tokenMint.trim() || !profitPercentage}
                    >
                      Set Take Profit Target
                    </button>
                    <p className="trading-note">
                      📈 Monitor token price. When it increases by the target percentage, auto-sell will execute.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {account.all_wallets && account.all_wallets.length > 1 && (
          <div className="wallets-preview">
            <div className="wallets-preview-header">
              <span className="label">All Wallets:</span>
            </div>
            <div className="wallets-preview-list">
              {account.all_wallets.slice(0, 3).map((wallet, idx) => (
                <div key={wallet.address} className="wallet-preview-item">
                  <span className="wallet-preview-label">
                    {wallet.label || `Wallet ${idx + 1}`}:
                  </span>
                  <code className="wallet-preview-address">{formatAddress(wallet.address)}</code>
                  <span className="wallet-preview-balance">{wallet.balance_sol.toFixed(4)} SOL</span>
                  {wallet.health === 'disabled' && (
                    <span className="wallet-preview-status disabled">⏸️</span>
                  )}
                </div>
              ))}
              {account.all_wallets.length > 3 && (
                <div className="wallet-preview-more">
                  +{account.all_wallets.length - 3} more...
                </div>
              )}
            </div>
            {onManageWallets && (
              <button 
                className="btn-view-all"
                onClick={onManageWallets}
              >
                View All Wallets →
              </button>
            )}
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
