import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

/**
 * Trading Store - Centralized state management for trading operations
 * Uses Zustand with subscribeWithSelector for fine-grained subscriptions
 */
const useTradingStore = create(
    subscribeWithSelector((set, get) => ({
        // ==================== STATE ====================

        // Positions state
        positions: [],
        positionsLoading: false,
        positionsError: null,

        // Orders state
        orders: [],
        ordersLoading: false,
        ordersError: null,

        // Markets state
        markets: [],
        selectedMarket: null,
        marketsLoading: false,

        // Real-time data
        orderBook: null,
        priceHistory: [],
        lastPrice: null,

        // Trading metrics
        metrics: {
            totalPnL: 0,
            winRate: 0,
            totalTrades: 0,
            openPositions: 0,
            dailyPnL: 0,
        },

        // Detection signals
        activeSignals: [],
        goldenRectangleStatus: null,

        // Safety status
        safetyStatus: {
            killSwitchEnabled: false,
            panicTriggered: false,
            lastCheck: null,
        },

        // UI state
        isConnected: false,
        lastUpdate: null,
        notifications: [],

        // ==================== ACTIONS ====================

        // Position actions
        setPositions: (positions) => set({ positions, positionsLoading: false }),
        addPosition: (position) => set((state) => ({
            positions: [...state.positions, position]
        })),
        updatePosition: (positionId, updates) => set((state) => ({
            positions: state.positions.map((p) =>
                p.id === positionId ? { ...p, ...updates } : p
            ),
        })),
        removePosition: (positionId) => set((state) => ({
            positions: state.positions.filter((p) => p.id !== positionId),
        })),

        // Order actions
        setOrders: (orders) => set({ orders, ordersLoading: false }),
        addOrder: (order) => set((state) => ({
            orders: [...state.orders, order]
        })),
        updateOrder: (orderId, updates) => set((state) => ({
            orders: state.orders.map((o) =>
                o.id === orderId ? { ...o, ...updates } : o
            ),
        })),
        removeOrder: (orderId) => set((state) => ({
            orders: state.orders.filter((o) => o.id !== orderId),
        })),

        // Market actions
        setMarkets: (markets) => set({ markets, marketsLoading: false }),
        selectMarket: (market) => set({ selectedMarket: market }),

        // Real-time data actions
        setOrderBook: (orderBook) => set({ orderBook }),
        setPriceHistory: (priceHistory) => set({ priceHistory }),
        updateLastPrice: (price) => set({ lastPrice: price }),

        // Metrics actions
        setMetrics: (metrics) => set({ metrics }),
        updateMetrics: (updates) => set((state) => ({
            metrics: { ...state.metrics, ...updates }
        })),

        // Detection actions
        setActiveSignals: (signals) => set({ activeSignals: signals }),
        addSignal: (signal) => set((state) => ({
            activeSignals: [...state.activeSignals, signal]
        })),
        removeSignal: (signalId) => set((state) => ({
            activeSignals: state.activeSignals.filter((s) => s.id !== signalId),
        })),
        setGoldenRectangleStatus: (status) => set({ goldenRectangleStatus: status }),

        // Safety actions
        setSafetyStatus: (status) => set({ safetyStatus: status }),
        triggerPanic: () => set((state) => ({
            safetyStatus: { ...state.safetyStatus, panicTriggered: true }
        })),
        toggleKillSwitch: (enabled) => set((state) => ({
            safetyStatus: { ...state.safetyStatus, killSwitchEnabled: enabled }
        })),

        // Connection actions
        setConnected: (isConnected) => set({ isConnected }),
        setLastUpdate: (timestamp) => set({ lastUpdate: timestamp }),

        // Notification actions
        addNotification: (notification) => set((state) => ({
            notifications: [
                ...state.notifications,
                {
                    id: Date.now(),
                    timestamp: new Date().toISOString(),
                    ...notification,
                },
            ].slice(-50), // Keep last 50 notifications
        })),
        removeNotification: (id) => set((state) => ({
            notifications: state.notifications.filter((n) => n.id !== id),
        })),
        clearNotifications: () => set({ notifications: [] }),

        // Loading states
        setPositionsLoading: (loading) => set({ positionsLoading: loading }),
        setOrdersLoading: (loading) => set({ ordersLoading: loading }),
        setMarketsLoading: (loading) => set({ marketsLoading: loading }),

        // Error states
        setPositionsError: (error) => set({ positionsError: error }),
        setOrdersError: (error) => set({ ordersError: error }),

        // Reset store
        reset: () => set({
            positions: [],
            orders: [],
            markets: [],
            selectedMarket: null,
            orderBook: null,
            priceHistory: [],
            lastPrice: null,
            metrics: {
                totalPnL: 0,
                winRate: 0,
                totalTrades: 0,
                openPositions: 0,
                dailyPnL: 0,
            },
            activeSignals: [],
            goldenRectangleStatus: null,
            safetyStatus: {
                killSwitchEnabled: false,
                panicTriggered: false,
                lastCheck: null,
            },
            isConnected: false,
            lastUpdate: null,
            notifications: [],
        }),

        // ==================== SELECTORS ====================
        // These can be used with subscribeWithSelector

        getOpenPositions: () => get().positions.filter((p) => p.status === 'open'),
        getOpenOrders: () => get().orders.filter((o) => o.status === 'open'),
        getTotalPnL: () => get().metrics.totalPnL,
        getWinRate: () => get().metrics.winRate,
    }))
);

export default useTradingStore;

// Export specific selectors for convenience
export const selectPositions = (state) => state.positions;
export const selectOrders = (state) => state.orders;
export const selectMarkets = (state) => state.markets;
export const selectSelectedMarket = (state) => state.selectedMarket;
export const selectMetrics = (state) => state.metrics;
export const selectActiveSignals = (state) => state.activeSignals;
export const selectSafetyStatus = (state) => state.safetyStatus;
export const selectIsConnected = (state) => state.isConnected;
export const selectNotifications = (state) => state.notifications;
