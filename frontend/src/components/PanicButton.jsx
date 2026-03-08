import React, { useState } from 'react'
import { useSocket } from '../context/SocketContext'

function PanicButton() {
  const { connected, systemStatus, emitPanic, emitReset } = useSocket()
  const [showConfirm, setShowConfirm] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)

  const isHalted = systemStatus === 'HALTED'

  const handleClick = () => {
    if (isHalted) {
      // Reset panic
      setShowConfirm(true)
    } else {
      // Trigger panic
      setShowConfirm(true)
    }
  }

  const handleConfirm = async () => {
    setIsProcessing(true)
    
    try {
      if (isHalted) {
        emitReset()
      } else {
        emitPanic()
      }
      
      // Wait a moment for visual feedback
      await new Promise(resolve => setTimeout(resolve, 500))
    } catch (error) {
      console.error('Panic action failed:', error)
    } finally {
      setIsProcessing(false)
      setShowConfirm(false)
    }
  }

  const handleCancel = () => {
    setShowConfirm(false)
  }

  return (
    <div className="flex flex-col items-center gap-6">
      {/* Connection Status */}
      <div className="flex items-center gap-2">
        <div className={`w-3 h-3 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="text-sm text-slate-400">
          {connected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      {/* System Status */}
      <div className={`px-4 py-2 rounded-lg font-bold text-lg ${
        isHalted 
          ? 'bg-red-900 text-red-200 border-2 border-red-500' 
          : 'bg-green-900 text-green-200 border-2 border-green-500'
      }`}>
        System: {systemStatus}
      </div>

      {/* Panic Button */}
      <button
        onClick={handleClick}
        disabled={!connected || isProcessing}
        className={`
          relative
          w-64 h-64
          rounded-full
          text-white
          font-bold
          text-3xl
          uppercase
          tracking-wider
          transition-all
          duration-200
          border-4
          ${isHalted 
            ? 'bg-red-900 border-red-700 hover:bg-red-800' 
            : 'bg-red-600 border-red-500 hover:bg-red-700 panic-button-active'
          }
          ${!connected ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          ${isProcessing ? 'animate-pulse' : ''}
          shadow-2xl
          active:scale-95
        `}
      >
        <div className="flex flex-col items-center gap-2">
          {isProcessing ? (
            <>
              <svg className="animate-spin h-12 w-12 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>Processing...</span>
            </>
          ) : isHalted ? (
            <>
              <span className="text-5xl">🔒</span>
              <span>RESET</span>
              <span className="text-sm font-normal">Click to Resume</span>
            </>
          ) : (
            <>
              <span className="text-5xl">⚠️</span>
              <span>PANIC</span>
              <span className="text-sm font-normal">Emergency Halt</span>
            </>
          )}
        </div>
      </button>

      {/* Warning Text */}
      {!isHalted && (
        <p className="text-slate-400 text-center max-w-md">
          ⚠️ Pressing this button will immediately halt all trading and cancel all open orders.
        </p>
      )}

      {/* Confirmation Dialog */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-lg p-8 max-w-md border-2 border-red-500 shadow-2xl">
            <h2 className="text-2xl font-bold text-red-500 mb-4">
              {isHalted ? '⚠️ RESET PANIC?' : '🚨 CONFIRM PANIC?'}
            </h2>
            <p className="text-slate-300 mb-6">
              {isHalted 
                ? 'This will resume trading operations. Are you sure you want to continue?'
                : 'This will immediately halt all trading and cancel all open orders. This action cannot be undone easily.'
              }
            </p>
            <div className="flex gap-4">
              <button
                onClick={handleCancel}
                className="flex-1 px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-semibold transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                className={`flex-1 px-6 py-3 rounded-lg font-semibold transition-colors ${
                  isHalted
                    ? 'bg-green-600 hover:bg-green-700 text-white'
                    : 'bg-red-600 hover:bg-red-700 text-white'
                }`}
              >
                {isHalted ? 'Yes, Reset' : 'Yes, HALT'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default PanicButton
