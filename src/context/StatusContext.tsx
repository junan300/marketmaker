import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import axios from 'axios'

interface CapitalStatus {
  total_budget_usd: number
  total_budget_sol: number
  deployed_capital_usd: number
  deployed_capital_sol: number
  available_capital_usd: number
  available_capital_sol: number
  capital_utilization_pct: number
  sol_price_usd: number
  price_last_updated: number
}

interface StatusData {
  is_running: boolean
  account: {
    wallet_loaded: boolean
    public_key: string | null
    balance: number
    network: string
  }
  stats: {
    total_trades: number
    total_profit: number
    last_trade_time: string | null
    start_time: string | null
  }
  config: {
    spread_percentage: number
    order_size: number
    min_balance: number
    network: string
  }
  capital?: CapitalStatus
  bonding_phase?: string
}

interface StatusContextType {
  status: StatusData | null
  loading: boolean
  refresh: () => Promise<void>
}

const StatusContext = createContext<StatusContextType | undefined>(undefined)

export const useStatus = () => {
  const context = useContext(StatusContext)
  if (!context) {
    throw new Error('useStatus must be used within StatusProvider')
  }
  return context
}

export const StatusProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [status, setStatus] = useState<StatusData | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    try {
      const response = await axios.get('/api/status')
      setStatus(response.data)
    } catch (error) {
      console.error('Error fetching status:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 3000) // Refresh every 3 seconds
    return () => clearInterval(interval)
  }, [])

  return (
    <StatusContext.Provider value={{ status, loading, refresh }}>
      {children}
    </StatusContext.Provider>
  )
}
