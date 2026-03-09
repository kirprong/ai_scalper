/**
 * PnLPanel Component
 * Comprehensive PnL and trading performance metrics panel
 */

import React, { useState, useMemo, useCallback } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Sector } from 'recharts';
import { PnLChart } from './charts';
import { usePerformance, TIME_PERIODS, TIME_PERIOD_LABELS } from '../hooks/usePerformance';
import { formatCurrency, formatPercent, formatRatio, getPerformanceGrade } from '../utils/metricsUtils';

/**
 * Metric Card Component
 */
const MetricCard = ({ label, value, subValue, icon, color = 'blue', trend, onClick }) => {
    const colorClasses = {
        green: 'text-emerald-400',
        red: 'text-red-400',
        blue: 'text-blue-400',
        amber: 'text-amber-400',
        purple: 'text-purple-400',
        slate: 'text-slate-400',
    };

    const trendClasses = {
        up: 'text-emerald-400',
        down: 'text-red-400',
        neutral: 'text-slate-400',
    };

    return (
        <div
            className={`bg-slate-800 rounded-lg p-4 border border-slate-700 ${onClick ? 'cursor-pointer hover:border-slate-600 transition-colors' : ''}`}
            onClick={onClick}
        >
            <div className="flex items-center justify-between mb-2">
                <span className="text-slate-400 text-sm">{label}</span>
                {icon && <span className="text-slate-500">{icon}</span>}
            </div>
            <div className="flex items-end gap-2">
                <span className={`text-2xl font-bold ${colorClasses[color]}`}>
                    {value}
                </span>
                {subValue && (
                    <span className="text-sm text-slate-500 mb-1">{subValue}</span>
                )}
            </div>
            {trend !== undefined && (
                <div className={`text-xs mt-1 ${trend >= 0 ? trendClasses.up : trendClasses.down}`}>
                    {trend >= 0 ? '↑' : '↓'} {Math.abs(trend).toFixed(2)}%
                </div>
            )}
        </div>
    );
};

/**
 * Timeframe Selector Component
 */
const TimeframeSelector = ({ selected, onChange }) => {
    const timeframes = [
        { key: TIME_PERIODS.TODAY, label: 'Today' },
        { key: TIME_PERIODS.WEEK, label: '7D' },
        { key: TIME_PERIODS.MONTH, label: '30D' },
        { key: TIME_PERIODS.QUARTER, label: '90D' },
        { key: TIME_PERIODS.ALL, label: 'All' },
    ];

    return (
        <div className="flex gap-1 bg-slate-700 rounded-lg p-1">
            {timeframes.map((tf) => (
                <button
                    key={tf.key}
                    onClick={() => onChange(tf.key)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${selected === tf.key
                        ? 'bg-blue-600 text-white'
                        : 'text-slate-400 hover:text-white hover:bg-slate-600'
                        }`}
                >
                    {tf.label}
                </button>
            ))}
        </div>
    );
};

/**
 * PnL Breakdown Chart
 */
const PnLBreakdownChart = ({ data, type = 'daily' }) => {
    const chartData = useMemo(() => {
        if (!data || data.length === 0) return [];

        return data.slice(-14).map((item) => ({
            name: type === 'daily'
                ? new Date(item.date).toLocaleDateString('en-US', { weekday: 'short' })
                : type === 'weekly'
                    ? `W${item.week.slice(-2)}`
                    : item.month,
            pnl: item.pnl,
            color: item.pnl >= 0 ? '#22c55e' : '#ef4444',
        }));
    }, [data, type]);

    if (chartData.length === 0) {
        return (
            <div className="h-48 flex items-center justify-center text-slate-500">
                No data available
            </div>
        );
    }

    return (
        <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="name" stroke="#64748b" fontSize={10} />
                <YAxis stroke="#64748b" fontSize={10} />
                <Tooltip
                    contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                    labelStyle={{ color: '#fff' }}
                    formatter={(value) => [formatCurrency(value), 'PnL']}
                />
                <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                </Bar>
            </BarChart>
        </ResponsiveContainer>
    );
};

/**
 * Win/Loss Pie Chart
 */
const WinLossChart = ({ wins, losses }) => {
    const data = [
        { name: 'Wins', value: wins, color: '#22c55e' },
        { name: 'Losses', value: losses, color: '#ef4444' },
    ].filter(d => d.value > 0);

    const total = wins + losses;

    if (total === 0) {
        return (
            <div className="h-32 flex items-center justify-center text-slate-500 text-sm">
                No trades yet
            </div>
        );
    }

    return (
        <div className="flex items-center gap-4">
            <PieChart width={100} height={100}>
                <Pie
                    data={data}
                    cx={50}
                    cy={50}
                    innerRadius={30}
                    outerRadius={45}
                    paddingAngle={2}
                    dataKey="value"
                >
                    {data.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                </Pie>
            </PieChart>
            <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-emerald-500" />
                    <span className="text-sm text-slate-400">Wins: {wins}</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-red-500" />
                    <span className="text-sm text-slate-400">Losses: {losses}</span>
                </div>
            </div>
        </div>
    );
};

/**
 * Performance Grade Badge
 */
const PerformanceGrade = ({ grade }) => {
    const gradeColors = {
        'A+': 'bg-emerald-500 text-white',
        'A': 'bg-emerald-600 text-white',
        'A-': 'bg-emerald-700 text-white',
        'B+': 'bg-blue-500 text-white',
        'B': 'bg-blue-600 text-white',
        'B-': 'bg-blue-700 text-white',
        'C+': 'bg-amber-500 text-white',
        'C': 'bg-amber-600 text-white',
        'C-': 'bg-amber-700 text-white',
        'D': 'bg-red-600 text-white',
        'F': 'bg-red-700 text-white',
    };

    return (
        <div className={`px-3 py-1 rounded-lg font-bold text-lg ${gradeColors[grade] || 'bg-slate-600 text-white'}`}>
            {grade}
        </div>
    );
};

/**
 * Stats Table Component
 */
const StatsTable = ({ stats }) => {
    const rows = [
        { label: 'Total Trades', value: stats.totalTrades },
        { label: 'Winning Trades', value: stats.winningTrades, color: 'text-emerald-400' },
        { label: 'Losing Trades', value: stats.losingTrades, color: 'text-red-400' },
        { label: 'Largest Win', value: formatCurrency(stats.largestWin), color: 'text-emerald-400' },
        { label: 'Largest Loss', value: formatCurrency(stats.largestLoss), color: 'text-red-400' },
        { label: 'Avg Trade', value: formatCurrency(stats.avgTrade) },
        { label: 'Avg Win', value: formatCurrency(stats.avgWin), color: 'text-emerald-400' },
        { label: 'Avg Loss', value: formatCurrency(stats.avgLoss), color: 'text-red-400' },
        { label: 'Expectancy', value: formatCurrency(stats.expectancy) },
        { label: 'Risk/Reward', value: formatRatio(stats.riskRewardRatio) },
    ];

    return (
        <div className="grid grid-cols-2 gap-2">
            {rows.map((row, index) => (
                <div key={index} className="flex justify-between py-1.5 border-b border-slate-700">
                    <span className="text-slate-400 text-sm">{row.label}</span>
                    <span className={`text-sm font-medium ${row.color || 'text-white'}`}>
                        {row.value}
                    </span>
                </div>
            ))}
        </div>
    );
};

/**
 * PnLPanel - Main Component
 */
const PnLPanel = ({ className = '' }) => {
    const [timeframe, setTimeframe] = useState(TIME_PERIODS.WEEK);
    const [showDetails, setShowDetails] = useState(false);

    const {
        performance,
        isLoading,
        error,
        lastUpdate,
        isConnected,
        refreshAll,
    } = usePerformance({ period: timeframe });

    // Calculate performance grade
    const grade = useMemo(() => {
        if (!performance) return 'N/A';
        return getPerformanceGrade(performance);
    }, [performance]);

    // Determine PnL color
    const pnlColor = useMemo(() => {
        if (!performance) return 'slate';
        return performance.totalPnL >= 0 ? 'green' : 'red';
    }, [performance]);

    // Loading state
    if (isLoading && !performance) {
        return (
            <div className={`bg-slate-800 rounded-lg p-6 border border-slate-700 ${className}`}>
                <div className="flex items-center justify-center h-64">
                    <div className="flex items-center gap-3">
                        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                        <span className="text-slate-400">Loading performance data...</span>
                    </div>
                </div>
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div className={`bg-slate-800 rounded-lg p-6 border border-slate-700 ${className}`}>
                <div className="flex flex-col items-center justify-center h-64 gap-4">
                    <span className="text-red-400">Error loading performance data</span>
                    <button
                        onClick={refreshAll}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-sm transition-colors"
                    >
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className={`bg-slate-800 rounded-lg border border-slate-700 ${className}`}>
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-slate-700">
                <div className="flex items-center gap-3">
                    <h2 className="text-lg font-semibold text-white">PnL & Performance</h2>
                    <PerformanceGrade grade={grade} />
                </div>
                <div className="flex items-center gap-3">
                    <TimeframeSelector selected={timeframe} onChange={setTimeframe} />
                    <button
                        onClick={refreshAll}
                        className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
                        title="Refresh"
                    >
                        <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                    </button>
                </div>
            </div>

            {/* Main Metrics Grid */}
            <div className="p-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <MetricCard
                        label="Total PnL"
                        value={formatCurrency(performance.totalPnL)}
                        color={pnlColor}
                        icon={
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                            </svg>
                        }
                    />
                    <MetricCard
                        label="Win Rate"
                        value={formatPercent(performance.winRate)}
                        color={performance.winRate >= 50 ? 'green' : 'red'}
                        icon={
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        }
                    />
                    <MetricCard
                        label="Profit Factor"
                        value={formatRatio(performance.profitFactor)}
                        color={performance.profitFactor >= 1.5 ? 'green' : performance.profitFactor >= 1 ? 'amber' : 'red'}
                        icon={
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                            </svg>
                        }
                    />
                    <MetricCard
                        label="Sharpe Ratio"
                        value={formatRatio(performance.sharpeRatio)}
                        color={performance.sharpeRatio >= 1 ? 'green' : performance.sharpeRatio >= 0 ? 'amber' : 'red'}
                        icon={
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                        }
                    />
                </div>

                {/* Secondary Metrics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <MetricCard
                        label="Max Drawdown"
                        value={formatPercent(performance.maxDrawdownPercent)}
                        color={performance.maxDrawdownPercent <= 10 ? 'green' : performance.maxDrawdownPercent <= 20 ? 'amber' : 'red'}
                    />
                    <MetricCard
                        label="Realized PnL"
                        value={formatCurrency(performance.realizedPnL)}
                        color={performance.realizedPnL >= 0 ? 'green' : 'red'}
                    />
                    <MetricCard
                        label="Unrealized PnL"
                        value={formatCurrency(performance.unrealizedPnL)}
                        color={performance.unrealizedPnL >= 0 ? 'green' : 'red'}
                    />
                    <MetricCard
                        label="Total Trades"
                        value={performance.totalTrades}
                        color="purple"
                    />
                </div>

                {/* Charts Section */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
                    {/* PnL Chart */}
                    <div className="lg:col-span-2 bg-slate-900 rounded-lg p-4">
                        <h3 className="text-sm font-medium text-slate-400 mb-3">Cumulative PnL</h3>
                        <PnLChart
                            data={performance.equityCurve.map((d, i) => ({
                                time: d.time,
                                pnl: d.value,
                            }))}
                            height={200}
                            showStats={false}
                            showArea={true}
                        />
                    </div>

                    {/* Win/Loss Distribution */}
                    <div className="bg-slate-900 rounded-lg p-4">
                        <h3 className="text-sm font-medium text-slate-400 mb-3">Win/Loss Distribution</h3>
                        <div className="flex flex-col items-center justify-center h-[200px]">
                            <WinLossChart
                                wins={performance.winningTrades}
                                losses={performance.losingTrades}
                            />
                            <div className="mt-4 text-center">
                                <span className="text-2xl font-bold text-white">
                                    {formatPercent(performance.winRate)}
                                </span>
                                <p className="text-xs text-slate-500 mt-1">Win Rate</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Daily PnL Breakdown */}
                <div className="bg-slate-900 rounded-lg p-4 mb-6">
                    <h3 className="text-sm font-medium text-slate-400 mb-3">Daily PnL Breakdown</h3>
                    <PnLBreakdownChart data={performance.dailyPnL} type="daily" />
                </div>

                {/* Detailed Stats Toggle */}
                <div className="border-t border-slate-700 pt-4">
                    <button
                        onClick={() => setShowDetails(!showDetails)}
                        className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
                    >
                        <svg
                            className={`w-4 h-4 transition-transform ${showDetails ? 'rotate-180' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                        {showDetails ? 'Hide' : 'Show'} Detailed Statistics
                    </button>

                    {showDetails && (
                        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="bg-slate-900 rounded-lg p-4">
                                <h4 className="text-sm font-medium text-slate-400 mb-3">Trade Statistics</h4>
                                <StatsTable stats={performance} />
                            </div>
                            <div className="bg-slate-900 rounded-lg p-4">
                                <h4 className="text-sm font-medium text-slate-400 mb-3">Risk Metrics</h4>
                                <div className="grid grid-cols-2 gap-2">
                                    <div className="flex justify-between py-1.5 border-b border-slate-700">
                                        <span className="text-slate-400 text-sm">Sharpe Ratio</span>
                                        <span className="text-sm font-medium text-white">{formatRatio(performance.sharpeRatio)}</span>
                                    </div>
                                    <div className="flex justify-between py-1.5 border-b border-slate-700">
                                        <span className="text-slate-400 text-sm">Max Drawdown</span>
                                        <span className="text-sm font-medium text-red-400">{formatPercent(performance.maxDrawdownPercent)}</span>
                                    </div>
                                    <div className="flex justify-between py-1.5 border-b border-slate-700">
                                        <span className="text-slate-400 text-sm">Profit Factor</span>
                                        <span className="text-sm font-medium text-white">{formatRatio(performance.profitFactor)}</span>
                                    </div>
                                    <div className="flex justify-between py-1.5 border-b border-slate-700">
                                        <span className="text-slate-400 text-sm">Expectancy</span>
                                        <span className={`text-sm font-medium ${performance.expectancy >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                            {formatCurrency(performance.expectancy)}
                                        </span>
                                    </div>
                                    <div className="flex justify-between py-1.5 border-b border-slate-700">
                                        <span className="text-slate-400 text-sm">Risk/Reward</span>
                                        <span className="text-sm font-medium text-white">{formatRatio(performance.riskRewardRatio)}</span>
                                    </div>
                                    <div className="flex justify-between py-1.5 border-b border-slate-700">
                                        <span className="text-slate-400 text-sm">Avg Trade</span>
                                        <span className={`text-sm font-medium ${performance.avgTrade >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                            {formatCurrency(performance.avgTrade)}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Footer */}
            <div className="px-4 py-3 border-t border-slate-700 flex items-center justify-between text-xs text-slate-500">
                <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-red-500'}`} />
                    <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
                </div>
                {lastUpdate && (
                    <span>Last updated: {new Date(lastUpdate).toLocaleTimeString()}</span>
                )}
            </div>
        </div>
    );
};

export default PnLPanel;
