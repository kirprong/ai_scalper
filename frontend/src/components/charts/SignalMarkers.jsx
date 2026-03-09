/**
 * SignalMarkers Component
 * Utility component for managing trading signal markers on charts
 */

import React, { useEffect, useMemo, useCallback } from 'react';
import {
    CHART_COLORS,
    transformSignalsToMarkers,
} from '../../utils/chartUtils';

/**
 * Signal marker types
 */
export const SIGNAL_TYPES = {
    BUY: 'buy',
    SELL: 'sell',
    LONG: 'long',
    SHORT: 'short',
    ENTRY: 'entry',
    EXIT: 'exit',
    STOP_LOSS: 'stop_loss',
    TAKE_PROFIT: 'take_profit',
};

/**
 * Signal marker shapes
 */
export const SIGNAL_SHAPES = {
    ARROW_UP: 'arrowUp',
    ARROW_DOWN: 'arrowDown',
    CIRCLE: 'circle',
    SQUARE: 'square',
};

/**
 * Get marker configuration based on signal type
 * @param {string} type - Signal type
 * @returns {Object} - Marker configuration
 */
export const getMarkerConfig = (type) => {
    const configs = {
        [SIGNAL_TYPES.BUY]: {
            position: 'belowBar',
            color: CHART_COLORS.buySignal,
            shape: SIGNAL_SHAPES.ARROW_UP,
            text: 'BUY',
        },
        [SIGNAL_TYPES.SELL]: {
            position: 'aboveBar',
            color: CHART_COLORS.sellSignal,
            shape: SIGNAL_SHAPES.ARROW_DOWN,
            text: 'SELL',
        },
        [SIGNAL_TYPES.LONG]: {
            position: 'belowBar',
            color: CHART_COLORS.buySignal,
            shape: SIGNAL_SHAPES.ARROW_UP,
            text: 'LONG',
        },
        [SIGNAL_TYPES.SHORT]: {
            position: 'aboveBar',
            color: CHART_COLORS.sellSignal,
            shape: SIGNAL_SHAPES.ARROW_DOWN,
            text: 'SHORT',
        },
        [SIGNAL_TYPES.ENTRY]: {
            position: 'belowBar',
            color: CHART_COLORS.accent,
            shape: SIGNAL_SHAPES.CIRCLE,
            text: 'ENTRY',
        },
        [SIGNAL_TYPES.EXIT]: {
            position: 'aboveBar',
            color: CHART_COLORS.accent,
            shape: SIGNAL_SHAPES.CIRCLE,
            text: 'EXIT',
        },
        [SIGNAL_TYPES.STOP_LOSS]: {
            position: 'aboveBar',
            color: '#f97316', // Orange
            shape: SIGNAL_SHAPES.SQUARE,
            text: 'SL',
        },
        [SIGNAL_TYPES.TAKE_PROFIT]: {
            position: 'belowBar',
            color: '#06b6d4', // Cyan
            shape: SIGNAL_SHAPES.SQUARE,
            text: 'TP',
        },
    };

    return configs[type] || configs[SIGNAL_TYPES.BUY];
};

/**
 * SignalMarkers - Component for adding signal markers to a chart series
 * This is a headless component that manages markers on a series ref
 * 
 * @param {Object} props
 * @param {Object} props.seriesRef - Reference to the chart series
 * @param {Array} props.signals - Array of trading signals
 * @param {boolean} props.enabled - Whether markers are enabled
 * @param {Function} props.onMarkerClick - Callback when marker is clicked
 */
const SignalMarkers = ({
    seriesRef,
    signals = [],
    enabled = true,
    onMarkerClick,
}) => {
    // Transform signals to chart markers
    const markers = useMemo(() => {
        if (!enabled || !signals.length) return [];

        return signals.map((signal) => {
            const config = getMarkerConfig(signal.type || signal.signal);
            const time = typeof signal.time === 'number'
                ? signal.time
                : Math.floor(new Date(signal.time || signal.timestamp).getTime() / 1000);

            return {
                time,
                position: signal.position || config.position,
                color: signal.color || config.color,
                shape: signal.shape || config.shape,
                text: signal.text || config.text,
                size: signal.size || 2,
                // Store original signal data for click handling
                _signalData: signal,
            };
        });
    }, [signals, enabled]);

    // Apply markers to series
    useEffect(() => {
        if (!seriesRef?.current) return;

        if (markers.length > 0) {
            seriesRef.current.setMarkers(markers);
        } else {
            // Clear markers if none
            seriesRef.current.setMarkers([]);
        }
    }, [seriesRef, markers]);

    // This component doesn't render anything visible
    return null;
};

/**
 * SignalMarkersOverlay - Visual overlay showing signal list
 * 
 * @param {Object} props
 * @param {Array} props.signals - Array of trading signals
 * @param {number} props.maxVisible - Maximum signals to show
 * @param {Function} props.onSignalClick - Callback when signal is clicked
 */
export const SignalMarkersOverlay = ({
    signals = [],
    maxVisible = 10,
    onSignalClick,
}) => {
    const visibleSignals = signals.slice(-maxVisible);

    return (
        <div className="signal-markers-overlay bg-slate-800/90 backdrop-blur-sm rounded-lg p-3 max-h-64 overflow-y-auto">
            <h4 className="text-sm font-medium text-slate-300 mb-2">Recent Signals</h4>
            {visibleSignals.length === 0 ? (
                <p className="text-xs text-slate-500">No signals available</p>
            ) : (
                <div className="space-y-1">
                    {visibleSignals.map((signal, index) => {
                        const config = getMarkerConfig(signal.type || signal.signal);
                        const isBuy = signal.type === 'buy' || signal.type === 'long' || signal.signal === 1;

                        return (
                            <div
                                key={`${signal.time}-${index}`}
                                className="flex items-center justify-between p-2 bg-slate-700/50 rounded cursor-pointer hover:bg-slate-700 transition-colors"
                                onClick={() => onSignalClick?.(signal)}
                            >
                                <div className="flex items-center gap-2">
                                    <div
                                        className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold ${isBuy ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                                            }`}
                                    >
                                        {isBuy ? '↑' : '↓'}
                                    </div>
                                    <div>
                                        <div className="text-sm text-white">{config.text}</div>
                                        <div className="text-xs text-slate-500">
                                            {new Date((signal.time || signal.timestamp) * 1000).toLocaleTimeString()}
                                        </div>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-sm text-white">
                                        {signal.price?.toFixed(4) || '-'}
                                    </div>
                                    {signal.confidence && (
                                        <div className="text-xs text-slate-500">
                                            {(signal.confidence * 100).toFixed(0)}% conf
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};

/**
 * SignalLegend - Legend showing signal types
 * 
 * @param {Object} props
 * @param {boolean} props.showLabels - Show signal type labels
 */
export const SignalLegend = ({ showLabels = true }) => {
    const signalTypes = [
        { type: SIGNAL_TYPES.BUY, label: 'Buy Signal' },
        { type: SIGNAL_TYPES.SELL, label: 'Sell Signal' },
        { type: SIGNAL_TYPES.ENTRY, label: 'Entry Point' },
        { type: SIGNAL_TYPES.EXIT, label: 'Exit Point' },
        { type: SIGNAL_TYPES.STOP_LOSS, label: 'Stop Loss' },
        { type: SIGNAL_TYPES.TAKE_PROFIT, label: 'Take Profit' },
    ];

    return (
        <div className="signal-legend flex flex-wrap gap-3">
            {signalTypes.map(({ type, label }) => {
                const config = getMarkerConfig(type);
                return (
                    <div key={type} className="flex items-center gap-1">
                        <div
                            className="w-3 h-3 rounded-sm"
                            style={{ backgroundColor: config.color }}
                        />
                        {showLabels && (
                            <span className="text-xs text-slate-400">{label}</span>
                        )}
                    </div>
                );
            })}
        </div>
    );
};

/**
 * useSignalMarkers - Hook for managing signal markers
 * 
 * @param {Object} seriesRef - Reference to the chart series
 * @param {Array} signals - Array of trading signals
 * @returns {Object} - Signal marker utilities
 */
export const useSignalMarkers = (seriesRef, signals = []) => {
    // Add markers to series
    const setMarkers = useCallback((newMarkers) => {
        if (!seriesRef?.current) return;
        seriesRef.current.setMarkers(newMarkers);
    }, [seriesRef]);

    // Clear all markers
    const clearMarkers = useCallback(() => {
        if (!seriesRef?.current) return;
        seriesRef.current.setMarkers([]);
    }, [seriesRef]);

    // Add a single marker
    const addMarker = useCallback((signal) => {
        if (!seriesRef?.current) return;

        const config = getMarkerConfig(signal.type || signal.signal);
        const time = typeof signal.time === 'number'
            ? signal.time
            : Math.floor(new Date(signal.time || signal.timestamp).getTime() / 1000);

        const marker = {
            time,
            position: signal.position || config.position,
            color: signal.color || config.color,
            shape: signal.shape || config.shape,
            text: signal.text || config.text,
            size: signal.size || 2,
        };

        // Get existing markers and add new one
        const existingMarkers = seriesRef.current.markers() || [];
        seriesRef.current.setMarkers([...existingMarkers, marker]);
    }, [seriesRef]);

    // Remove marker by time
    const removeMarker = useCallback((time) => {
        if (!seriesRef?.current) return;

        const existingMarkers = seriesRef.current.markers() || [];
        const filteredMarkers = existingMarkers.filter((m) => m.time !== time);
        seriesRef.current.setMarkers(filteredMarkers);
    }, [seriesRef]);

    // Get all markers
    const getMarkers = useCallback(() => {
        if (!seriesRef?.current) return [];
        return seriesRef.current.markers() || [];
    }, [seriesRef]);

    return {
        setMarkers,
        clearMarkers,
        addMarker,
        removeMarker,
        getMarkers,
    };
};

export default SignalMarkers;
