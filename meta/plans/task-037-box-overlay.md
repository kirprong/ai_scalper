# TASK-037: Box Overlay Visualization

## Overview
Implementation of Golden Rectangle box overlay visualization on the price chart to display detected trading opportunities.

## Status: ✅ COMPLETE

## Implementation Date: 2026-03-09

## Files Created/Modified

### New Files Created

1. **`frontend/src/utils/boxUtils.js`** (380+ lines)
   - Box status types and color definitions
   - `transformBoxData()` - Convert backend box data to chart format
   - `transformBoxes()` - Transform multiple boxes
   - `getBoxStyle()` - Get styling based on box status
   - `calculateBoxDimensions()` - Calculate pixel dimensions for rendering
   - `isPointInBox()` - Hit testing for hover interactions
   - `filterBoxesByStatus()` - Filter boxes by status
   - `filterBoxesByTimeRange()` - Filter by time range
   - `filterBoxesByMarket()` - Filter by market ID
   - `sortBoxesByTime()` - Sort boxes chronologically
   - `getBoxStatistics()` - Calculate box statistics
   - `formatBoxTimeRange()` - Format time for display
   - `formatBoxPriceRange()` - Format price for display
   - `getBoxAge()` - Calculate box age
   - `getBoxRemainingTime()` - Calculate remaining time
   - `isBoxInTimeWindow()` - Check if box is active
   - `generateSampleBoxes()` - Generate test data
   - `createBoxTooltipContent()` - Create tooltip content

2. **`frontend/src/components/charts/BoxOverlay.jsx`** (400+ lines)
   - `BoxTooltip` - Tooltip component for box metadata
   - `SingleBox` - Individual box overlay component
   - `BoxOverlay` - Main component for rendering multiple boxes
   - `BoxLegend` - Legend showing box status types
   - `BoxList` - List view for sidebar display

3. **`frontend/src/hooks/useBoxes.js`** (350+ lines)
   - `useBoxes` - Main hook for box state management
     - Socket.io integration for real-time updates
     - Box filtering and statistics
     - Subscription management
   - `useBoxHover` - Hook for hover state management
   - `useBoxSelection` - Hook for selection state management
   - `useBoxFilters` - Hook for filter state management

### Modified Files

4. **`frontend/src/components/charts/PriceChart.jsx`**
   - Added box overlay integration
   - Added `showBoxes` prop for visibility toggle
   - Added `boxes` prop for external box data
   - Added `marketId` prop for filtering
   - Added `onBoxClick` and `onBoxHover` callbacks
   - Added box visibility toggle button
   - Added box statistics overlay
   - Added box status filter buttons
   - Integrated `useBoxes` hook for real-time updates

5. **`frontend/src/components/charts/index.js`**
   - Added exports for BoxOverlay, BoxLegend, BoxList

## Box Types and Colors

| Type | Fill Color | Stroke Color | Description |
|------|------------|--------------|-------------|
| Active | `rgba(59, 130, 246, 0.15)` | `#3b82f6` (Blue) | Currently valid trading opportunity |
| Triggered | `rgba(234, 179, 8, 0.15)` | `#eab308` (Gold) | Price entered the box zone |
| Expired | `rgba(100, 116, 139, 0.1)` | `#64748b` (Gray) | Box time window passed |
| Failed | `rgba(239, 68, 68, 0.15)` | `#ef4444` (Red) | Box invalidated |

## Box Data Structure

```javascript
{
  id: string,           // Unique identifier
  marketId: string,     // Market ID
  timeStart: number,    // Unix timestamp (seconds)
  timeEnd: number,      // Unix timestamp (seconds)
  priceLow: number,     // Lower price boundary
  priceHigh: number,    // Upper price boundary
  confidence: number,   // 0-1 confidence score
  expectedMove: number, // Expected price movement
  status: 'active' | 'triggered' | 'expired' | 'failed',
  createdAt: number,    // Creation timestamp
  metadata: Object      // Additional metadata
}
```

## Socket.io Events

### Subscribed Events
- `boxes:update` - Bulk box updates
- `box:new` - New box detected
- `box:status` - Box status change
- `box:removed` - Box removed

### Emitted Events
- `subscribe_boxes` - Subscribe to box updates
- `unsubscribe_boxes` - Unsubscribe from updates
- `get_boxes` - Request current boxes

## Features Implemented

### 1. Box Rendering
- ✅ Rectangular boxes drawn on chart
- ✅ Multiple boxes simultaneously
- ✅ Color coding by status
- ✅ Status labels on boxes
- ✅ Confidence percentage display

### 2. Interactivity
- ✅ Hover shows detailed tooltip
- ✅ Box click callback support
- ✅ Box hover callback support
- ✅ Filter by status buttons

### 3. Real-time Updates
- ✅ Socket.io integration
- ✅ Automatic box updates
- ✅ Status change handling
- ✅ Box removal handling

### 4. UI Controls
- ✅ Toggle boxes visibility button
- ✅ Box count display
- ✅ Average confidence display
- ✅ Status filter buttons
- ✅ Box legend with statistics

### 5. Animations
- ✅ Pulse animation on new boxes
- ✅ Smooth transitions

## Usage Examples

### Basic Usage
```jsx
import { PriceChart } from './components/charts';

<PriceChart
    data={ohlcvData}
    signals={signals}
    showBoxes={true}
    symbol="POLY"
    marketId="market-123"
/>
```

### With External Box Data
```jsx
<PriceChart
    data={ohlcvData}
    boxes={transformedBoxes}
    showBoxes={true}
    onBoxClick={(box) => console.log('Box clicked:', box)}
/>
```

### Using Hook Directly
```jsx
import { useBoxes } from './hooks/useBoxes';

const { boxes, activeBoxes, statistics } = useBoxes({
    marketId: 'market-123',
    statuses: ['active', 'triggered'],
});
```

## Testing Steps

1. **Box Rendering**
   - Load chart with sample data
   - Enable boxes with toggle button
   - Verify boxes appear at correct positions
   - Check color coding matches status

2. **Multiple Boxes**
   - Generate multiple sample boxes
   - Verify all boxes display correctly
   - Check no overlap issues

3. **Hover Interactions**
   - Hover over a box
   - Verify tooltip appears
   - Check all metadata displays correctly

4. **Real-time Updates**
   - Connect to Socket.io server
   - Verify boxes update on events
   - Test status changes

5. **Filtering**
   - Click status filter buttons
   - Verify boxes filter correctly
   - Test multiple filter combinations

## Dependencies

- React 18+
- Lightweight Charts
- Socket.io Client
- Tailwind CSS

## Future Enhancements

1. Box drawing/editing tools
2. Box alerts and notifications
3. Historical box performance
4. Box export functionality
5. Advanced filtering options
