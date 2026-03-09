/**
 * Box Utilities for Golden Rectangle Visualization
 * Helper functions for box data transformation, styling, and coordinate conversion
 */

import { CHART_COLORS } from './chartUtils';

/**
 * Box status types
 */
export const BOX_STATUS = {
    ACTIVE: 'active',
    TRIGGERED: 'triggered',
    EXPIRED: 'expired',
    FAILED: 'failed',
};

/**
 * Box colors by status
 */
export const BOX_COLORS = {
    [BOX_STATUS.ACTIVE]: {
        fill: 'rgba(59, 130, 246, 0.15)', // Blue with transparency
        stroke: '#3b82f6',
        text: '#60a5fa',
    },
    [BOX_STATUS.TRIGGERED]: {
        fill: 'rgba(234, 179, 8, 0.15)', // Gold with transparency
        stroke: '#eab308',
        text: '#fbbf24',
    },
    [BOX_STATUS.EXPIRED]: {
        fill: 'rgba(100, 116, 139, 0.1)', // Gray with transparency
        stroke: '#64748b',
        text: '#94a3b8',
    },
    [BOX_STATUS.FAILED]: {
        fill: 'rgba(239, 68, 68, 0.15)', // Red with transparency
        stroke: '#ef4444',
        text: '#f87171',
    },
};

/**
 * Box line styles by status
 */
export const BOX_LINE_STYLES = {
    [BOX_STATUS.ACTIVE]: 0, // Solid
    [BOX_STATUS.TRIGGERED]: 0, // Solid
    [BOX_STATUS.EXPIRED]: 2, // Dashed
    [BOX_STATUS.FAILED]: 2, // Dashed
};

/**
 * Box line widths by status
 */
export const BOX_LINE_WIDTHS = {
    [BOX_STATUS.ACTIVE]: 2,
    [BOX_STATUS.TRIGGERED]: 2,
    [BOX_STATUS.EXPIRED]: 1,
    [BOX_STATUS.FAILED]: 1,
};

/**
 * Convert backend box data to chart overlay format
 * @param {Object} box - Backend box data
 * @returns {Object} - Chart overlay box data
 */
export const transformBoxData = (box) => {
    if (!box) return null;

    const timeStart = typeof box.time_start === 'number'
        ? box.time_start
        : Math.floor(new Date(box.time_start || box.timeStart).getTime() / 1000);

    const timeEnd = typeof box.time_end === 'number'
        ? box.time_end
        : Math.floor(new Date(box.time_end || box.timeEnd).getTime() / 1000);

    const createdAt = typeof box.created_at === 'number'
        ? box.created_at
        : Math.floor(new Date(box.created_at || box.createdAt).getTime() / 1000);

    return {
        id: box.id || `box-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        marketId: box.market_id || box.marketId,
        timeStart,
        timeEnd,
        priceLow: box.price_low || box.priceLow,
        priceHigh: box.price_high || box.priceHigh,
        confidence: box.confidence || 0.5,
        expectedMove: box.expected_move || box.expectedMove || 0,
        status: box.status || BOX_STATUS.ACTIVE,
        createdAt,
        // Additional metadata
        metadata: box.metadata || {},
    };
};

/**
 * Transform multiple boxes
 * @param {Array} boxes - Array of backend box data
 * @returns {Array} - Array of transformed box data
 */
export const transformBoxes = (boxes) => {
    if (!Array.isArray(boxes)) return [];
    return boxes.map(transformBoxData).filter(Boolean);
};

/**
 * Get box styling based on status
 * @param {string} status - Box status
 * @returns {Object} - Styling configuration
 */
export const getBoxStyle = (status) => {
    const colors = BOX_COLORS[status] || BOX_COLORS[BOX_STATUS.ACTIVE];
    const lineStyle = BOX_LINE_STYLES[status] ?? 0;
    const lineWidth = BOX_LINE_WIDTHS[status] ?? 2;

    return {
        fillColor: colors.fill,
        strokeColor: colors.stroke,
        textColor: colors.text,
        lineStyle,
        lineWidth,
    };
};

/**
 * Calculate box dimensions for rendering
 * @param {Object} box - Transformed box data
 * @param {Object} timeScale - Chart time scale
 * @param {Object} priceScale - Chart price scale
 * @returns {Object|null} - Box dimensions in pixels
 */
export const calculateBoxDimensions = (box, timeScale, priceScale) => {
    if (!box || !timeScale || !priceScale) return null;

    try {
        // Convert time to x coordinate
        const xStart = timeScale.timeToCoordinate(box.timeStart);
        const xEnd = timeScale.timeToCoordinate(box.timeEnd);

        // Convert price to y coordinate
        const yHigh = priceScale.priceToCoordinate(box.priceHigh);
        const yLow = priceScale.priceToCoordinate(box.priceLow);

        // Check if coordinates are valid
        if (xStart === null || xEnd === null || yHigh === null || yLow === null) {
            return null;
        }

        return {
            x: Math.min(xStart, xEnd),
            y: Math.min(yHigh, yLow),
            width: Math.abs(xEnd - xStart),
            height: Math.abs(yLow - yHigh),
            xStart,
            xEnd,
            yHigh,
            yLow,
        };
    } catch (error) {
        console.error('Error calculating box dimensions:', error);
        return null;
    }
};

/**
 * Check if a point is inside a box
 * @param {Object} point - Point with x, y coordinates
 * @param {Object} boxDimensions - Box dimensions from calculateBoxDimensions
 * @returns {boolean} - True if point is inside box
 */
export const isPointInBox = (point, boxDimensions) => {
    if (!point || !boxDimensions) return false;

    const { x, y } = point;
    const { x: boxX, y: boxY, width, height } = boxDimensions;

    return x >= boxX && x <= boxX + width && y >= boxY && y <= boxY + height;
};

/**
 * Filter boxes by status
 * @param {Array} boxes - Array of transformed boxes
 * @param {string|Array} statuses - Status or array of statuses to filter by
 * @returns {Array} - Filtered boxes
 */
export const filterBoxesByStatus = (boxes, statuses) => {
    if (!Array.isArray(boxes)) return [];

    const statusArray = Array.isArray(statuses) ? statuses : [statuses];
    return boxes.filter(box => statusArray.includes(box.status));
};

/**
 * Filter boxes by time range
 * @param {Array} boxes - Array of transformed boxes
 * @param {number} timeStart - Start time (Unix timestamp)
 * @param {number} timeEnd - End time (Unix timestamp)
 * @returns {Array} - Filtered boxes
 */
export const filterBoxesByTimeRange = (boxes, timeStart, timeEnd) => {
    if (!Array.isArray(boxes)) return [];

    return boxes.filter(box => {
        // Box overlaps with time range
        return box.timeStart <= timeEnd && box.timeEnd >= timeStart;
    });
};

/**
 * Filter boxes by market
 * @param {Array} boxes - Array of transformed boxes
 * @param {string} marketId - Market ID to filter by
 * @returns {Array} - Filtered boxes
 */
export const filterBoxesByMarket = (boxes, marketId) => {
    if (!Array.isArray(boxes)) return [];
    return boxes.filter(box => box.marketId === marketId);
};

/**
 * Sort boxes by creation time (newest first)
 * @param {Array} boxes - Array of transformed boxes
 * @returns {Array} - Sorted boxes
 */
export const sortBoxesByTime = (boxes) => {
    if (!Array.isArray(boxes)) return [];
    return [...boxes].sort((a, b) => b.createdAt - a.createdAt);
};

/**
 * Get box statistics
 * @param {Array} boxes - Array of transformed boxes
 * @returns {Object} - Statistics object
 */
export const getBoxStatistics = (boxes) => {
    if (!Array.isArray(boxes) || boxes.length === 0) {
        return {
            total: 0,
            active: 0,
            triggered: 0,
            expired: 0,
            failed: 0,
            avgConfidence: 0,
            avgExpectedMove: 0,
        };
    }

    const stats = {
        total: boxes.length,
        active: 0,
        triggered: 0,
        expired: 0,
        failed: 0,
        totalConfidence: 0,
        totalExpectedMove: 0,
    };

    boxes.forEach(box => {
        switch (box.status) {
            case BOX_STATUS.ACTIVE:
                stats.active++;
                break;
            case BOX_STATUS.TRIGGERED:
                stats.triggered++;
                break;
            case BOX_STATUS.EXPIRED:
                stats.expired++;
                break;
            case BOX_STATUS.FAILED:
                stats.failed++;
                break;
        }
        stats.totalConfidence += box.confidence || 0;
        stats.totalExpectedMove += Math.abs(box.expectedMove || 0);
    });

    stats.avgConfidence = stats.totalConfidence / stats.total;
    stats.avgExpectedMove = stats.totalExpectedMove / stats.total;

    return stats;
};

/**
 * Format box time range for display
 * @param {Object} box - Transformed box data
 * @returns {string} - Formatted time range
 */
export const formatBoxTimeRange = (box) => {
    if (!box) return '-';

    const startDate = new Date(box.timeStart * 1000);
    const endDate = new Date(box.timeEnd * 1000);

    const formatTime = (date) => {
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    return `${formatTime(startDate)} - ${formatTime(endDate)}`;
};

/**
 * Format box price range for display
 * @param {Object} box - Transformed box data
 * @param {number} precision - Decimal precision
 * @returns {string} - Formatted price range
 */
export const formatBoxPriceRange = (box, precision = 2) => {
    if (!box) return '-';
    return `${box.priceLow.toFixed(precision)} - ${box.priceHigh.toFixed(precision)}`;
};

/**
 * Calculate box age in seconds
 * @param {Object} box - Transformed box data
 * @returns {number} - Age in seconds
 */
export const getBoxAge = (box) => {
    if (!box) return 0;
    return Math.floor(Date.now() / 1000) - box.createdAt;
};

/**
 * Calculate remaining time for box in seconds
 * @param {Object} box - Transformed box data
 * @returns {number} - Remaining time in seconds (negative if expired)
 */
export const getBoxRemainingTime = (box) => {
    if (!box) return 0;
    return box.timeEnd - Math.floor(Date.now() / 1000);
};

/**
 * Check if box is currently active (within time window)
 * @param {Object} box - Transformed box data
 * @returns {boolean} - True if box is within its time window
 */
export const isBoxInTimeWindow = (box) => {
    if (!box) return false;
    const now = Math.floor(Date.now() / 1000);
    return now >= box.timeStart && now <= box.timeEnd;
};

/**
 * Generate sample box data for testing
 * @param {number} count - Number of boxes to generate
 * @param {number} basePrice - Base price for boxes
 * @returns {Array} - Sample box data
 */
export const generateSampleBoxes = (count = 5, basePrice = 100) => {
    const boxes = [];
    const now = Math.floor(Date.now() / 1000);
    const statuses = Object.values(BOX_STATUS);

    for (let i = 0; i < count; i++) {
        const duration = Math.floor(Math.random() * 3600) + 1800; // 30-90 minutes
        const timeStart = now - Math.floor(Math.random() * 7200); // Within last 2 hours
        const priceOffset = (Math.random() - 0.5) * 10;
        const priceRange = Math.random() * 2 + 0.5;

        boxes.push({
            id: `sample-box-${i}`,
            market_id: 'sample-market',
            time_start: timeStart,
            time_end: timeStart + duration,
            price_low: basePrice + priceOffset,
            price_high: basePrice + priceOffset + priceRange,
            confidence: Math.random() * 0.5 + 0.5,
            expected_move: (Math.random() - 0.3) * 5,
            status: statuses[i % statuses.length],
            created_at: timeStart - Math.floor(Math.random() * 300),
        });
    }

    return boxes;
};

/**
 * Create box tooltip content
 * @param {Object} box - Transformed box data
 * @returns {Object} - Tooltip content object
 */
export const createBoxTooltipContent = (box) => {
    if (!box) return null;

    const style = getBoxStyle(box.status);
    const remainingTime = getBoxRemainingTime(box);
    const age = getBoxAge(box);

    return {
        id: box.id,
        status: box.status.toUpperCase(),
        priceRange: formatBoxPriceRange(box),
        timeRange: formatBoxTimeRange(box),
        confidence: `${(box.confidence * 100).toFixed(1)}%`,
        expectedMove: `${box.expectedMove >= 0 ? '+' : ''}${box.expectedMove.toFixed(2)}`,
        age: formatDuration(age),
        remaining: remainingTime > 0 ? formatDuration(remainingTime) : 'Expired',
        color: style.strokeColor,
    };
};

/**
 * Format duration in seconds to human readable string
 * @param {number} seconds - Duration in seconds
 * @returns {string} - Formatted duration
 */
const formatDuration = (seconds) => {
    if (seconds < 60) {
        return `${seconds}s`;
    } else if (seconds < 3600) {
        const minutes = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${minutes}m ${secs}s`;
    } else {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${minutes}m`;
    }
};

export default {
    BOX_STATUS,
    BOX_COLORS,
    transformBoxData,
    transformBoxes,
    getBoxStyle,
    calculateBoxDimensions,
    isPointInBox,
    filterBoxesByStatus,
    filterBoxesByTimeRange,
    filterBoxesByMarket,
    sortBoxesByTime,
    getBoxStatistics,
    formatBoxTimeRange,
    formatBoxPriceRange,
    getBoxAge,
    getBoxRemainingTime,
    isBoxInTimeWindow,
    generateSampleBoxes,
    createBoxTooltipContent,
};
