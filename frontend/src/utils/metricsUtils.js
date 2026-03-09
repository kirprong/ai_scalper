/**
 * Metrics Utilities
 * Calculation functions for trading performance metrics
 */

/**
 * Calculate Sharpe Ratio
 * Measures risk-adjusted return
 * @param {number[]} returns - Array of period returns
 * @param {number} riskFreeRate - Risk-free rate (default: 0.02 for 2% annual)
 * @param {number} periodsPerYear - Number of periods per year (252 for daily)
 * @returns {number} Sharpe ratio
 */
export const calculateSharpeRatio = (returns, riskFreeRate = 0.02, periodsPerYear = 252) => {
    if (!returns || returns.length < 2) return 0;

    // Filter out invalid values
    const validReturns = returns.filter(r => isFinite(r));
    if (validReturns.length < 2) return 0;

    const meanReturn = validReturns.reduce((sum, r) => sum + r, 0) / validReturns.length;
    const variance = validReturns.reduce((sum, r) => sum + Math.pow(r - meanReturn, 2), 0) / validReturns.length;
    const stdDev = Math.sqrt(variance);

    if (stdDev === 0) return 0;

    // Annualize the Sharpe ratio
    const excessReturn = meanReturn - (riskFreeRate / periodsPerYear);
    const sharpeRatio = (excessReturn / stdDev) * Math.sqrt(periodsPerYear);

    return isFinite(sharpeRatio) ? sharpeRatio : 0;
};

/**
 * Calculate Maximum Drawdown
 * Largest peak-to-trough decline in cumulative returns
 * @param {number[]} values - Array of portfolio values or cumulative PnL
 * @returns {Object} Max drawdown info { maxDrawdown, peakValue, troughValue, peakIndex, troughIndex }
 */
export const calculateMaxDrawdown = (values) => {
    if (!values || values.length < 2) {
        return {
            maxDrawdown: 0,
            maxDrawdownPercent: 0,
            peakValue: 0,
            troughValue: 0,
            peakIndex: 0,
            troughIndex: 0,
        };
    }

    // Filter out invalid values
    const validValues = values.filter(v => isFinite(v));
    if (validValues.length < 2) {
        return {
            maxDrawdown: 0,
            maxDrawdownPercent: 0,
            peakValue: 0,
            troughValue: 0,
            peakIndex: 0,
            troughIndex: 0,
        };
    }

    let maxDrawdown = 0;
    let maxDrawdownPercent = 0;
    let peak = validValues[0];
    let peakValue = validValues[0];
    let troughValue = validValues[0];
    let peakIndex = 0;
    let troughIndex = 0;

    for (let i = 1; i < validValues.length; i++) {
        const currentValue = validValues[i];

        if (currentValue > peak) {
            peak = currentValue;
        }

        const drawdown = peak - currentValue;
        const drawdownPercent = peak > 0 ? (drawdown / peak) * 100 : 0;

        if (drawdown > maxDrawdown) {
            maxDrawdown = drawdown;
            maxDrawdownPercent = drawdownPercent;
            peakValue = peak;
            troughValue = currentValue;
            peakIndex = validValues.indexOf(peak);
            troughIndex = i;
        }
    }

    return {
        maxDrawdown,
        maxDrawdownPercent,
        peakValue,
        troughValue,
        peakIndex,
        troughIndex,
    };
};

/**
 * Calculate Profit Factor
 * Ratio of gross profit to gross loss
 * @param {number[]} tradePnLs - Array of individual trade P&L values
 * @returns {number} Profit factor (Infinity if no losses)
 */
export const calculateProfitFactor = (tradePnLs) => {
    if (!tradePnLs || tradePnLs.length === 0) return 0;

    // Filter out invalid values
    const validPnLs = tradePnLs.filter(pnl => isFinite(pnl));
    if (validPnLs.length === 0) return 0;

    const grossProfit = validPnLs
        .filter(pnl => pnl > 0)
        .reduce((sum, pnl) => sum + pnl, 0);

    const grossLoss = Math.abs(validPnLs
        .filter(pnl => pnl < 0)
        .reduce((sum, pnl) => sum + pnl, 0));

    if (grossLoss === 0) return grossProfit > 0 ? Infinity : 0;

    return grossProfit / grossLoss;
};

/**
 * Calculate Win Rate
 * Percentage of profitable trades
 * @param {number[]} tradePnLs - Array of individual trade P&L values
 * @returns {number} Win rate as percentage (0-100)
 */
export const calculateWinRate = (tradePnLs) => {
    if (!tradePnLs || tradePnLs.length === 0) return 0;

    // Filter out invalid values
    const validPnLs = tradePnLs.filter(pnl => isFinite(pnl));
    if (validPnLs.length === 0) return 0;

    const wins = validPnLs.filter(pnl => pnl > 0).length;
    const total = validPnLs.length;

    return (wins / total) * 100;
};

/**
 * Calculate Average Trade
 * Mean P&L per trade
 * @param {number[]} tradePnLs - Array of individual trade P&L values
 * @returns {number} Average trade P&L
 */
export const calculateAverageTrade = (tradePnLs) => {
    if (!tradePnLs || tradePnLs.length === 0) return 0;

    // Filter out invalid values
    const validPnLs = tradePnLs.filter(pnl => isFinite(pnl));
    if (validPnLs.length === 0) return 0;

    const sum = validPnLs.reduce((total, pnl) => total + pnl, 0);
    return sum / validPnLs.length;
};

/**
 * Calculate Average Win
 * Mean P&L for profitable trades
 * @param {number[]} tradePnLs - Array of individual trade P&L values
 * @returns {number} Average winning trade P&L
 */
export const calculateAverageWin = (tradePnLs) => {
    if (!tradePnLs || tradePnLs.length === 0) return 0;

    const wins = tradePnLs.filter(pnl => isFinite(pnl) && pnl > 0);
    if (wins.length === 0) return 0;

    return wins.reduce((sum, pnl) => sum + pnl, 0) / wins.length;
};

/**
 * Calculate Average Loss
 * Mean P&L for losing trades
 * @param {number[]} tradePnLs - Array of individual trade P&L values
 * @returns {number} Average losing trade P&L (negative value)
 */
export const calculateAverageLoss = (tradePnLs) => {
    if (!tradePnLs || tradePnLs.length === 0) return 0;

    const losses = tradePnLs.filter(pnl => isFinite(pnl) && pnl < 0);
    if (losses.length === 0) return 0;

    return losses.reduce((sum, pnl) => sum + pnl, 0) / losses.length;
};

/**
 * Calculate Expectancy
 * Expected value per trade
 * @param {number[]} tradePnLs - Array of individual trade P&L values
 * @returns {number} Expectancy
 */
export const calculateExpectancy = (tradePnLs) => {
    if (!tradePnLs || tradePnLs.length === 0) return 0;

    const winRate = calculateWinRate(tradePnLs) / 100;
    const avgWin = calculateAverageWin(tradePnLs);
    const avgLoss = Math.abs(calculateAverageLoss(tradePnLs));

    if (avgLoss === 0) return avgWin * winRate;

    return (winRate * avgWin) - ((1 - winRate) * avgLoss);
};

/**
 * Calculate Risk-Reward Ratio
 * Ratio of average win to average loss
 * @param {number[]} tradePnLs - Array of individual trade P&L values
 * @returns {number} Risk-reward ratio
 */
export const calculateRiskRewardRatio = (tradePnLs) => {
    const avgWin = calculateAverageWin(tradePnLs);
    const avgLoss = Math.abs(calculateAverageLoss(tradePnLs));

    if (avgLoss === 0) return avgWin > 0 ? Infinity : 0;

    return avgWin / avgLoss;
};

/**
 * Calculate Sortino Ratio
 * Risk-adjusted return considering only downside volatility
 * @param {number[]} returns - Array of period returns
 * @param {number} riskFreeRate - Risk-free rate (default: 0.02 for 2% annual)
 * @param {number} periodsPerYear - Number of periods per year
 * @returns {number} Sortino ratio
 */
export const calculateSortinoRatio = (returns, riskFreeRate = 0.02, periodsPerYear = 252) => {
    if (!returns || returns.length < 2) return 0;

    const validReturns = returns.filter(r => isFinite(r));
    if (validReturns.length < 2) return 0;

    const meanReturn = validReturns.reduce((sum, r) => sum + r, 0) / validReturns.length;
    const targetReturn = riskFreeRate / periodsPerYear;

    // Calculate downside deviation
    const negativeReturns = validReturns.filter(r => r < targetReturn);
    if (negativeReturns.length === 0) return 0;

    const downsideVariance = negativeReturns.reduce((sum, r) => {
        return sum + Math.pow(r - targetReturn, 2);
    }, 0) / validReturns.length;

    const downsideDeviation = Math.sqrt(downsideVariance);

    if (downsideDeviation === 0) return 0;

    const excessReturn = meanReturn - targetReturn;
    const sortinoRatio = (excessReturn / downsideDeviation) * Math.sqrt(periodsPerYear);

    return isFinite(sortinoRatio) ? sortinoRatio : 0;
};

/**
 * Calculate Calmar Ratio
 * Annual return divided by maximum drawdown
 * @param {number[]} values - Array of portfolio values
 * @param {number} periodsPerYear - Number of periods per year
 * @returns {number} Calmar ratio
 */
export const calculateCalmarRatio = (values, periodsPerYear = 252) => {
    if (!values || values.length < 2) return 0;

    const validValues = values.filter(v => isFinite(v));
    if (validValues.length < 2) return 0;

    const startValue = validValues[0];
    const endValue = validValues[validValues.length - 1];

    if (startValue <= 0) return 0;

    const totalReturn = (endValue - startValue) / startValue;
    const annualizedReturn = totalReturn * (periodsPerYear / validValues.length);

    const { maxDrawdownPercent } = calculateMaxDrawdown(validValues);

    if (maxDrawdownPercent === 0) return annualizedReturn > 0 ? Infinity : 0;

    return (annualizedReturn * 100) / maxDrawdownPercent;
};

/**
 * Calculate Volatility (Annualized)
 * Standard deviation of returns annualized
 * @param {number[]} returns - Array of period returns
 * @param {number} periodsPerYear - Number of periods per year
 * @returns {number} Annualized volatility
 */
export const calculateVolatility = (returns, periodsPerYear = 252) => {
    if (!returns || returns.length < 2) return 0;

    const validReturns = returns.filter(r => isFinite(r));
    if (validReturns.length < 2) return 0;

    const meanReturn = validReturns.reduce((sum, r) => sum + r, 0) / validReturns.length;
    const variance = validReturns.reduce((sum, r) => sum + Math.pow(r - meanReturn, 2), 0) / validReturns.length;
    const stdDev = Math.sqrt(variance);

    return stdDev * Math.sqrt(periodsPerYear);
};

/**
 * Calculate Total PnL
 * Sum of all trade P&L values
 * @param {number[]} tradePnLs - Array of individual trade P&L values
 * @returns {number} Total P&L
 */
export const calculateTotalPnL = (tradePnLs) => {
    if (!tradePnLs || tradePnLs.length === 0) return 0;

    return tradePnLs
        .filter(pnl => isFinite(pnl))
        .reduce((sum, pnl) => sum + pnl, 0);
};

/**
 * Calculate Trade Statistics
 * Comprehensive statistics for a set of trades
 * @param {Array} trades - Array of trade objects with pnl property
 * @returns {Object} Trade statistics
 */
export const calculateTradeStatistics = (trades) => {
    if (!trades || trades.length === 0) {
        return {
            totalTrades: 0,
            winningTrades: 0,
            losingTrades: 0,
            totalPnL: 0,
            winRate: 0,
            profitFactor: 0,
            avgTrade: 0,
            avgWin: 0,
            avgLoss: 0,
            largestWin: 0,
            largestLoss: 0,
            expectancy: 0,
            riskRewardRatio: 0,
        };
    }

    const tradePnLs = trades.map(t => t.pnl).filter(pnl => isFinite(pnl));
    const wins = tradePnLs.filter(pnl => pnl > 0);
    const losses = tradePnLs.filter(pnl => pnl < 0);

    return {
        totalTrades: tradePnLs.length,
        winningTrades: wins.length,
        losingTrades: losses.length,
        totalPnL: calculateTotalPnL(tradePnLs),
        winRate: calculateWinRate(tradePnLs),
        profitFactor: calculateProfitFactor(tradePnLs),
        avgTrade: calculateAverageTrade(tradePnLs),
        avgWin: calculateAverageWin(tradePnLs),
        avgLoss: calculateAverageLoss(tradePnLs),
        largestWin: wins.length > 0 ? Math.max(...wins) : 0,
        largestLoss: losses.length > 0 ? Math.min(...losses) : 0,
        expectancy: calculateExpectancy(tradePnLs),
        riskRewardRatio: calculateRiskRewardRatio(tradePnLs),
    };
};

/**
 * Calculate Performance Metrics
 * Comprehensive performance metrics for a portfolio
 * @param {Array} trades - Array of trade objects
 * @param {number[]} equityCurve - Array of portfolio values over time
 * @param {number[]} returns - Array of period returns
 * @returns {Object} Performance metrics
 */
export const calculatePerformanceMetrics = (trades, equityCurve, returns) => {
    const tradeStats = calculateTradeStatistics(trades);
    const maxDrawdown = calculateMaxDrawdown(equityCurve);
    const sharpeRatio = calculateSharpeRatio(returns);
    const sortinoRatio = calculateSortinoRatio(returns);
    const calmarRatio = calculateCalmarRatio(equityCurve);
    const volatility = calculateVolatility(returns);

    return {
        ...tradeStats,
        maxDrawdown: maxDrawdown.maxDrawdown,
        maxDrawdownPercent: maxDrawdown.maxDrawdownPercent,
        sharpeRatio,
        sortinoRatio,
        calmarRatio,
        volatility,
    };
};

/**
 * Format currency value
 * @param {number} value - Value to format
 * @param {string} currency - Currency symbol
 * @returns {string} Formatted currency string
 */
export const formatCurrency = (value, currency = '$') => {
    if (!isFinite(value)) return `${currency}0.00`;
    const sign = value < 0 ? '-' : '';
    return `${sign}${currency}${Math.abs(value).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    })}`;
};

/**
 * Format percentage value
 * @param {number} value - Value to format
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted percentage string
 */
export const formatPercent = (value, decimals = 2) => {
    if (!isFinite(value)) return '0.00%';
    return `${value.toFixed(decimals)}%`;
};

/**
 * Format ratio value
 * @param {number} value - Value to format
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted ratio string
 */
export const formatRatio = (value, decimals = 2) => {
    if (!isFinite(value)) return '0.00';
    if (value === Infinity) return '∞';
    return value.toFixed(decimals);
};

/**
 * Get performance grade based on metrics
 * @param {Object} metrics - Performance metrics object
 * @returns {string} Grade (A+ to F)
 */
export const getPerformanceGrade = (metrics) => {
    const { winRate, profitFactor, sharpeRatio, maxDrawdownPercent } = metrics;

    let score = 0;

    // Win rate score (max 25 points)
    if (winRate >= 70) score += 25;
    else if (winRate >= 60) score += 20;
    else if (winRate >= 50) score += 15;
    else if (winRate >= 40) score += 10;
    else score += 5;

    // Profit factor score (max 25 points)
    if (profitFactor >= 2.5) score += 25;
    else if (profitFactor >= 2) score += 20;
    else if (profitFactor >= 1.5) score += 15;
    else if (profitFactor >= 1) score += 10;
    else score += 5;

    // Sharpe ratio score (max 25 points)
    if (sharpeRatio >= 3) score += 25;
    else if (sharpeRatio >= 2) score += 20;
    else if (sharpeRatio >= 1) score += 15;
    else if (sharpeRatio >= 0) score += 10;
    else score += 5;

    // Max drawdown score (max 25 points)
    if (maxDrawdownPercent <= 5) score += 25;
    else if (maxDrawdownPercent <= 10) score += 20;
    else if (maxDrawdownPercent <= 20) score += 15;
    else if (maxDrawdownPercent <= 30) score += 10;
    else score += 5;

    // Grade assignment
    if (score >= 90) return 'A+';
    if (score >= 85) return 'A';
    if (score >= 80) return 'A-';
    if (score >= 75) return 'B+';
    if (score >= 70) return 'B';
    if (score >= 65) return 'B-';
    if (score >= 60) return 'C+';
    if (score >= 55) return 'C';
    if (score >= 50) return 'C-';
    if (score >= 40) return 'D';
    return 'F';
};

export default {
    calculateSharpeRatio,
    calculateMaxDrawdown,
    calculateProfitFactor,
    calculateWinRate,
    calculateAverageTrade,
    calculateAverageWin,
    calculateAverageLoss,
    calculateExpectancy,
    calculateRiskRewardRatio,
    calculateSortinoRatio,
    calculateCalmarRatio,
    calculateVolatility,
    calculateTotalPnL,
    calculateTradeStatistics,
    calculatePerformanceMetrics,
    formatCurrency,
    formatPercent,
    formatRatio,
    getPerformanceGrade,
};
