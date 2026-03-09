import React, { createContext, useContext, useEffect, useState } from 'react'
import { io } from 'socket.io-client'

const SocketContext = createContext(null)

export function SocketProvider({ children }) {
  const [socket, setSocket] = useState(null)
  const [connected, setConnected] = useState(false)
  const [systemStatus, setSystemStatus] = useState('ACTIVE')

  useEffect(() => {
    const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

    const socketInstance = io(backendUrl, {
      transports: ['websocket', 'polling']
    })

    socketInstance.on('connect', () => {
      console.log('✅ Socket connected')
      setConnected(true)
    })

    socketInstance.on('disconnect', () => {
      console.log('❌ Socket disconnected')
      setConnected(false)
    })

    socketInstance.on('system_status', (status) => {
      console.log('📊 System status:', status)
      setSystemStatus(status.status || 'ACTIVE')
    })

    socketInstance.on('panic_triggered', (data) => {
      console.log('🚨 PANIC TRIGGERED:', data)
      setSystemStatus('HALTED')
    })

    socketInstance.on('panic_reset', (data) => {
      console.log('✅ Panic reset:', data)
      setSystemStatus('ACTIVE')
    })

    setSocket(socketInstance)

    return () => {
      socketInstance.disconnect()
    }
  }, [])

  const emitPanic = () => {
    if (socket && connected) {
      socket.emit('panic_halt')
    }
  }

  const emitReset = () => {
    if (socket && connected) {
      socket.emit('panic_reset')
    }
  }

  return (
    <SocketContext.Provider value={{
      socket,
      connected,
      systemStatus,
      emitPanic,
      emitReset
    }}>
      {children}
    </SocketContext.Provider>
  )
}

export function useSocket() {
  const context = useContext(SocketContext)
  if (!context) {
    throw new Error('useSocket must be used within SocketProvider')
  }
  return context
}
