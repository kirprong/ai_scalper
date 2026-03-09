import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';

/**
 * Navigation sidebar component
 * Provides navigation between main sections of the application
 */
const Navigation = () => {
    const location = useLocation();

    const navItems = [
        {
            path: '/',
            label: 'Dashboard',
            icon: (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                </svg>
            ),
        },
        {
            path: '/trading',
            label: 'Trading',
            icon: (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
            ),
        },
        {
            path: '/settings',
            label: 'Settings',
            icon: (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
            ),
        },
    ];

    return (
        <nav className="w-64 bg-slate-800 border-r border-slate-700 min-h-screen">
            {/* Logo/Brand */}
            <div className="p-4 border-b border-slate-700">
                <h1 className="text-xl font-bold text-white flex items-center gap-2">
                    <svg className="w-6 h-6 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    AI Lead Scalper
                </h1>
                <p className="text-xs text-slate-400 mt-1">War Room v1.0</p>
            </div>

            {/* Navigation Links */}
            <div className="p-4">
                <ul className="space-y-2">
                    {navItems.map((item) => (
                        <li key={item.path}>
                            <NavLink
                                to={item.path}
                                className={({ isActive }) =>
                                    `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${isActive
                                        ? 'bg-emerald-600 text-white'
                                        : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                                    }`
                                }
                            >
                                {item.icon}
                                <span className="font-medium">{item.label}</span>
                            </NavLink>
                        </li>
                    ))}
                </ul>
            </div>

            {/* Status Section */}
            <div className="absolute bottom-0 left-0 w-64 p-4 border-t border-slate-700 bg-slate-800">
                <div className="flex items-center gap-2 text-sm">
                    <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
                    <span className="text-slate-400">System Active</span>
                </div>
                <div className="mt-2 text-xs text-slate-500">
                    Last update: {new Date().toLocaleTimeString()}
                </div>
            </div>
        </nav>
    );
};

export default Navigation;
