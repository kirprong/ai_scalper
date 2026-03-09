import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { tradingApi, marketApi } from '../services/api';
import useTradingStore from '../stores/tradingStore';
import { PriceChart, VolumeChart, SignalLegend } from '../components/charts';
import OrderBook, { OrderBookCompact } from '../components/OrderBook';
import DepthChart, { DepthChartCompact } from '../components/DepthChart';
import { useSocket } from '../context/SocketContext';
import { generateSampleSignals } from '../utils/chartUtils';

/**
 * Trading page - Trading interface with charts and order management
 */
const Trading = () => {
    const queryClient = useQueryClient();
    const {
        selectedMarket,
        selectMarket,
        orderBook,
        setOrderBook,
        lastPrice,
        updateLastPrice,
    } = useTradingStore();

    const [orderForm, setOrderForm] = useState({
        side: 'YES',
        type: 'limit',
        price: '',
        size: '',
    });

    // View mode for order book (full or compact)
    const [orderBookView, setOrderBookView] = useState('full'); // 'full' | 'compact'
    const [showDepthChart, setShowDepthChart] = useState(true);

    // Fetch markets
    const { data: marketsData, isLoading: marketsLoading } = useQuery({
        queryKey: ['markets'],
        queryFn: marketApi.getMarkets,
    });

    // Fetch price history for selected market
    const { data: priceHistoryData, isLoading: priceHistoryLoading } = useQuery({
        queryKey: ['priceHistory', selectedMarket?.id],
        queryFn: () => selectedMarket ? marketApi.getPriceHistory(selectedMarket.id, { period: '1h' }) : null,
        enabled: !!selectedMarket,
        refetchInterval: 5000,
    });

    // Place order mutation
    const placeOrderMutation = useMutation({
        mutationFn: tradingApi.placeOrder,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['orders'] });
            setOrderForm({ side: 'YES', type: 'limit', price: '', size: '' });
        },
    });

    // Cancel order mutation
    const cancelOrderMutation = useMutation({
        mutationFn: tradingApi.cancelOrder,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['orders'] });
        },
    });

    // Fetch open orders
    const { data: ordersData, isLoading: ordersLoading } = useQuery({
        queryKey: ['orders'],
        queryFn: tradingApi.getOrders,
        refetchInterval: 3000,
    });

    // Handle market selection
    const handleMarketSelect = (market) => {
        selectMarket(market);
    };

    // Handle order form changes
    const handleFormChange = (field, value) => {
        setOrderForm((prev) => ({ ...prev, [field]: value }));
    };

    // Handle order submission
    const handleSubmitOrder = (e) => {
        e.preventDefault();
        if (!selectedMarket) return;

        placeOrderMutation.mutate({
            marketId: selectedMarket.id,
            ...orderForm,
            price: parseFloat(orderForm.price),
            size: parseFloat(orderForm.size),
        });
    };

    // Handle cancel order
    const handleCancelOrder = (orderId) => {
        cancelOrderMutation.mutate(orderId);
    };

    // Handle price click from order book
    const handlePriceClick = useCallback((level) => {
        setOrderForm((prev) => ({
            ...prev,
            price: level.price.toString(),
            side: level.side === 'bid' ? 'YES' : 'NO',
        }));
    }, []);

    // Socket connection for real-time updates
    const { connected } = useSocket();

    // Transform price history data for Lightweight Charts
    const chartData = useMemo(() => {
        if (!priceHistoryData?.data) return [];

        // If data is already in OHLCV format
        if (priceHistoryData.data[0]?.open !== undefined) {
            return priceHistoryData.data;
        }

        // Transform simple price data to candlestick format
        return priceHistoryData.data.map((item, index) => {
            const time = typeof item.time === 'string'
                ? Math.floor(new Date(`2024-01-01 ${item.time}`).getTime() / 1000)
                : item.time || Math.floor(Date.now() / 1000) - (index * 60);
            const price = item.price || item.close || 0.5;
            const volatility = 0.01;

            return {
                time,
                open: price * (1 + (Math.random() - 0.5) * volatility),
                high: price * (1 + Math.random() * volatility),
                low: price * (1 - Math.random() * volatility),
                close: price,
                volume: Math.random() * 10000 + 1000,
            };
        });
    }, [priceHistoryData]);

    // Generate sample signals for demonstration
    const signals = useMemo(() => {
        if (chartData.length === 0) return [];
        return generateSampleSignals(chartData, 8);
    }, [chartData]);

    return (
        <div className="space-y-6">
            {/* Page Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Trading</h1>
                    <p className="text-slate-400">Market view and order management</p>
                </div>
                <div className="flex items-center gap-2">
                    {connected ? (
                        <span className="flex items-center gap-1 text-sm text-emerald-400">
                            <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                            Connected
                        </span>
                    ) : (
                        <span className="flex items-center gap-1 text-sm text-red-400">
                            <span className="w-2 h-2 bg-red-400 rounded-full" />
                            Disconnected
                        </span>
                    )}
                </div>
            </div>

            {/* Market Selection */}
            <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                <h3 className="text-lg font-semibold text-white mb-3">Select Market</h3>
                {marketsLoading ? (
                    <div className="text-slate-400">Loading markets...</div>
                ) : (
                    <div className="flex flex-wrap gap-2">
                        {marketsData?.data?.slice(0, 10).map((market) => (
                            <button
                                key={market.id}
                                onClick={() => handleMarketSelect(market)}
                                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${selectedMarket?.id === market.id
                                    ? 'bg-emerald-600 text-white'
                                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                                    }`}
                            >
                                {market.question || market.name}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            {/* Main Trading Interface - 3 Column Layout */}
            <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
                {/* Left Column - Price Chart */}
                <div className="xl:col-span-2 space-y-6">
                    {/* Price Chart */}
                    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold text-white">
                                {selectedMarket?.question || 'Select a Market'}
                            </h3>
                            {lastPrice && (
                                <div className="text-right">
                                    <span className="text-2xl font-bold text-emerald-400">
                                        ${lastPrice.toFixed(2)}
                                    </span>
                                </div>
                            )}
                        </div>

                        {selectedMarket ? (
                            <div className="space-y-4">
                                <PriceChart
                                    data={chartData}
                                    signals={signals}
                                    height={350}
                                    showVolume={true}
                                    showSignals={true}
                                    symbol={selectedMarket?.ticker || 'POLY'}
                                />
                                <SignalLegend showLabels={true} />
                            </div>
                        ) : (
                            <div className="h-[350px] flex items-center justify-center text-slate-400">
                                Select a market to view price chart
                            </div>
                        )}
                    </div>

                    {/* Depth Chart */}
                    {showDepthChart && selectedMarket && (
                        <DepthChart
                            marketId={selectedMarket?.id}
                            width={600}
                            height={250}
                            maxLevels={40}
                            className="w-full"
                        />
                    )}
                </div>

                {/* Middle Column - Order Book */}
                <div className="xl:col-span-1">
                    <div className="sticky top-4">
                        {/* Order Book View Toggle */}
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setOrderBookView('full')}
                                    className={`px-3 py-1 text-xs rounded ${orderBookView === 'full'
                                        ? 'bg-emerald-600 text-white'
                                        : 'bg-slate-700 text-slate-300'
                                        }`}
                                >
                                    Full
                                </button>
                                <button
                                    onClick={() => setOrderBookView('compact')}
                                    className={`px-3 py-1 text-xs rounded ${orderBookView === 'compact'
                                        ? 'bg-emerald-600 text-white'
                                        : 'bg-slate-700 text-slate-300'
                                        }`}
                                >
                                    Compact
                                </button>
                            </div>
                            <button
                                onClick={() => setShowDepthChart(!showDepthChart)}
                                className={`px-3 py-1 text-xs rounded ${showDepthChart
                                    ? 'bg-emerald-600 text-white'
                                    : 'bg-slate-700 text-slate-300'
                                    }`}
                            >
                                {showDepthChart ? 'Hide Depth' : 'Show Depth'}
                            </button>
                        </div>

                        {/* Order Book Component */}
                        {orderBookView === 'full' ? (
                            <OrderBook
                                marketId={selectedMarket?.id}
                                maxLevels={15}
                                showCumulative={true}
                                showImbalance={true}
                                showSpread={true}
                                onPriceClick={handlePriceClick}
                            />
                        ) : (
                            <OrderBookCompact
                                marketId={selectedMarket?.id}
                                maxLevels={8}
                                onPriceClick={handlePriceClick}
                            />
                        )}
                    </div>
                </div>

                {/* Right Column - Order Form & Open Orders */}
                <div className="xl:col-span-1 space-y-6">
                    {/* Place Order Form */}
                    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                        <h3 className="text-lg font-semibold text-white mb-4">Place Order</h3>
                        <form onSubmit={handleSubmitOrder} className="space-y-4">
                            {/* Side Selection */}
                            <div>
                                <label className="block text-sm text-slate-400 mb-2">Side</label>
                                <div className="flex gap-2">
                                    <button
                                        type="button"
                                        onClick={() => handleFormChange('side', 'YES')}
                                        className={`flex-1 py-2 rounded-lg font-medium transition-colors ${orderForm.side === 'YES'
                                            ? 'bg-emerald-600 text-white'
                                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                                            }`}
                                    >
                                        YES
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => handleFormChange('side', 'NO')}
                                        className={`flex-1 py-2 rounded-lg font-medium transition-colors ${orderForm.side === 'NO'
                                            ? 'bg-red-600 text-white'
                                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                                            }`}
                                    >
                                        NO
                                    </button>
                                </div>
                            </div>

                            {/* Order Type */}
                            <div>
                                <label className="block text-sm text-slate-400 mb-2">Order Type</label>
                                <select
                                    value={orderForm.type}
                                    onChange={(e) => handleFormChange('type', e.target.value)}
                                    className="w-full bg-slate-700 text-white rounded-lg px-4 py-2 border border-slate-600 focus:border-emerald-500 focus:outline-none"
                                >
                                    <option value="limit">Limit</option>
                                    <option value="market">Market</option>
                                </select>
                            </div>

                            {/* Price (for limit orders) */}
                            {orderForm.type === 'limit' && (
                                <div>
                                    <label className="block text-sm text-slate-400 mb-2">Price</label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        min="0.01"
                                        max="0.99"
                                        value={orderForm.price}
                                        onChange={(e) => handleFormChange('price', e.target.value)}
                                        placeholder="0.50"
                                        className="w-full bg-slate-700 text-white rounded-lg px-4 py-2 border border-slate-600 focus:border-emerald-500 focus:outline-none"
                                    />
                                </div>
                            )}

                            {/* Size */}
                            <div>
                                <label className="block text-sm text-slate-400 mb-2">Size ($)</label>
                                <input
                                    type="number"
                                    step="1"
                                    min="1"
                                    value={orderForm.size}
                                    onChange={(e) => handleFormChange('size', e.target.value)}
                                    placeholder="100"
                                    className="w-full bg-slate-700 text-white rounded-lg px-4 py-2 border border-slate-600 focus:border-emerald-500 focus:outline-none"
                                />
                            </div>

                            {/* Submit Button */}
                            <button
                                type="submit"
                                disabled={!selectedMarket || placeOrderMutation.isPending}
                                className={`w-full py-3 rounded-lg font-semibold transition-colors ${orderForm.side === 'YES'
                                    ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                                    : 'bg-red-600 hover:bg-red-700 text-white'
                                    } disabled:opacity-50 disabled:cursor-not-allowed`}
                            >
                                {placeOrderMutation.isPending ? 'Placing...' : `Place ${orderForm.side} Order`}
                            </button>
                        </form>
                    </div>

                    {/* Open Orders */}
                    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                        <h3 className="text-lg font-semibold text-white mb-4">Open Orders</h3>
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="text-left text-slate-400 text-sm border-b border-slate-700">
                                        <th className="pb-3">Side</th>
                                        <th className="pb-3">Price</th>
                                        <th className="pb-3">Size</th>
                                        <th className="pb-3">Action</th>
                                    </tr>
                                </thead>
                                <tbody className="text-sm">
                                    {ordersLoading ? (
                                        <tr>
                                            <td colSpan={4} className="py-4 text-center text-slate-400">Loading...</td>
                                        </tr>
                                    ) : ordersData?.data?.length > 0 ? (
                                        ordersData.data.filter((o) => o.status === 'open').slice(0, 5).map((order) => (
                                            <tr key={order.id} className="border-b border-slate-700">
                                                <td className={`py-3 ${order.side === 'YES' ? 'text-emerald-400' : 'text-red-400'}`}>
                                                    {order.side}
                                                </td>
                                                <td className="py-3 text-slate-300">${order.price}</td>
                                                <td className="py-3 text-slate-300">${order.size}</td>
                                                <td className="py-3">
                                                    <button
                                                        onClick={() => handleCancelOrder(order.id)}
                                                        disabled={cancelOrderMutation.isPending}
                                                        className="text-red-400 hover:text-red-300 transition-colors"
                                                    >
                                                        Cancel
                                                    </button>
                                                </td>
                                            </tr>
                                        ))
                                    ) : (
                                        <tr>
                                            <td colSpan={4} className="py-4 text-center text-slate-400">No open orders</td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Trading;
