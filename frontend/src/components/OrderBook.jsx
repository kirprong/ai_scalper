/**
 * OrderBook Component
 * 
 * Real-time order book visualization showing bid/ask depth.
 * Features:
 * - Color-coded bid (green) and ask (red) levels
 * - Visual depth bars showing relative size
 * - Spread indicator
 * - Price level highlighting on hover
 * - Cumulative depth display
 */
import React, { useState, useMemo, useCallback, memo } from 'react';
import { useOrderBook } from '../hooks/useOrderBook';
import { calculateImbalance } from '../utils/orderBookUtils';

/**
 * Price Level Row Component
 */
const PriceLevelRow = memo(function PriceLevelRow({
    level,
    side,
    maxDepth,
    isHovered,
    onHover,
    onClick,
    showCumulative = true,
    priceDecimals = 2,
    sizeDecimals = 2,
}) {
    const depthPercent = maxDepth > 0 ? (parseFloat(level.cumulativeSize) / maxDepth) * 100 : 0;

    const bgColor = side === 'bid'
        ? 'bg-emerald-500/20'
        : 'bg-red-500/20';
    const textColor = side === 'bid'
        ? 'text-emerald-400'
        : 'text-red-400';
    const barColor = side === 'bid'
        ? 'bg-emerald-500/30'
        : 'bg-red-500/30';

    return (
        <div
            className={`
        relative flex items-center justify-between py-1.5 px-2 
        cursor-pointer transition-colors duration-150
        ${isHovered ? 'bg-slate-600/50' : 'hover:bg-slate-700/50'}
      `}
            onMouseEnter={() => onHover(level)}
            onMouseLeave={() => onHover(null)}
            onClick={() => onClick?.(level)}
        >
            {/* Depth bar background */}
            <div
                className={`absolute inset-y-0 ${side === 'ask' ? 'left-0' : 'right-0'} ${barColor} transition-all duration-300`}
                style={{ width: `${depthPercent}%` }}
            />

            {/* Content */}
            <div className="relative flex items-center justify-between w-full text-sm">
                <span className={`font-mono ${textColor}`}>
                    ${level.price}
                </span>
                <div className="flex items-center gap-4">
                    <span className="font-mono text-slate-300">
                        {level.size}
                    </span>
                    {showCumulative && (
                        <span className="font-mono text-slate-500 text-xs min-w-[60px] text-right">
                            {level.cumulativeSize}
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
});

/**
 * Spread Indicator Component
 */
const SpreadIndicator = memo(function SpreadIndicator({
    spread,
    spreadPercent,
    midPrice,
}) {
    return (
        <div className="py-2 px-3 bg-slate-700/50 border-y border-slate-600">
            <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                    <span className="text-slate-400">Spread:</span>
                    <span className="text-white font-medium">
                        ${spread?.toFixed(4) || '0.0000'}
                    </span>
                    <span className="text-slate-500">
                        ({spreadPercent?.toFixed(2) || '0.00'}%)
                    </span>
                </div>
                {midPrice && (
                    <div className="flex items-center gap-2">
                        <span className="text-slate-400">Mid:</span>
                        <span className="text-amber-400 font-medium">
                            ${midPrice.toFixed(4)}
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
});

/**
 * Order Book Header Component
 */
const OrderBookHeader = memo(function OrderBookHeader({
    showCumulative = true,
}) {
    return (
        <div className="flex items-center justify-between py-2 px-3 bg-slate-700/30 text-xs text-slate-400 uppercase tracking-wider">
            <span>Price</span>
            <div className="flex items-center gap-4">
                <span>Size</span>
                {showCumulative && (
                    <span className="min-w-[60px] text-right">Total</span>
                )}
            </div>
        </div>
    );
});

/**
 * Imbalance Indicator Component
 */
const ImbalanceIndicator = memo(function ImbalanceIndicator({
    imbalance,
    direction,
}) {
    const barWidth = Math.abs(imbalance) * 100;
    const isBullish = imbalance > 0;

    return (
        <div className="py-2 px-3 bg-slate-700/30">
            <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-emerald-400">Bids</span>
                <span className={`font-medium ${direction === 'bullish' ? 'text-emerald-400' :
                        direction === 'bearish' ? 'text-red-400' :
                            'text-slate-400'
                    }`}>
                    {direction.toUpperCase()}
                </span>
                <span className="text-red-400">Asks</span>
            </div>
            <div className="relative h-1.5 bg-slate-600 rounded-full overflow-hidden">
                <div
                    className={`absolute top-0 bottom-0 transition-all duration-300 ${isBullish ? 'right-1/2 bg-emerald-500' : 'left-1/2 bg-red-500'
                        }`}
                    style={{ width: `${barWidth / 2}%` }}
                />
            </div>
        </div>
    );
});

/**
 * OrderBook Component
 * 
 * @param {Object} props
 * @param {string} props.marketId - Market ID to subscribe to
 * @param {number} props.maxLevels - Maximum number of levels to display per side
 * @param {boolean} props.showCumulative - Show cumulative depth column
 * @param {boolean} props.showImbalance - Show imbalance indicator
 * @param {boolean} props.showSpread - Show spread indicator
 * @param {function} props.onPriceClick - Callback when price level is clicked
 * @param {Object} props.options - Order book formatting options
 */
function OrderBook({
    marketId,
    maxLevels = 15,
    showCumulative = true,
    showImbalance = true,
    showSpread = true,
    onPriceClick,
    options = {},
    className = '',
}) {
    const [hoveredLevel, setHoveredLevel] = useState(null);

    const {
        orderBook,
        spread,
        isLoading,
        error,
        isSubscribed,
        stats,
    } = useOrderBook(marketId, {
        maxLevels,
        ...options,
    });

    // Calculate max depth for scaling
    const maxDepth = useMemo(() => {
        if (!orderBook) return 0;
        const bidMax = orderBook.bids?.length > 0
            ? Math.max(...orderBook.bids.map(b => parseFloat(b.cumulativeSize)))
            : 0;
        const askMax = orderBook.asks?.length > 0
            ? Math.max(...orderBook.asks.map(a => parseFloat(a.cumulativeSize)))
            : 0;
        return Math.max(bidMax, askMax);
    }, [orderBook]);

    // Calculate imbalance
    const imbalanceData = useMemo(() => {
        if (!stats) return { imbalance: 0, direction: 'neutral' };
        return {
            imbalance: stats.imbalance,
            direction: stats.direction,
        };
    }, [stats]);

    // Handle price level click
    const handlePriceClick = useCallback((level) => {
        onPriceClick?.({
            price: parseFloat(level.price),
            side: level.side,
            size: parseFloat(level.size),
        });
    }, [onPriceClick]);

    // Loading state
    if (isLoading && !orderBook) {
        return (
            <div className={`bg-slate-800 rounded-lg border border-slate-700 ${className}`}>
                <div className="p-4 text-center text-slate-400">
                    <div className="animate-pulse">Loading order book...</div>
                </div>
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div className={`bg-slate-800 rounded-lg border border-slate-700 ${className}`}>
                <div className="p-4 text-center text-red-400">
                    <div className="text-sm">Error: {error}</div>
                </div>
            </div>
        );
    }

    // No data state
    if (!orderBook || !isSubscribed) {
        return (
            <div className={`bg-slate-800 rounded-lg border border-slate-700 ${className}`}>
                <div className="p-4 text-center text-slate-400">
                    <div className="text-sm">
                        {!marketId ? 'Select a market' : 'Waiting for order book data...'}
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className={`bg-slate-800 rounded-lg border border-slate-700 overflow-hidden ${className}`}>
            {/* Header */}
            <div className="px-4 py-3 border-b border-slate-700">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-white">Order Book</h3>
                    <div className="flex items-center gap-2">
                        {isSubscribed && (
                            <span className="flex items-center gap-1 text-xs text-emerald-400">
                                <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                                Live
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* Imbalance Indicator */}
            {showImbalance && (
                <ImbalanceIndicator
                    imbalance={imbalanceData.imbalance}
                    direction={imbalanceData.direction}
                />
            )}

            {/* Ask Side Header */}
            <OrderBookHeader showCumulative={showCumulative} />

            {/* Asks (displayed in reverse order - lowest ask at bottom) */}
            <div className="flex flex-col-reverse">
                {orderBook.asks?.slice(0, maxLevels).map((ask, index) => (
                    <PriceLevelRow
                        key={`ask-${ask.price}`}
                        level={ask}
                        side="ask"
                        maxDepth={maxDepth}
                        isHovered={hoveredLevel?.price === ask.price}
                        onHover={setHoveredLevel}
                        onClick={handlePriceClick}
                        showCumulative={showCumulative}
                        priceDecimals={options.priceDecimals || 2}
                        sizeDecimals={options.sizeDecimals || 2}
                    />
                ))}
            </div>

            {/* Spread Indicator */}
            {showSpread && (
                <SpreadIndicator
                    spread={spread?.spread}
                    spreadPercent={spread?.spreadPercent}
                    midPrice={spread?.midPrice}
                />
            )}

            {/* Bids (displayed in normal order - highest bid at top) */}
            <div className="flex flex-col">
                {orderBook.bids?.slice(0, maxLevels).map((bid, index) => (
                    <PriceLevelRow
                        key={`bid-${bid.price}`}
                        level={bid}
                        side="bid"
                        maxDepth={maxDepth}
                        isHovered={hoveredLevel?.price === bid.price}
                        onHover={setHoveredLevel}
                        onClick={handlePriceClick}
                        showCumulative={showCumulative}
                        priceDecimals={options.priceDecimals || 2}
                        sizeDecimals={options.sizeDecimals || 2}
                    />
                ))}
            </div>

            {/* Hovered Level Tooltip */}
            {hoveredLevel && (
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg shadow-lg z-10">
                    <div className="text-xs space-y-1">
                        <div className="flex justify-between gap-4">
                            <span className="text-slate-400">Price:</span>
                            <span className={`font-mono ${hoveredLevel.side === 'bid' ? 'text-emerald-400' : 'text-red-400'}`}>
                                ${hoveredLevel.price}
                            </span>
                        </div>
                        <div className="flex justify-between gap-4">
                            <span className="text-slate-400">Size:</span>
                            <span className="font-mono text-white">{hoveredLevel.size}</span>
                        </div>
                        <div className="flex justify-between gap-4">
                            <span className="text-slate-400">Total:</span>
                            <span className="font-mono text-slate-300">{hoveredLevel.cumulativeSize}</span>
                        </div>
                        {hoveredLevel.count > 1 && (
                            <div className="flex justify-between gap-4">
                                <span className="text-slate-400">Orders:</span>
                                <span className="font-mono text-slate-300">{hoveredLevel.count}</span>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Stats Footer */}
            {stats && (
                <div className="px-3 py-2 bg-slate-700/30 border-t border-slate-700 text-xs text-slate-400">
                    <div className="flex items-center justify-between">
                        <span>
                            {orderBook.bids?.length || 0} bids / {orderBook.asks?.length || 0} asks
                        </span>
                        <span>
                            Vol: ${(stats.totalBidDepth + stats.totalAskDepth).toFixed(2)}
                        </span>
                    </div>
                </div>
            )}
        </div>
    );
}

/**
 * Compact OrderBook variant for smaller displays
 */
export function OrderBookCompact({
    marketId,
    maxLevels = 5,
    onPriceClick,
    className = '',
}) {
    return (
        <OrderBook
            marketId={marketId}
            maxLevels={maxLevels}
            showCumulative={false}
            showImbalance={false}
            showSpread={true}
            onPriceClick={onPriceClick}
            className={className}
        />
    );
}

/**
 * OrderBook with depth visualization
 */
export function OrderBookWithDepth({
    marketId,
    maxLevels = 10,
    onPriceClick,
    className = '',
}) {
    return (
        <div className={`grid grid-cols-1 gap-4 ${className}`}>
            <OrderBook
                marketId={marketId}
                maxLevels={maxLevels}
                showCumulative={true}
                showImbalance={true}
                showSpread={true}
                onPriceClick={onPriceClick}
            />
        </div>
    );
}

export default memo(OrderBook);
