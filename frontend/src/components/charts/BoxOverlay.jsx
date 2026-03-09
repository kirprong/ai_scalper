/**
 * BoxOverlay Component
 * Renders Golden Rectangle boxes as overlays on the price chart
 */

import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import {
    BOX_STATUS,
    BOX_COLORS,
    getBoxStyle,
    calculateBoxDimensions,
    isPointInBox,
    createBoxTooltipContent,
} from '../../utils/boxUtils';

/**
 * BoxTooltip - Tooltip component for displaying box metadata
 * 
 * @param {Object} props
 * @param {Object} props.content - Tooltip content
 * @param {Object} props.position - Tooltip position {x, y}
 * @param {boolean} props.visible - Whether tooltip is visible
 */
const BoxTooltip = ({ content, position, visible }) => {
    if (!visible || !content) return null;

    return (
        <div
            className="box-tooltip absolute z-50 pointer-events-none"
            style={{
                left: `${position.x + 15}px`,
                top: `${position.y - 10}px`,
                transform: 'translateY(-100%)',
            }}
        >
            <div className="bg-slate-800 border border-slate-600 rounded-lg shadow-xl p-3 min-w-[200px]">
                {/* Header */}
                <div className="flex items-center justify-between mb-2 pb-2 border-b border-slate-700">
                    <span className="text-xs font-medium text-slate-400">Golden Rectangle</span>
                    <span
                        className="text-xs font-bold px-2 py-0.5 rounded"
                        style={{ color: content.color }}
                    >
                        {content.status}
                    </span>
                </div>

                {/* Content */}
                <div className="space-y-1.5 text-xs">
                    <div className="flex justify-between">
                        <span className="text-slate-500">Price Range:</span>
                        <span className="text-white font-mono">{content.priceRange}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-slate-500">Time Range:</span>
                        <span className="text-white">{content.timeRange}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-slate-500">Confidence:</span>
                        <span className="text-green-400 font-mono">{content.confidence}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-slate-500">Expected Move:</span>
                        <span className={content.expectedMove.startsWith('+') ? 'text-green-400' : 'text-red-400'}>
                            {content.expectedMove}
                        </span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-slate-500">Age:</span>
                        <span className="text-slate-300">{content.age}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-slate-500">Remaining:</span>
                        <span className="text-slate-300">{content.remaining}</span>
                    </div>
                </div>

                {/* ID */}
                <div className="mt-2 pt-2 border-t border-slate-700">
                    <span className="text-xs text-slate-600 font-mono truncate block">{content.id}</span>
                </div>
            </div>
        </div>
    );
};

/**
 * SingleBox - Individual box overlay component
 * 
 * @param {Object} props
 * @param {Object} props.box - Transformed box data
 * @param {Object} props.chart - Chart instance
 * @param {Object} props.series - Series instance for price scale
 * @param {Function} props.onHover - Hover callback
 * @param {Function} props.onClick - Click callback
 * @param {boolean} props.animated - Enable animations
 * @param {boolean} props.showLabel - Show status label
 */
const SingleBox = ({
    box,
    chart,
    series,
    onHover,
    onClick,
    animated = true,
    showLabel = true,
}) => {
    const boxRef = useRef(null);
    const [dimensions, setDimensions] = useState(null);
    const [isVisible, setIsVisible] = useState(true);
    const [isAnimating, setIsAnimating] = useState(animated);

    const style = useMemo(() => getBoxStyle(box.status), [box.status]);

    // Calculate box dimensions when chart updates
    useEffect(() => {
        if (!chart || !series) return;

        const updateDimensions = () => {
            const timeScale = chart.timeScale();
            const priceScale = series.priceScale();

            const dims = calculateBoxDimensions(box, timeScale, priceScale);
            setDimensions(dims);
            setIsVisible(dims !== null);
        };

        // Initial calculation
        updateDimensions();

        // Subscribe to visible range changes
        const timeScale = chart.timeScale();
        timeScale.subscribeVisibleLogicalRangeChange(updateDimensions);

        // Subscribe to crosshair move for updates
        chart.subscribeCrosshairMove(updateDimensions);

        return () => {
            timeScale.unsubscribeVisibleLogicalRangeChange(updateDimensions);
        };
    }, [chart, series, box]);

    // Animation effect
    useEffect(() => {
        if (animated && boxRef.current) {
            setIsAnimating(true);
            const timer = setTimeout(() => setIsAnimating(false), 300);
            return () => clearTimeout(timer);
        }
    }, [box.id, animated]);

    // Handle mouse events
    const handleMouseEnter = useCallback((e) => {
        onHover?.(box, { x: e.clientX, y: e.clientY });
    }, [box, onHover]);

    const handleMouseLeave = useCallback(() => {
        onHover?.(null, null);
    }, [onHover]);

    const handleClick = useCallback(() => {
        onClick?.(box);
    }, [box, onClick]);

    if (!isVisible || !dimensions) return null;

    const { x, y, width, height } = dimensions;

    return (
        <div
            ref={boxRef}
            className="box-overlay-item absolute cursor-pointer transition-opacity duration-200"
            style={{
                left: `${x}px`,
                top: `${y}px`,
                width: `${width}px`,
                height: `${height}px`,
                pointerEvents: 'auto',
            }}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            onClick={handleClick}
        >
            {/* Box fill */}
            <div
                className={`absolute inset-0 ${isAnimating ? 'animate-pulse' : ''}`}
                style={{
                    backgroundColor: style.fillColor,
                    border: `${style.lineWidth}px solid ${style.strokeColor}`,
                    borderStyle: style.lineStyle === 2 ? 'dashed' : 'solid',
                    borderRadius: '2px',
                    transition: animated ? 'all 0.3s ease-out' : 'none',
                }}
            />

            {/* Box label */}
            {showLabel && height > 20 && (
                <div
                    className="absolute top-0 left-0 px-1.5 py-0.5 text-xs font-medium rounded-br"
                    style={{
                        backgroundColor: style.strokeColor,
                        color: 'white',
                        fontSize: '10px',
                        lineHeight: '1',
                    }}
                >
                    {box.status.toUpperCase()}
                </div>
            )}

            {/* Confidence indicator */}
            {width > 60 && height > 30 && (
                <div className="absolute bottom-1 right-1 text-xs font-mono" style={{ color: style.textColor }}>
                    {(box.confidence * 100).toFixed(0)}%
                </div>
            )}
        </div>
    );
};

/**
 * BoxOverlay - Main component for rendering multiple boxes on a chart
 * 
 * @param {Object} props
 * @param {Array} props.boxes - Array of transformed box data
 * @param {Object} props.chart - Chart instance
 * @param {Object} props.series - Series instance for price scale
 * @param {boolean} props.visible - Whether boxes are visible
 * @param {boolean} props.animated - Enable animations
 * @param {boolean} props.showLabels - Show status labels on boxes
 * @param {Array} props.filterStatuses - Filter boxes by status
 * @param {Function} props.onBoxHover - Callback when box is hovered
 * @param {Function} props.onBoxClick - Callback when box is clicked
 * @param {Object} props.containerRef - Reference to chart container for positioning
 */
const BoxOverlay = ({
    boxes = [],
    chart,
    series,
    visible = true,
    animated = true,
    showLabels = true,
    filterStatuses = null,
    onBoxHover,
    onBoxClick,
    containerRef,
}) => {
    const [hoveredBox, setHoveredBox] = useState(null);
    const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });

    // Filter boxes by status if specified
    const filteredBoxes = useMemo(() => {
        if (!filterStatuses) return boxes;
        return boxes.filter(box => filterStatuses.includes(box.status));
    }, [boxes, filterStatuses]);

    // Handle box hover
    const handleBoxHover = useCallback((box, position) => {
        setHoveredBox(box);
        if (position) {
            // Convert to container-relative coordinates
            if (containerRef?.current) {
                const rect = containerRef.current.getBoundingClientRect();
                setTooltipPosition({
                    x: position.x - rect.left,
                    y: position.y - rect.top,
                });
            } else {
                setTooltipPosition(position);
            }
        }
        onBoxHover?.(box);
    }, [containerRef, onBoxHover]);

    // Handle box click
    const handleBoxClick = useCallback((box) => {
        onBoxClick?.(box);
    }, [onBoxClick]);

    // Create tooltip content
    const tooltipContent = useMemo(() => {
        return hoveredBox ? createBoxTooltipContent(hoveredBox) : null;
    }, [hoveredBox]);

    if (!visible || !chart || !series || filteredBoxes.length === 0) {
        return null;
    }

    return (
        <div className="box-overlay absolute inset-0 pointer-events-none overflow-hidden">
            {/* Render each box */}
            {filteredBoxes.map((box) => (
                <SingleBox
                    key={box.id}
                    box={box}
                    chart={chart}
                    series={series}
                    onHover={handleBoxHover}
                    onClick={handleBoxClick}
                    animated={animated}
                    showLabel={showLabels}
                />
            ))}

            {/* Tooltip */}
            <BoxTooltip
                content={tooltipContent}
                position={tooltipPosition}
                visible={hoveredBox !== null}
            />
        </div>
    );
};

/**
 * BoxLegend - Legend component showing box status types
 * 
 * @param {Object} props
 * @param {boolean} props.showLabels - Show status labels
 * @param {Object} props.statistics - Box statistics to display
 */
export const BoxLegend = ({ showLabels = true, statistics = null }) => {
    const statusTypes = [
        { status: BOX_STATUS.ACTIVE, label: 'Active', description: 'Valid trading opportunity' },
        { status: BOX_STATUS.TRIGGERED, label: 'Triggered', description: 'Price entered zone' },
        { status: BOX_STATUS.EXPIRED, label: 'Expired', description: 'Time window passed' },
        { status: BOX_STATUS.FAILED, label: 'Failed', description: 'Box invalidated' },
    ];

    return (
        <div className="box-legend bg-slate-800/90 backdrop-blur-sm rounded-lg p-3">
            <h4 className="text-sm font-medium text-slate-300 mb-2">Golden Rectangles</h4>

            <div className="space-y-1.5">
                {statusTypes.map(({ status, label, description }) => {
                    const style = getBoxStyle(status);
                    const count = statistics ? statistics[status] || 0 : null;

                    return (
                        <div key={status} className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <div
                                    className="w-4 h-3 rounded-sm"
                                    style={{
                                        backgroundColor: style.fillColor,
                                        border: `1px solid ${style.strokeColor}`,
                                    }}
                                />
                                {showLabels && (
                                    <div>
                                        <span className="text-xs text-white">{label}</span>
                                        <span className="text-xs text-slate-500 ml-1">({description})</span>
                                    </div>
                                )}
                            </div>
                            {count !== null && (
                                <span className="text-xs text-slate-400 font-mono">{count}</span>
                            )}
                        </div>
                    );
                })}
            </div>

            {statistics && (
                <div className="mt-2 pt-2 border-t border-slate-700">
                    <div className="flex justify-between text-xs">
                        <span className="text-slate-500">Total:</span>
                        <span className="text-white font-mono">{statistics.total}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                        <span className="text-slate-500">Avg Confidence:</span>
                        <span className="text-green-400 font-mono">
                            {(statistics.avgConfidence * 100).toFixed(1)}%
                        </span>
                    </div>
                </div>
            )}
        </div>
    );
};

/**
 * BoxList - List view of boxes for sidebar display
 * 
 * @param {Object} props
 * @param {Array} props.boxes - Array of transformed box data
 * @param {number} props.maxVisible - Maximum boxes to show
 * @param {Function} props.onBoxClick - Callback when box is clicked
 * @param {Function} props.onBoxHover - Callback when box is hovered
 */
export const BoxList = ({
    boxes = [],
    maxVisible = 10,
    onBoxClick,
    onBoxHover,
}) => {
    const visibleBoxes = boxes.slice(0, maxVisible);

    return (
        <div className="box-list bg-slate-800/90 backdrop-blur-sm rounded-lg p-3 max-h-80 overflow-y-auto">
            <h4 className="text-sm font-medium text-slate-300 mb-2">Recent Boxes</h4>

            {visibleBoxes.length === 0 ? (
                <p className="text-xs text-slate-500">No boxes available</p>
            ) : (
                <div className="space-y-2">
                    {visibleBoxes.map((box) => {
                        const style = getBoxStyle(box.status);

                        return (
                            <div
                                key={box.id}
                                className="flex items-center justify-between p-2 bg-slate-700/50 rounded cursor-pointer hover:bg-slate-700 transition-colors"
                                onClick={() => onBoxClick?.(box)}
                                onMouseEnter={() => onBoxHover?.(box)}
                                onMouseLeave={() => onBoxHover?.(null)}
                            >
                                <div className="flex items-center gap-2">
                                    <div
                                        className="w-3 h-3 rounded-sm"
                                        style={{ backgroundColor: style.strokeColor }}
                                    />
                                    <div>
                                        <div className="text-xs text-white font-medium">
                                            {box.status.toUpperCase()}
                                        </div>
                                        <div className="text-xs text-slate-500">
                                            {box.priceLow.toFixed(2)} - {box.priceHigh.toFixed(2)}
                                        </div>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-xs text-green-400 font-mono">
                                        {(box.confidence * 100).toFixed(0)}%
                                    </div>
                                    <div className="text-xs text-slate-500">
                                        {box.expectedMove >= 0 ? '+' : ''}{box.expectedMove.toFixed(2)}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};

export default BoxOverlay;
