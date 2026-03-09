/**
 * DepthChart Component
 * 
 * Visual representation of order book depth.
 * Features:
 * - X-axis: cumulative size
 * - Y-axis: price
 * - Area chart for bids and asks
 * - Mid-price indicator
 * - Real-time updates
 */
import React, { useMemo, useRef, useEffect, useState, memo, useCallback } from 'react';
import { useOrderBook } from '../hooks/useOrderBook';
import { calculateDepthChartData, calculateCumulativeDepth } from '../utils/orderBookUtils';

/**
 * Chart dimensions and styling
 */
const CHART_CONFIG = {
    padding: { top: 20, right: 60, bottom: 30, left: 10 },
    colors: {
        bid: {
            fill: 'rgba(16, 185, 129, 0.3)', // emerald-500 with opacity
            stroke: 'rgb(16, 185, 129)',
        },
        ask: {
            fill: 'rgba(239, 68, 68, 0.3)', // red-500 with opacity
            stroke: 'rgb(239, 68, 68)',
        },
        midPrice: 'rgb(251, 191, 36)', // amber-400
        grid: 'rgba(71, 85, 105, 0.3)', // slate-500 with opacity
        text: 'rgb(148, 163, 184)', // slate-400
    },
    animation: {
        duration: 150,
    },
};

/**
 * Generate SVG path for area chart
 */
function generateAreaPath(data, xScale, yScale, side) {
    if (!data || data.length === 0) return '';

    const points = data.map((d) => ({
        x: xScale(d.size),
        y: yScale(d.price),
    }));

    // Create area path
    let path = '';

    if (side === 'bid') {
        // Bids: start from bottom-right, go up-left, then down to baseline
        const firstPoint = points[0];
        const lastPoint = points[points.length - 1];

        path = `M ${lastPoint.x} ${yScale.range()[0]}`;
        path += ` L ${lastPoint.x} ${lastPoint.y}`;

        for (let i = points.length - 2; i >= 0; i--) {
            path += ` L ${points[i].x} ${points[i].y}`;
        }

        path += ` L ${firstPoint.x} ${yScale.range()[0]} Z`;
    } else {
        // Asks: start from bottom-left, go up-right, then down to baseline
        const firstPoint = points[0];
        const lastPoint = points[points.length - 1];

        path = `M ${firstPoint.x} ${yScale.range()[0]}`;
        path += ` L ${firstPoint.x} ${firstPoint.y}`;

        for (let i = 1; i < points.length; i++) {
            path += ` L ${points[i].x} ${points[i].y}`;
        }

        path += ` L ${lastPoint.x} ${yScale.range()[0]} Z`;
    }

    return path;
}

/**
 * Generate SVG path for line
 */
function generateLinePath(data, xScale, yScale) {
    if (!data || data.length === 0) return '';

    const points = data.map((d) => ({
        x: xScale(d.size),
        y: yScale(d.price),
    }));

    let path = `M ${points[0].x} ${points[0].y}`;

    for (let i = 1; i < points.length; i++) {
        path += ` L ${points[i].x} ${points[i].y}`;
    }

    return path;
}

/**
 * Create scale functions
 */
function createScales(data, width, height, padding) {
    const { bidData, askData, maxDepth, priceRange, midPrice } = data;

    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // X scale (size)
    const xExtent = [0, maxDepth * 1.1];
    const xScale = (value) => padding.left + (value / xExtent[1]) * chartWidth;
    xScale.range = () => [padding.left, padding.left + chartWidth];

    // Y scale (price)
    const yExtent = [priceRange.min, priceRange.max];
    const yScale = (value) => {
        const normalized = (value - yExtent[0]) / (yExtent[1] - yExtent[0]);
        return padding.top + chartHeight - normalized * chartHeight;
    };
    yScale.range = () => [padding.top + chartHeight, padding.top];

    return { xScale, yScale, xExtent, yExtent };
}

/**
 * Grid lines component
 */
const GridLines = memo(function GridLines({
    xScale,
    yScale,
    xExtent,
    yExtent,
    width,
    height,
    padding,
}) {
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Generate horizontal grid lines (price levels)
    const priceSteps = 5;
    const priceLines = [];
    for (let i = 0; i <= priceSteps; i++) {
        const price = yExtent[0] + (i / priceSteps) * (yExtent[1] - yExtent[0]);
        const y = yScale(price);
        priceLines.push(
            <line
                key={`price-grid-${i}`}
                x1={padding.left}
                y1={y}
                x2={width - padding.right}
                y2={y}
                stroke={CHART_CONFIG.colors.grid}
                strokeWidth={1}
                strokeDasharray="4,4"
            />
        );
    }

    // Generate vertical grid lines (size)
    const sizeSteps = 4;
    const sizeLines = [];
    for (let i = 0; i <= sizeSteps; i++) {
        const size = (i / sizeSteps) * xExtent[1];
        const x = xScale(size);
        sizeLines.push(
            <line
                key={`size-grid-${i}`}
                x1={x}
                y1={padding.top}
                x2={x}
                y2={height - padding.bottom}
                stroke={CHART_CONFIG.colors.grid}
                strokeWidth={1}
                strokeDasharray="4,4"
            />
        );
    }

    return (
        <g className="depth-chart-grid">
            {priceLines}
            {sizeLines}
        </g>
    );
});

/**
 * Axis labels component
 */
const AxisLabels = memo(function AxisLabels({
    xScale,
    yScale,
    xExtent,
    yExtent,
    width,
    height,
    padding,
    midPrice,
}) {
    const chartHeight = height - padding.top - padding.bottom;

    // Price labels (Y-axis)
    const priceSteps = 5;
    const priceLabels = [];
    for (let i = 0; i <= priceSteps; i++) {
        const price = yExtent[0] + (i / priceSteps) * (yExtent[1] - yExtent[0]);
        const y = yScale(price);
        priceLabels.push(
            <text
                key={`price-label-${i}`}
                x={width - padding.right + 5}
                y={y + 4}
                fill={CHART_CONFIG.colors.text}
                fontSize={10}
                textAnchor="start"
            >
                ${price.toFixed(3)}
            </text>
        );
    }

    // Size labels (X-axis)
    const sizeSteps = 4;
    const sizeLabels = [];
    for (let i = 0; i <= sizeSteps; i++) {
        const size = (i / sizeSteps) * xExtent[1];
        const x = xScale(size);
        sizeLabels.push(
            <text
                key={`size-label-${i}`}
                x={x}
                y={height - padding.bottom + 15}
                fill={CHART_CONFIG.colors.text}
                fontSize={10}
                textAnchor="middle"
            >
                {size.toFixed(0)}
            </text>
        );
    }

    // Mid price label
    const midPriceLabel = midPrice ? (
        <text
            x={width - padding.right + 5}
            y={yScale(midPrice) + 4}
            fill={CHART_CONFIG.colors.midPrice}
            fontSize={10}
            fontWeight="bold"
            textAnchor="start"
        >
            ${midPrice.toFixed(4)}
        </text>
    ) : null;

    return (
        <g className="depth-chart-labels">
            {priceLabels}
            {sizeLabels}
            {midPriceLabel}
        </g>
    );
});

/**
 * Mid-price line component
 */
const MidPriceLine = memo(function MidPriceLine({
    midPrice,
    yScale,
    width,
    padding,
}) {
    if (!midPrice) return null;

    const y = yScale(midPrice);

    return (
        <g className="depth-chart-mid-price">
            <line
                x1={padding.left}
                y1={y}
                x2={width - padding.right}
                y2={y}
                stroke={CHART_CONFIG.colors.midPrice}
                strokeWidth={1}
                strokeDasharray="6,3"
            />
            <circle
                cx={width - padding.right}
                cy={y}
                r={4}
                fill={CHART_CONFIG.colors.midPrice}
            />
        </g>
    );
});

/**
 * Tooltip component
 */
const DepthTooltip = memo(function DepthTooltip({
    position,
    data,
    side,
    visible,
}) {
    if (!visible || !position || !data) return null;

    return (
        <div
            className="absolute bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 shadow-lg z-20 pointer-events-none"
            style={{
                left: `${position.x + 10}px`,
                top: `${position.y - 10}px`,
                transform: 'translateY(-100%)',
            }}
        >
            <div className="text-xs space-y-1">
                <div className="flex justify-between gap-4">
                    <span className="text-slate-400">Price:</span>
                    <span className={`font-mono ${side === 'bid' ? 'text-emerald-400' : 'text-red-400'}`}>
                        ${data.price.toFixed(4)}
                    </span>
                </div>
                <div className="flex justify-between gap-4">
                    <span className="text-slate-400">Size:</span>
                    <span className="font-mono text-white">{data.size.toFixed(2)}</span>
                </div>
                <div className="flex justify-between gap-4">
                    <span className="text-slate-400">Cumulative:</span>
                    <span className="font-mono text-slate-300">{data.cumulativeSize.toFixed(2)}</span>
                </div>
            </div>
        </div>
    );
});

/**
 * DepthChart Component
 * 
 * @param {Object} props
 * @param {string} props.marketId - Market ID to subscribe to
 * @param {number} props.width - Chart width
 * @param {number} props.height - Chart height
 * @param {number} props.maxLevels - Maximum price levels to include
 * @param {Object} props.options - Order book options
 */
function DepthChart({
    marketId,
    width = 400,
    height = 300,
    maxLevels = 50,
    options = {},
    className = '',
}) {
    const svgRef = useRef(null);
    const [tooltip, setTooltip] = useState({ visible: false, position: null, data: null, side: null });

    const {
        rawOrderBook,
        spread,
        isLoading,
        error,
        isSubscribed,
    } = useOrderBook(marketId, {
        maxLevels,
        ...options,
    });

    // Calculate cumulative depth
    const cumulativeDepth = useMemo(() => {
        if (!rawOrderBook) return null;
        return calculateCumulativeDepth(rawOrderBook.bids, rawOrderBook.asks);
    }, [rawOrderBook]);

    // Calculate depth chart data
    const depthData = useMemo(() => {
        if (!cumulativeDepth || !spread?.midPrice) return null;
        return calculateDepthChartData(
            cumulativeDepth.bids,
            cumulativeDepth.asks,
            spread.midPrice
        );
    }, [cumulativeDepth, spread]);

    // Create scales
    const scales = useMemo(() => {
        if (!depthData) return null;
        return createScales(depthData, width, height, CHART_CONFIG.padding);
    }, [depthData, width, height]);

    // Generate paths
    const paths = useMemo(() => {
        if (!depthData || !scales) return null;

        const { xScale, yScale } = scales;

        return {
            bidArea: generateAreaPath(depthData.bidData, xScale, yScale, 'bid'),
            bidLine: generateLinePath(depthData.bidData, xScale, yScale),
            askArea: generateAreaPath(depthData.askData, xScale, yScale, 'ask'),
            askLine: generateLinePath(depthData.askData, xScale, yScale),
        };
    }, [depthData, scales]);

    // Handle mouse move for tooltip
    const handleMouseMove = useCallback((event) => {
        if (!svgRef.current || !depthData || !scales) return;

        const rect = svgRef.current.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        // Check if mouse is within chart area
        const { padding } = CHART_CONFIG;
        if (x < padding.left || x > width - padding.right ||
            y < padding.top || y > height - padding.bottom) {
            setTooltip({ visible: false, position: null, data: null, side: null });
            return;
        }

        // Find closest data point
        const { xScale, yScale, xExtent, yExtent } = scales;
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;

        // Convert mouse position to data coordinates
        const sizeValue = ((x - padding.left) / chartWidth) * xExtent[1];
        const priceValue = yExtent[0] + ((height - padding.bottom - y) / chartHeight) * (yExtent[1] - yExtent[0]);

        // Find closest bid or ask
        let closestData = null;
        let closestSide = null;
        let minDistance = Infinity;

        const findClosest = (data, side) => {
            data?.forEach((d) => {
                const dx = Math.abs(d.size - sizeValue);
                const dy = Math.abs(d.price - priceValue);
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < minDistance) {
                    minDistance = distance;
                    closestData = d;
                    closestSide = side;
                }
            });
        };

        findClosest(depthData.bidData, 'bid');
        findClosest(depthData.askData, 'ask');

        if (closestData && minDistance < 50) {
            setTooltip({
                visible: true,
                position: { x: event.clientX - rect.left, y: event.clientY - rect.top },
                data: closestData,
                side: closestSide,
            });
        } else {
            setTooltip({ visible: false, position: null, data: null, side: null });
        }
    }, [depthData, scales, width, height]);

    // Handle mouse leave
    const handleMouseLeave = useCallback(() => {
        setTooltip({ visible: false, position: null, data: null, side: null });
    }, []);

    // Loading state
    if (isLoading && !depthData) {
        return (
            <div className={`bg-slate-800 rounded-lg border border-slate-700 ${className}`}>
                <div className="p-4 text-center text-slate-400">
                    <div className="animate-pulse">Loading depth chart...</div>
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
    if (!depthData || !isSubscribed) {
        return (
            <div className={`bg-slate-800 rounded-lg border border-slate-700 ${className}`}>
                <div className="p-4 text-center text-slate-400">
                    <div className="text-sm">
                        {!marketId ? 'Select a market' : 'Waiting for depth data...'}
                    </div>
                </div>
            </div>
        );
    }

    const { xScale, yScale, xExtent, yExtent } = scales;

    return (
        <div className={`bg-slate-800 rounded-lg border border-slate-700 overflow-hidden ${className}`}>
            {/* Header */}
            <div className="px-4 py-3 border-b border-slate-700">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-white">Depth Chart</h3>
                    <div className="flex items-center gap-4 text-xs">
                        <div className="flex items-center gap-1">
                            <span className="w-3 h-3 bg-emerald-500/50 rounded" />
                            <span className="text-slate-400">Bids</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <span className="w-3 h-3 bg-red-500/50 rounded" />
                            <span className="text-slate-400">Asks</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Chart */}
            <div className="relative" style={{ width, height }}>
                <svg
                    ref={svgRef}
                    width={width}
                    height={height}
                    className="depth-chart-svg"
                    onMouseMove={handleMouseMove}
                    onMouseLeave={handleMouseLeave}
                >
                    {/* Grid */}
                    <GridLines
                        xScale={xScale}
                        yScale={yScale}
                        xExtent={xExtent}
                        yExtent={yExtent}
                        width={width}
                        height={height}
                        padding={CHART_CONFIG.padding}
                    />

                    {/* Bid area */}
                    <path
                        d={paths.bidArea}
                        fill={CHART_CONFIG.colors.bid.fill}
                        className="transition-all duration-150"
                    />
                    <path
                        d={paths.bidLine}
                        fill="none"
                        stroke={CHART_CONFIG.colors.bid.stroke}
                        strokeWidth={2}
                        className="transition-all duration-150"
                    />

                    {/* Ask area */}
                    <path
                        d={paths.askArea}
                        fill={CHART_CONFIG.colors.ask.fill}
                        className="transition-all duration-150"
                    />
                    <path
                        d={paths.askLine}
                        fill="none"
                        stroke={CHART_CONFIG.colors.ask.stroke}
                        strokeWidth={2}
                        className="transition-all duration-150"
                    />

                    {/* Mid-price line */}
                    <MidPriceLine
                        midPrice={depthData.midPrice}
                        yScale={yScale}
                        width={width}
                        padding={CHART_CONFIG.padding}
                    />

                    {/* Axis labels */}
                    <AxisLabels
                        xScale={xScale}
                        yScale={yScale}
                        xExtent={xExtent}
                        yExtent={yExtent}
                        width={width}
                        height={height}
                        padding={CHART_CONFIG.padding}
                        midPrice={depthData.midPrice}
                    />
                </svg>

                {/* Tooltip */}
                <DepthTooltip
                    visible={tooltip.visible}
                    position={tooltip.position}
                    data={tooltip.data}
                    side={tooltip.side}
                />
            </div>

            {/* Footer stats */}
            <div className="px-4 py-2 bg-slate-700/30 border-t border-slate-700 text-xs text-slate-400">
                <div className="flex items-center justify-between">
                    <span>
                        Bid Depth: ${depthData.bidData[depthData.bidData.length - 1]?.size.toFixed(2) || '0'}
                    </span>
                    <span>
                        Ask Depth: ${depthData.askData[depthData.askData.length - 1]?.size.toFixed(2) || '0'}
                    </span>
                </div>
            </div>
        </div>
    );
}

/**
 * Compact DepthChart variant
 */
export function DepthChartCompact({
    marketId,
    className = '',
}) {
    return (
        <DepthChart
            marketId={marketId}
            width={350}
            height={200}
            maxLevels={30}
            className={className}
        />
    );
}

export default memo(DepthChart);
