import axios from 'axios';

// Base axios instance with default configuration
const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor for adding auth token
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('auth_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('auth_token');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

// Trading API endpoints
export const tradingApi = {
    // Get current positions
    getPositions: () => api.get('/api/positions'),

    // Get open orders
    getOrders: () => api.get('/api/orders'),

    // Place new order
    placeOrder: (orderData) => api.post('/api/orders', orderData),

    // Cancel order
    cancelOrder: (orderId) => api.delete(`/api/orders/${orderId}`),

    // Get order book
    getOrderBook: (marketId) => api.get(`/api/markets/${marketId}/orderbook`),

    // Get trade history
    getTradeHistory: (params) => api.get('/api/trades', { params }),
};

// Metrics API endpoints
export const metricsApi = {
    // Get system metrics
    getSystemMetrics: () => api.get('/api/metrics/system'),

    // Get trading metrics
    getTradingMetrics: (params) => api.get('/api/metrics/trading', { params }),

    // Get performance stats
    getPerformanceStats: (period) => api.get(`/api/metrics/performance/${period}`),

    // Get PnL data
    getPnL: (params) => api.get('/api/metrics/pnl', { params }),

    // Get win/loss ratio
    getWinLossRatio: () => api.get('/api/metrics/win-loss'),
};

// Market API endpoints
export const marketApi = {
    // Get available markets
    getMarkets: () => api.get('/api/markets'),

    // Get market details
    getMarket: (marketId) => api.get(`/api/markets/${marketId}`),

    // Get market price history
    getPriceHistory: (marketId, params) =>
        api.get(`/api/markets/${marketId}/price-history`, { params }),

    // Get market order book
    getOrderBook: (marketId) => api.get(`/api/markets/${marketId}/orderbook`),
};

// Account API endpoints
export const accountApi = {
    // Get account balance
    getBalance: () => api.get('/api/account/balance'),

    // Get account info
    getAccountInfo: () => api.get('/api/account/info'),

    // Get API key status
    getApiKeyStatus: () => api.get('/api/account/api-status'),
};

// Settings API endpoints
export const settingsApi = {
    // Get all settings
    getSettings: () => api.get('/api/settings'),

    // Update settings
    updateSettings: (settings) => api.put('/api/settings', settings),

    // Reset to defaults
    resetToDefaults: () => api.post('/api/settings/reset'),
};

// Detection API endpoints (Golden Rectangle)
export const detectionApi = {
    // Get active signals
    getActiveSignals: () => api.get('/api/detection/signals'),

    // Get signal history
    getSignalHistory: (params) => api.get('/api/detection/signals/history', { params }),

    // Get golden rectangle status
    getGoldenRectangleStatus: () => api.get('/api/detection/golden-rectangle'),
};

// Safety API endpoints
export const safetyApi = {
    // Trigger panic button
    panic: () => api.post('/api/safety/panic'),

    // Get kill switch status
    getKillSwitchStatus: () => api.get('/api/safety/kill-switch'),

    // Toggle kill switch
    toggleKillSwitch: (enabled) => api.post('/api/safety/kill-switch', { enabled }),

    // Get safety status
    getSafetyStatus: () => api.get('/api/safety/status'),
};

export default api;
