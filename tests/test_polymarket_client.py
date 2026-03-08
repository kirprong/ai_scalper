"""
Tests for Polymarket API Client
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from aiohttp import ClientSession

from backend.api import PolymarketClient
from backend.signing import PolymarketSigner, SignedOrder, OrderSide


@pytest.fixture
def mock_signer():
    """Create mock PolymarketSigner"""
    signer = Mock(spec=PolymarketSigner)
    signer.address = "0x1234567890123456789012345678901234567890"
    
    signed_order = SignedOrder(
        salt=12345,
        maker=signer.address,
        signer=signer.address,
        taker="0x0000000000000000000000000000000000000000",
        tokenId="12345",
        makerAmount="1000000",
        takerAmount="500000",
        expiration=0,
        nonce=1,
        feeRateBps="100",
        side="BUY",
        signatureType=0,
        signature="0xabc123"
    )
    
    signer.sign_order.return_value = signed_order
    signer.to_dict.return_value = {
        "salt": 12345,
        "maker": signer.address,
        "signer": signer.address,
        "taker": "0x0000000000000000000000000000000000000000",
        "tokenId": "12345",
        "makerAmount": "1000000",
        "takerAmount": "500000",
        "expiration": 0,
        "nonce": 1,
        "feeRateBps": "100",
        "side": "BUY",
        "signatureType": 0,
        "signature": "0xabc123"
    }
    
    return signer


@pytest.fixture
def client(mock_signer):
    """Create PolymarketClient instance"""
    return PolymarketClient(
        signer=mock_signer,
        chain_id=137,
        timeout=10.0,
        max_retries=2,
        rate_limit_delay=0.01
    )


class TestPolymarketClient:
    """Test PolymarketClient class"""
    
    def test_init(self, mock_signer):
        """Test client initialization"""
        client = PolymarketClient(
            signer=mock_signer,
            chain_id=137,
            timeout=30.0,
            max_retries=3,
            rate_limit_delay=0.1
        )
        
        assert client.signer == mock_signer
        assert client.chain_id == 137
        assert client.timeout == 30.0
        assert client.max_retries == 3
        assert client.rate_limit_delay == 0.1
        assert client.base_url == "https://clob.polymarket.com"
    
    def test_init_testnet(self, mock_signer):
        """Test client initialization with testnet"""
        client = PolymarketClient(
            signer=mock_signer,
            chain_id=80002
        )
        
        assert client.chain_id == 80002
        assert client.base_url == "https://clob.polymarket.com"
    
    @pytest.mark.asyncio
    async def test_get_session(self, client):
        """Test session creation with Keep-Alive"""
        session = await client._get_session()
        
        assert isinstance(session, ClientSession)
        assert not session.closed
        assert session.connector is not None
        
        # Cleanup
        await client.close()
    
    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test session cleanup"""
        session = await client._get_session()
        await client.close()
        
        assert session.closed
    
    @pytest.mark.asyncio
    async def test_rate_limit(self, client):
        """Test rate limiting"""
        import time
        
        client.rate_limit_delay = 0.1
        
        start = time.time()
        await client._rate_limit()
        elapsed1 = time.time() - start
        
        start = time.time()
        await client._rate_limit()
        elapsed2 = time.time() - start
        
        # First call should be instant
        assert elapsed1 < 0.01
        
        # Second call should wait for rate_limit_delay
        assert elapsed2 >= client.rate_limit_delay * 0.9
    
    @pytest.mark.asyncio
    async def test_request_success(self, client):
        """Test successful API request"""
        mock_response = {"test": "data"}
        
        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session
            
            mock_response_obj = AsyncMock()
            mock_response_obj.status = 200
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.text = AsyncMock(return_value="OK")
            
            mock_session.request = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response_obj)))
            
            result = await client._request("GET", "/test")
            
            assert result == mock_response
    
    @pytest.mark.asyncio
    async def test_request_rate_limited(self, client):
        """Test rate limit handling"""
        mock_response = {"test": "data"}
        
        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session
            
            # First response: rate limited
            mock_response_429 = AsyncMock()
            mock_response_429.status = 429
            mock_response_429.headers = {"Retry-After": "0.1"}
            mock_response_429.text = AsyncMock(return_value="Rate limited")
            
            # Second response: success
            mock_response_200 = AsyncMock()
            mock_response_200.status = 200
            mock_response_200.json = AsyncMock(return_value=mock_response)
            mock_response_200.text = AsyncMock(return_value="OK")
            
            call_count = [0]
            
            async def mock_request(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_response_429
                return mock_response_200
            
            mock_session.request = MagicMock(return_value=AsyncMock(__aenter__=mock_request))
            
            result = await client._request("GET", "/test")
            
            assert result == mock_response
            assert call_count[0] == 2
    
    @pytest.mark.asyncio
    async def test_get_markets(self, client):
        """Test get_markets endpoint"""
        mock_data = [
            {
                "condition_id": "cond1",
                "question_id": "q1",
                "question": "Test question?",
                "description": "Test description",
                "outcomes": ["Yes", "No"],
                "tokens": [{"token_id": "123"}],
                "active": True
            }
        ]
        
        with patch.object(client, '_request', return_value=mock_data):
            markets = await client.get_markets()
            
            assert len(markets) == 1
            assert markets[0].condition_id == "cond1"
            assert markets[0].question == "Test question?"
            assert markets[0].active is True
    
    @pytest.mark.asyncio
    async def test_get_markets_active_only(self, client):
        """Test get_markets with active_only filter"""
        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = []
            
            await client.get_markets(active_only=True)
            
            # Check that params were passed
            call_args = mock_request.call_args
            assert call_args[0][0] == "GET"
            assert call_args[0][1] == "/markets"
            assert call_args[1].get("params") == {"active": "true"}
    
    @pytest.mark.asyncio
    async def test_get_market(self, client):
        """Test get_market endpoint"""
        mock_data = {
            "condition_id": "cond1",
            "question_id": "q1",
            "question": "Test question?",
            "description": "Test description",
            "outcomes": ["Yes", "No"],
            "tokens": [{"token_id": "123"}],
            "active": True
        }
        
        with patch.object(client, '_request', return_value=mock_data):
            market = await client.get_market("cond1")
            
            assert market.condition_id == "cond1"
            assert market.question == "Test question?"
    
    @pytest.mark.asyncio
    async def test_post_order(self, client, mock_signer):
        """Test post_order endpoint"""
        mock_response = {"order_id": "order123"}
        
        signed_order = mock_signer.sign_order.return_value
        
        with patch.object(client, '_request', return_value=mock_response):
            result = await client.post_order(signed_order)
            
            assert result["order_id"] == "order123"
            mock_signer.to_dict.assert_called_once_with(signed_order)
    
    @pytest.mark.asyncio
    async def test_get_orders(self, client, mock_signer):
        """Test get_orders endpoint"""
        mock_response = [
            {"order_id": "order1", "maker": mock_signer.address}
        ]
        
        with patch.object(client, '_request', return_value=mock_response):
            orders = await client.get_orders()
            
            assert len(orders) == 1
            assert orders[0]["order_id"] == "order1"
    
    @pytest.mark.asyncio
    async def test_get_order(self, client):
        """Test get_order endpoint"""
        mock_response = {"order_id": "order123", "status": "LIVE"}
        
        with patch.object(client, '_request', return_value=mock_response):
            order = await client.get_order("order123")
            
            assert order["order_id"] == "order123"
            assert order["status"] == "LIVE"
    
    @pytest.mark.asyncio
    async def test_delete_order(self, client):
        """Test delete_order endpoint"""
        mock_response = {"status": "cancelled"}
        
        with patch.object(client, '_request', return_value=mock_response):
            result = await client.delete_order("order123")
            
            assert result["status"] == "cancelled"
    
    @pytest.mark.asyncio
    async def test_cancel_all_orders(self, client, mock_signer):
        """Test cancel_all_orders endpoint"""
        mock_response = {"cancelled": 5}
        
        with patch.object(client, '_request', return_value=mock_response):
            result = await client.cancel_all_orders()
            
            assert result["cancelled"] == 5
    
    @pytest.mark.asyncio
    async def test_get_order_book(self, client):
        """Test get_order_book endpoint"""
        mock_response = {
            "market": "market1",
            "asset_id": "asset1",
            "bids": [{"price": "0.5", "size": "100"}],
            "asks": [{"price": "0.6", "size": "100"}]
        }
        
        with patch.object(client, '_request', return_value=mock_response):
            order_book = await client.get_order_book("token123")
            
            assert order_book.market == "market1"
            assert len(order_book.bids) == 1
            assert len(order_book.asks) == 1
    
    @pytest.mark.asyncio
    async def test_create_and_submit_order(self, client, mock_signer):
        """Test create_and_submit_order helper"""
        mock_response = {"order_id": "order123"}
        
        with patch.object(client, 'post_order', return_value=mock_response):
            result = await client.create_and_submit_order(
                token_id="token123",
                side=OrderSide.BUY,
                maker_amount="1000000",
                taker_amount="500000",
                nonce=1
            )
            
            assert result["order_id"] == "order123"
            mock_signer.sign_order.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_context_manager(self, mock_signer):
        """Test async context manager"""
        async with PolymarketClient(signer=mock_signer) as client:
            session = await client._get_session()
            assert not session.closed
        
        # Session should be closed after exiting context
        assert session.closed


class TestPolymarketClientIntegration:
    """Integration tests (require network access)"""
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires network access to Polymarket API")
    async def test_real_get_markets(self):
        """Test real API call to get markets"""
        # This test requires a real private key and network access
        # Skip in CI/CD
        from backend.vault import Vault
        from backend.signing import PolymarketSigner
        
        # Load private key from vault
        vault = Vault()
        private_key = vault.get("POLYMARKET_PRIVATE_KEY")
        
        signer = PolymarketSigner(private_key=private_key)
        
        async with PolymarketClient(signer=signer) as client:
            markets = await client.get_markets(active_only=True)
            
            assert isinstance(markets, list)
            assert len(markets) > 0
            
            # Verify market structure
            market = markets[0]
            assert market.condition_id is not None
            assert market.question is not None
            assert market.active is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
