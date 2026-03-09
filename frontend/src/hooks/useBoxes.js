/**
 * useBoxes Hook
 * Manages Golden Rectangle box data with Socket.io real-time updates
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useSocket } from '../context/SocketContext';
import {
    transformBoxData,
    transformBoxes,
    filterBoxesByStatus,
    filterBoxesByTimeRange,
    filterBoxesByMarket,
    sortBoxesByTime,
    getBoxStatistics,
    generateSampleBoxes,
    BOX_STATUS,
} from '../utils/boxUtils';

/**
 * useBoxes - Hook for managing Golden Rectangle boxes
 * 
 * @param {Object} options - Hook options
 * @param {string} options.marketId - Filter by market ID
 * @param {Array} options.statuses - Filter by statuses
 * @param {boolean} options.useSampleData - Use sample data for testing
 * @param {number} options.maxBoxes - Maximum number of boxes to keep
 * @param {boolean} options.autoSubscribe - Auto-subscribe to box updates
 * @returns {Object} - Box state and utilities
 */
export const useBoxes = ({
    marketId = null,
    statuses = null,
    useSampleData = false,
    maxBoxes = 100,
    autoSubscribe = true,
} = {}) => {
    const { socket, connected } = useSocket();

    // Box state
    const [boxes, setBoxes] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    const [lastUpdate, setLastUpdate] = useState(null);

    // Subscription state
    const [isSubscribed, setIsSubscribed] = useState(false);
    const subscriptionsRef = useRef(new Set());

    // Initialize with sample data if enabled
    useEffect(() => {
        if (useSampleData) {
            const sampleBoxes = transformBoxes(generateSampleBoxes(10));
            setBoxes(sampleBoxes);
            setIsLoading(false);
            setLastUpdate(new Date().toISOString());
        }
    }, [useSampleData]);

    // Subscribe to box updates
    useEffect(() => {
        if (!socket || !connected || !autoSubscribe || useSampleData) return;

        // Subscribe to box events
        const handleBoxUpdate = (data) => {
            if (data && data.boxes) {
                setBoxes((prevBoxes) => {
                    const newBoxes = transformBoxes(data.boxes);
                    // Merge with existing boxes, updating duplicates
                    const mergedBoxes = [...prevBoxes];
                    newBoxes.forEach((newBox) => {
                        const existingIndex = mergedBoxes.findIndex((b) => b.id === newBox.id);
                        if (existingIndex >= 0) {
                            mergedBoxes[existingIndex] = newBox;
                        } else {
                            mergedBoxes.push(newBox);
                        }
                    });
                    // Sort and limit
                    return sortBoxesByTime(mergedBoxes).slice(0, maxBoxes);
                });
                setLastUpdate(new Date().toISOString());
                setIsLoading(false);
            }
        };

        const handleNewBox = (data) => {
            if (data && data.box) {
                const newBox = transformBoxData(data.box);
                if (newBox) {
                    setBoxes((prevBoxes) => {
                        // Check if box already exists
                        const existingIndex = prevBoxes.findIndex((b) => b.id === newBox.id);
                        if (existingIndex >= 0) {
                            // Update existing box
                            const updated = [...prevBoxes];
                            updated[existingIndex] = newBox;
                            return updated;
                        }
                        // Add new box at the beginning
                        return [newBox, ...prevBoxes].slice(0, maxBoxes);
                    });
                    setLastUpdate(new Date().toISOString());
                }
            }
        };

        const handleBoxStatusChange = (data) => {
            if (data && data.boxId && data.status) {
                setBoxes((prevBoxes) =>
                    prevBoxes.map((box) =>
                        box.id === data.boxId ? { ...box, status: data.status } : box
                    )
                );
                setLastUpdate(new Date().toISOString());
            }
        };

        const handleBoxRemoved = (data) => {
            if (data && data.boxId) {
                setBoxes((prevBoxes) => prevBoxes.filter((box) => box.id !== data.boxId));
                setLastUpdate(new Date().toISOString());
            }
        };

        const handleError = (err) => {
            console.error('Box subscription error:', err);
            setError(err?.message || 'Unknown error');
            setIsLoading(false);
        };

        // Register event handlers
        socket.on('boxes:update', handleBoxUpdate);
        socket.on('box:new', handleNewBox);
        socket.on('box:status', handleBoxStatusChange);
        socket.on('box:removed', handleBoxRemoved);
        socket.on('error', handleError);

        // Subscribe to market boxes if marketId provided
        if (marketId) {
            socket.emit('subscribe_boxes', { market_id: marketId });
            subscriptionsRef.current.add(marketId);
        } else {
            socket.emit('subscribe_boxes', {});
        }

        setIsSubscribed(true);

        // Request initial box data
        socket.emit('get_boxes', { market_id: marketId });

        // Cleanup
        return () => {
            socket.off('boxes:update', handleBoxUpdate);
            socket.off('box:new', handleNewBox);
            socket.off('box:status', handleBoxStatusChange);
            socket.off('box:removed', handleBoxRemoved);
            socket.off('error', handleError);

            if (marketId) {
                socket.emit('unsubscribe_boxes', { market_id: marketId });
                subscriptionsRef.current.delete(marketId);
            }

            setIsSubscribed(false);
        };
    }, [socket, connected, autoSubscribe, useSampleData, marketId, maxBoxes]);

    // Filtered boxes based on options
    const filteredBoxes = useMemo(() => {
        let result = boxes;

        // Filter by market
        if (marketId) {
            result = filterBoxesByMarket(result, marketId);
        }

        // Filter by statuses
        if (statuses && statuses.length > 0) {
            result = filterBoxesByStatus(result, statuses);
        }

        return result;
    }, [boxes, marketId, statuses]);

    // Box statistics
    const statistics = useMemo(() => getBoxStatistics(filteredBoxes), [filteredBoxes]);

    // Subscribe to a specific market's boxes
    const subscribeToMarket = useCallback(
        (newMarketId) => {
            if (!socket || !connected) return;

            // Unsubscribe from previous market if any
            subscriptionsRef.current.forEach((subId) => {
                socket.emit('unsubscribe_boxes', { market_id: subId });
            });
            subscriptionsRef.current.clear();

            // Subscribe to new market
            socket.emit('subscribe_boxes', { market_id: newMarketId });
            subscriptionsRef.current.add(newMarketId);

            // Request boxes for new market
            socket.emit('get_boxes', { market_id: newMarketId });
        },
        [socket, connected]
    );

    // Unsubscribe from market
    const unsubscribeFromMarket = useCallback(
        (unsubMarketId) => {
            if (!socket || !connected) return;

            socket.emit('unsubscribe_boxes', { market_id: unsubMarketId });
            subscriptionsRef.current.delete(unsubMarketId);
        },
        [socket, connected]
    );

    // Manually refresh boxes
    const refreshBoxes = useCallback(() => {
        if (!socket || !connected) return;

        setIsLoading(true);
        socket.emit('get_boxes', { market_id: marketId });
    }, [socket, connected, marketId]);

    // Add a box manually (for testing)
    const addBox = useCallback((box) => {
        const transformedBox = transformBoxData(box);
        if (transformedBox) {
            setBoxes((prevBoxes) => [transformedBox, ...prevBoxes].slice(0, maxBoxes));
        }
    }, [maxBoxes]);

    // Remove a box manually
    const removeBox = useCallback((boxId) => {
        setBoxes((prevBoxes) => prevBoxes.filter((box) => box.id !== boxId));
    }, []);

    // Update box status
    const updateBoxStatus = useCallback((boxId, status) => {
        setBoxes((prevBoxes) =>
            prevBoxes.map((box) =>
                box.id === boxId ? { ...box, status } : box
            )
        );
    }, []);

    // Clear all boxes
    const clearBoxes = useCallback(() => {
        setBoxes([]);
    }, []);

    // Get boxes by time range
    const getBoxesByTimeRange = useCallback(
        (timeStart, timeEnd) => {
            return filterBoxesByTimeRange(filteredBoxes, timeStart, timeEnd);
        },
        [filteredBoxes]
    );

    // Get boxes by status
    const getBoxesByStatus = useCallback(
        (status) => {
            return filterBoxesByStatus(filteredBoxes, status);
        },
        [filteredBoxes]
    );

    // Get active boxes
    const activeBoxes = useMemo(
        () => filterBoxesByStatus(filteredBoxes, BOX_STATUS.ACTIVE),
        [filteredBoxes]
    );

    // Get triggered boxes
    const triggeredBoxes = useMemo(
        () => filterBoxesByStatus(filteredBoxes, BOX_STATUS.TRIGGERED),
        [filteredBoxes]
    );

    return {
        // State
        boxes: filteredBoxes,
        activeBoxes,
        triggeredBoxes,
        isLoading,
        error,
        lastUpdate,
        isSubscribed,
        statistics,

        // Actions
        subscribeToMarket,
        unsubscribeFromMarket,
        refreshBoxes,
        addBox,
        removeBox,
        updateBoxStatus,
        clearBoxes,

        // Utilities
        getBoxesByTimeRange,
        getBoxesByStatus,
    };
};

/**
 * useBoxHover - Hook for managing box hover state
 * 
 * @returns {Object} - Hover state and handlers
 */
export const useBoxHover = () => {
    const [hoveredBox, setHoveredBox] = useState(null);
    const [hoverPosition, setHoverPosition] = useState({ x: 0, y: 0 });

    const handleBoxHover = useCallback((box, position) => {
        setHoveredBox(box);
        if (position) {
            setHoverPosition(position);
        }
    }, []);

    const clearHover = useCallback(() => {
        setHoveredBox(null);
    }, []);

    return {
        hoveredBox,
        hoverPosition,
        handleBoxHover,
        clearHover,
    };
};

/**
 * useBoxSelection - Hook for managing box selection state
 * 
 * @returns {Object} - Selection state and handlers
 */
export const useBoxSelection = () => {
    const [selectedBox, setSelectedBox] = useState(null);
    const [selectedBoxes, setSelectedBoxes] = useState(new Set());

    const selectBox = useCallback((box) => {
        setSelectedBox(box);
    }, []);

    const toggleBoxSelection = useCallback((boxId) => {
        setSelectedBoxes((prev) => {
            const newSet = new Set(prev);
            if (newSet.has(boxId)) {
                newSet.delete(boxId);
            } else {
                newSet.add(boxId);
            }
            return newSet;
        });
    }, []);

    const clearSelection = useCallback(() => {
        setSelectedBox(null);
        setSelectedBoxes(new Set());
    }, []);

    const selectAll = useCallback((boxIds) => {
        setSelectedBoxes(new Set(boxIds));
    }, []);

    return {
        selectedBox,
        selectedBoxes,
        selectBox,
        toggleBoxSelection,
        clearSelection,
        selectAll,
        isBoxSelected: (boxId) => selectedBoxes.has(boxId),
    };
};

/**
 * useBoxFilters - Hook for managing box filters
 * 
 * @param {Object} initialFilters - Initial filter values
 * @returns {Object} - Filter state and handlers
 */
export const useBoxFilters = (initialFilters = {}) => {
    const [filters, setFilters] = useState({
        marketId: initialFilters.marketId || null,
        statuses: initialFilters.statuses || null,
        timeRange: initialFilters.timeRange || null,
        minConfidence: initialFilters.minConfidence || 0,
        ...initialFilters,
    });

    const setFilter = useCallback((key, value) => {
        setFilters((prev) => ({ ...prev, [key]: value }));
    }, []);

    const setFiltersMultiple = useCallback((newFilters) => {
        setFilters((prev) => ({ ...prev, ...newFilters }));
    }, []);

    const resetFilters = useCallback(() => {
        setFilters({
            marketId: null,
            statuses: null,
            timeRange: null,
            minConfidence: 0,
        });
    }, []);

    const applyFilters = useCallback(
        (boxes) => {
            let result = boxes;

            if (filters.marketId) {
                result = filterBoxesByMarket(result, filters.marketId);
            }

            if (filters.statuses && filters.statuses.length > 0) {
                result = filterBoxesByStatus(result, filters.statuses);
            }

            if (filters.timeRange) {
                const { start, end } = filters.timeRange;
                result = filterBoxesByTimeRange(result, start, end);
            }

            if (filters.minConfidence > 0) {
                result = result.filter((box) => box.confidence >= filters.minConfidence);
            }

            return result;
        },
        [filters]
    );

    return {
        filters,
        setFilter,
        setFiltersMultiple,
        resetFilters,
        applyFilters,
    };
};

export default useBoxes;
