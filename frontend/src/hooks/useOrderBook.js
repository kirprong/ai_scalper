/**
 * useOrderBook Hook
 * 
 * Custom hook for subscribing to and managing order book state.
 * Handles snapshot and delta updates via Socket.io.
 */
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useSocket } from '../context/SocketContext';
import {
    formatOrderBook,
    mergeOrderBookDelta,
    calculateSpread,
    calculateCumulativeDepth,
    calculateImbalance,
    getOrderBookStats,
} from '../utils/orderBookUtils';

/**
 * Default order book state
 */
const DEFAULT_ORDER_BOOK = {
    market_id: null,
    bids: [],
    asks: [],
    timestamp: null,
    sequence: 0,
};

/**
 * Hook options defaults
 */
const DEFAULT_OPTIONS = {
    tickSize: 0.01,
    maxLevels: 20,
    priceDecimals: 2,
    sizeDecimals: 2,
    enableAggregation: true,
};

/**
 * useOrderBook Hook
 * 
 * @param {string} marketId - Market ID to subscribe to
 * @param {Object} options - Configuration options
 * @returns {Object} Order book state and utilities
 */
export function useOrderBook(marketId, options = {}) {
    const opts = { ...DEFAULT_OPTIONS, ...options };

    // Socket context
    const { socket, connected, on, off, emit } = useSocket();

    // Order book state
    const [rawOrderBook, setRawOrderBook] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [isSubscribed, setIsSubscribed] = useState(false);

    // Refs for managing updates
    const lastSequenceRef = useRef(0);
    const updateCountRef = useRef(0);
    const subscriptionRef = useRef(null);

    /**
     * Handle order book snapshot
     */
    const handleSnapshot = useCallback((data) => {
        if (data.market_id !== marketId) return;

        setIsLoading(false);
        setError(null);
        setRawOrderBook({
            market_id: data.market_id,
            bids: data.bids || [],
            asks: data.asks || [],
            timestamp: data.timestamp || Date.now(),
            sequence: data.sequence || 0,
        });
        lastSequenceRef.current = data.sequence || 0;
        updateCountRef.current += 1;
    }, [marketId]);

    /**
     * Handle order book delta update
     */
    const handleDelta = useCallback((delta) => {
        if (delta.market_id !== marketId) return;

        // Check sequence ordering
        if (delta.sequence && delta.sequence <= lastSequenceRef.current) {
            console.warn('Received out-of-order delta, ignoring');
            return;
        }

        setRawOrderBook((prev) => {
            if (!prev) {
                // No existing book, wait for snapshot
                return null;
            }

            const merged = mergeOrderBookDelta(prev, delta);
            lastSequenceRef.current = delta.sequence || lastSequenceRef.current + 1;
            updateCountRef.current += 1;

            return merged;
        });
    }, [marketId]);

    /**
     * Handle order book clear
     */
    const handleClear = useCallback((data) => {
        if (data.market_id && data.market_id !== marketId) return;

        setRawOrderBook(null);
        lastSequenceRef.current = 0;
        updateCountRef.current = 0;
    }, [marketId]);

    /**
     * Handle errors
     */
    const handleError = useCallback((err) => {
        console.error('Order book error:', err);
        setError(err.message || 'Order book error');
        setIsLoading(false);
    }, []);

    /**
     * Subscribe to order book updates
     */
    const subscribe = useCallback(() => {
        if (!socket || !connected || !marketId) {
            console.warn('Cannot subscribe: socket not connected or no market ID');
            return;
        }

        setIsLoading(true);
        setError(null);

        // Register event handlers
        on('order_book_snapshot', handleSnapshot);
        on('order_book_delta', handleDelta);
        on('order_book_clear', handleClear);
        on('order_book_error', handleError);

        // Subscribe to market
        emit('subscribe_order_book', { market_id: marketId }, (response) => {
            if (response?.success) {
                setIsSubscribed(true);
                console.log(`✅ Subscribed to order book for market ${marketId}`);
            } else {
                setError(response?.error || 'Failed to subscribe to order book');
                setIsLoading(false);
            }
        });

        subscriptionRef.current = marketId;
    }, [socket, connected, marketId, on, emit, handleSnapshot, handleDelta, handleClear, handleError]);

    /**
     * Unsubscribe from order book updates
     */
    const unsubscribe = useCallback(() => {
        if (!socket || !marketId) return;

        // Unregister event handlers
        off('order_book_snapshot');
        off('order_book_delta');
        off('order_book_clear');
        off('order_book_error');

        // Unsubscribe from market
        emit('unsubscribe_order_book', { market_id: marketId });

        setIsSubscribed(false);
        setRawOrderBook(null);
        lastSequenceRef.current = 0;
        subscriptionRef.current = null;

        console.log(`✅ Unsubscribed from order book for market ${marketId}`);
    }, [socket, marketId, off, emit]);

    /**
     * Request order book snapshot
     */
    const requestSnapshot = useCallback(() => {
        if (!socket || !connected || !marketId) return;

        emit('request_order_book', { market_id: marketId });
    }, [socket, connected, marketId, emit]);

    /**
     * Subscribe on mount, unsubscribe on unmount
     */
    useEffect(() => {
        if (marketId && connected) {
            subscribe();
        }

        return () => {
            if (isSubscribed) {
                unsubscribe();
            }
        };
    }, [marketId, connected]); // eslint-disable-line react-hooks/exhaustive-deps

    /**
     * Re-subscribe on reconnection
     */
    useEffect(() => {
        if (connected && marketId && subscriptionRef.current === marketId && !isSubscribed) {
            subscribe();
        }
    }, [connected, marketId, isSubscribed, subscribe]);

    /**
     * Formatted order book data
     */
    const formattedOrderBook = useMemo(() => {
        if (!rawOrderBook) return null;

        return formatOrderBook(rawOrderBook, {
            tickSize: opts.tickSize,
            maxLevels: opts.maxLevels,
            priceDecimals: opts.priceDecimals,
            sizeDecimals: opts.sizeDecimals,
        });
    }, [rawOrderBook, opts.tickSize, opts.maxLevels, opts.priceDecimals, opts.sizeDecimals]);

    /**
     * Spread information
     */
    const spread = useMemo(() => {
        if (!rawOrderBook) return null;
        return calculateSpread(rawOrderBook.bids, rawOrderBook.asks);
    }, [rawOrderBook]);

    /**
     * Cumulative depth
     */
    const cumulativeDepth = useMemo(() => {
        if (!rawOrderBook) return null;
        return calculateCumulativeDepth(rawOrderBook.bids, rawOrderBook.asks);
    }, [rawOrderBook]);

    /**
     * Order book imbalance
     */
    const imbalance = useMemo(() => {
        if (!cumulativeDepth) return null;
        return calculateImbalance(cumulativeDepth.totalBidDepth, cumulativeDepth.totalAskDepth);
    }, [cumulativeDepth]);

    /**
     * Order book statistics
     */
    const stats = useMemo(() => {
        if (!rawOrderBook) return null;
        return getOrderBookStats(rawOrderBook);
    }, [rawOrderBook]);

    /**
     * Update count (for debugging/monitoring)
     */
    const updateCount = updateCountRef.current;

    return {
        // Raw order book data
        rawOrderBook,

        // Formatted order book
        orderBook: formattedOrderBook,

        // Derived data
        spread,
        cumulativeDepth,
        imbalance,
        stats,

        // State
        isLoading,
        error,
        isSubscribed,
        updateCount,

        // Actions
        subscribe,
        unsubscribe,
        requestSnapshot,

        // Utilities
        lastUpdate: rawOrderBook?.timestamp || null,
        sequence: lastSequenceRef.current,
    };
}

/**
 * useOrderBookStats Hook
 * 
 * Lightweight hook that only returns statistics for an order book.
 * Useful for displaying summary information without full order book rendering.
 * 
 * @param {string} marketId - Market ID
 * @returns {Object} Order book statistics
 */
export function useOrderBookStats(marketId) {
    const { stats, isLoading, error } = useOrderBook(marketId, { maxLevels: 10 });

    return {
        stats,
        isLoading,
        error,
    };
}

/**
 * useOrderBookSpread Hook
 * 
 * Lightweight hook that only returns spread information.
 * 
 * @param {string} marketId - Market ID
 * @returns {Object} Spread information
 */
export function useOrderBookSpread(marketId) {
    const { spread, isLoading, error } = useOrderBook(marketId, { maxLevels: 5 });

    return {
        spread,
        isLoading,
        error,
    };
}

export default useOrderBook;
