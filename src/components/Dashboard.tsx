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

const PHASE_LABELS: Record<string, string> = {
  stealth_accumulation: 'Stealth Accumulation',
  stabilization: 'Stabilization & Momentum',
  graduation_push: 'Graduation Push',
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
    return status.is_running ? 'Running' : 'Stopped'
  }

  const capital = status.capital
  const phase = status.bonding_phase
  const phaseLabel = phase ? (PHASE_LABELS[phase] || phase) : ''

  return (
    <div className="dashboard">
      {/* Status Banner */}
      <div className="status-banner" style={{ backgroundColor: getStatusColor() }}>
        <div className="status-content">
          <span className="status-indicator">{getStatusText()}</span>
          <span className="status-details">
            {status.is_running
              ? `Active | ${status.stats?.total_trades || 0} trades | ${status.account?.balance?.toFixed(4) || '0.0000'} SOL`
              : 'Ready to start'
            }
          </span>
          {onShowWalletManagement && (
            <button
              className="btn-manage-wallets"
              onClick={onShowWalletManagement}
              title="Manage wallets"
            >
              Manage Wallets
            </button>
          )}
        </div>
      </div>

      {/* Capital Overview Bar */}
      {capital && (
        <div className="capital-bar">
          <div className="capital-bar-item">
            <span className="capital-label">Budget</span>
            <span className="capital-value">${capital.total_budget_usd.toLocaleString()}</span>
            <span className="capital-sub">{capital.total_budget_sol.toFixed(2)} SOL</span>
          </div>
          <div className="capital-bar-item">
            <span className="capital-label">Deployed</span>
            <span className="capital-value">${capital.deployed_capital_usd.toFixed(0)}</span>
            <span className="capital-sub">{capital.deployed_capital_sol.toFixed(2)} SOL</span>
          </div>
          <div className="capital-bar-item">
            <span className="capital-label">Available</span>
            <span className="capital-value">${capital.available_capital_usd.toFixed(0)}</span>
            <span className="capital-sub">{capital.available_capital_sol.toFixed(2)} SOL</span>
          </div>
          <div className="capital-bar-item">
            <span className="capital-label">Utilization</span>
            <span className="capital-value">{capital.capital_utilization_pct.toFixed(1)}%</span>
          </div>
          <div className="capital-bar-item">
            <span className="capital-label">SOL/USD</span>
            <span className="capital-value">${capital.sol_price_usd.toFixed(2)}</span>
          </div>
          {phaseLabel && (
            <div className="capital-bar-item phase-item">
              <span className="capital-label">Phase</span>
              <span className="capital-value phase-badge">{phaseLabel}</span>
            </div>
          )}
        </div>
      )}

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
