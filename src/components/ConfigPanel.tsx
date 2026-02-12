import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useStatus } from '../context/StatusContext'
import './ConfigPanel.css'

interface PhaseConfig {
  phase_name: string
  phase_capital_allocation_pct: number
  base_trade_size_pct: number
  strong_signal_multiplier: number
  min_trade_size_pct: number
  max_trade_size_pct: number
  max_slippage_pct: number
  cycle_interval_s: number
  force_buy_mode: boolean
}

interface EffectiveSizes {
  phase_allocation_usd: number
  phase_allocation_sol: number
  base_trade_usd: number
  base_trade_sol: number
  strong_signal_trade_usd: number
  strong_signal_trade_sol: number
  min_trade_usd: number
  min_trade_sol: number
  max_trade_usd: number
  max_trade_sol: number
}

interface ConfigPanelProps {
  config: {
    spread_percentage: number
    order_size: number
    min_balance: number
    network: string
  }
}

const PHASE_OPTIONS = [
  { value: 'stealth_accumulation', label: 'Stealth Accumulation' },
  { value: 'stabilization', label: 'Stabilization & Momentum' },
  { value: 'graduation_push', label: 'Graduation Push' },
]

const ConfigPanel: React.FC<ConfigPanelProps> = () => {
  const { status, refresh } = useStatus()
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [budgetUsd, setBudgetUsd] = useState(1000)
  const [currentPhase, setCurrentPhase] = useState('stealth_accumulation')
  const [phaseConfig, setPhaseConfig] = useState<PhaseConfig | null>(null)
  const [effectiveSizes, setEffectiveSizes] = useState<EffectiveSizes | null>(null)

  // Load capital and phase data
  useEffect(() => {
    const loadCapitalData = async () => {
      try {
        const [capitalRes, phaseRes] = await Promise.all([
          axios.get('/api/v2/capital').catch(() => null),
          axios.get('/api/v2/phases/current').catch(() => null),
        ])

        if (capitalRes?.data) {
          setBudgetUsd(capitalRes.data.total_budget_usd || 1000)
          if (capitalRes.data.effective_sizes) {
            setEffectiveSizes(capitalRes.data.effective_sizes)
          }
        }

        if (phaseRes?.data) {
          setCurrentPhase(phaseRes.data.phase || 'stealth_accumulation')
          if (phaseRes.data.config) {
            setPhaseConfig(phaseRes.data.config)
          }
          if (phaseRes.data.effective_sizes) {
            setEffectiveSizes(phaseRes.data.effective_sizes)
          }
        }
      } catch (error) {
        console.error('Failed to load capital data:', error)
      }
    }

    loadCapitalData()
  }, [])

  // Update from status context
  useEffect(() => {
    if (status?.capital) {
      setBudgetUsd(status.capital.total_budget_usd)
    }
    if (status?.bonding_phase) {
      setCurrentPhase(status.bonding_phase)
    }
  }, [status])

  const handleBudgetSubmit = async () => {
    setLoading(true)
    setMessage(null)
    try {
      await axios.put('/api/v2/capital/budget', { total_budget_usd: budgetUsd })
      setMessage({ type: 'success', text: `Budget updated to $${budgetUsd.toLocaleString()}` })
      refresh()
      // Refresh effective sizes
      const phaseRes = await axios.get('/api/v2/phases/current')
      if (phaseRes.data?.effective_sizes) {
        setEffectiveSizes(phaseRes.data.effective_sizes)
      }
    } catch (error: any) {
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to update budget'
      })
    } finally {
      setLoading(false)
    }
  }

  const handlePhaseChange = async (newPhase: string) => {
    setLoading(true)
    setMessage(null)
    try {
      const res = await axios.post('/api/v2/phases/set', { phase: newPhase })
      setCurrentPhase(newPhase)
      if (res.data?.config) {
        setPhaseConfig(res.data.config)
      }
      if (res.data?.effective_sizes) {
        setEffectiveSizes(res.data.effective_sizes)
      }
      const phaseLabel = PHASE_OPTIONS.find(p => p.value === newPhase)?.label || newPhase
      setMessage({ type: 'success', text: `Phase changed to ${phaseLabel}` })
      refresh()
    } catch (error: any) {
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to change phase'
      })
    } finally {
      setLoading(false)
    }
  }

  if (!status) return null

  const solPrice = status.capital?.sol_price_usd || 0
  const utilization = status.capital?.capital_utilization_pct || 0

  return (
    <div className="config-panel">
      <h2>Capital & Phase Config</h2>

      {/* Budget Input */}
      <div className="config-item">
        <label htmlFor="total_budget">
          Total Budget (USD)
          <span className="tooltip" title="Total operational budget for the market maker">
            ?
          </span>
        </label>
        <div className="budget-input-row">
          <input
            type="number"
            id="total_budget"
            value={budgetUsd}
            onChange={e => setBudgetUsd(parseFloat(e.target.value) || 0)}
            step="100"
            min="1"
          />
          <button
            className="btn-apply"
            onClick={handleBudgetSubmit}
            disabled={loading}
          >
            Apply
          </button>
        </div>
      </div>

      {/* Phase Selector */}
      <div className="config-item">
        <label htmlFor="bonding_phase">
          Bonding Curve Phase
          <span className="tooltip" title="Controls capital allocation percentages and trade sizing">
            ?
          </span>
        </label>
        <select
          id="bonding_phase"
          value={currentPhase}
          onChange={e => handlePhaseChange(e.target.value)}
          disabled={loading}
          className="phase-select"
        >
          {PHASE_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* Capital Overview */}
      <div className="config-info">
        <p><strong>SOL/USD:</strong> ${solPrice.toFixed(2)}</p>
        <p><strong>Capital Utilization:</strong> {utilization.toFixed(1)}%</p>
        {status.capital && (
          <>
            <p><strong>Deployed:</strong> ${status.capital.deployed_capital_usd.toFixed(2)} ({status.capital.deployed_capital_sol.toFixed(4)} SOL)</p>
            <p><strong>Available:</strong> ${status.capital.available_capital_usd.toFixed(2)} ({status.capital.available_capital_sol.toFixed(4)} SOL)</p>
          </>
        )}
      </div>

      {/* Effective Trade Sizes */}
      {effectiveSizes && (
        <div className="config-info effective-sizes">
          <p className="section-label"><strong>Effective Trade Sizes</strong></p>
          <p><strong>Phase Allocation:</strong> ${effectiveSizes.phase_allocation_usd.toFixed(2)} ({effectiveSizes.phase_allocation_sol.toFixed(4)} SOL)</p>
          <p><strong>Base Trade:</strong> ${effectiveSizes.base_trade_usd.toFixed(2)} ({effectiveSizes.base_trade_sol.toFixed(4)} SOL)</p>
          <p><strong>Strong Signal:</strong> ${effectiveSizes.strong_signal_trade_usd.toFixed(2)} ({effectiveSizes.strong_signal_trade_sol.toFixed(4)} SOL)</p>
          <p><strong>Min/Max Trade:</strong> ${effectiveSizes.min_trade_usd.toFixed(2)} - ${effectiveSizes.max_trade_usd.toFixed(2)}</p>
        </div>
      )}

      {/* Phase Config Summary */}
      {phaseConfig && (
        <div className="config-info phase-summary">
          <p className="section-label"><strong>Phase Settings</strong></p>
          <p><strong>Capital Allocation:</strong> {phaseConfig.phase_capital_allocation_pct}%</p>
          <p><strong>Base Trade Size:</strong> {phaseConfig.base_trade_size_pct}% of phase</p>
          <p><strong>Strong Multiplier:</strong> {phaseConfig.strong_signal_multiplier}x</p>
          <p><strong>Max Slippage:</strong> {phaseConfig.max_slippage_pct}%</p>
          <p><strong>Cycle Interval:</strong> {phaseConfig.cycle_interval_s}s</p>
          {phaseConfig.force_buy_mode && (
            <p className="force-buy-badge">Force Buy Mode Active</p>
          )}
        </div>
      )}

      {/* Network Info */}
      <div className="config-info">
        <p><strong>Network:</strong> {status.config.network}</p>
      </div>

      {message && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
        </div>
      )}
    </div>
  )
}

export default ConfigPanel
