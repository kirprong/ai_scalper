/**
 * VolumeChart Component
 * Standalone volume histogram chart
 */

import React, { useEffect, useRef, useState, useMemo } from 'react';
import { createChart } from 'lightweight-charts';
import { useSocket } from '../../context/SocketContext';
import {
    CHART_COLORS,
    getDefaultChartOptions,
    formatVolume,
    generateSampleData,
    transformOHLCVData,
} from '../../utils/chartUtils';

/**
 * VolumeChart - Standalone volume histogram
 * @param {Object} props
 * @param {Array} props.data - Volume data (can be OHLCV or just volume)
 * @param {number} props.height - Chart height in pixels
 * @param {string} props.title - Chart title
 * @param {boolean} props.showTotal - Show total volume in header
 * @param {Object} props.options - Additional chart options
 */
const VolumeChart = ({
    data = [],
    height = 200,
    title = 'Volume',
    showTotal = true,
    options = {},
}) => {
    const chartContainerRef = useRef(null);
    const chartRef = useRef(null);
    const volumeSeriesRef = useRef(null);

    const [isLoading, setIsLoading] = useState(true);
    const [crosshairVolume, setCrosshairVolume] = useState(null);
    const [useSampleData, setUseSampleData] = useState(false);

    const { socket, connected } = useSocket();

    // Transform data for volume chart
    const volumeData = useMemo(() => {
        if (useSampleData || data.length === 0) {
            const sampleData = generateSampleData(100);
            return transformOHLCVData(sampleData).volumeData;
        }

        // Check if data is OHLCV or already volume format
        if (data[0]?.volume !== undefined) {
            return transformOHLCVData(data).volumeData;
        }

        // Assume data is already in volume format
        return data.map((item) => ({
            time: item.time,
            value: item.value || item.volume,
            color: item.color || CHART_COLORS.volumeBullish,
        }));
    }, [data, useSampleData]);

    // Calculate total volume
    const totalVolume = useMemo(() => {
        return volumeData.reduce((sum, item) => sum + (item.value || 0), 0);
    }, [volumeData]);

    // Calculate average volume
    const avgVolume = useMemo(() => {
        return volumeData.length > 0 ? totalVolume / volumeData.length : 0;
    }, [volumeData, totalVolume]);

    // Initialize chart
    useEffect(() => {
        if (!chartContainerRef.current) return;

        const chartOptions = {
            ...getDefaultChartOptions(height),
            rightPriceScale: {
                ...getDefaultChartOptions(height).rightPriceScale,
                scaleMargins: {
                    top: 0.1,
                    bottom: 0.1,
                },
            },
            ...options,
        };

        const chart = createChart(chartContainerRef.current, chartOptions);
        chartRef.current = chart;

        // Add volume histogram series
        const volumeSeries = chart.addHistogramSeries({
            color: CHART_COLORS.volumeBullish,
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: 'right',
        });
        volumeSeriesRef.current = volumeSeries;

        // Subscribe to crosshair moves
        chart.subscribeCrosshairMove((param) => {
            if (!param.point || !param.time) {
                setCrosshairVolume(null);
                return;
            }

            const volumeData = param.seriesData.get(volumeSeriesRef.current);
            if (volumeData) {
                setCrosshairVolume(volumeData.value);
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
            volumeSeriesRef.current = null;
        };
    }, [height, options]);

    // Update chart data
    useEffect(() => {
        if (!volumeSeriesRef.current || volumeData.length === 0) return;

        volumeSeriesRef.current.setData(volumeData);

        if (chartRef.current) {
            chartRef.current.timeScale().fitContent();
        }
    }, [volumeData]);

    // Real-time updates via Socket.io
    useEffect(() => {
        if (!socket || !connected || !volumeSeriesRef.current) return;

        const handleVolumeUpdate = (update) => {
            if (!volumeSeriesRef.current) return;

            volumeSeriesRef.current.update({
                time: update.time,
                value: update.volume || update.value,
                color: update.close >= update.open
                    ? CHART_COLORS.volumeBullish
                    : CHART_COLORS.volumeBearish,
            });
        };

        socket.on('price_update', handleVolumeUpdate);
        socket.on('volume_update', handleVolumeUpdate);

        return () => {
            socket.off('price_update', handleVolumeUpdate);
            socket.off('volume_update', handleVolumeUpdate);
        };
    }, [socket, connected]);

    // Toggle sample data
    const toggleSampleData = () => {
        setUseSampleData((prev) => !prev);
    };

    // Fit content
    const fitContent = () => {
        if (chartRef.current) {
            chartRef.current.timeScale().fitContent();
        }
    };

    return (
        <div className="volume-chart-container relative">
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-4">
                    <h3 className="text-sm font-medium text-slate-400">{title}</h3>
                    {showTotal && (
                        <div className="flex items-center gap-3 text-xs">
                            <span className="text-slate-500">
                                Total: <span className="text-white">{formatVolume(totalVolume)}</span>
                            </span>
                            <span className="text-slate-500">
                                Avg: <span className="text-white">{formatVolume(avgVolume)}</span>
                            </span>
                            {crosshairVolume !== null && (
                                <span className="text-slate-500">
                                    Selected: <span className="text-blue-400">{formatVolume(crosshairVolume)}</span>
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
        </div>
    );
};

export default VolumeChart;
