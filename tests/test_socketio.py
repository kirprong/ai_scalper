"""
Tests for Socket.io real-time communication.

This module contains unit and integration tests for the Socket.io
server, event handlers, and emitters.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

# Test the Socket.io server module
class TestSocketIOServer:
    """Tests for Socket.io server configuration."""

    def test_create_socketio_server_default_config(self):
        """Test creating Socket.io server with default configuration."""
        from backend.realtime.socketio_server import create_socketio_server
        
        sio = create_socketio_server()
        
        assert sio is not None
        assert sio.async_mode == "aiohttp"

    def test_create_socketio_server_custom_cors(self):
        """Test creating Socket.io server with custom CORS origins."""
        from backend.realtime.socketio_server import create_socketio_server
        
        cors_origins = ["http://localhost:3000", "http://example.com"]
        sio = create_socketio_server(cors_allowed_origins=cors_origins)
        
        assert sio is not None

    def test_create_socket_app(self):
        """Test creating Socket.io ASGI app."""
        from backend.realtime.socketio_server import create_socket_app
        
        app = create_socket_app()
        
        assert app is not None

    def test_get_socketio_server(self):
        """Test getting the default Socket.io server instance."""
        from backend.realtime.socketio_server import get_socketio_server
        
        sio = get_socketio_server()
        
        assert sio is not None

    def test_register_client(self):
        """Test registering a connected client."""
        from backend.realtime.socketio_server import (
            register_client,
            unregister_client,
            get_connected_clients,
        )
        
        # Clear any existing clients
        from backend.realtime import socketio_server
        socketio_server.connected_clients.clear()
        
        register_client("test_session_1")
        
        clients = get_connected_clients()
        assert "test_session_1" in clients
        
        # Cleanup
        unregister_client("test_session_1")

    def test_unregister_client(self):
        """Test unregistering a disconnected client."""
        from backend.realtime.socketio_server import (
            register_client,
            unregister_client,
            get_connected_clients,
        )
        
        register_client("test_session_2")
        unregister_client("test_session_2")
        
        clients = get_connected_clients()
        assert "test_session_2" not in clients

    def test_add_subscription(self):
        """Test adding a market subscription."""
        from backend.realtime.socketio_server import (
            register_client,
            add_subscription,
            remove_subscription,
            get_market_subscribers,
            unregister_client,
        )
        
        register_client("test_session_3")
        add_subscription("test_session_3", "market_123")
        
        subscribers = get_market_subscribers("market_123")
        assert "test_session_3" in subscribers
        
        # Cleanup
        remove_subscription("test_session_3", "market_123")
        unregister_client("test_session_3")

    def test_remove_subscription(self):
        """Test removing a market subscription."""
        from backend.realtime.socketio_server import (
            register_client,
            add_subscription,
            remove_subscription,
            get_market_subscribers,
            unregister_client,
        )
        
        register_client("test_session_4")
        add_subscription("test_session_4", "market_456")
        remove_subscription("test_session_4", "market_456")
        
        subscribers = get_market_subscribers("market_456")
        assert "test_session_4" not in subscribers
        
        # Cleanup
        unregister_client("test_session_4")

    def test_remove_all_subscriptions(self):
        """Test removing all subscriptions for a client."""
        from backend.realtime.socketio_server import (
            register_client,
            add_subscription,
            remove_all_subscriptions,
            get_market_subscribers,
            unregister_client,
        )
        
        register_client("test_session_5")
        add_subscription("test_session_5", "market_1")
        add_subscription("test_session_5", "market_2")
        add_subscription("test_session_5", "market_3")
        
        remove_all_subscriptions("test_session_5")
        
        assert get_market_subscribers("market_1") == set()
        assert get_market_subscribers("market_2") == set()
        assert get_market_subscribers("market_3") == set()
        
        # Cleanup
        unregister_client("test_session_5")

    def test_get_subscription_stats(self):
        """Test getting subscription statistics."""
        from backend.realtime.socketio_server import (
            register_client,
            add_subscription,
            get_subscription_stats,
            unregister_client,
        )
        
        register_client("test_session_6")
        add_subscription("test_session_6", "market_789")
        
        stats = get_subscription_stats()
        
        assert "connected_clients" in stats
        assert "total_subscriptions" in stats
        assert "markets_with_subscribers" in stats
        assert "timestamp" in stats
        assert stats["connected_clients"] >= 1
        
        # Cleanup
        unregister_client("test_session_6")


class TestEventHandlers:
    """Tests for Socket.io event handlers."""

    @pytest.mark.asyncio
    async def test_register_event_handlers(self):
        """Test that event handlers are registered without errors."""
        from backend.realtime.event_handlers import register_event_handlers
        
        # Should not raise any exceptions
        register_event_handlers()

    @pytest.mark.asyncio
    async def test_emit_to_market_subscribers(self):
        """Test emitting to market subscribers."""
        from backend.realtime.socketio_server import (
            register_client,
            add_subscription,
        )
        from backend.realtime.event_handlers import emit_to_market_subscribers
        
        # Mock the sio.emit method
        with patch('backend.realtime.socketio_server.sio.emit', new_callable=AsyncMock) as mock_emit:
            register_client("test_session_emit")
            add_subscription("test_session_emit", "market_emit_test")
            
            count = await emit_to_market_subscribers(
                "market_emit_test",
                "test_event",
                {"test": "data"}
            )
            
            assert count == 1
            mock_emit.assert_called_once()


class TestEmitters:
    """Tests for Socket.io data emitters."""

    @pytest.mark.asyncio
    async def test_emit_price_update(self):
        """Test emitting price update."""
        from backend.realtime.emitters import emit_price_update
        
        with patch('backend.realtime.socketio_server.sio.emit', new_callable=AsyncMock) as mock_emit:
            with patch('backend.realtime.socketio_server.get_market_subscribers') as mock_subscribers:
                mock_subscribers.return_value = {"session1", "session2"}
                
                count = await emit_price_update(
                    "market_123",
                    {"price": 0.55, "volume": 1000},
                    broadcast=True
                )
                
                assert count == 2
                assert mock_emit.call_count == 2

    @pytest.mark.asyncio
    async def test_emit_price_update_no_subscribers(self):
        """Test emitting price update with no subscribers."""
        from backend.realtime.emitters import emit_price_update
        
        with patch('backend.realtime.socketio_server.get_market_subscribers') as mock_subscribers:
            mock_subscribers.return_value = set()
            
            count = await emit_price_update(
                "market_no_subs",
                {"price": 0.55},
                broadcast=True
            )
            
            assert count == 0

    @pytest.mark.asyncio
    async def test_emit_signal_detected(self):
        """Test emitting signal detection."""
        from backend.realtime.emitters import emit_signal_detected
        
        with patch('backend.realtime.socketio_server.sio.emit', new_callable=AsyncMock) as mock_emit:
            with patch('backend.realtime.socketio_server.get_connected_clients') as mock_clients:
                mock_clients.return_value = {"session1"}
                
                count = await emit_signal_detected({
                    "signal_type": "golden_rectangle",
                    "direction": "buy",
                    "confidence": 0.85,
                })
                
                assert count >= 1
                mock_emit.assert_called()

    @pytest.mark.asyncio
    async def test_emit_position_update(self):
        """Test emitting position update."""
        from backend.realtime.emitters import emit_position_update
        
        with patch('backend.realtime.socketio_server.sio.emit', new_callable=AsyncMock) as mock_emit:
            with patch('backend.realtime.socketio_server.get_connected_clients') as mock_clients:
                mock_clients.return_value = {"session1"}
                
                count = await emit_position_update({
                    "position_id": "pos_123",
                    "market_id": "market_456",
                    "side": "long",
                    "size": 100,
                })
                
                assert count >= 1
                mock_emit.assert_called()

    @pytest.mark.asyncio
    async def test_emit_metrics_update(self):
        """Test emitting metrics update."""
        from backend.realtime.emitters import emit_metrics_update
        
        with patch('backend.realtime.socketio_server.sio.emit', new_callable=AsyncMock) as mock_emit:
            with patch('backend.realtime.socketio_server.get_connected_clients') as mock_clients:
                mock_clients.return_value = {"session1"}
                
                count = await emit_metrics_update({
                    "total_pnl": 150.50,
                    "win_rate": 0.65,
                    "sharpe_ratio": 1.8,
                })
                
                assert count >= 1
                mock_emit.assert_called()

    @pytest.mark.asyncio
    async def test_emit_panic_alert(self):
        """Test emitting panic alert."""
        from backend.realtime.emitters import emit_panic_alert
        
        with patch('backend.realtime.socketio_server.sio.emit', new_callable=AsyncMock) as mock_emit:
            with patch('backend.realtime.socketio_server.get_connected_clients') as mock_clients:
                mock_clients.return_value = {"session1", "session2"}
                
                count = await emit_panic_alert({
                    "alert_type": "kill_switch",
                    "severity": "critical",
                    "message": "Emergency halt triggered",
                })
                
                assert count >= 2
                mock_emit.assert_called()

    @pytest.mark.asyncio
    async def test_broadcast_to_all(self):
        """Test broadcasting to all clients."""
        from backend.realtime.emitters import broadcast_to_all
        
        with patch('backend.realtime.socketio_server.sio.emit', new_callable=AsyncMock) as mock_emit:
            with patch('backend.realtime.socketio_server.get_connected_clients') as mock_clients:
                mock_clients.return_value = {"session1", "session2", "session3"}
                
                count = await broadcast_to_all("custom_event", {"custom": "data"})
                
                assert count == 3
                mock_emit.assert_called_once_with("custom_event", {"custom": "data"})

    @pytest.mark.asyncio
    async def test_emit_order_update(self):
        """Test emitting order update."""
        from backend.realtime.emitters import emit_order_update
        
        with patch('backend.realtime.socketio_server.sio.emit', new_callable=AsyncMock) as mock_emit:
            with patch('backend.realtime.socketio_server.get_connected_clients') as mock_clients:
                mock_clients.return_value = {"session1"}
                
                count = await emit_order_update({
                    "order_id": "order_123",
                    "market_id": "market_456",
                    "status": "filled",
                })
                
                assert count >= 1
                mock_emit.assert_called()

    @pytest.mark.asyncio
    async def test_emit_system_status(self):
        """Test emitting system status."""
        from backend.realtime.emitters import emit_system_status
        
        with patch('backend.realtime.socketio_server.sio.emit', new_callable=AsyncMock) as mock_emit:
            with patch('backend.realtime.socketio_server.get_connected_clients') as mock_clients:
                mock_clients.return_value = {"session1"}
                
                count = await emit_system_status({
                    "status": "online",
                    "version": "1.0.0",
                })
                
                assert count >= 1
                mock_emit.assert_called()

    @pytest.mark.asyncio
    async def test_emit_error(self):
        """Test emitting error."""
        from backend.realtime.emitters import emit_error
        
        with patch('backend.realtime.socketio_server.sio.emit', new_callable=AsyncMock) as mock_emit:
            count = await emit_error({
                "error_code": "TEST_ERROR",
                "error_message": "Test error message",
            }, session_id="test_session")
            
            assert count == 1
            mock_emit.assert_called()


class TestModuleImports:
    """Tests for module imports and exports."""

    def test_realtime_module_imports(self):
        """Test that all expected exports are available from realtime module."""
        from backend.realtime import (
            sio,
            socket_app,
            get_socketio_server,
            register_event_handlers,
            emit_price_update,
            emit_signal_detected,
            emit_position_update,
            emit_metrics_update,
            emit_panic_alert,
            broadcast_to_all,
            emit_order_update,
            emit_system_status,
            emit_model_update,
            emit_error,
        )
        
        assert sio is not None
        assert socket_app is not None
        assert callable(get_socketio_server)
        assert callable(register_event_handlers)
        assert callable(emit_price_update)
        assert callable(emit_signal_detected)
        assert callable(emit_position_update)
        assert callable(emit_metrics_update)
        assert callable(emit_panic_alert)
        assert callable(broadcast_to_all)
        assert callable(emit_order_update)
        assert callable(emit_system_status)
        assert callable(emit_model_update)
        assert callable(emit_error)


class TestIntegration:
    """Integration tests for Socket.io communication."""

    @pytest.mark.asyncio
    async def test_full_event_flow(self):
        """Test a full event flow from subscription to emission."""
        from backend.realtime.socketio_server import (
            register_client,
            add_subscription,
            get_market_subscribers,
            unregister_client,
        )
        from backend.realtime.emitters import emit_price_update
        
        # Setup
        register_client("integration_session")
        add_subscription("integration_session", "integration_market")
        
        # Verify subscription
        subscribers = get_market_subscribers("integration_market")
        assert "integration_session" in subscribers
        
        # Emit event
        with patch('backend.realtime.socketio_server.sio.emit', new_callable=AsyncMock) as mock_emit:
            count = await emit_price_update(
                "integration_market",
                {"price": 0.75, "volume": 5000},
                broadcast=True
            )
            
            assert count == 1
        
        # Cleanup
        unregister_client("integration_session")
        
        # Verify cleanup
        subscribers = get_market_subscribers("integration_market")
        assert "integration_session" not in subscribers

    @pytest.mark.asyncio
    async def test_multiple_clients_same_market(self):
        """Test multiple clients subscribing to the same market."""
        from backend.realtime.socketio_server import (
            register_client,
            add_subscription,
            get_market_subscribers,
            unregister_client,
        )
        from backend.realtime.emitters import emit_price_update
        
        # Setup multiple clients
        for i in range(5):
            register_client(f"multi_client_{i}")
            add_subscription(f"multi_client_{i}", "shared_market")
        
        # Verify all subscriptions
        subscribers = get_market_subscribers("shared_market")
        assert len(subscribers) == 5
        
        # Emit to all
        with patch('backend.realtime.socketio_server.sio.emit', new_callable=AsyncMock) as mock_emit:
            count = await emit_price_update(
                "shared_market",
                {"price": 0.80},
                broadcast=True
            )
            
            assert count == 5
            assert mock_emit.call_count == 5
        
        # Cleanup
        for i in range(5):
            unregister_client(f"multi_client_{i}")

    @pytest.mark.asyncio
    async def test_client_multiple_markets(self):
        """Test a single client subscribing to multiple markets."""
        from backend.realtime.socketio_server import (
            register_client,
            add_subscription,
            get_market_subscribers,
            unregister_client,
        )
        
        # Setup
        register_client("multi_market_client")
        
        markets = ["market_a", "market_b", "market_c"]
        for market in markets:
            add_subscription("multi_market_client", market)
        
        # Verify subscriptions
        for market in markets:
            subscribers = get_market_subscribers(market)
            assert "multi_market_client" in subscribers
        
        # Cleanup
        unregister_client("multi_market_client")
        
        # Verify all cleaned up
        for market in markets:
            subscribers = get_market_subscribers(market)
            assert "multi_market_client" not in subscribers


# Run tests with: pytest tests/test_socketio.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
