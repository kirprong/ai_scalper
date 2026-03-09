import React, { useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { metricsApi, tradingApi, detectionApi } from '../services/api';
import useTradingStore from '../stores/tradingStore';
import { PnLChart } from '../components/charts';
import { useSocket } from '../context/SocketContext';
import PnLPanel from '../components/PnLPanel';
import MLAccuracyPanel from '../components/MLAccuracyPanel';

/**
 * Dashboard page - Main overview of trading system
 * Now includes comprehensive PnL & ML Accuracy panels
 */
const Dashboard = () => {
    const { metrics, setMetrics, activeSignals, setActiveSignals } = useTradingStore();

    // Fetch trading metrics
    const { data: metricsData, isLoading: metricsLoading } = useQuery({
        queryKey: ['metrics'],
        queryFn: metricsApi.getTradingMetrics,
        refetchInterval: 5000, // Refresh every 5 seconds
    });

    // Fetch positions
    const { data: positionsData, isLoading: positionsLoading } = useQuery({
        queryKey: ['positions'],
        queryFn: tradingApi.getPositions,
        refetchInterval: 3000,
    });

    // Fetch active signals
    const { data: signalsData, isLoading: signalsLoading } = useQuery({
        queryKey: ['signals'],
        queryFn: detectionApi.getActiveSignals,
        refetchInterval: 2000,
    });

    // Fetch PnL data
    const { data: pnlData, isLoading: pnlLoading } = useQuery({
        queryKey: ['pnl'],
        queryFn: () => metricsApi.getPnL({ period: '7d' }),
        refetchInterval: 10000,
    });

    // Update store when data changes
    useEffect(() => {
        if (metricsData?.data) {
            setMetrics(metricsData.data);
        }
    }, [metricsData, setMetrics]);

    useEffect(() => {
        if (signalsData?.data) {
            setActiveSignals(signalsData.data);
        }
    }, [signalsData, setActiveSignals]);

    // Socket connection for real-time updates
    const { connected } = useSocket();

    // Transform PnL data for Lightweight Charts
    const pnlChartData = useMemo(() => {
        if (pnlData?.data && Array.isArray(pnlData.data)) {
            return pnlData.data.map((item) => ({
                time: item.time || Math.floor(new Date(item.timestamp).getTime() / 1000),
                pnl: item.pnl || item.cumulativePnl || item.value,
            }));
        }

        // Generate sample data if no real data available
        const now = Math.floor(Date.now() / 1000);
        const interval = 3600; // 1 hour
        let cumulativePnl = 0;

        return Array.from({ length: 24 }, (_, i) => {
            const tradePnl = (Math.random() - 0.4) * 50;
            cumulativePnl += tradePnl;
            return {
                time: now - (24 - i) * interval,
                pnl: cumulativePnl,
            };
        });
    }, [pnlData]);

    // Mock data for trades chart (will be replaced with real data)
    const performanceData = [
        { time: '00:00', pnl: 120, trades: 5 },
        { time: '04:00', pnl: 180, trades: 8 },
        { time: '08:00', pnl: 150, trades: 6 },
        { time: '12:00', pnl: 320, trades: 12 },
        { time: '16:00', pnl: 280, trades: 10 },
        { time: '20:00', pnl: 450, trades: 15 },
    ];

    return (
        <div className="space-y-6">
            {/* Page Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Dashboard</h1>
                    <p className="text-slate-400">System overview and performance metrics</p>
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-red-500'}`} />
                        <span className="text-sm text-slate-400">
                            {connected ? 'Connected' : 'Disconnected'}
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-slate-400">Last updated:</span>
                        <span className="text-sm text-emerald-400">{new Date().toLocaleTimeString()}</span>
                    </div>
                </div>
            </div>

            {/* Quick Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Total PnL Card */}
                <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                    <div className="flex items-center justify-between">
                        <span className="text-slate-400 text-sm">Total PnL</span>
                        <svg className="w-5 h-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                        </svg>
                    </div>
                    <div className="mt-2">
                        <span className="text-2xl font-bold text-emerald-400">
                            ${metrics?.totalPnL?.toLocaleString() || '0'}
                        </span>
                        <span className="text-emerald-500 text-sm ml-2">+12.5%</span>
                    </div>
                </div>

                {/* Win Rate Card */}
                <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                    <div className="flex items-center justify-between">
                        <span className="text-slate-400 text-sm">Win Rate</span>
                        <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    </div>
                    <div className="mt-2">
                        <span className="text-2xl font-bold text-blue-400">
                            {metrics?.winRate || 0}%
                        </span>
                    </div>
                </div>

                {/* Total Trades Card */}
                <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                    <div className="flex items-center justify-between">
                        <span className="text-slate-400 text-sm">Total Trades</span>
                        <svg className="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                        </svg>
                    </div>
                    <div className="mt-2">
                        <span className="text-2xl font-bold text-purple-400">
                            {metrics?.totalTrades || 0}
                        </span>
                    </div>
                </div>

                {/* Open Positions Card */}
                <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                    <div className="flex items-center justify-between">
                        <span className="text-slate-400 text-sm">Open Positions</span>
                        <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                        </svg>
                    </div>
                    <div className="mt-2">
                        <span className="text-2xl font-bold text-amber-400">
                            {metrics?.openPositions || 0}
                        </span>
                    </div>
                </div>
            </div>

            {/* PnL & Performance Panel - NEW */}
            <PnLPanel />

            {/* ML Accuracy Panel - NEW */}
            <MLAccuracyPanel />

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* PnL Chart */}
                <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                    <PnLChart
                        data={pnlChartData}
                        height={280}
                        title="Cumulative PnL"
                        showArea={true}
                        showStats={true}
                    />
                </div>

                {/* Trades Chart */}
                <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                    <h3 className="text-lg font-semibold text-white mb-4">Trades per Period</h3>
                    <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={performanceData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                            <XAxis dataKey="time" stroke="#94a3b8" />
                            <YAxis stroke="#94a3b8" />
                            <Tooltip
                                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
                                labelStyle={{ color: '#fff' }}
                            />
                            <Bar dataKey="trades" fill="#6366f1" />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Active Signals Section */}
            <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                <h3 className="text-lg font-semibold text-white mb-4">Active Signals</h3>
                {activeSignals.length > 0 ? (
                    <div className="space-y-2">
                        {activeSignals.map((signal) => (
                            <div key={signal.id} className="flex items-center justify-between p-3 bg-slate-700 rounded-lg">
                                <div className="flex items-center gap-3">
                                    <span className={`w-2 h-2 rounded-full ${signal.type === 'buy' ? 'bg-emerald-500' : 'bg-red-500'
                                        }`}></span>
                                    <span className="text-white font-medium">{signal.market}</span>
                                    <span className="text-slate-400 text-sm">{signal.type.toUpperCase()}</span>
                                </div>
                                <div className="flex items-center gap-4">
                                    <span className="text-slate-300">${signal.price}</span>
                                    <span className="text-emerald-400">{signal.confidence}% confidence</span>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-center py-8 text-slate-400">
                        No active signals at the moment
                    </div>
                )}
            </div>

            {/* Recent Positions */}
            <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                <h3 className="text-lg font-semibold text-white mb-4">Recent Positions</h3>
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="text-left text-slate-400 text-sm border-b border-slate-700">
                                <th className="pb-3">Market</th>
                                <th className="pb-3">Side</th>
                                <th className="pb-3">Size</th>
                                <th className="pb-3">Entry</th>
                                <th className="pb-3">Current</th>
                                <th className="pb-3">PnL</th>
                                <th className="pb-3">Status</th>
                            </tr>
                        </thead>
                        <tbody className="text-sm">
                            {positionsLoading ? (
                                <tr>
                                    <td colSpan={7} className="py-4 text-center text-slate-400">Loading...</td>
                                </tr>
                            ) : positionsData?.data?.length > 0 ? (
                                positionsData.data.slice(0, 5).map((position) => (
                                    <tr key={position.id} className="border-b border-slate-700">
                                        <td className="py-3 text-white">{position.market}</td>
                                        <td className={`py-3 ${position.side === 'YES' ? 'text-emerald-400' : 'text-red-400'}`}>
                                            {position.side}
                                        </td>
                                        <td className="py-3 text-slate-300">${position.size}</td>
                                        <td className="py-3 text-slate-300">${position.entryPrice}</td>
                                        <td className="py-3 text-slate-300">${position.currentPrice}</td>
                                        <td className={`py-3 ${position.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                            ${position.pnl}
                                        </td>
                                        <td className="py-3">
                                            <span className={`px-2 py-1 rounded text-xs ${position.status === 'open'
                                                ? 'bg-emerald-500/20 text-emerald-400'
                                                : 'bg-slate-600 text-slate-300'
                                                }`}>
                                                {position.status}
                                            </span>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={7} className="py-4 text-center text-slate-400">No positions found</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
