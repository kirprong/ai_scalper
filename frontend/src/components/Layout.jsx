import React from 'react';
import { Outlet } from 'react-router-dom';
import Navigation from './Navigation';
import PanicButton from './PanicButton';
import { SocketProvider } from '../context/SocketContext';

/**
 * Main layout component with navigation sidebar
 * Wraps all pages with consistent structure
 */
const Layout = () => {
    return (
        <SocketProvider>
            <div className="flex min-h-screen bg-slate-900 text-white">
                {/* Navigation Sidebar */}
                <Navigation />

                {/* Main Content Area */}
                <div className="flex-1 flex flex-col">
                    {/* Top Header Bar */}
                    <header className="bg-slate-800 border-b border-slate-700 px-6 py-4 flex items-center justify-between">
                        <div>
                            <h2 className="text-lg font-semibold text-slate-100">
                                Polymarket AI Lead-Lag Scalper
                            </h2>
                            <p className="text-sm text-slate-400">
                                Real-time trading dashboard
                            </p>
                        </div>

                        {/* Header Actions */}
                        <div className="flex items-center gap-4">
                            {/* Connection Status */}
                            <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 rounded-full">
                                <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
                                <span className="text-xs text-slate-300">Connected</span>
                            </div>

                            {/* Panic Button */}
                            <PanicButton />
                        </div>
                    </header>

                    {/* Page Content */}
                    <main className="flex-1 p-6 overflow-auto">
                        <Outlet />
                    </main>

                    {/* Footer */}
                    <footer className="bg-slate-800 border-t border-slate-700 px-6 py-3">
                        <div className="flex items-center justify-between text-xs text-slate-500">
                            <span>AI Lead Scalper v1.0.0</span>
                            <span>© 2024 Polymarket Trading System</span>
                        </div>
                    </footer>
                </div>
            </div>
        </SocketProvider>
    );
};

export default Layout;
