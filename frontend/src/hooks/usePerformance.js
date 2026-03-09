/**
 * usePerformance Hook
 * Custom hook for managing performance metrics and real-time updates
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSocket } from '../context/SocketContext';
import { metricsApi } from '../services/api';
import {
    calculateSharpeRatio,
    calculateMaxDrawdown,
    calculateProfitFactor,
    calculateWinRate,
    calculateAverageTrade,
    calculateAverageWin,
    calculateAverageLoss,
    calculateExpectancy,
    calculateRiskRewardRatio,
    calculateTotalPnL,
    calculateTradeStatistics,
    calculatePerformanceMetrics,
} from '../utils/metricsUtils';

/**
 * Time period options for performance data
 */
export const TIME_PERIODS = {
    TODAY: 'today',
    WEEK: '7d',
    MONTH: '30d',
    QUARTER: '90d',
    YEAR: '365d',
    ALL: 'all',
};

/**
 * Time period labels
 */
export const TIME_PERIOD_LABELS = {
    [TIME_PERIODS.TODAY]: 'Today',
    [TIME_PERIODS.WEEK]: '7 Days',
    [TIME_PERIODS.MONTH]: '30 Days',
    [TIME_PERIODS.QUARTER]: '90 Days',
    [TIME_PERIODS.YEAR]: '1 Year',
    [TIME_PERIODS.ALL]: 'All Time',
};

/**
 * usePerformance - Main hook for performance metrics
 * @param {Object} options - Hook options
 * @param {string} options.period - Time period for data
 * @param {boolean} options.realTime - Enable real-time updates
 * @param {number} options.refreshInterval - Refresh interval in ms
 * @returns {Object} Performance data and methods
 */
export const usePerformance = (options = {}) => {
    const {
        period = TIME_PERIODS.WEEK,
        realTime = true,
        refreshInterval = 5000,
    } = options;

    const queryClient = useQueryClient();
    const { socket, connected } = useSocket();

    // Local state for real-time updates
    const [realTimeMetrics, setRealTimeMetrics] = useState(null);
    const [lastUpdate, setLastUpdate] = useState(null);
    const listenersRegistered = useRef(false);

    // Fetch PnL data
    const {
        data: pnlData,
        isLoading: pnlLoading,
        error: pnlError,
        refetch: refetchPnL,
    } = useQuery({
        queryKey: ['pnl', period],
        queryFn: () => metricsApi.getPnL({ period }),
        refetchInterval: refreshInterval,
        staleTime: 30000,
    });

    // Fetch trading metrics
    const {
        data: metricsData,
        isLoading: metricsLoading,
        error: metricsError,
        refetch: refetchMetrics,
    } = useQuery({
        queryKey: ['metrics', period],
        queryFn: metricsApi.getTradingMetrics,
        refetchInterval: refreshInterval,
        staleTime: 30000,
    });

    // Fetch trade history
    const {
        data: tradesData,
        isLoading: tradesLoading,
        error: tradesError,
        refetch: refetchTrades,
    } = useQuery({
        queryKey: ['trades', period],
        queryFn: () => metricsApi.getTrades({ period, limit: 1000 }),
        refetchInterval: refreshInterval,
        staleTime: 30000,
    });

    // Fetch ML metrics
    const {
        data: mlMetricsData,
        isLoading: mlMetricsLoading,
        error: mlMetricsError,
        refetch: refetchMLMetrics,
    } = useQuery({
        queryKey: ['mlMetrics', period],
        queryFn: metricsApi.getMLMetrics,
        refetchInterval: refreshInterval,
        staleTime: 60000,
    });

    // Process and calculate derived metrics
    const processedData = useMemo(() => {
        const pnl = pnlData?.data || [];
        const metrics = metricsData?.data || {};
        const trades = tradesData?.data || [];

        // Calculate equity curve from PnL data
        const equityCurve = pnl.length > 0
            ? pnl.map((d, i) => ({
                time: d.time || d.timestamp,
                value: pnl.slice(0, i + 1).reduce((sum, p) => sum + (p.pnl || p.value || 0), 0),
            }))
            : [];

        // Calculate returns from equity curve
        const returns = equityCurve.length > 1
            ? equityCurve.slice(1).map((d, i) => {
                const prev = equityCurve[i].value;
                return prev !== 0 ? (d.value - prev) / prev : 0;
            })
            : [];

        // Extract trade P&Ls
        const tradePnLs = trades.map(t => t.pnl).filter(pnl => isFinite(pnl));

        // Calculate derived metrics
        const tradeStats = calculateTradeStatistics(trades);
        const maxDrawdown = calculateMaxDrawdown(equityCurve.map(d => d.value));
        const sharpeRatio = calculateSharpeRatio(returns);
        const profitFactor = calculateProfitFactor(tradePnLs);
        const winRate = calculateWinRate(tradePnLs);
        const avgTrade = calculateAverageTrade(tradePnLs);
        const avgWin = calculateAverageWin(tradePnLs);
        const avgLoss = calculateAverageLoss(tradePnLs);
        const expectancy = calculateExpectancy(tradePnLs);
        const riskRewardRatio = calculateRiskRewardRatio(tradePnLs);

        // Calculate period PnL
        const totalPnL = calculateTotalPnL(tradePnLs);
        const realizedPnL = trades
            .filter(t => t.status === 'closed')
            .reduce((sum, t) => sum + (t.pnl || 0), 0);
        const unrealizedPnL = trades
            .filter(t => t.status === 'open')
            .reduce((sum, t) => sum + (t.unrealizedPnl || 0), 0);

        // Daily breakdown
        const dailyPnL = calculateDailyPnL(pnl);
        const weeklyPnL = calculateWeeklyPnL(pnl);
        const monthlyPnL = calculateMonthlyPnL(pnl);

        return {
            // Raw data
            pnl,
            trades,
            equityCurve,
            returns,

            // PnL metrics
            totalPnL,
            realizedPnL,
            unrealizedPnL,
            dailyPnL,
            weeklyPnL,
            monthlyPnL,

            // Trade statistics
            ...tradeStats,

            // Risk metrics
            sharpeRatio,
            maxDrawdown: maxDrawdown.maxDrawdown,
            maxDrawdownPercent: maxDrawdown.maxDrawdownPercent,
            profitFactor,
            expectancy,
            riskRewardRatio,

            // Averages
            avgTrade,
            avgWin,
            avgLoss,

            // Original metrics from API
            ...metrics,
        };
    }, [pnlData, metricsData, tradesData]);

    // ML metrics processing
    const mlMetrics = useMemo(() => {
        const data = mlMetricsData?.data || {};

        return {
            accuracy: data.accuracy || 0,
            precision: data.precision || 0,
            recall: data.recall || 0,
            f1Score: data.f1Score || data.f1 || 0,
            aucRoc: data.aucRoc || data.auc || 0,
            confusionMatrix: data.confusionMatrix || [[0, 0], [0, 0]],
            featureImportance: data.featureImportance || [],
            predictionDistribution: data.predictionDistribution || [],
            modelDrift: data.modelDrift || 0,
            lastTraining: data.lastTraining || null,
            modelVersion: data.modelVersion || 'unknown',
        };
    }, [mlMetricsData]);

    // Socket event handlers
    useEffect(() => {
        if (!socket || !connected || !realTime || listenersRegistered.current) return;

        const handleMetricsUpdate = (data) => {
            setRealTimeMetrics(data);
            setLastUpdate(new Date().toISOString());

            // Invalidate relevant queries
            queryClient.invalidateQueries({ queryKey: ['pnl'] });
            queryClient.invalidateQueries({ queryKey: ['metrics'] });
            queryClient.invalidateQueries({ queryKey: ['trades'] });
        };

        const handleTradeClosed = (trade) => {
            queryClient.invalidateQueries({ queryKey: ['trades'] });
            queryClient.invalidateQueries({ queryKey: ['pnl'] });
            setLastUpdate(new Date().toISOString());
        };

        const handlePnLUpdate = (update) => {
            setRealTimeMetrics(prev => ({
                ...prev,
                totalPnL: update.totalPnL,
                unrealizedPnL: update.unrealizedPnL,
            }));
            setLastUpdate(new Date().toISOString());
        };

        // Register listeners
        socket.on('metrics:update', handleMetricsUpdate);
        socket.on('trade:closed', handleTradeClosed);
        socket.on('pnl:update', handlePnLUpdate);

        listenersRegistered.current = true;

        return () => {
            socket.off('metrics:update', handleMetricsUpdate);
            socket.off('trade:closed', handleTradeClosed);
            socket.off('pnl:update', handlePnLUpdate);
            listenersRegistered.current = false;
        };
    }, [socket, connected, realTime, queryClient]);

    // Refresh all data
    const refreshAll = useCallback(async () => {
        await Promise.all([
            refetchPnL(),
            refetchMetrics(),
            refetchTrades(),
            refetchMLMetrics(),
        ]);
    }, [refetchPnL, refetchMetrics, refetchTrades, refetchMLMetrics]);

    // Loading state
    const isLoading = pnlLoading || metricsLoading || tradesLoading || mlMetricsLoading;

    // Error state
    const error = pnlError || metricsError || tradesError || mlMetricsError;

    return {
        // Processed performance data
        performance: processedData,

        // ML metrics
        mlMetrics,

        // Real-time state
        realTimeMetrics,
        lastUpdate,
        isConnected: connected,

        // Loading states
        isLoading,
        pnlLoading,
        metricsLoading,
        tradesLoading,
        mlMetricsLoading,

        // Error states
        error,

        // Methods
        refreshAll,
        refetchPnL,
        refetchMetrics,
        refetchTrades,
        refetchMLMetrics,
    };
};

/**
 * usePnLHistory - Hook for historical PnL data
 * @param {Object} options - Hook options
 * @returns {Object} Historical PnL data
 */
export const usePnLHistory = (options = {}) => {
    const { period = TIME_PERIODS.MONTH } = options;

    const { data, isLoading, error, refetch } = useQuery({
        queryKey: ['pnlHistory', period],
        queryFn: () => metricsApi.getPnLHistory({ period }),
        staleTime: 60000,
    });

    const processedData = useMemo(() => {
        if (!data?.data) return [];

        return data.data.map(item => ({
            time: item.time || Math.floor(new Date(item.timestamp).getTime() / 1000),
            value: item.pnl || item.value || 0,
            cumulative: item.cumulativePnl || 0,
        }));
    }, [data]);

    return {
        data: processedData,
        isLoading,
        error,
        refetch,
    };
};

/**
 * useTradeHistory - Hook for trade history
 * @param {Object} options - Hook options
 * @returns {Object} Trade history data
 */
export const useTradeHistory = (options = {}) => {
    const { limit = 100, status = 'all' } = options;

    const { data, isLoading, error, refetch } = useQuery({
        queryKey: ['tradeHistory', limit, status],
        queryFn: () => metricsApi.getTrades({ limit, status }),
        staleTime: 30000,
    });

    const processedTrades = useMemo(() => {
        if (!data?.data) return [];

        return data.data.map(trade => ({
            ...trade,
            timestamp: new Date(trade.timestamp || trade.createdAt),
            pnl: trade.pnl || 0,
            side: trade.side || 'unknown',
            market: trade.market || trade.symbol || 'Unknown',
            size: trade.size || trade.quantity || 0,
            entryPrice: trade.entryPrice || trade.entry || 0,
            exitPrice: trade.exitPrice || trade.exit || 0,
        }));
    }, [data]);

    return {
        trades: processedTrades,
        isLoading,
        error,
        refetch,
    };
};

/**
 * useMLMetrics - Hook for ML model metrics
 * @returns {Object} ML metrics data
 */
export const useMLMetrics = () => {
    const { socket, connected } = useSocket();
    const [realTimeUpdate, setRealTimeUpdate] = useState(null);

    const { data, isLoading, error, refetch } = useQuery({
        queryKey: ['mlMetrics'],
        queryFn: metricsApi.getMLMetrics,
        staleTime: 60000,
    });

    // Real-time ML metric updates
    useEffect(() => {
        if (!socket || !connected) return;

        const handleMLUpdate = (update) => {
            setRealTimeUpdate(update);
        };

        socket.on('ml:metrics', handleMLUpdate);

        return () => {
            socket.off('ml:metrics', handleMLUpdate);
        };
    }, [socket, connected]);

    const metrics = useMemo(() => {
        const baseMetrics = data?.data || {};

        return {
            // Core metrics
            accuracy: baseMetrics.accuracy || 0,
            precision: baseMetrics.precision || 0,
            recall: baseMetrics.recall || 0,
            f1Score: baseMetrics.f1Score || baseMetrics.f1 || 0,
            aucRoc: baseMetrics.aucRoc || baseMetrics.auc || 0,

            // Confusion matrix
            confusionMatrix: baseMetrics.confusionMatrix || {
                truePositives: 0,
                trueNegatives: 0,
                falsePositives: 0,
                falseNegatives: 0,
            },

            // Feature importance
            featureImportance: baseMetrics.featureImportance || [],

            // Prediction distribution
            predictionDistribution: baseMetrics.predictionDistribution || [],

            // Model drift
            modelDrift: baseMetrics.modelDrift || {
                score: 0,
                status: 'stable',
                lastCheck: null,
            },

            // Model info
            modelVersion: baseMetrics.modelVersion || 'unknown',
            lastTraining: baseMetrics.lastTraining || null,
            trainingSamples: baseMetrics.trainingSamples || 0,

            // Real-time overlay
            ...realTimeUpdate,
        };
    }, [data, realTimeUpdate]);

    return {
        metrics,
        isLoading,
        error,
        refetch,
        isConnected: connected,
    };
};

/**
 * Calculate daily PnL breakdown
 * @param {Array} pnlData - PnL data array
 * @returns {Array} Daily PnL breakdown
 */
const calculateDailyPnL = (pnlData) => {
    if (!pnlData || pnlData.length === 0) return [];

    const dailyMap = new Map();

    pnlData.forEach(item => {
        const date = new Date(item.time || item.timestamp).toISOString().split('T')[0];
        const pnl = item.pnl || item.value || 0;

        if (dailyMap.has(date)) {
            dailyMap.set(date, dailyMap.get(date) + pnl);
        } else {
            dailyMap.set(date, pnl);
        }
    });

    return Array.from(dailyMap.entries())
        .map(([date, pnl]) => ({ date, pnl }))
        .sort((a, b) => a.date.localeCompare(b.date));
};

/**
 * Calculate weekly PnL breakdown
 * @param {Array} pnlData - PnL data array
 * @returns {Array} Weekly PnL breakdown
 */
const calculateWeeklyPnL = (pnlData) => {
    if (!pnlData || pnlData.length === 0) return [];

    const weeklyMap = new Map();

    pnlData.forEach(item => {
        const date = new Date(item.time || item.timestamp);
        const weekStart = getWeekStart(date).toISOString().split('T')[0];
        const pnl = item.pnl || item.value || 0;

        if (weeklyMap.has(weekStart)) {
            weeklyMap.set(weekStart, weeklyMap.get(weekStart) + pnl);
        } else {
            weeklyMap.set(weekStart, pnl);
        }
    });

    return Array.from(weeklyMap.entries())
        .map(([week, pnl]) => ({ week, pnl }))
        .sort((a, b) => a.week.localeCompare(b.week));
};

/**
 * Calculate monthly PnL breakdown
 * @param {Array} pnlData - PnL data array
 * @returns {Array} Monthly PnL breakdown
 */
const calculateMonthlyPnL = (pnlData) => {
    if (!pnlData || pnlData.length === 0) return [];

    const monthlyMap = new Map();

    pnlData.forEach(item => {
        const date = new Date(item.time || item.timestamp);
        const month = date.toISOString().slice(0, 7); // YYYY-MM
        const pnl = item.pnl || item.value || 0;

        if (monthlyMap.has(month)) {
            monthlyMap.set(month, monthlyMap.get(month) + pnl);
        } else {
            monthlyMap.set(month, pnl);
        }
    });

    return Array.from(monthlyMap.entries())
        .map(([month, pnl]) => ({ month, pnl }))
        .sort((a, b) => a.month.localeCompare(b.month));
};

/**
 * Get the start of the week for a date
 * @param {Date} date - Input date
 * @returns {Date} Week start date
 */
const getWeekStart = (date) => {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Adjust for Monday start
    return new Date(d.setDate(diff));
};

export default {
    usePerformance,
    usePnLHistory,
    useTradeHistory,
    useMLMetrics,
    TIME_PERIODS,
    TIME_PERIOD_LABELS,
};
