import React, { useState } from 'react'
import axios from 'axios'
import { useStatus } from '../context/StatusContext'
import './ControlPanel.css'

interface ControlPanelProps {
  isRunning: boolean
}

const ControlPanel: React.FC<ControlPanelProps> = () => {
  const { status, refresh } = useStatus()
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  const handleStart = async () => {
    setLoading(true)
    setMessage(null)
    
    try {
      const response = await axios.post('/api/marketmaker/start')
      setMessage({ type: 'success', text: response.data.message || 'Market maker started!' })
      refresh()
    } catch (error: any) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.detail || 'Failed to start market maker' 
      })
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    setLoading(true)
    setMessage(null)
    
    try {
      const response = await axios.post('/api/marketmaker/stop')
      setMessage({ type: 'success', text: response.data.message || 'Market maker stopped!' })
      refresh()
    } catch (error: any) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.detail || 'Failed to stop market maker' 
      })
    } finally {
      setLoading(false)
    }
  }

  if (!status) return null

  return (
    <div className="control-panel">
      <h2>🎮 Control Panel</h2>
      
      <div className="status-indicator">
        <div className={`status-dot ${status.is_running ? 'running' : 'stopped'}`}></div>
        <span className="status-text">
          {status.is_running ? 'Running' : 'Stopped'}
        </span>
      </div>

      <div className="control-buttons">
        <button
          onClick={handleStart}
          disabled={loading || status.is_running}
          className={`btn btn-start ${status.is_running ? 'disabled' : ''}`}
        >
          ▶️ Start Market Maker
        </button>
        
        <button
          onClick={handleStop}
          disabled={loading || !status.is_running}
          className={`btn btn-stop ${!status.is_running ? 'disabled' : ''}`}
        >
          ⏹️ Stop Market Maker
        </button>
      </div>

      {message && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
        </div>
      )}

      <div className="control-info">
        <p>
          {status.is_running 
            ? 'Market maker is actively trading. Monitor the stats panel for updates.'
            : 'Click start to begin market making. Make sure you have sufficient balance.'}
        </p>
      </div>
    </div>
  )
}

export default ControlPanel
