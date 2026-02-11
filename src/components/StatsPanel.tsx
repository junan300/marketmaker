import React from 'react'
import './StatsPanel.css'

interface StatsPanelProps {
  stats: {
    total_trades: number
    total_profit: number
    last_trade_time: string | null
    start_time: string | null
  }
}

const StatsPanel: React.FC<StatsPanelProps> = ({ stats }) => {
  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A'
    try {
      const date = new Date(dateString)
      return date.toLocaleString()
    } catch {
      return dateString
    }
  }

  const getUptime = () => {
    if (!stats.start_time) return 'N/A'
    try {
      const start = new Date(stats.start_time)
      const now = new Date()
      const diff = now.getTime() - start.getTime()
      const hours = Math.floor(diff / (1000 * 60 * 60))
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
      return `${hours}h ${minutes}m`
    } catch {
      return 'N/A'
    }
  }

  return (
    <div className="stats-panel">
      <h2>📊 Statistics</h2>
      
      <div className="stats-grid">
        <div className="stat-item">
          <div className="stat-value">{stats.total_trades}</div>
          <div className="stat-label">Total Trades</div>
        </div>
        
        <div className="stat-item">
          <div className="stat-value profit">
            {stats.total_profit >= 0 ? '+' : ''}{stats.total_profit.toFixed(4)} SOL
          </div>
          <div className="stat-label">Total Profit</div>
        </div>
        
        <div className="stat-item">
          <div className="stat-value">{getUptime()}</div>
          <div className="stat-label">Uptime</div>
        </div>
      </div>

      <div className="stats-details">
        <div className="detail-row">
          <span className="detail-label">Last Trade:</span>
          <span className="detail-value">{formatDate(stats.last_trade_time)}</span>
        </div>
        
        <div className="detail-row">
          <span className="detail-label">Started:</span>
          <span className="detail-value">{formatDate(stats.start_time)}</span>
        </div>
      </div>
    </div>
  )
}

export default StatsPanel
