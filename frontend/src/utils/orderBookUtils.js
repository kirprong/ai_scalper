/**
 * Order Book Utilities
 * 
 * Utility functions for processing and analyzing order book data.
 * Includes functions for calculating spread, cumulative depth, and aggregation.
 */

/**
 * Calculate the bid-ask spread
 * @param {Array} bids - Array of bid objects { price, size }
 * @param {Array} asks - Array of ask objects { price, size }
 * @returns {Object} Spread information { spread, spreadPercent, midPrice, bestBid, bestAsk }
 */
export function calculateSpread(bids, asks) {
    if (!bids?.length || !asks?.length) {
        return {
            spread: 0,
            spreadPercent: 0,
            midPrice: 0,
            bestBid: null,
            bestAsk: null,
        };
    }

    // Sort bids descending by price, asks ascending by price
    const sortedBids = [...bids].sort((a, b) => b.price - a.price);
    const sortedAsks = [...asks].sort((a, b) => a.price - b.price);

    const bestBid = sortedBids[0];
    const bestAsk = sortedAsks[0];

    if (!bestBid || !bestAsk) {
        return {
            spread: 0,
            spreadPercent: 0,
            midPrice: 0,
            bestBid: null,
            bestAsk: null,
        };
    }

    const spread = bestAsk.price - bestBid.price;
    const midPrice = (bestBid.price + bestAsk.price) / 2;
    const spreadPercent = midPrice > 0 ? (spread / midPrice) * 100 : 0;

    return {
        spread,
        spreadPercent,
        midPrice,
        bestBid,
        bestAsk,
    };
}

/**
 * Calculate cumulative depth for bids and asks
 * @param {Array} bids - Array of bid objects { price, size }
 * @param {Array} asks - Array of ask objects { price, size }
 * @returns {Object} Object with cumulative bids and asks
 */
export function calculateCumulativeDepth(bids, asks) {
    // Sort bids descending by price (highest first)
    const sortedBids = [...(bids || [])].sort((a, b) => b.price - a.price);

    // Sort asks ascending by price (lowest first)
    const sortedAsks = [...(asks || [])].sort((a, b) => a.price - b.price);

    // Calculate cumulative depth for bids (from highest price down)
    let cumulativeBidSize = 0;
    const cumulativeBids = sortedBids.map((bid) => {
        cumulativeBidSize += bid.size;
        return {
            ...bid,
            cumulativeSize: cumulativeBidSize,
        };
    });

    // Calculate cumulative depth for asks (from lowest price up)
    let cumulativeAskSize = 0;
    const cumulativeAsks = sortedAsks.map((ask) => {
        cumulativeAskSize += ask.size;
        return {
            ...ask,
            cumulativeSize: cumulativeAskSize,
        };
    });

    return {
        bids: cumulativeBids,
        asks: cumulativeAsks,
        totalBidDepth: cumulativeBidSize,
        totalAskDepth: cumulativeAskSize,
    };
}

/**
 * Aggregate order book levels by price tick size
 * @param {Array} levels - Array of price level objects { price, size }
 * @param {number} tickSize - Price tick size for aggregation
 * @param {string} side - 'bid' or 'ask' to determine aggregation direction
 * @returns {Array} Aggregated price levels
 */
export function aggregatePriceLevels(levels, tickSize = 0.01, side = 'bid') {
    if (!levels?.length) return [];

    // Group levels by rounded price
    const aggregated = new Map();

    levels.forEach((level) => {
        // Round to tick size
        const roundedPrice = Math.round(level.price / tickSize) * tickSize;
        const key = roundedPrice.toFixed(Math.max(0, -Math.floor(Math.log10(tickSize))));

        if (aggregated.has(key)) {
            const existing = aggregated.get(key);
            existing.size += level.size;
            existing.count = (existing.count || 1) + 1;
        } else {
            aggregated.set(key, {
                price: roundedPrice,
                size: level.size,
                count: 1,
            });
        }
    });

    // Convert to array and sort
    const result = Array.from(aggregated.values());

    if (side === 'bid') {
        result.sort((a, b) => b.price - a.price); // Descending for bids
    } else {
        result.sort((a, b) => a.price - b.price); // Ascending for asks
    }

    return result;
}

/**
 * Format order book data for display
 * @param {Object} orderBook - Raw order book data
 * @param {Object} options - Formatting options
 * @returns {Object} Formatted order book data
 */
export function formatOrderBook(orderBook, options = {}) {
    const {
        tickSize = 0.01,
        maxLevels = 20,
        priceDecimals = 2,
        sizeDecimals = 2,
    } = options;

    if (!orderBook) {
        return {
            bids: [],
            asks: [],
            spread: null,
            midPrice: null,
        };
    }

    // Aggregate levels
    const aggregatedBids = aggregatePriceLevels(orderBook.bids, tickSize, 'bid');
    const aggregatedAsks = aggregatePriceLevels(orderBook.asks, tickSize, 'ask');

    // Calculate cumulative depth
    const { bids, asks, totalBidDepth, totalAskDepth } = calculateCumulativeDepth(
        aggregatedBids.slice(0, maxLevels),
        aggregatedAsks.slice(0, maxLevels)
    );

    // Calculate spread
    const spreadInfo = calculateSpread(bids, asks);

    // Format price levels for display
    const formatLevel = (level, side) => {
        const maxDepth = Math.max(totalBidDepth, totalAskDepth);
        const depthPercent = maxDepth > 0 ? (level.cumulativeSize / maxDepth) * 100 : 0;

        return {
            price: level.price.toFixed(priceDecimals),
            size: level.size.toFixed(sizeDecimals),
            cumulativeSize: level.cumulativeSize.toFixed(sizeDecimals),
            depthPercent,
            side,
            count: level.count || 1,
        };
    };

    return {
        bids: bids.map((b) => formatLevel(b, 'bid')),
        asks: asks.map((a) => formatLevel(a, 'ask')),
        spread: spreadInfo,
        midPrice: spreadInfo.midPrice,
        totalBidDepth,
        totalAskDepth,
        timestamp: orderBook.timestamp || Date.now(),
        sequence: orderBook.sequence || 0,
    };
}

/**
 * Calculate order book imbalance
 * @param {number} bidDepth - Total bid depth
 * @param {number} askDepth - Total ask depth
 * @returns {Object} Imbalance information
 */
export function calculateImbalance(bidDepth, askDepth) {
    const total = bidDepth + askDepth;

    if (total === 0) {
        return {
            imbalance: 0,
            bidRatio: 0.5,
            askRatio: 0.5,
            direction: 'neutral',
        };
    }

    const bidRatio = bidDepth / total;
    const askRatio = askDepth / total;
    const imbalance = bidRatio - askRatio;

    let direction;
    if (imbalance > 0.1) {
        direction = 'bullish';
    } else if (imbalance < -0.1) {
        direction = 'bearish';
    } else {
        direction = 'neutral';
    }

    return {
        imbalance,
        bidRatio,
        askRatio,
        direction,
    };
}

/**
 * Calculate price levels for depth chart
 * @param {Array} bids - Cumulative bid levels
 * @param {Array} asks - Cumulative ask levels
 * @param {number} midPrice - Current mid price
 * @returns {Object} Depth chart data
 */
export function calculateDepthChartData(bids, asks, midPrice) {
    if (!bids?.length || !asks?.length || !midPrice) {
        return {
            bidData: [],
            askData: [],
            maxDepth: 0,
            priceRange: { min: 0, max: 0 },
        };
    }

    // Prepare bid data (price vs cumulative size)
    // For area chart, we need to plot from lowest bid price to highest
    const bidData = [...bids]
        .sort((a, b) => a.price - b.price)
        .map((level) => ({
            price: level.price,
            size: level.cumulativeSize,
            type: 'bid',
        }));

    // Prepare ask data (price vs cumulative size)
    const askData = asks.map((level) => ({
        price: level.price,
        size: level.cumulativeSize,
        type: 'ask',
    }));

    // Calculate max depth for scaling
    const maxDepth = Math.max(
        ...bidData.map((d) => d.size),
        ...askData.map((d) => d.size)
    );

    // Calculate price range
    const allPrices = [...bidData, ...askData].map((d) => d.price);
    const priceRange = {
        min: Math.min(...allPrices),
        max: Math.max(...allPrices),
    };

    return {
        bidData,
        askData,
        maxDepth,
        priceRange,
        midPrice,
    };
}

/**
 * Merge order book delta updates
 * @param {Object} currentBook - Current order book state
 * @param {Object} delta - Delta update
 * @returns {Object} Updated order book
 */
export function mergeOrderBookDelta(currentBook, delta) {
    if (!currentBook) {
        return delta;
    }

    // Check sequence for ordering
    if (delta.sequence && currentBook.sequence && delta.sequence <= currentBook.sequence) {
        return currentBook;
    }

    const mergeLevels = (existingLevels, deltaLevels) => {
        const levelMap = new Map();

        // Add existing levels
        existingLevels?.forEach((level) => {
            levelMap.set(level.price, level.size);
        });

        // Apply delta updates
        deltaLevels?.forEach((level) => {
            if (level.size === 0) {
                levelMap.delete(level.price);
            } else {
                levelMap.set(level.price, level.size);
            }
        });

        // Convert back to array
        return Array.from(levelMap.entries()).map(([price, size]) => ({
            price,
            size,
        }));
    };

    return {
        ...currentBook,
        bids: mergeLevels(currentBook.bids, delta.bids),
        asks: mergeLevels(currentBook.asks, delta.asks),
        timestamp: delta.timestamp || Date.now(),
        sequence: delta.sequence || (currentBook.sequence || 0) + 1,
    };
}

/**
 * Calculate price impact for a given order size
 * @param {Array} levels - Order book levels (bids or asks)
 * @param {number} orderSize - Size of the order
 * @param {string} side - 'buy' or 'sell'
 * @returns {Object} Price impact information
 */
export function calculatePriceImpact(levels, orderSize, side = 'buy') {
    if (!levels?.length || orderSize <= 0) {
        return {
            averagePrice: 0,
            worstPrice: 0,
            priceImpact: 0,
            filledSize: 0,
        };
    }

    // For buys, we use asks (ascending price)
    // For sells, we use bids (descending price)
    const sortedLevels = side === 'buy'
        ? [...levels].sort((a, b) => a.price - b.price)
        : [...levels].sort((a, b) => b.price - a.price);

    let remainingSize = orderSize;
    let totalCost = 0;
    let worstPrice = 0;
    let filledSize = 0;

    for (const level of sortedLevels) {
        if (remainingSize <= 0) break;

        const fillSize = Math.min(remainingSize, level.size);
        totalCost += fillSize * level.price;
        worstPrice = level.price;
        filledSize += fillSize;
        remainingSize -= fillSize;
    }

    const averagePrice = filledSize > 0 ? totalCost / filledSize : 0;
    const bestPrice = sortedLevels[0]?.price || 0;
    const priceImpact = bestPrice > 0
        ? Math.abs(averagePrice - bestPrice) / bestPrice * 100
        : 0;

    return {
        averagePrice,
        worstPrice,
        priceImpact,
        filledSize,
        isFullyFilled: remainingSize === 0,
    };
}

/**
 * Get order book statistics
 * @param {Object} orderBook - Order book data
 * @returns {Object} Statistics object
 */
export function getOrderBookStats(orderBook) {
    if (!orderBook?.bids?.length || !orderBook?.asks?.length) {
        return null;
    }

    const { bids, asks } = orderBook;
    const spreadInfo = calculateSpread(bids, asks);
    const { totalBidDepth, totalAskDepth } = calculateCumulativeDepth(bids, asks);
    const imbalance = calculateImbalance(totalBidDepth, totalAskDepth);

    // Calculate average bid/ask sizes
    const avgBidSize = bids.reduce((sum, b) => sum + b.size, 0) / bids.length;
    const avgAskSize = asks.reduce((sum, a) => sum + a.size, 0) / asks.length;

    // Calculate price levels count
    const bidLevels = bids.length;
    const askLevels = asks.length;

    return {
        spread: spreadInfo.spread,
        spreadPercent: spreadInfo.spreadPercent,
        midPrice: spreadInfo.midPrice,
        totalBidDepth,
        totalAskDepth,
        avgBidSize,
        avgAskSize,
        bidLevels,
        askLevels,
        imbalance: imbalance.imbalance,
        direction: imbalance.direction,
        timestamp: orderBook.timestamp || Date.now(),
    };
}

export default {
    calculateSpread,
    calculateCumulativeDepth,
    aggregatePriceLevels,
    formatOrderBook,
    calculateImbalance,
    calculateDepthChartData,
    mergeOrderBookDelta,
    calculatePriceImpact,
    getOrderBookStats,
};
