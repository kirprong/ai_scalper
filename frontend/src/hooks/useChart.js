/**
 * Custom hook for Lightweight Charts management
 * Handles chart creation, updates, and cleanup
 */

import { useRef, useEffect, useCallback, useState } from 'react';
import { createChart } from 'lightweight-charts';
import {
    getDefaultChartOptions,
    CHART_COLORS,
} from '../utils/chartUtils';

/**
 * Hook for managing a Lightweight Chart instance
 * @param {Object} options - Chart configuration options
 * @returns {Object} - Chart management utilities
 */
export const useChart = (options = {}) => {
    const chartContainerRef = useRef(null);
    const chartRef = useRef(null);
    const seriesRef = useRef({});
    const [isReady, setIsReady] = useState(false);
    const [crosshairData, setCrosshairData] = useState(null);

    // Initialize chart
    const initChart = useCallback((container) => {
        if (!container || chartRef.current) return;

        const chartOptions = {
            ...getDefaultChartOptions(options.height || 400),
            ...options,
        };

        const chart = createChart(container, chartOptions);
        chartRef.current = chart;
        chartContainerRef.current = container;
        setIsReady(true);

        // Set up crosshair subscription
        chart.subscribeCrosshairMove((param) => {
            if (!param.point || !param.time) {
                setCrosshairData(null);
                return;
            }

            const data = {
                point: param.point,
                time: param.time,
                seriesData: {},
            };

            // Extract data from each series
            param.seriesData.forEach((value, series) => {
                const seriesName = Object.keys(seriesRef.current).find(
                    (key) => seriesRef.current[key] === series
                );
                if (seriesName) {
                    data.seriesData[seriesName] = value;
                }
            });

            setCrosshairData(data);
        });

        // Handle resize
        const handleResize = () => {
            if (chartRef.current && container) {
                chartRef.current.applyOptions({
                    width: container.clientWidth,
                });
            }
        };

        const resizeObserver = new ResizeObserver(handleResize);
        resizeObserver.observe(container);

        return () => {
            resizeObserver.disconnect();
        };
    }, [options]);

    // Cleanup chart
    const cleanupChart = useCallback(() => {
        if (chartRef.current) {
            chartRef.current.remove();
            chartRef.current = null;
            seriesRef.current = {};
            setIsReady(false);
            chartContainerRef.current = null;
        }
    }, []);

    // Add candlestick series
    const addCandlestickSeries = useCallback((seriesOptions = {}) => {
        if (!chartRef.current) return null;

        const series = chartRef.current.addCandlestickSeries({
            upColor: CHART_COLORS.bullish,
            downColor: CHART_COLORS.bearish,
            borderUpColor: CHART_COLORS.bullish,
            borderDownColor: CHART_COLORS.bearish,
            wickUpColor: CHART_COLORS.bullish,
            wickDownColor: CHART_COLORS.bearish,
            ...seriesOptions,
        });

        return series;
    }, []);

    // Add line series
    const addLineSeries = useCallback((seriesOptions = {}) => {
        if (!chartRef.current) return null;

        const series = chartRef.current.addLineSeries({
            color: CHART_COLORS.accent,
            lineWidth: 2,
            ...seriesOptions,
        });

        return series;
    }, []);

    // Add area series
    const addAreaSeries = useCallback((seriesOptions = {}) => {
        if (!chartRef.current) return null;

        const series = chartRef.current.addAreaSeries({
            topColor: 'rgba(59, 130, 246, 0.4)',
            bottomColor: 'rgba(59, 130, 246, 0.0)',
            lineColor: CHART_COLORS.accent,
            lineWidth: 2,
            ...seriesOptions,
        });

        return series;
    }, []);

    // Add histogram series (for volume)
    const addHistogramSeries = useCallback((seriesOptions = {}) => {
        if (!chartRef.current) return null;

        const series = chartRef.current.addHistogramSeries({
            color: CHART_COLORS.volumeBullish,
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: 'volume',
            ...seriesOptions,
        });

        // Set price scale for volume
        chartRef.current.priceScale('volume').applyOptions({
            scaleMargins: {
                top: 0.8,
                bottom: 0,
            },
        });

        return series;
    }, []);

    // Register series with a name
    const registerSeries = useCallback((name, series) => {
        if (series) {
            seriesRef.current[name] = series;
        }
    }, []);

    // Remove series by name
    const removeSeries = useCallback((name) => {
        const series = seriesRef.current[name];
        if (series && chartRef.current) {
            chartRef.current.removeSeries(series);
            delete seriesRef.current[name];
        }
    }, []);

    // Update series data
    const updateSeriesData = useCallback((seriesName, data) => {
        const series = seriesRef.current[seriesName];
        if (!series) return;

        if (Array.isArray(data)) {
            series.setData(data);
        } else {
            series.update(data);
        }
    }, []);

    // Set markers on a series
    const setSeriesMarkers = useCallback((seriesName, markers) => {
        const series = seriesRef.current[seriesName];
        if (!series || !Array.isArray(markers)) return;

        series.setMarkers(markers);
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

    // Apply options
    const applyOptions = useCallback((newOptions) => {
        if (chartRef.current) {
            chartRef.current.applyOptions(newOptions);
        }
    }, []);

    // Get visible range
    const getVisibleRange = useCallback(() => {
        if (!chartRef.current) return null;

        const timeScale = chartRef.current.timeScale();
        return timeScale.getVisibleLogicalRange();
    }, []);

    // Subscribe to visible range changes
    const subscribeToVisibleRange = useCallback((callback) => {
        if (!chartRef.current) return () => { };

        const timeScale = chartRef.current.timeScale();

        const handler = (range) => {
            callback(range);
        };

        timeScale.subscribeVisibleLogicalRangeChange(handler);

        return () => {
            timeScale.unsubscribeVisibleLogicalRangeChange(handler);
        };
    }, []);

    // Take screenshot
    const takeScreenshot = useCallback(() => {
        if (!chartRef.current) return null;
        return chartRef.current.takeScreenshot();
    }, []);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            cleanupChart();
        };
    }, [cleanupChart]);

    return {
        // Refs
        chartContainerRef,
        chartRef,
        seriesRef,

        // State
        isReady,
        crosshairData,

        // Chart methods
        initChart,
        cleanupChart,
        applyOptions,
        fitContent,
        scrollToRealTime,
        getVisibleRange,
        subscribeToVisibleRange,
        takeScreenshot,

        // Series methods
        addCandlestickSeries,
        addLineSeries,
        addAreaSeries,
        addHistogramSeries,
        registerSeries,
        removeSeries,
        updateSeriesData,
        setSeriesMarkers,
    };
};

/**
 * Hook for managing real-time price updates
 * @param {Object} seriesRef - Reference to the series
 * @param {Object} socket - Socket.io connection
 * @param {string} eventName - Event to subscribe to
 * @returns {Object} - Update state
 */
export const useRealtimeUpdates = (seriesRef, socket, eventName = 'price_update') => {
    const [lastUpdate, setLastUpdate] = useState(null);
    const [updateCount, setUpdateCount] = useState(0);

    useEffect(() => {
        if (!socket || !seriesRef?.current) return;

        const handleUpdate = (data) => {
            const series = seriesRef.current;
            if (!series) return;

            // Update the series with new data
            series.update({
                time: data.time,
                open: data.open,
                high: data.high,
                low: data.low,
                close: data.close,
            });

            setLastUpdate(data);
            setUpdateCount((prev) => prev + 1);
        };

        socket.on(eventName, handleUpdate);

        return () => {
            socket.off(eventName, handleUpdate);
        };
    }, [socket, eventName, seriesRef]);

    return {
        lastUpdate,
        updateCount,
    };
};

/**
 * Hook for managing chart time scale
 * @param {Object} chartRef - Reference to the chart
 * @returns {Object} - Time scale utilities
 */
export const useTimeScale = (chartRef) => {
    const [visibleRange, setVisibleRange] = useState(null);
    const [scrollPosition, setScrollPosition] = useState(0);

    useEffect(() => {
        if (!chartRef?.current) return;

        const timeScale = chartRef.current.timeScale();

        const handleRangeChange = (range) => {
            setVisibleRange(range);
        };

        const handleScroll = () => {
            const position = timeScale.scrollPosition();
            setScrollPosition(position);
        };

        timeScale.subscribeVisibleLogicalRangeChange(handleRangeChange);
        timeScale.subscribeScrollPositionChange(handleScroll);

        return () => {
            timeScale.unsubscribeVisibleLogicalRangeChange(handleRangeChange);
            timeScale.unsubscribeScrollPositionChange(handleScroll);
        };
    }, [chartRef]);

    const scrollToPosition = useCallback((position, animated = true) => {
        if (!chartRef?.current) return;
        chartRef.current.timeScale().scrollToPosition(position, animated);
    }, [chartRef]);

    const setVisibleLogicalRange = useCallback((range) => {
        if (!chartRef?.current) return;
        chartRef.current.timeScale().setVisibleLogicalRange(range);
    }, [chartRef]);

    return {
        visibleRange,
        scrollPosition,
        scrollToPosition,
        setVisibleLogicalRange,
    };
};

/**
 * Hook for responsive chart sizing
 * @param {Object} containerRef - Reference to the container element
 * @returns {Object} - Size information
 */
export const useChartSize = (containerRef) => {
    const [size, setSize] = useState({ width: 0, height: 0 });

    useEffect(() => {
        if (!containerRef?.current) return;

        const updateSize = () => {
            const container = containerRef.current;
            if (!container) return;

            setSize({
                width: container.clientWidth,
                height: container.clientHeight,
            });
        };

        updateSize();

        const resizeObserver = new ResizeObserver(updateSize);
        resizeObserver.observe(containerRef.current);

        return () => {
            resizeObserver.disconnect();
        };
    }, [containerRef]);

    return size;
};

export default useChart;
