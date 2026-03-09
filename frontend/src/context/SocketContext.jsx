/**
 * Socket.io Context Provider for Real-time Communication
 * 
 * This context provides Socket.io connection management and real-time
 * event handling for the frontend application.
 */
import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react'
import { io } from 'socket.io-client'

// Create the Socket context
const SocketContext = createContext(null)

// Default backend URL
const DEFAULT_BACKEND_URL = 'http://localhost:8000'

// Reconnection configuration
const RECONNECTION_CONFIG = {
  reconnection: true,
  reconnectionAttempts: Infinity,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  randomizationFactor: 0.5,
}

/**
 * Socket Provider Component
 * 
 * Wraps the application with Socket.io context, providing:
 * - Connection management with automatic reconnection
 * - Event subscription management
 * - Real-time data state management
 */
export function SocketProvider({ children }) {
  // Connection state
  const [socket, setSocket] = useState(null)
  const [connected, setConnected] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [connectionError, setConnectionError] = useState(null)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)

  // System state
  const [systemStatus, setSystemStatus] = useState('INITIALIZING')
  const [serverStats, setServerStats] = useState(null)

  // Market data state
  const [priceUpdates, setPriceUpdates] = useState({})
  const [subscribedMarkets, setSubscribedMarkets] = useState(new Set())

  // Trading state
  const [signals, setSignals] = useState([])
  const [positions, setPosition] = useState([])
  const [orders, setOrders] = useState([])
  const [metrics, setMetrics] = useState(null)

  // Panic state
  const [panicAlert, setPanicAlert] = useState(null)

  // Refs for managing subscriptions
  const subscriptionsRef = useRef(new Set())
  const eventHandlersRef = useRef(new Map())

  /**
   * Initialize Socket.io connection
   */
  useEffect(() => {
    const backendUrl = import.meta.env.VITE_BACKEND_URL || DEFAULT_BACKEND_URL
    const socketPath = '/socket.io'

    console.log(`🔌 Connecting to Socket.io server at ${backendUrl}`)

    const socketInstance = io(backendUrl, {
      path: socketPath,
      transports: ['websocket', 'polling'],
      ...RECONNECTION_CONFIG,
    })

    // Connection events
    socketInstance.on('connect', () => {
      console.log('✅ Socket connected:', socketInstance.id)
      setConnected(true)
      setConnecting(false)
      setConnectionError(null)
      setReconnectAttempts(0)

      // Re-subscribe to markets after reconnection
      subscriptionsRef.current.forEach(marketId => {
        socketInstance.emit('subscribe_market', { market_id: marketId })
      })
    })

    socketInstance.on('disconnect', (reason) => {
      console.log('❌ Socket disconnected:', reason)
      setConnected(false)

      if (reason === 'io server disconnect') {
        // Server disconnected us, try to reconnect
        socketInstance.connect()
      }
    })

    socketInstance.on('connect_error', (error) => {
      console.error('🔴 Connection error:', error.message)
      setConnectionError(error.message)
      setConnecting(false)
    })

    socketInstance.on('reconnect_attempt', (attempt) => {
      console.log(`🔄 Reconnection attempt ${attempt}`)
      setReconnectAttempts(attempt)
      setConnecting(true)
    })

    socketInstance.on('reconnect_failed', () => {
      console.error('❌ Reconnection failed')
      setConnectionError('Reconnection failed after maximum attempts')
    })

    // Server-initiated events
    socketInstance.on('connection_established', (data) => {
      console.log('✅ Connection established:', data)
    })

    socketInstance.on('server_stats', (stats) => {
      console.log('📊 Server stats:', stats)
      setServerStats(stats)
    })

    socketInstance.on('system_status', (status) => {
      console.log('📊 System status:', status)
      setSystemStatus(status.status || 'ACTIVE')
      if (status.statistics) {
        setServerStats(status.statistics)
      }
    })

    // Price updates
    socketInstance.on('price_update', (data) => {
      console.log('📈 Price update:', data)
      setPriceUpdates(prev => ({
        ...prev,
        [data.market_id]: {
          ...prev[data.market_id],
          ...data,
          lastUpdate: new Date().toISOString(),
        }
      }))
    })

    // Signal detection
    socketInstance.on('signal_detected', (signal) => {
      console.log('🎯 Signal detected:', signal)
      setSignals(prev => [signal, ...prev.slice(0, 99)]) // Keep last 100 signals
    })

    // Position updates
    socketInstance.on('position_update', (position) => {
      console.log('📊 Position update:', position)
      setPosition(prev => {
        const index = prev.findIndex(p => p.position_id === position.position_id)
        if (index >= 0) {
          return [...prev.slice(0, index), position, ...prev.slice(index + 1)]
        }
        return [position, ...prev]
      })
    })

    // Order updates
    socketInstance.on('order_update', (order) => {
      console.log('📝 Order update:', order)
      setOrders(prev => {
        const index = prev.findIndex(o => o.order_id === order.order_id)
        if (index >= 0) {
          return [...prev.slice(0, index), order, ...prev.slice(index + 1)]
        }
        return [order, ...prev]
      })
    })

    // Metrics updates
    socketInstance.on('metrics_update', (data) => {
      console.log('📊 Metrics update:', data)
      setMetrics(data)
    })

    // Panic alerts
    socketInstance.on('panic_alert', (alert) => {
      console.error('🚨 PANIC ALERT:', alert)
      setPanicAlert(alert)
      setSystemStatus('HALTED')
    })

    // Error handling
    socketInstance.on('error', (error) => {
      console.error('🔴 Socket error:', error)
      setConnectionError(error.error_message || error.message || 'Unknown error')
    })

    // Model updates
    socketInstance.on('model_update', (model) => {
      console.log('🤖 Model update:', model)
    })

    setSocket(socketInstance)

    // Cleanup on unmount
    return () => {
      console.log('🔌 Disconnecting socket...')
      socketInstance.disconnect()
    }
  }, [])

  /**
   * Subscribe to market updates
   */
  const subscribeToMarket = useCallback((marketId) => {
    if (!socket || !connected) {
      console.warn('Cannot subscribe: socket not connected')
      return Promise.reject(new Error('Socket not connected'))
    }

    return new Promise((resolve, reject) => {
      socket.emit('subscribe_market', { market_id: marketId }, (response) => {
        if (response.success) {
          console.log(`✅ Subscribed to market ${marketId}`)
          subscriptionsRef.current.add(marketId)
          setSubscribedMarkets(new Set(subscriptionsRef.current))
          resolve(response)
        } else {
          console.error(`❌ Failed to subscribe to market ${marketId}:`, response.error)
          reject(new Error(response.error))
        }
      })
    })
  }, [socket, connected])

  /**
   * Unsubscribe from market updates
   */
  const unsubscribeFromMarket = useCallback((marketId) => {
    if (!socket || !connected) {
      console.warn('Cannot unsubscribe: socket not connected')
      return Promise.reject(new Error('Socket not connected'))
    }

    return new Promise((resolve, reject) => {
      socket.emit('unsubscribe_market', { market_id: marketId }, (response) => {
        if (response.success) {
          console.log(`✅ Unsubscribed from market ${marketId}`)
          subscriptionsRef.current.delete(marketId)
          setSubscribedMarkets(new Set(subscriptionsRef.current))
          resolve(response)
        } else {
          console.error(`❌ Failed to unsubscribe from market ${marketId}:`, response.error)
          reject(new Error(response.error))
        }
      })
    })
  }, [socket, connected])

  /**
   * Request current market data
   */
  const requestMarketData = useCallback((marketId) => {
    if (!socket || !connected) {
      console.warn('Cannot request market data: socket not connected')
      return Promise.reject(new Error('Socket not connected'))
    }

    return new Promise((resolve, reject) => {
      socket.emit('request_market_data', { market_id: marketId }, (response) => {
        if (response.success) {
          resolve(response)
        } else {
          reject(new Error(response.error))
        }
      })
    })
  }, [socket, connected])

  /**
   * Get server statistics
   */
  const getServerStats = useCallback(() => {
    if (!socket || !connected) {
      return Promise.reject(new Error('Socket not connected'))
    }

    return new Promise((resolve) => {
      socket.emit('get_stats', (stats) => {
        setServerStats(stats)
        resolve(stats)
      })
    })
  }, [socket, connected])

  /**
   * Ping server for latency measurement
   */
  const pingServer = useCallback(() => {
    if (!socket || !connected) {
      return Promise.reject(new Error('Socket not connected'))
    }

    const startTime = Date.now()
    return new Promise((resolve) => {
      socket.emit('ping_server', (response) => {
        const latency = Date.now() - startTime
        resolve({ ...response, latency })
      })
    })
  }, [socket, connected])

  /**
   * Trigger panic halt
   */
  const emitPanic = useCallback(() => {
    if (!socket || !connected) {
      console.warn('Cannot emit panic: socket not connected')
      return
    }
    console.log('🚨 Emitting panic halt')
    socket.emit('panic_halt')
  }, [socket, connected])

  /**
   * Reset panic state
   */
  const emitReset = useCallback(() => {
    if (!socket || !connected) {
      console.warn('Cannot emit reset: socket not connected')
      return
    }
    console.log('✅ Emitting panic reset')
    socket.emit('panic_reset')
  }, [socket, connected])

  /**
   * Clear panic alert
   */
  const clearPanicAlert = useCallback(() => {
    setPanicAlert(null)
  }, [])

  /**
   * Clear signals
   */
  const clearSignals = useCallback(() => {
    setSignals([])
  }, [])

  /**
   * Register custom event handler
   */
  const on = useCallback((eventName, handler) => {
    if (!socket) return

    socket.on(eventName, handler)
    eventHandlersRef.current.set(eventName, handler)
  }, [socket])

  /**
   * Unregister custom event handler
   */
  const off = useCallback((eventName) => {
    if (!socket) return

    socket.off(eventName)
    eventHandlersRef.current.delete(eventName)
  }, [socket])

  /**
   * Emit custom event
   */
  const emit = useCallback((eventName, data, callback) => {
    if (!socket || !connected) {
      console.warn(`Cannot emit ${eventName}: socket not connected`)
      return
    }
    socket.emit(eventName, data, callback)
  }, [socket, connected])

  // Context value
  const value = {
    // Connection state
    socket,
    connected,
    connecting,
    connectionError,
    reconnectAttempts,

    // System state
    systemStatus,
    serverStats,

    // Market data
    priceUpdates,
    subscribedMarkets,
    subscribeToMarket,
    unsubscribeFromMarket,
    requestMarketData,

    // Trading data
    signals,
    positions,
    orders,
    metrics,

    // Panic state
    panicAlert,
    clearPanicAlert,

    // Actions
    emitPanic,
    emitReset,
    getServerStats,
    pingServer,
    clearSignals,

    // Low-level API
    on,
    off,
    emit,
  }

  return (
    <SocketContext.Provider value={value}>
      {children}
    </SocketContext.Provider>
  )
}

/**
 * Custom hook to access Socket context
 */
export function useSocket() {
  const context = useContext(SocketContext)
  if (!context) {
    throw new Error('useSocket must be used within SocketProvider')
  }
  return context
}

/**
 * Custom hook for market subscriptions
 */
export function useMarketSubscription(marketId) {
  const {
    subscribeToMarket,
    unsubscribeFromMarket,
    priceUpdates,
    connected
  } = useSocket()

  useEffect(() => {
    if (marketId && connected) {
      subscribeToMarket(marketId).catch(console.error)
    }

    return () => {
      if (marketId && connected) {
        unsubscribeFromMarket(marketId).catch(console.error)
      }
    }
  }, [marketId, connected, subscribeToMarket, unsubscribeFromMarket])

  return priceUpdates[marketId] || null
}

/**
 * Custom hook for signals
 */
export function useSignals() {
  const { signals, clearSignals } = useSocket()
  return { signals, clearSignals }
}

/**
 * Custom hook for positions
 */
export function usePositions() {
  const { positions } = useSocket()
  return positions
}

/**
 * Custom hook for metrics
 */
export function useMetrics() {
  const { metrics } = useSocket()
  return metrics
}

/**
 * Custom hook for panic state
 */
export function usePanicState() {
  const { panicAlert, systemStatus, emitPanic, emitReset, clearPanicAlert } = useSocket()
  return {
    panicAlert,
    systemStatus,
    isHalted: systemStatus === 'HALTED',
    triggerPanic: emitPanic,
    resetPanic: emitReset,
    clearAlert: clearPanicAlert,
  }
}

export default SocketContext
