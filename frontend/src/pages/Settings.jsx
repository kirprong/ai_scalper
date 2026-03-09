import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi, accountApi, safetyApi } from '../services/api';
import useTradingStore from '../stores/tradingStore';

/**
 * Settings page - System configuration and preferences
 */
const Settings = () => {
    const queryClient = useQueryClient();
    const { safetyStatus, setSafetyStatus } = useTradingStore();

    const [activeTab, setActiveTab] = useState('general');
    const [localSettings, setLocalSettings] = useState({
        // General settings
        autoTrading: true,
        maxPositionSize: 1000,
        defaultLeverage: 1,
        tradingEnabled: true,

        // Risk settings
        maxDailyLoss: 500,
        maxDrawdown: 20,
        stopLossPercent: 5,
        takeProfitPercent: 10,

        // Detection settings
        goldenRectangleEnabled: true,
        minConfidence: 75,
        signalCooldown: 30,

        // Notification settings
        emailNotifications: false,
        pushNotifications: true,
        soundAlerts: true,

        // API settings
        apiKey: '',
        apiSecret: '',
    });

    // Fetch current settings
    const { data: settingsData, isLoading: settingsLoading } = useQuery({
        queryKey: ['settings'],
        queryFn: settingsApi.getSettings,
    });

    // Fetch account info
    const { data: accountData, isLoading: accountLoading } = useQuery({
        queryKey: ['account'],
        queryFn: accountApi.getAccountInfo,
    });

    // Update settings mutation
    const updateSettingsMutation = useMutation({
        mutationFn: settingsApi.updateSettings,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['settings'] });
        },
    });

    // Reset settings mutation
    const resetSettingsMutation = useMutation({
        mutationFn: settingsApi.resetToDefaults,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['settings'] });
        },
    });

    // Toggle kill switch mutation
    const toggleKillSwitchMutation = useMutation({
        mutationFn: (enabled) => safetyApi.toggleKillSwitch(enabled),
        onSuccess: (data) => {
            setSafetyStatus(data.data);
        },
    });

    // Handle settings change
    const handleSettingChange = (key, value) => {
        setLocalSettings((prev) => ({ ...prev, [key]: value }));
    };

    // Handle save settings
    const handleSaveSettings = () => {
        updateSettingsMutation.mutate(localSettings);
    };

    // Handle reset settings
    const handleResetSettings = () => {
        if (window.confirm('Are you sure you want to reset all settings to defaults?')) {
            resetSettingsMutation.mutate();
        }
    };

    // Handle kill switch toggle
    const handleKillSwitchToggle = () => {
        const newState = !safetyStatus?.killSwitchEnabled;
        toggleKillSwitchMutation.mutate(newState);
    };

    // Tabs configuration
    const tabs = [
        { id: 'general', label: 'General', icon: '⚙️' },
        { id: 'risk', label: 'Risk Management', icon: '🛡️' },
        { id: 'detection', label: 'Detection', icon: '🎯' },
        { id: 'notifications', label: 'Notifications', icon: '🔔' },
        { id: 'api', label: 'API Keys', icon: '🔑' },
        { id: 'safety', label: 'Safety', icon: '🚨' },
    ];

    return (
        <div className="space-y-6">
            {/* Page Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Settings</h1>
                    <p className="text-slate-400">Configure your trading system preferences</p>
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={handleResetSettings}
                        className="px-4 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors"
                    >
                        Reset to Defaults
                    </button>
                    <button
                        onClick={handleSaveSettings}
                        disabled={updateSettingsMutation.isPending}
                        className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50"
                    >
                        {updateSettingsMutation.isPending ? 'Saving...' : 'Save Changes'}
                    </button>
                </div>
            </div>

            {/* Settings Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                {/* Tabs Sidebar */}
                <div className="lg:col-span-1">
                    <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
                        {tabs.map((tab) => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`w-full px-4 py-3 text-left flex items-center gap-3 transition-colors ${activeTab === tab.id
                                        ? 'bg-emerald-600 text-white'
                                        : 'text-slate-300 hover:bg-slate-700'
                                    }`}
                            >
                                <span>{tab.icon}</span>
                                <span>{tab.label}</span>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Settings Content */}
                <div className="lg:col-span-3">
                    <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
                        {/* General Settings */}
                        {activeTab === 'general' && (
                            <div className="space-y-6">
                                <h2 className="text-xl font-semibold text-white mb-4">General Settings</h2>

                                <div className="space-y-4">
                                    {/* Auto Trading Toggle */}
                                    <div className="flex items-center justify-between p-4 bg-slate-700 rounded-lg">
                                        <div>
                                            <h3 className="text-white font-medium">Auto Trading</h3>
                                            <p className="text-sm text-slate-400">Enable automatic trade execution</p>
                                        </div>
                                        <label className="relative inline-flex items-center cursor-pointer">
                                            <input
                                                type="checkbox"
                                                checked={localSettings.autoTrading}
                                                onChange={(e) => handleSettingChange('autoTrading', e.target.checked)}
                                                className="sr-only peer"
                                            />
                                            <div className="w-11 h-6 bg-slate-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
                                        </label>
                                    </div>

                                    {/* Max Position Size */}
                                    <div className="p-4 bg-slate-700 rounded-lg">
                                        <label className="block text-white font-medium mb-2">Max Position Size ($)</label>
                                        <input
                                            type="number"
                                            value={localSettings.maxPositionSize}
                                            onChange={(e) => handleSettingChange('maxPositionSize', parseInt(e.target.value))}
                                            className="w-full bg-slate-600 text-white rounded-lg px-4 py-2 border border-slate-500 focus:border-emerald-500 focus:outline-none"
                                        />
                                        <p className="text-sm text-slate-400 mt-1">Maximum size per position in USD</p>
                                    </div>

                                    {/* Default Leverage */}
                                    <div className="p-4 bg-slate-700 rounded-lg">
                                        <label className="block text-white font-medium mb-2">Default Leverage</label>
                                        <select
                                            value={localSettings.defaultLeverage}
                                            onChange={(e) => handleSettingChange('defaultLeverage', parseInt(e.target.value))}
                                            className="w-full bg-slate-600 text-white rounded-lg px-4 py-2 border border-slate-500 focus:border-emerald-500 focus:outline-none"
                                        >
                                            <option value={1}>1x</option>
                                            <option value={2}>2x</option>
                                            <option value={3}>3x</option>
                                            <option value={5}>5x</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Risk Management Settings */}
                        {activeTab === 'risk' && (
                            <div className="space-y-6">
                                <h2 className="text-xl font-semibold text-white mb-4">Risk Management</h2>

                                <div className="space-y-4">
                                    {/* Max Daily Loss */}
                                    <div className="p-4 bg-slate-700 rounded-lg">
                                        <label className="block text-white font-medium mb-2">Max Daily Loss ($)</label>
                                        <input
                                            type="number"
                                            value={localSettings.maxDailyLoss}
                                            onChange={(e) => handleSettingChange('maxDailyLoss', parseInt(e.target.value))}
                                            className="w-full bg-slate-600 text-white rounded-lg px-4 py-2 border border-slate-500 focus:border-emerald-500 focus:outline-none"
                                        />
                                        <p className="text-sm text-slate-400 mt-1">Stop trading when daily loss exceeds this amount</p>
                                    </div>

                                    {/* Max Drawdown */}
                                    <div className="p-4 bg-slate-700 rounded-lg">
                                        <label className="block text-white font-medium mb-2">Max Drawdown (%)</label>
                                        <input
                                            type="number"
                                            value={localSettings.maxDrawdown}
                                            onChange={(e) => handleSettingChange('maxDrawdown', parseInt(e.target.value))}
                                            className="w-full bg-slate-600 text-white rounded-lg px-4 py-2 border border-slate-500 focus:border-emerald-500 focus:outline-none"
                                        />
                                        <p className="text-sm text-slate-400 mt-1">Maximum portfolio drawdown percentage</p>
                                    </div>

                                    {/* Stop Loss */}
                                    <div className="p-4 bg-slate-700 rounded-lg">
                                        <label className="block text-white font-medium mb-2">Stop Loss (%)</label>
                                        <input
                                            type="number"
                                            value={localSettings.stopLossPercent}
                                            onChange={(e) => handleSettingChange('stopLossPercent', parseInt(e.target.value))}
                                            className="w-full bg-slate-600 text-white rounded-lg px-4 py-2 border border-slate-500 focus:border-emerald-500 focus:outline-none"
                                        />
                                        <p className="text-sm text-slate-400 mt-1">Default stop loss percentage</p>
                                    </div>

                                    {/* Take Profit */}
                                    <div className="p-4 bg-slate-700 rounded-lg">
                                        <label className="block text-white font-medium mb-2">Take Profit (%)</label>
                                        <input
                                            type="number"
                                            value={localSettings.takeProfitPercent}
                                            onChange={(e) => handleSettingChange('takeProfitPercent', parseInt(e.target.value))}
                                            className="w-full bg-slate-600 text-white rounded-lg px-4 py-2 border border-slate-500 focus:border-emerald-500 focus:outline-none"
                                        />
                                        <p className="text-sm text-slate-400 mt-1">Default take profit percentage</p>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Detection Settings */}
                        {activeTab === 'detection' && (
                            <div className="space-y-6">
                                <h2 className="text-xl font-semibold text-white mb-4">Detection Settings</h2>

                                <div className="space-y-4">
                                    {/* Golden Rectangle Toggle */}
                                    <div className="flex items-center justify-between p-4 bg-slate-700 rounded-lg">
                                        <div>
                                            <h3 className="text-white font-medium">Golden Rectangle Detection</h3>
                                            <p className="text-sm text-slate-400">Enable AI-powered pattern detection</p>
                                        </div>
                                        <label className="relative inline-flex items-center cursor-pointer">
                                            <input
                                                type="checkbox"
                                                checked={localSettings.goldenRectangleEnabled}
                                                onChange={(e) => handleSettingChange('goldenRectangleEnabled', e.target.checked)}
                                                className="sr-only peer"
                                            />
                                            <div className="w-11 h-6 bg-slate-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
                                        </label>
                                    </div>

                                    {/* Min Confidence */}
                                    <div className="p-4 bg-slate-700 rounded-lg">
                                        <label className="block text-white font-medium mb-2">Minimum Confidence (%)</label>
                                        <input
                                            type="number"
                                            min="50"
                                            max="100"
                                            value={localSettings.minConfidence}
                                            onChange={(e) => handleSettingChange('minConfidence', parseInt(e.target.value))}
                                            className="w-full bg-slate-600 text-white rounded-lg px-4 py-2 border border-slate-500 focus:border-emerald-500 focus:outline-none"
                                        />
                                        <p className="text-sm text-slate-400 mt-1">Minimum confidence threshold for signals</p>
                                    </div>

                                    {/* Signal Cooldown */}
                                    <div className="p-4 bg-slate-700 rounded-lg">
                                        <label className="block text-white font-medium mb-2">Signal Cooldown (seconds)</label>
                                        <input
                                            type="number"
                                            value={localSettings.signalCooldown}
                                            onChange={(e) => handleSettingChange('signalCooldown', parseInt(e.target.value))}
                                            className="w-full bg-slate-600 text-white rounded-lg px-4 py-2 border border-slate-500 focus:border-emerald-500 focus:outline-none"
                                        />
                                        <p className="text-sm text-slate-400 mt-1">Minimum time between signals for same market</p>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Notifications Settings */}
                        {activeTab === 'notifications' && (
                            <div className="space-y-6">
                                <h2 className="text-xl font-semibold text-white mb-4">Notification Settings</h2>

                                <div className="space-y-4">
                                    {/* Email Notifications */}
                                    <div className="flex items-center justify-between p-4 bg-slate-700 rounded-lg">
                                        <div>
                                            <h3 className="text-white font-medium">Email Notifications</h3>
                                            <p className="text-sm text-slate-400">Receive email alerts for important events</p>
                                        </div>
                                        <label className="relative inline-flex items-center cursor-pointer">
                                            <input
                                                type="checkbox"
                                                checked={localSettings.emailNotifications}
                                                onChange={(e) => handleSettingChange('emailNotifications', e.target.checked)}
                                                className="sr-only peer"
                                            />
                                            <div className="w-11 h-6 bg-slate-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
                                        </label>
                                    </div>

                                    {/* Push Notifications */}
                                    <div className="flex items-center justify-between p-4 bg-slate-700 rounded-lg">
                                        <div>
                                            <h3 className="text-white font-medium">Push Notifications</h3>
                                            <p className="text-sm text-slate-400">Browser push notifications</p>
                                        </div>
                                        <label className="relative inline-flex items-center cursor-pointer">
                                            <input
                                                type="checkbox"
                                                checked={localSettings.pushNotifications}
                                                onChange={(e) => handleSettingChange('pushNotifications', e.target.checked)}
                                                className="sr-only peer"
                                            />
                                            <div className="w-11 h-6 bg-slate-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
                                        </label>
                                    </div>

                                    {/* Sound Alerts */}
                                    <div className="flex items-center justify-between p-4 bg-slate-700 rounded-lg">
                                        <div>
                                            <h3 className="text-white font-medium">Sound Alerts</h3>
                                            <p className="text-sm text-slate-400">Play sound for trade signals</p>
                                        </div>
                                        <label className="relative inline-flex items-center cursor-pointer">
                                            <input
                                                type="checkbox"
                                                checked={localSettings.soundAlerts}
                                                onChange={(e) => handleSettingChange('soundAlerts', e.target.checked)}
                                                className="sr-only peer"
                                            />
                                            <div className="w-11 h-6 bg-slate-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
                                        </label>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* API Keys Settings */}
                        {activeTab === 'api' && (
                            <div className="space-y-6">
                                <h2 className="text-xl font-semibold text-white mb-4">API Keys</h2>

                                <div className="space-y-4">
                                    {/* API Key */}
                                    <div className="p-4 bg-slate-700 rounded-lg">
                                        <label className="block text-white font-medium mb-2">Polymarket API Key</label>
                                        <input
                                            type="password"
                                            value={localSettings.apiKey}
                                            onChange={(e) => handleSettingChange('apiKey', e.target.value)}
                                            placeholder="Enter your API key"
                                            className="w-full bg-slate-600 text-white rounded-lg px-4 py-2 border border-slate-500 focus:border-emerald-500 focus:outline-none"
                                        />
                                        <p className="text-sm text-slate-400 mt-1">Your Polymarket API key for trading</p>
                                    </div>

                                    {/* API Secret */}
                                    <div className="p-4 bg-slate-700 rounded-lg">
                                        <label className="block text-white font-medium mb-2">Polymarket API Secret</label>
                                        <input
                                            type="password"
                                            value={localSettings.apiSecret}
                                            onChange={(e) => handleSettingChange('apiSecret', e.target.value)}
                                            placeholder="Enter your API secret"
                                            className="w-full bg-slate-600 text-white rounded-lg px-4 py-2 border border-slate-500 focus:border-emerald-500 focus:outline-none"
                                        />
                                        <p className="text-sm text-slate-400 mt-1">Your Polymarket API secret</p>
                                    </div>

                                    {/* Warning */}
                                    <div className="p-4 bg-amber-900/30 border border-amber-600/50 rounded-lg">
                                        <div className="flex items-start gap-3">
                                            <span className="text-amber-500 text-xl">⚠️</span>
                                            <div>
                                                <h4 className="text-amber-400 font-medium">Security Notice</h4>
                                                <p className="text-sm text-amber-300/80 mt-1">
                                                    Never share your API keys. Keys are stored securely and encrypted.
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Safety Settings */}
                        {activeTab === 'safety' && (
                            <div className="space-y-6">
                                <h2 className="text-xl font-semibold text-white mb-4">Safety Controls</h2>

                                <div className="space-y-4">
                                    {/* Kill Switch */}
                                    <div className="p-4 bg-slate-700 rounded-lg">
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <h3 className="text-white font-medium">Kill Switch</h3>
                                                <p className="text-sm text-slate-400">Immediately stop all trading operations</p>
                                            </div>
                                            <button
                                                onClick={handleKillSwitchToggle}
                                                disabled={toggleKillSwitchMutation.isPending}
                                                className={`px-4 py-2 rounded-lg font-medium transition-colors ${safetyStatus?.killSwitchEnabled
                                                        ? 'bg-red-600 hover:bg-red-700 text-white'
                                                        : 'bg-emerald-600 hover:bg-emerald-700 text-white'
                                                    }`}
                                            >
                                                {toggleKillSwitchMutation.isPending
                                                    ? 'Updating...'
                                                    : safetyStatus?.killSwitchEnabled
                                                        ? 'Disable Kill Switch'
                                                        : 'Enable Kill Switch'}
                                            </button>
                                        </div>
                                        {safetyStatus?.killSwitchEnabled && (
                                            <div className="mt-3 p-3 bg-red-900/30 border border-red-600/50 rounded-lg">
                                                <p className="text-red-400 text-sm">
                                                    ⚠️ Kill switch is active. All trading operations are suspended.
                                                </p>
                                            </div>
                                        )}
                                    </div>

                                    {/* Panic Button Info */}
                                    <div className="p-4 bg-slate-700 rounded-lg">
                                        <h3 className="text-white font-medium mb-2">Panic Button</h3>
                                        <p className="text-sm text-slate-400 mb-3">
                                            The panic button is available in the header. Clicking it will:
                                        </p>
                                        <ul className="text-sm text-slate-300 space-y-1 list-disc list-inside">
                                            <li>Cancel all open orders</li>
                                            <li>Close all positions at market</li>
                                            <li>Disable auto-trading</li>
                                            <li>Send notification alerts</li>
                                        </ul>
                                    </div>

                                    {/* Safety Status */}
                                    <div className="p-4 bg-slate-700 rounded-lg">
                                        <h3 className="text-white font-medium mb-3">Safety Status</h3>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="flex items-center gap-2">
                                                <span className={`w-2 h-2 rounded-full ${!safetyStatus?.killSwitchEnabled ? 'bg-emerald-500' : 'bg-red-500'
                                                    }`}></span>
                                                <span className="text-slate-300 text-sm">
                                                    Trading: {!safetyStatus?.killSwitchEnabled ? 'Enabled' : 'Disabled'}
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className={`w-2 h-2 rounded-full ${!safetyStatus?.panicTriggered ? 'bg-emerald-500' : 'bg-red-500'
                                                    }`}></span>
                                                <span className="text-slate-300 text-sm">
                                                    Panic: {!safetyStatus?.panicTriggered ? 'Not Triggered' : 'Triggered'}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Settings;
