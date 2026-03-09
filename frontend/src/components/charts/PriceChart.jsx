/**
 * PriceChart Component
 * Main candlestick chart with volume overlay, signal markers, and Golden Rectangle boxes
 */

import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { createChart } from 'lightweight-charts';
import { useSocket } from '../../context/SocketContext';
import {
    CHART_COLORS,
    getDefaultChartOptions,
    getCandlestickSeriesOptions,
    getVolumeSeriesOptions,
    transformOHLCVData,
    transformSignalsToMarkers,
    formatPrice,
    formatVolume,
    generateSampleData,
    generateSampleSignals,
} from '../../utils/chartUtils';
import BoxOverlay, { BoxLegend, BoxList } from './BoxOverlay';
import { useBoxes } from '../../hooks/useBoxes';
import { BOX_STATUS } from '../../utils/boxUtils';

/**
 * PriceChart - Interactive candlestick chart with real-time updates
 * @param {Object} props
 * @param {Array} props.data - OHLCV candlestick data
 * @param {Array} props.signals - Trading signals for markers
 * @param {Array} props.boxes - Golden Rectangle boxes to display
 * @param {number} props.height - Chart height in pixels
 * @param {boolean} props.showVolume - Show volume histogram
 * @param {boolean} props.showSignals - Show signal markers
 * @param {boolean} props.showBoxes - Show Golden Rectangle boxes
 * @param {string} props.symbol - Trading symbol for display
 * @param {string} props.marketId - Market ID for box filtering
 * @param {Function} props.onCrosshairMove - Crosshair move callback
 * @param {Function} props.onRangeChange - Visible range change callback
 * @param {Function} props.onBoxClick - Box click callback
 * @param {Function} props.onBoxHover - Box hover callback
 * @param {Object} props.options - Additional chart options
 */
const PriceChart = ({
    data = [],
    signals = [],
    boxes: externalBoxes,
    height = 400,
    showVolume = true,
    showSignals = true,
    showBoxes = true,
    symbol = 'POLY',
    marketId = null,
    onCrosshairMove,
    onRangeChange,
    onBoxClick,
    onBoxHover,
    options = {},
}) => {
    const chartContainerRef = useRef(null);
    const chartRef = useRef(null);
    const candlestickSeriesRef = useRef(null);
    const volumeSeriesRef = useRef(null);

    const [isLoading, setIsLoading] = useState(true);
    const [crosshairInfo, setCrosshairInfo] = useState(null);
    const [useSampleData, setUseSampleData] = useState(false);
    const [boxesVisible, setBoxesVisible] = useState(showBoxes);
    const [boxFilterStatuses, setBoxFilterStatuses] = useState(null);

    const { socket, connected } = useSocket();

    // Use boxes hook for real-time box updates (if external boxes not provided)
    const {
        boxes: socketBoxes,
        statistics: boxStatistics,
        isLoading: boxesLoading,
    } = useBoxes({
        marketId,
        useSampleData: useSampleData && !externalBoxes,
        autoSubscribe: !externalBoxes,
    });

    // Use external boxes if provided, otherwise use socket boxes
    const boxes = useMemo(() => {
        return externalBoxes || socketBoxes;
    }, [externalBoxes, socketBoxes]);

    // Memoized transformed data
    const chartData = useMemo(() => {
        if (useSampleData || data.length === 0) {
            const sampleData = generateSampleData(100);
            const sampleSignals = generateSampleSignals(sampleData, 8);
            return {
                candlestick: transformOHLCVData(sampleData).candlestickData,
                volume: transformOHLCVData(sampleData).volumeData,
                markers: transformSignalsToMarkers(sampleSignals),
            };
        }

        const transformed = transformOHLCVData(data);
        return {
            candlestick: transformed.candlestickData,
            volume: transformed.volumeData,
            markers: transformSignalsToMarkers(signals),
        };
    }, [data, signals, useSampleData]);

    // Initialize chart
    useEffect(() => {
        if (!chartContainerRef.current) return;

        // Create chart
        const chartOptions = {
            ...getDefaultChartOptions(height),
            ...options,
        };

        const chart = createChart(chartContainerRef.current, chartOptions);
        chartRef.current = chart;

        // Add candlestick series
        const candlestickSeries = chart.addCandlestickSeries(getCandlestickSeriesOptions());
        candlestickSeriesRef.current = candlestickSeries;

        // Add volume series if enabled
        if (showVolume) {
            const volumeSeries = chart.addHistogramSeries(getVolumeSeriesOptions());
            volumeSeriesRef.current = volumeSeries;
        }

        // Subscribe to crosshair moves
        chart.subscribeCrosshairMove((param) => {
            if (!param.point || !param.time) {
                setCrosshairInfo(null);
                onCrosshairMove?.(null);
                return;
            }

            const candleData = param.seriesData.get(candlestickSeriesRef.current);
            const volumeData = volumeSeriesRef.current
                ? param.seriesData.get(volumeSeriesRef.current)
                : null;

            const info = {
                time: param.time,
                price: candleData?.close || 0,
                open: candleData?.open || 0,
                high: candleData?.high || 0,
                low: candleData?.low || 0,
                close: candleData?.close || 0,
                volume: volumeData?.value || 0,
                point: param.point,
            };

            setCrosshairInfo(info);
            onCrosshairMove?.(info);
        });

        // Subscribe to visible range changes
        if (onRangeChange) {
            chart.timeScale().subscribeVisibleLogicalRangeChange(onRangeChange);
        }

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
            candlestickSeriesRef.current = null;
            volumeSeriesRef.current = null;
        };
    }, [height, showVolume, options, onCrosshairMove, onRangeChange]);

    // Update chart data
    useEffect(() => {
        if (!candlestickSeriesRef.current) return;

        candlestickSeriesRef.current.setData(chartData.candlestick);

        if (volumeSeriesRef.current && chartData.volume.length > 0) {
            volumeSeriesRef.current.setData(chartData.volume);
        }

        // Add signal markers
        if (showSignals && chartData.markers.length > 0) {
            candlestickSeriesRef.current.setMarkers(chartData.markers);
        }

        // Fit content
        if (chartRef.current) {
            chartRef.current.timeScale().fitContent();
        }
    }, [chartData, showSignals]);

    // Real-time updates via Socket.io
    useEffect(() => {
        if (!socket || !connected || !candlestickSeriesRef.current) return;

        const handlePriceUpdate = (update) => {
            if (!candlestickSeriesRef.current) return;

            // Update candlestick
            candlestickSeriesRef.current.update({
                time: update.time,
                open: update.open,
                high: update.high,
                low: update.low,
                close: update.close,
            });

            // Update volume
            if (volumeSeriesRef.current && update.volume) {
                volumeSeriesRef.current.update({
                    time: update.time,
                    value: update.volume,
                    color: update.close >= update.open
                        ? CHART_COLORS.volumeBullish
                        : CHART_COLORS.volumeBearish,
                });
            }
        };

        socket.on('price_update', handlePriceUpdate);
        socket.on('candle_update', handlePriceUpdate);

        return () => {
            socket.off('price_update', handlePriceUpdate);
            socket.off('candle_update', handlePriceUpdate);
        };
    }, [socket, connected]);

    // Toggle sample data
    const toggleSampleData = useCallback(() => {
        setUseSampleData((prev) => !prev);
    }, []);

    // Toggle boxes visibility
    const toggleBoxes = useCallback(() => {
        setBoxesVisible((prev) => !prev);
    }, []);

    // Fit content
    const fitContent = useCallback(() => {
        if (chartRef.current) {
            chartRef.current.timeScale().fitContent();
        }
    }, []);

    // Scroll to real-time
    const scrollToRealTime = useCallback(() => {
        if (chartRef.current) {
            chartRef.current.timeScale().scrollToRealTime();
        }
    }, []);

    // Handle box click
    const handleBoxClick = useCallback((box) => {
        onBoxClick?.(box);
    }, [onBoxClick]);

    // Handle box hover
    const handleBoxHover = useCallback((box) => {
        onBoxHover?.(box);
    }, [onBoxHover]);

    // Toggle box status filter
    const toggleBoxStatusFilter = useCallback((status) => {
        setBoxFilterStatuses((prev) => {
            if (!prev) {
                return [status];
            }
            if (prev.includes(status)) {
                const newFilters = prev.filter((s) => s !== status);
                return newFilters.length > 0 ? newFilters : null;
            }
            return [...prev, status];
        });
    }, []);

    return (
        <div className="price-chart-container relative">
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-4">
                    <h3 className="text-lg font-semibold text-white">{symbol}</h3>
                    {crosshairInfo && (
                        <div className="flex items-center gap-4 text-sm">
                            <span className="text-slate-400">
                                O: <span className="text-white">{formatPrice(crosshairInfo.open)}</span>
                            </span>
                            <span className="text-slate-400">
                                H: <span className="text-green-400">{formatPrice(crosshairInfo.high)}</span>
                            </span>
                            <span className="text-slate-400">
                                L: <span className="text-red-400">{formatPrice(crosshairInfo.low)}</span>
                            </span>
                            <span className="text-slate-400">
                                C: <span className={crosshairInfo.close >= crosshairInfo.open ? 'text-green-400' : 'text-red-400'}>
                                    {formatPrice(crosshairInfo.close)}
                                </span>
                            </span>
                            {crosshairInfo.volume > 0 && (
                                <span className="text-slate-400">
                                    Vol: <span className="text-white">{formatVolume(crosshairInfo.volume)}</span>
                                </span>
                            )}
                        </div>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    <button
                        onClick={fitContent}
                        className="px-2 py-1 text-xs bg-slate-700 hover:bg-slate-600 rounded text-slate-300 transition-colors"
                        title="Fit Content"
                    >
                        Fit
                    </button>
                    <button
                        onClick={scrollToRealTime}
                        className="px-2 py-1 text-xs bg-slate-700 hover:bg-slate-600 rounded text-slate-300 transition-colors"
                        title="Scroll to Real-time"
                    >
                        Live
                    </button>
                    <button
                        onClick={toggleBoxes}
                        className={`px-2 py-1 text-xs rounded transition-colors ${boxesVisible
                            ? 'bg-amber-600 text-white'
                            : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
                            }`}
                        title="Toggle Golden Rectangles"
                    >
                        Boxes
                    </button>
                    <button
                        onClick={toggleSampleData}
                        className={`px-2 py-1 text-xs rounded transition-colors ${useSampleData
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
                            }`}
                        title="Toggle Sample Data"
                    >
                        Sample
                    </button>
                </div>
            </div>

            {/* Chart Container with Box Overlay */}
            <div className="relative">
                <div
                    ref={chartContainerRef}
                    className="chart-wrapper rounded-lg overflow-hidden bg-slate-900"
                    style={{ height: `${height}px` }}
                />

                {/* Box Overlay */}
                {chartRef.current && candlestickSeriesRef.current && boxesVisible && (
                    <BoxOverlay
                        boxes={boxes}
                        chart={chartRef.current}
                        series={candlestickSeriesRef.current}
                        visible={boxesVisible}
                        animated={true}
                        showLabels={true}
                        filterStatuses={boxFilterStatuses}
                        onBoxClick={handleBoxClick}
                        onBoxHover={handleBoxHover}
                        containerRef={chartContainerRef}
                    />
                )}

                {/* Loading Overlay */}
                {isLoading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80">
                        <div className="flex items-center gap-2">
                            <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                            <span className="text-slate-400">Loading chart...</span>
                        </div>
                    </div>
                )}

                {/* Connection Status */}
                <div className="absolute top-2 right-2 flex items-center gap-1">
                    <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
                    <span className="text-xs text-slate-500">
                        {connected ? 'Live' : 'Offline'}
                    </span>
                </div>

                {/* Box Statistics Overlay */}
                {boxesVisible && boxes.length > 0 && (
                    <div className="absolute top-2 left-2">
                        <div className="bg-slate-800/90 backdrop-blur-sm rounded px-2 py-1 text-xs">
                            <span className="text-slate-400">Boxes: </span>
                            <span className="text-white font-mono">{boxes.length}</span>
                            {boxStatistics && (
                                <>
                                    <span className="text-slate-500 mx-1">|</span>
                                    <span className="text-green-400 font-mono">
                                        {(boxStatistics.avgConfidence * 100).toFixed(0)}% avg
                                    </span>
                                </>
                            )}
                        </div>
                    </div>
                )}
            </div>

            {/* Box Legend (optional, shown below chart) */}
            {boxesVisible && boxes.length > 0 && (
                <div className="mt-2 flex gap-4">
                    <BoxLegend showLabels={true} statistics={boxStatistics} />

                    {/* Quick filters */}
                    <div className="flex items-center gap-2 bg-slate-800/90 backdrop-blur-sm rounded-lg p-2">
                        <span className="text-xs text-slate-400">Filter:</span>
                        {Object.values(BOX_STATUS).map((status) => (
                            <button
                                key={status}
                                onClick={() => toggleBoxStatusFilter(status)}
                                className={`px-2 py-0.5 text-xs rounded transition-colors ${boxFilterStatuses?.includes(status)
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                                    }`}
                            >
                                {status}
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default PriceChart;
