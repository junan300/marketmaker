import React from 'react'
import { useStatus } from '../context/StatusContext'
import ControlPanel from './ControlPanel'
import StatsPanel from './StatsPanel'
import AccountPanel from './AccountPanel'
import ConfigPanel from './ConfigPanel'
import './Dashboard.css'

interface DashboardProps {
  onShowWalletManagement?: () => void
}

const Dashboard: React.FC<DashboardProps> = ({ onShowWalletManagement }) => {
  const { status, loading } = useStatus()

  if (loading || !status) {
    return (
      <div className="dashboard-loading">
        <div className="spinner"></div>
        <p>Loading dashboard...</p>
      </div>
    )
  }

  const getStatusColor = () => {
    if (!status.is_running) return '#999'
    return '#4caf50'
  }

  const getStatusText = () => {
    return status.is_running ? '🟢 Running' : '⚪ Stopped'
  }

  return (
    <div className="dashboard">
      {/* Status Banner */}
      <div className="status-banner" style={{ backgroundColor: getStatusColor() }}>
        <div className="status-content">
          <span className="status-indicator">{getStatusText()}</span>
          <span className="status-details">
            {status.is_running 
              ? `Active • ${status.stats?.total_trades || 0} trades • ${status.account?.balance?.toFixed(4) || '0.0000'} SOL`
              : 'Ready to start'
            }
          </span>
          {onShowWalletManagement && (
            <button 
              className="btn-manage-wallets"
              onClick={onShowWalletManagement}
              title="Manage wallets"
            >
              🔐 Manage Wallets
            </button>
          )}
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-card account-card">
          <AccountPanel 
            account={status.account} 
            onManageWallets={onShowWalletManagement}
          />
        </div>
        
        <div className="dashboard-card control-card">
          <ControlPanel isRunning={status.is_running} />
        </div>
        
        <div className="dashboard-card stats-card">
          <StatsPanel stats={status.stats} />
        </div>
        
        <div className="dashboard-card config-card">
          <ConfigPanel config={status.config} />
        </div>
      </div>
    </div>
  )
}

export default Dashboard
