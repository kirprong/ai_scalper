/**
 * Chart Utilities for Lightweight Charts
 * Helper functions for chart configuration, data transformation, and styling
 */

import { createChart } from 'lightweight-charts';

/**
 * Dark theme colors matching the UI
 */
export const CHART_COLORS = {
    // Background
    background: '#0f172a',
    surfaceBackground: '#1e293b',

    // Grid
    gridLine: '#334155',

    // Text
    text: '#94a3b8',
    textMuted: '#64748b',

    // Candlestick colors
    bullish: '#22c55e',
    bearish: '#ef4444',

    // Volume colors
    volumeBullish: 'rgba(34, 197, 94, 0.5)',
    volumeBearish: 'rgba(239, 68, 68, 0.5)',

    // Signal markers
    buySignal: '#22c55e',
    sellSignal: '#ef4444',

    // PnL colors
    profit: '#22c55e',
    loss: '#ef4444',

    // Accent
    accent: '#3b82f6',
    accentMuted: 'rgba(59, 130, 246, 0.3)',

    // Crosshair
    crosshair: '#64748b',
};

/**
 * Default chart options for dark theme
 */
export const getDefaultChartOptions = (height = 400) => ({
    width: undefined, // Auto width
    height,
    layout: {
        background: { type: 'solid', color: CHART_COLORS.background },
        textColor: CHART_COLORS.text,
    },
    grid: {
        vertLines: { color: CHART_COLORS.gridLine },
        horzLines: { color: CHART_COLORS.gridLine },
    },
    crosshair: {
        mode: 1, // Magnet mode
        vertLine: {
            color: CHART_COLORS.crosshair,
            width: 1,
            style: 2, // Dashed
            labelBackgroundColor: CHART_COLORS.surfaceBackground,
        },
        horzLine: {
            color: CHART_COLORS.crosshair,
            width: 1,
            style: 2,
            labelBackgroundColor: CHART_COLORS.surfaceBackground,
        },
    },
    rightPriceScale: {
        borderColor: CHART_COLORS.gridLine,
        scaleMargins: {
            top: 0.1,
            bottom: 0.2,
        },
    },
    timeScale: {
        borderColor: CHART_COLORS.gridLine,
        timeVisible: true,
        secondsVisible: false,
    },
    handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
    },
    handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true,
    },
});

/**
 * Candlestick series options
 */
export const getCandlestickSeriesOptions = () => ({
    upColor: CHART_COLORS.bullish,
    downColor: CHART_COLORS.bearish,
    borderUpColor: CHART_COLORS.bullish,
    borderDownColor: CHART_COLORS.bearish,
    wickUpColor: CHART_COLORS.bullish,
    wickDownColor: CHART_COLORS.bearish,
});

/**
 * Volume series options
 */
export const getVolumeSeriesOptions = () => ({
    color: CHART_COLORS.volumeBullish,
    priceFormat: {
        type: 'volume',
    },
    priceScaleId: 'volume',
    scaleMargins: {
        top: 0.8,
        bottom: 0,
    },
});

/**
 * Line series options for PnL chart
 */
export const getLineSeriesOptions = (color = CHART_COLORS.accent) => ({
    color,
    lineWidth: 2,
    priceFormat: {
        type: 'price',
        precision: 2,
        minMove: 0.01,
    },
    crosshairMarkerVisible: true,
    crosshairMarkerRadius: 4,
    crosshairMarkerBorderColor: color,
    crosshairMarkerBackgroundColor: CHART_COLORS.background,
});

/**
 * Area series options for cumulative PnL
 */
export const getAreaSeriesOptions = (isPositive = true) => ({
    topColor: isPositive ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)',
    bottomColor: isPositive ? 'rgba(34, 197, 94, 0.0)' : 'rgba(239, 68, 68, 0.0)',
    lineColor: isPositive ? CHART_COLORS.profit : CHART_COLORS.loss,
    lineWidth: 2,
    priceFormat: {
        type: 'price',
        precision: 2,
        minMove: 0.01,
    },
});

/**
 * Transform OHLCV data to Lightweight Charts format
 * @param {Array} data - Raw OHLCV data
 * @returns {Object} - Candlestick and volume data
 */
export const transformOHLCVData = (data) => {
    if (!Array.isArray(data)) {
        return { candlestickData: [], volumeData: [] };
    }

    const candlestickData = [];
    const volumeData = [];

    for (const candle of data) {
        const time = typeof candle.time === 'number'
            ? candle.time
            : Math.floor(new Date(candle.time || candle.timestamp).getTime() / 1000);

        // Candlestick data
        candlestickData.push({
            time,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
        });

        // Volume data with color based on price direction
        volumeData.push({
            time,
            value: candle.volume,
            color: candle.close >= candle.open
                ? CHART_COLORS.volumeBullish
                : CHART_COLORS.volumeBearish,
        });
    }

    return { candlestickData, volumeData };
};

/**
 * Transform trade signals to chart markers
 * @param {Array} signals - Trading signals
 * @returns {Array} - Chart markers
 */
export const transformSignalsToMarkers = (signals) => {
    if (!Array.isArray(signals)) {
        return [];
    }

    return signals.map((signal, index) => {
        const time = typeof signal.time === 'number'
            ? signal.time
            : Math.floor(new Date(signal.time || signal.timestamp).getTime() / 1000);

        const isBuy = signal.type === 'buy' || signal.side === 'buy' || signal.signal === 1;

        return {
            time,
            position: isBuy ? 'belowBar' : 'aboveBar',
            color: isBuy ? CHART_COLORS.buySignal : CHART_COLORS.sellSignal,
            shape: isBuy ? 'arrowUp' : 'arrowDown',
            text: isBuy ? 'BUY' : 'SELL',
            size: 2,
        };
    });
};

/**
 * Transform PnL data to chart format
 * @param {Array} pnlData - PnL data points
 * @returns {Object} - Line and area data
 */
export const transformPnLData = (pnlData) => {
    if (!Array.isArray(pnlData)) {
        return { lineData: [], areaData: [] };
    }

    const lineData = [];
    const areaData = [];

    for (const point of pnlData) {
        const time = typeof point.time === 'number'
            ? point.time
            : Math.floor(new Date(point.time || point.timestamp).getTime() / 1000);

        const value = point.pnl || point.value || point.cumulativePnl;

        lineData.push({ time, value });
        areaData.push({ time, value });
    }

    return { lineData, areaData };
};

/**
 * Create a chart instance with proper cleanup handling
 * @param {HTMLElement} container - Container element
 * @param {Object} options - Chart options
 * @returns {Object} - Chart instance
 */
export const createChartInstance = (container, options = {}) => {
    const mergedOptions = {
        ...getDefaultChartOptions(options.height || 400),
        ...options,
    };

    return createChart(container, mergedOptions);
};

/**
 * Format price for display
 * @param {number} price - Price value
 * @param {number} precision - Decimal precision
 * @returns {string} - Formatted price
 */
export const formatPrice = (price, precision = 2) => {
    if (typeof price !== 'number' || isNaN(price)) {
        return '-';
    }
    return price.toFixed(precision);
};

/**
 * Format volume for display
 * @param {number} volume - Volume value
 * @returns {string} - Formatted volume
 */
export const formatVolume = (volume) => {
    if (typeof volume !== 'number' || isNaN(volume)) {
        return '-';
    }

    if (volume >= 1000000) {
        return `${(volume / 1000000).toFixed(2)}M`;
    }
    if (volume >= 1000) {
        return `${(volume / 1000).toFixed(2)}K`;
    }
    return volume.toFixed(2);
};

/**
 * Format percentage for display
 * @param {number} value - Percentage value
 * @returns {string} - Formatted percentage
 */
export const formatPercent = (value) => {
    if (typeof value !== 'number' || isNaN(value)) {
        return '-';
    }
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
};

/**
 * Calculate visible range for chart
 * @param {Object} timeScale - Time scale from chart
 * @returns {Object} - Visible range
 */
export const getVisibleRange = (timeScale) => {
    if (!timeScale) return null;

    const visibleRange = timeScale.getVisibleLogicalRange();
    if (!visibleRange) return null;

    return {
        from: visibleRange.from,
        to: visibleRange.to,
    };
};

/**
 * Fit content with optional padding
 * @param {Object} chart - Chart instance
 * @param {number} padding - Padding percentage (0-1)
 */
export const fitContent = (chart, padding = 0.1) => {
    if (!chart) return;

    const timeScale = chart.timeScale();
    timeScale.fitContent();

    // Optionally add padding by scrolling
    if (padding > 0) {
        const visibleRange = timeScale.getVisibleLogicalRange();
        if (visibleRange) {
            const range = visibleRange.to - visibleRange.from;
            const paddingBars = Math.floor(range * padding);
            timeScale.scrollToRealTime();
        }
    }
};

/**
 * Subscribe to visible range changes
 * @param {Object} chart - Chart instance
 * @param {Function} callback - Callback function
 * @returns {Function} - Unsubscribe function
 */
export const subscribeToVisibleRange = (chart, callback) => {
    if (!chart) return () => { };

    const timeScale = chart.timeScale();

    const handler = () => {
        const range = getVisibleRange(timeScale);
        callback(range);
    };

    timeScale.subscribeVisibleLogicalRangeChange(handler);

    return () => {
        timeScale.unsubscribeVisibleLogicalRangeChange(handler);
    };
};

/**
 * Subscribe to crosshair move
 * @param {Object} chart - Chart instance
 * @param {Function} callback - Callback function
 * @returns {Function} - Unsubscribe function
 */
export const subscribeToCrosshairMove = (chart, callback) => {
    if (!chart) return () => { };

    chart.subscribeCrosshairMove((param) => {
        if (!param.point || !param.time) {
            callback(null);
            return;
        }

        callback({
            point: param.point,
            time: param.time,
            seriesData: param.seriesData,
        });
    });

    // Note: For cleanup, store the handler reference
    return () => {
        chart.unsubscribeCrosshairMove(() => { });
    };
};

/**
 * Generate sample candlestick data for testing
 * @param {number} count - Number of candles
 * @param {number} startPrice - Starting price
 * @returns {Array} - Sample OHLCV data
 */
export const generateSampleData = (count = 100, startPrice = 100) => {
    const data = [];
    let currentPrice = startPrice;
    const now = Math.floor(Date.now() / 1000);
    const interval = 60; // 1 minute candles

    for (let i = 0; i < count; i++) {
        const time = now - (count - i) * interval;
        const volatility = 0.02;
        const change = (Math.random() - 0.5) * 2 * volatility;

        const open = currentPrice;
        const close = open * (1 + change);
        const high = Math.max(open, close) * (1 + Math.random() * volatility * 0.5);
        const low = Math.min(open, close) * (1 - Math.random() * volatility * 0.5);
        const volume = Math.random() * 10000 + 1000;

        data.push({
            time,
            open,
            high,
            low,
            close,
            volume,
        });

        currentPrice = close;
    }

    return data;
};

/**
 * Generate sample PnL data for testing
 * @param {number} count - Number of data points
 * @param {number} startPnl - Starting PnL
 * @returns {Array} - Sample PnL data
 */
export const generateSamplePnLData = (count = 50, startPnl = 0) => {
    const data = [];
    let cumulativePnl = startPnl;
    const now = Math.floor(Date.now() / 1000);
    const interval = 3600; // 1 hour intervals

    for (let i = 0; i < count; i++) {
        const time = now - (count - i) * interval;
        const tradePnl = (Math.random() - 0.4) * 100; // Slight positive bias
        cumulativePnl += tradePnl;

        data.push({
            time,
            pnl: cumulativePnl,
            tradePnl,
        });
    }

    return data;
};

/**
 * Generate sample signals for testing
 * @param {Array} candleData - Candlestick data
 * @param {number} count - Number of signals
 * @returns {Array} - Sample signals
 */
export const generateSampleSignals = (candleData, count = 10) => {
    if (!Array.isArray(candleData) || candleData.length === 0) {
        return [];
    }

    const signals = [];
    const step = Math.floor(candleData.length / count);

    for (let i = step; i < candleData.length; i += step) {
        const candle = candleData[i];
        const isBuy = Math.random() > 0.5;

        signals.push({
            time: candle.time,
            type: isBuy ? 'buy' : 'sell',
            price: candle.close,
            confidence: Math.random() * 0.5 + 0.5,
        });
    }

    return signals;
};
