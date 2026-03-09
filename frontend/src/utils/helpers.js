/**
 * Utility functions for the AI Lead Scalper frontend
 */

/**
 * Format a number as currency
 * @param {number} value - The value to format
 * @param {string} currency - Currency code (default: USD)
 * @returns {string} Formatted currency string
 */
export const formatCurrency = (value, currency = 'USD') => {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(value);
};

/**
 * Format a number with thousand separators
 * @param {number} value - The value to format
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted number string
 */
export const formatNumber = (value, decimals = 2) => {
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).format(value);
};

/**
 * Format a percentage value
 * @param {number} value - The value to format
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted percentage string
 */
export const formatPercent = (value, decimals = 2) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}%`;
};

/**
 * Format a timestamp to locale string
 * @param {string|Date} timestamp - The timestamp to format
 * @returns {string} Formatted date/time string
 */
export const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
};

/**
 * Format a timestamp to time only
 * @param {string|Date} timestamp - The timestamp to format
 * @returns {string} Formatted time string
 */
export const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
};

/**
 * Calculate PnL percentage
 * @param {number} entryPrice - Entry price
 * @param {number} currentPrice - Current price
 * @param {string} side - Position side (YES/NO)
 * @returns {number} PnL percentage
 */
export const calculatePnLPercent = (entryPrice, currentPrice, side) => {
    if (side === 'YES') {
        return ((currentPrice - entryPrice) / entryPrice) * 100;
    } else {
        return ((entryPrice - currentPrice) / entryPrice) * 100;
    }
};

/**
 * Truncate text with ellipsis
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated text
 */
export const truncateText = (text, maxLength = 50) => {
    if (!text || text.length <= maxLength) return text;
    return `${text.slice(0, maxLength)}...`;
};

/**
 * Generate a random ID
 * @returns {string} Random ID string
 */
export const generateId = () => {
    return Math.random().toString(36).substring(2, 9);
};

/**
 * Debounce function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {Function} Debounced function
 */
export const debounce = (func, wait) => {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
};

/**
 * Throttle function
 * @param {Function} func - Function to throttle
 * @param {number} limit - Time limit in ms
 * @returns {Function} Throttled function
 */
export const throttle = (func, limit) => {
    let inThrottle;
    return function executedFunction(...args) {
        if (!inThrottle) {
            func(...args);
            inThrottle = true;
            setTimeout(() => (inThrottle = false), limit);
        }
    };
};

/**
 * Deep clone an object
 * @param {Object} obj - Object to clone
 * @returns {Object} Cloned object
 */
export const deepClone = (obj) => {
    return JSON.parse(JSON.stringify(obj));
};

/**
 * Check if value is empty
 * @param {*} value - Value to check
 * @returns {boolean} True if empty
 */
export const isEmpty = (value) => {
    if (value === null || value === undefined) return true;
    if (typeof value === 'string') return value.trim() === '';
    if (Array.isArray(value)) return value.length === 0;
    if (typeof value === 'object') return Object.keys(value).length === 0;
    return false;
};

/**
 * Get color class based on value (positive/negative)
 * @param {number} value - Value to check
 * @returns {string} Tailwind color class
 */
export const getValueColor = (value) => {
    if (value > 0) return 'text-emerald-400';
    if (value < 0) return 'text-red-400';
    return 'text-slate-400';
};

/**
 * Get background color class based on value
 * @param {number} value - Value to check
 * @returns {string} Tailwind background color class
 */
export const getValueBgColor = (value) => {
    if (value > 0) return 'bg-emerald-500/20';
    if (value < 0) return 'bg-red-500/20';
    return 'bg-slate-500/20';
};

/**
 * Sleep function for async operations
 * @param {number} ms - Milliseconds to sleep
 * @returns {Promise} Promise that resolves after ms
 */
export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Retry a function with exponential backoff
 * @param {Function} fn - Function to retry
 * @param {number} maxRetries - Maximum retries
 * @param {number} baseDelay - Base delay in ms
 * @returns {Promise} Result of function
 */
export const retryWithBackoff = async (fn, maxRetries = 3, baseDelay = 1000) => {
    let lastError;
    for (let i = 0; i < maxRetries; i++) {
        try {
            return await fn();
        } catch (error) {
            lastError = error;
            if (i < maxRetries - 1) {
                await sleep(baseDelay * Math.pow(2, i));
            }
        }
    }
    throw lastError;
};

/**
 * Local storage helpers with JSON parsing
 */
export const storage = {
    get: (key, defaultValue = null) => {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch {
            return defaultValue;
        }
    },
    set: (key, value) => {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch {
            return false;
        }
    },
    remove: (key) => {
        try {
            localStorage.removeItem(key);
            return true;
        } catch {
            return false;
        }
    },
    clear: () => {
        try {
            localStorage.clear();
            return true;
        } catch {
            return false;
        }
    },
};

export default {
    formatCurrency,
    formatNumber,
    formatPercent,
    formatTimestamp,
    formatTime,
    calculatePnLPercent,
    truncateText,
    generateId,
    debounce,
    throttle,
    deepClone,
    isEmpty,
    getValueColor,
    getValueBgColor,
    sleep,
    retryWithBackoff,
    storage,
};
