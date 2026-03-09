import { useEffect, useCallback, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import useTradingStore from '../stores/tradingStore';
import { useSocket } from '../context/SocketContext';

/**
 * Custom hook for handling socket events and real-time updates
 * Integrates with React Query for cache invalidation
 */
export const useSocketEvents = () => {
    const queryClient = useQueryClient();
    const { socket, isConnected } = useSocket();
    const {
        setConnected,
        setLastUpdate,
        updateLastPrice,
        addNotification,
        setActiveSignals,
        setOrderBook,
        setPositions,
        setOrders,
        setMetrics,
    } = useTradingStore();

    // Track if listeners are registered
    const listenersRegistered = useRef(false);

    // Handle connection
    const handleConnect = useCallback(() => {
        setConnected(true);
        setLastUpdate(new Date().toISOString());
        addNotification({
            type: 'info',
            message: 'Connected to server',
        });
    }, [setConnected, setLastUpdate, addNotification]);

    // Handle disconnection
    const handleDisconnect = useCallback(() => {
        setConnected(false);
        addNotification({
            type: 'warning',
            message: 'Disconnected from server',
        });
    }, [setConnected, addNotification]);

    // Handle price update
    const handlePriceUpdate = useCallback((data) => {
        updateLastPrice(data.price);
        setLastUpdate(new Date().toISOString());

        // Invalidate price history query
        queryClient.invalidateQueries({ queryKey: ['priceHistory', data.marketId] });
    }, [updateLastPrice, setLastUpdate, queryClient]);

    // Handle signal update
    const handleSignalUpdate = useCallback((data) => {
        setActiveSignals(data.signals);
        setLastUpdate(new Date().toISOString());

        if (data.newSignal) {
            addNotification({
                type: 'signal',
                message: `New ${data.newSignal.type} signal: ${data.newSignal.market}`,
                data: data.newSignal,
            });
        }
    }, [setActiveSignals, setLastUpdate, addNotification]);

    // Handle order book update
    const handleOrderBookUpdate = useCallback((data) => {
        setOrderBook(data);
        setLastUpdate(new Date().toISOString());
    }, [setOrderBook, setLastUpdate]);

    // Handle position update
    const handlePositionUpdate = useCallback((data) => {
        setPositions(data.positions);
        setLastUpdate(new Date().toISOString());

        // Invalidate positions query
        queryClient.invalidateQueries({ queryKey: ['positions'] });
    }, [setPositions, setLastUpdate, queryClient]);

    // Handle order update
    const handleOrderUpdate = useCallback((data) => {
        setOrders(data.orders);
        setLastUpdate(new Date().toISOString());

        // Invalidate orders query
        queryClient.invalidateQueries({ queryKey: ['orders'] });

        if (data.newOrder) {
            addNotification({
                type: 'order',
                message: `Order ${data.newOrder.status}: ${data.newOrder.market}`,
                data: data.newOrder,
            });
        }
    }, [setOrders, setLastUpdate, queryClient, addNotification]);

    // Handle metrics update
    const handleMetricsUpdate = useCallback((data) => {
        setMetrics(data);
        setLastUpdate(new Date().toISOString());

        // Invalidate metrics queries
        queryClient.invalidateQueries({ queryKey: ['metrics'] });
    }, [setMetrics, setLastUpdate, queryClient]);

    // Register socket event listeners
    useEffect(() => {
        if (!socket || listenersRegistered.current) return;

        // Connection events
        socket.on('connect', handleConnect);
        socket.on('disconnect', handleDisconnect);

        // Data events
        socket.on('price:update', handlePriceUpdate);
        socket.on('signal:update', handleSignalUpdate);
        socket.on('orderbook:update', handleOrderBookUpdate);
        socket.on('position:update', handlePositionUpdate);
        socket.on('order:update', handleOrderUpdate);
        socket.on('metrics:update', handleMetricsUpdate);

        listenersRegistered.current = true;

        // Cleanup on unmount
        return () => {
            socket.off('connect', handleConnect);
            socket.off('disconnect', handleDisconnect);
            socket.off('price:update', handlePriceUpdate);
            socket.off('signal:update', handleSignalUpdate);
            socket.off('orderbook:update', handleOrderBookUpdate);
            socket.off('position:update', handlePositionUpdate);
            socket.off('order:update', handleOrderUpdate);
            socket.off('metrics:update', handleMetricsUpdate);
            listenersRegistered.current = false;
        };
    }, [
        socket,
        handleConnect,
        handleDisconnect,
        handlePriceUpdate,
        handleSignalUpdate,
        handleOrderBookUpdate,
        handlePositionUpdate,
        handleOrderUpdate,
        handleMetricsUpdate,
    ]);

    return { isConnected };
};

/**
 * Custom hook for trading operations
 */
export const useTrading = () => {
    const queryClient = useQueryClient();
    const store = useTradingStore();

    const refreshAll = useCallback(async () => {
        await Promise.all([
            queryClient.invalidateQueries({ queryKey: ['positions'] }),
            queryClient.invalidateQueries({ queryKey: ['orders'] }),
            queryClient.invalidateQueries({ queryKey: ['metrics'] }),
            queryClient.invalidateQueries({ queryKey: ['signals'] }),
        ]);
    }, [queryClient]);

    return {
        ...store,
        refreshAll,
    };
};

/**
 * Custom hook for local storage state
 */
export const useLocalStorage = (key, initialValue) => {
    const [storedValue, setStoredValue] = useState(() => {
        try {
            const item = window.localStorage.getItem(key);
            return item ? JSON.parse(item) : initialValue;
        } catch (error) {
            console.error('Error reading from localStorage:', error);
            return initialValue;
        }
    });

    const setValue = useCallback((value) => {
        try {
            const valueToStore = value instanceof Function ? value(storedValue) : value;
            setStoredValue(valueToStore);
            window.localStorage.setItem(key, JSON.stringify(valueToStore));
        } catch (error) {
            console.error('Error writing to localStorage:', error);
        }
    }, [key, storedValue]);

    return [storedValue, setValue];
};

/**
 * Custom hook for media queries
 */
export const useMediaQuery = (query) => {
    const [matches, setMatches] = useState(false);

    useEffect(() => {
        const media = window.matchMedia(query);
        if (media.matches !== matches) {
            setMatches(media.matches);
        }

        const listener = () => setMatches(media.matches);
        media.addEventListener('change', listener);

        return () => media.removeEventListener('change', listener);
    }, [matches, query]);

    return matches;
};

/**
 * Custom hook for interval
 */
export const useInterval = (callback, delay) => {
    const savedCallback = useRef(callback);

    useEffect(() => {
        savedCallback.current = callback;
    }, [callback]);

    useEffect(() => {
        if (delay === null) return;

        const id = setInterval(() => savedCallback.current(), delay);
        return () => clearInterval(id);
    }, [delay]);
};

/**
 * Custom hook for document title
 */
export const useDocumentTitle = (title) => {
    useEffect(() => {
        const previousTitle = document.title;
        document.title = title;

        return () => {
            document.title = previousTitle;
        };
    }, [title]);
};

export default {
    useSocketEvents,
    useTrading,
    useLocalStorage,
    useMediaQuery,
    useInterval,
    useDocumentTitle,
};
