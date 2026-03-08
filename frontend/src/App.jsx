import React from 'react'
import PanicButton from './components/PanicButton'
import { SocketProvider } from './context/SocketContext'

function App() {
  return (
    <SocketProvider>
      <div className="min-h-screen bg-slate-900 text-white">
        <header className="bg-slate-800 border-b border-slate-700 px-6 py-4">
          <h1 className="text-2xl font-bold text-slate-100">
            AI Lead Scalper - War Room
          </h1>
        </header>
        
        <main className="p-6">
          <div className="flex justify-center items-start">
            <PanicButton />
          </div>
        </main>
      </div>
    </SocketProvider>
  )
}

export default App
