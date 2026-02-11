import React, { useState } from 'react'
import axios from 'axios'
import { useStatus } from '../context/StatusContext'
import './ConfigPanel.css'

interface ConfigPanelProps {
  config: {
    spread_percentage: number
    order_size: number
    min_balance: number
    network: string
  }
}

const ConfigPanel: React.FC<ConfigPanelProps> = () => {
  const { status, refresh } = useStatus()
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [formData, setFormData] = useState({
    spread_percentage: status?.config.spread_percentage || 0.5,
    order_size: status?.config.order_size || 0.1,
    min_balance: status?.config.min_balance || 1.0,
  })

  React.useEffect(() => {
    if (status?.config) {
      setFormData({
        spread_percentage: status.config.spread_percentage,
        order_size: status.config.order_size,
        min_balance: status.config.min_balance,
      })
    }
  }, [status])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: parseFloat(value) || 0
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setMessage(null)

    try {
      await axios.put('/api/marketmaker/config', formData)
      setMessage({ type: 'success', text: 'Configuration updated successfully!' })
      refresh()
    } catch (error: any) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.detail || 'Failed to update configuration' 
      })
    } finally {
      setLoading(false)
    }
  }

  if (!status) return null

  return (
    <div className="config-panel">
      <h2>⚙️ Configuration</h2>
      
      <form onSubmit={handleSubmit}>
        <div className="config-item">
          <label htmlFor="spread_percentage">
            Spread Percentage (%)
            <span className="tooltip" title="The percentage spread between buy and sell orders">
              ℹ️
            </span>
          </label>
          <input
            type="number"
            id="spread_percentage"
            name="spread_percentage"
            value={formData.spread_percentage}
            onChange={handleChange}
            step="0.1"
            min="0.1"
            max="10"
            required
          />
        </div>

        <div className="config-item">
          <label htmlFor="order_size">
            Order Size (SOL)
            <span className="tooltip" title="The size of each order in SOL">
              ℹ️
            </span>
          </label>
          <input
            type="number"
            id="order_size"
            name="order_size"
            value={formData.order_size}
            onChange={handleChange}
            step="0.01"
            min="0.01"
            required
          />
        </div>

        <div className="config-item">
          <label htmlFor="min_balance">
            Minimum Balance (SOL)
            <span className="tooltip" title="Stop trading if balance falls below this amount">
              ℹ️
            </span>
          </label>
          <input
            type="number"
            id="min_balance"
            name="min_balance"
            value={formData.min_balance}
            onChange={handleChange}
            step="0.1"
            min="0.1"
            required
          />
        </div>

        <div className="config-info">
          <p><strong>Network:</strong> {status.config.network}</p>
        </div>

        {message && (
          <div className={`alert alert-${message.type}`}>
            {message.text}
          </div>
        )}

        <button 
          type="submit" 
          className="btn btn-save"
          disabled={loading}
        >
          {loading ? 'Saving...' : '💾 Save Configuration'}
        </button>
      </form>
    </div>
  )
}

export default ConfigPanel
