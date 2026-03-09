/**
 * PnLChart Component
 * Line/area chart for displaying profit/loss over time
 */

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { createChart } from 'lightweight-charts';
import { useSocket } from '../../context/SocketContext';
import {
    CHART_COLORS,
    getDefaultChartOptions,
    formatPrice,
    formatPercent,
    generateSamplePnLData,
    transformPnLData,
} from '../../utils/chartUtils';

/**
 * PnLChart - Performance chart showing cumulative PnL
 * @param {Object} props
 * @param {Array} props.data - PnL data points
 * @param {number} props.height - Chart height in pixels
 * @param {string} props.title - Chart title
 * @param {boolean} props.showArea - Show area fill under line
 * @param {boolean} props.showStats - Show statistics in header
 * @param {string} props.mode - Display mode: 'cumulative' or 'daily'
 * @param {Object} props.options - Additional chart options
 */
const PnLChart = ({
    data = [],
    height = 300,
    title = 'Cumulative PnL',
    showArea = true,
    showStats = true,
    mode = 'cumulative',
    options = {},
}) => {
    const chartContainerRef = useRef(null);
    const chartRef = useRef(null);
    const seriesRef = useRef(null);
    const baselineRef = useRef(null);

    const [isLoading, setIsLoading] = useState(true);
    const [crosshairData, setCrosshairData] = useState(null);
    const [useSampleData, setUseSampleData] = useState(false);

    const { socket, connected } = useSocket();

    // Transform and memoize PnL data
    const chartData = useMemo(() => {
        if (useSampleData || data.length === 0) {
            const sampleData = generateSamplePnLData(50);
            return {
                lineData: sampleData.map((d) => ({ time: d.time, value: d.pnl })),
                isPositive: sampleData[sampleData.length - 1]?.pnl >= 0,
            };
        }

        const transformed = transformPnLData(data);
        const values = data.map((d) => d.pnl || d.value || d.cumulativePnl || 0);
        const lastValue = values[values.length - 1] || 0;

        return {
            lineData: transformed.lineData,
            isPositive: lastValue >= 0,
        };
    }, [data, useSampleData]);

    // Calculate statistics
    const stats = useMemo(() => {
        if (chartData.lineData.length === 0) {
            return {
                totalPnl: 0,
                maxPnl: 0,
                minPnl: 0,
                avgPnl: 0,
                winRate: 0,
                tradeCount: 0,
            };
        }

        const values = chartData.lineData.map((d) => d.value);
        const totalPnl = values[values.length - 1] || 0;
        const maxPnl = Math.max(...values);
        const minPnl = Math.min(...values);
        const avgPnl = values.reduce((a, b) => a + b, 0) / values.length;

        // Calculate win rate from daily changes
        let wins = 0;
        let total = 0;
        for (let i = 1; i < values.length; i++) {
            const change = values[i] - values[i - 1];
            if (change !== 0) {
                total++;
                if (change > 0) wins++;
            }
        }
        const winRate = total > 0 ? (wins / total) * 100 : 0;

        return {
            totalPnl,
            maxPnl,
            minPnl,
            avgPnl,
            winRate,
            tradeCount: total,
        };
    }, [chartData]);

    // Initialize chart
    useEffect(() => {
        if (!chartContainerRef.current) return;

        const chartOptions = {
            ...getDefaultChartOptions(height),
            rightPriceScale: {
                ...getDefaultChartOptions(height).rightPriceScale,
                scaleMargins: {
                    top: 0.2,
                    bottom: 0.2,
                },
            },
            ...options,
        };

        const chart = createChart(chartContainerRef.current, chartOptions);
        chartRef.current = chart;

        // Add baseline at zero
        const baselineSeries = chart.addLineSeries({
            color: CHART_COLORS.textMuted,
            lineWidth: 1,
            lineStyle: 2, // Dashed
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
        });
        baselineRef.current = baselineSeries;

        // Add main series (area or line)
        if (showArea) {
            const areaSeries = chart.addAreaSeries({
                topColor: chartData.isPositive
                    ? 'rgba(34, 197, 94, 0.4)'
                    : 'rgba(239, 68, 68, 0.4)',
                bottomColor: chartData.isPositive
                    ? 'rgba(34, 197, 94, 0.0)'
                    : 'rgba(239, 68, 68, 0.0)',
                lineColor: chartData.isPositive
                    ? CHART_COLORS.profit
                    : CHART_COLORS.loss,
                lineWidth: 2,
                priceFormat: {
                    type: 'price',
                    precision: 2,
                    minMove: 0.01,
                },
            });
            seriesRef.current = areaSeries;
        } else {
            const lineSeries = chart.addLineSeries({
                color: chartData.isPositive
                    ? CHART_COLORS.profit
                    : CHART_COLORS.loss,
                lineWidth: 2,
                priceFormat: {
                    type: 'price',
                    precision: 2,
                    minMove: 0.01,
                },
            });
            seriesRef.current = lineSeries;
        }

        // Subscribe to crosshair moves
        chart.subscribeCrosshairMove((param) => {
            if (!param.point || !param.time) {
                setCrosshairData(null);
                return;
            }

            const seriesData = param.seriesData.get(seriesRef.current);
            if (seriesData) {
                setCrosshairData({
                    time: param.time,
                    value: seriesData.value,
                });
            }
        });

        // Handle resize
        const handleResize = () => {
            if (chartRef.current && chartContainerRef.current) {
                chartRef.current.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                });
            }
        };

        const resizeObserver = new ResizeObserver(handleResize);
        resizeObserver.observe(chartContainerRef.current);

        setIsLoading(false);

        return () => {
            resizeObserver.disconnect();
            chart.remove();
            chartRef.current = null;
            seriesRef.current = null;
            baselineRef.current = null;
        };
    }, [height, showArea, options, chartData.isPositive]);

    // Update chart data
    useEffect(() => {
        if (!seriesRef.current || chartData.lineData.length === 0) return;

        // Set main series data
        seriesRef.current.setData(chartData.lineData);

        // Set baseline at zero
        if (baselineRef.current && chartData.lineData.length > 0) {
            const firstTime = chartData.lineData[0].time;
            const lastTime = chartData.lineData[chartData.lineData.length - 1].time;
            baselineRef.current.setData([
                { time: firstTime, value: 0 },
                { time: lastTime, value: 0 },
            ]);
        }

        // Update series colors based on current value
        if (showArea && seriesRef.current) {
            seriesRef.current.applyOptions({
                topColor: chartData.isPositive
                    ? 'rgba(34, 197, 94, 0.4)'
                    : 'rgba(239, 68, 68, 0.4)',
                bottomColor: chartData.isPositive
                    ? 'rgba(34, 197, 94, 0.0)'
                    : 'rgba(239, 68, 68, 0.0)',
                lineColor: chartData.isPositive
                    ? CHART_COLORS.profit
                    : CHART_COLORS.loss,
            });
        }

        // Fit content
        if (chartRef.current) {
            chartRef.current.timeScale().fitContent();
        }
    }, [chartData, showArea]);

    // Real-time updates via Socket.io
    useEffect(() => {
        if (!socket || !connected || !seriesRef.current) return;

        const handlePnLUpdate = (update) => {
            if (!seriesRef.current) return;

            seriesRef.current.update({
                time: update.time,
                value: update.pnl || update.value,
            });
        };

        socket.on('pnl_update', handlePnLUpdate);
        socket.on('trade_closed', handlePnLUpdate);

        return () => {
            socket.off('pnl_update', handlePnLUpdate);
            socket.off('trade_closed', handlePnLUpdate);
        };
    }, [socket, connected]);

    // Toggle sample data
    const toggleSampleData = useCallback(() => {
        setUseSampleData((prev) => !prev);
    }, []);

    // Fit content
    const fitContent = useCallback(() => {
        if (chartRef.current) {
            chartRef.current.timeScale().fitContent();
        }
    }, []);

    return (
        <div className="pnl-chart-container relative">
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-4">
                    <h3 className="text-sm font-medium text-slate-400">{title}</h3>
                    {showStats && (
                        <div className="flex items-center gap-4 text-xs">
                            <span className="text-slate-500">
                                Total: <span className={stats.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                                    {formatPrice(stats.totalPnl)}
                                </span>
                            </span>
                            <span className="text-slate-500">
                                Max: <span className="text-green-400">{formatPrice(stats.maxPnl)}</span>
                            </span>
                            <span className="text-slate-500">
                                Min: <span className="text-red-400">{formatPrice(stats.minPnl)}</span>
                            </span>
                            <span className="text-slate-500">
                                Win Rate: <span className="text-blue-400">{formatPercent(stats.winRate)}</span>
                            </span>
                            {crosshairData && (
                                <span className="text-slate-500">
                                    Selected: <span className={crosshairData.value >= 0 ? 'text-green-400' : 'text-red-400'}>
                                        {formatPrice(crosshairData.value)}
                                    </span>
                                </span>
                            )}
                        </div>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    <button
                        onClick={fitContent}
                        className="px-2 py-1 text-xs bg-slate-700 hover:bg-slate-600 rounded text-slate-300 transition-colors"
                    >
                        Fit
                    </button>
                    <button
                        onClick={toggleSampleData}
                        className={`px-2 py-1 text-xs rounded transition-colors ${useSampleData
                                ? 'bg-blue-600 text-white'
                                : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
                            }`}
                    >
                        Sample
                    </button>
                </div>
            </div>

            {/* Chart Container */}
            <div
                ref={chartContainerRef}
                className="chart-wrapper rounded-lg overflow-hidden bg-slate-900"
                style={{ height: `${height}px` }}
            />

            {/* Loading Overlay */}
            {isLoading && (
                <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80">
                    <div className="flex items-center gap-2">
                        <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                        <span className="text-slate-400">Loading...</span>
                    </div>
                </div>
            )}

            {/* Summary Card */}
            {showStats && (
                <div className="absolute bottom-4 left-4 bg-slate-800/90 backdrop-blur-sm rounded-lg p-3 shadow-lg">
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                        <div className="text-slate-500">Total PnL:</div>
                        <div className={`font-medium ${stats.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {formatPrice(stats.totalPnl)}
                        </div>
                        <div className="text-slate-500">Win Rate:</div>
                        <div className="font-medium text-blue-400">{formatPercent(stats.winRate)}</div>
                        <div className="text-slate-500">Trades:</div>
                        <div className="font-medium text-white">{stats.tradeCount}</div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default PnLChart;
