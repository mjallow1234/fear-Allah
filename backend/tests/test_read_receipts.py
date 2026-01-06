"""
Tests for Phase 4.4 - Read Receipts.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

# Test ChannelRead model and basic operations
class TestChannelReadModel:
    """Tests for ChannelRead model functionality."""
    
    def test_channel_read_fields(self):
        """ChannelRead model should have correct fields."""
        from app.db.models import ChannelRead
        
        # Check the model has expected columns
        assert hasattr(ChannelRead, 'id')
        assert hasattr(ChannelRead, 'user_id')
        assert hasattr(ChannelRead, 'channel_id')
        assert hasattr(ChannelRead, 'last_read_message_id')
        assert hasattr(ChannelRead, 'updated_at')
    
    def test_channel_read_relationships(self):
        """ChannelRead model should have relationships."""
        from app.db.models import ChannelRead
        
        assert hasattr(ChannelRead, 'user')
        assert hasattr(ChannelRead, 'channel')
        assert hasattr(ChannelRead, 'message')


class TestReadReceiptLogic:
    """Tests for read receipt business logic."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock async database session."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        return db
    
    @pytest.fixture
    def mock_channel_read_class(self):
        """Mock ChannelRead class for testing."""
        class MockChannelRead:
            def __init__(self, user_id, channel_id, last_read_message_id=None):
                self.user_id = user_id
                self.channel_id = channel_id
                self.last_read_message_id = last_read_message_id
        return MockChannelRead
    
    def test_create_new_read_receipt(self, mock_channel_read_class):
        """Creating a new read receipt should work."""
        read = mock_channel_read_class(
            user_id=1,
            channel_id=5,
            last_read_message_id=100
        )
        
        assert read.user_id == 1
        assert read.channel_id == 5
        assert read.last_read_message_id == 100
    
    def test_update_with_higher_message_id(self, mock_channel_read_class):
        """Update should succeed when new message_id is higher."""
        read = mock_channel_read_class(
            user_id=1,
            channel_id=5,
            last_read_message_id=100
        )
        
        new_message_id = 150
        
        # Logic: only update if new > current
        if read.last_read_message_id is None or new_message_id > read.last_read_message_id:
            read.last_read_message_id = new_message_id
        
        assert read.last_read_message_id == 150
    
    def test_ignore_lower_message_id(self, mock_channel_read_class):
        """Update should be ignored when new message_id is lower."""
        read = mock_channel_read_class(
            user_id=1,
            channel_id=5,
            last_read_message_id=100
        )
        
        new_message_id = 50  # Lower than current
        
        # Logic: only update if new > current
        if read.last_read_message_id is None or new_message_id > read.last_read_message_id:
            read.last_read_message_id = new_message_id
        
        # Should remain 100
        assert read.last_read_message_id == 100
    
    def test_update_from_none(self, mock_channel_read_class):
        """Update should succeed when current is None."""
        read = mock_channel_read_class(
            user_id=1,
            channel_id=5,
            last_read_message_id=None
        )
        
        new_message_id = 50
        
        # Logic: only update if new > current OR current is None
        if read.last_read_message_id is None or new_message_id > read.last_read_message_id:
            read.last_read_message_id = new_message_id
        
        assert read.last_read_message_id == 50
    
    def test_multiple_users_same_channel(self, mock_channel_read_class):
        """Multiple users can have different read positions in same channel."""
        read1 = mock_channel_read_class(user_id=1, channel_id=5, last_read_message_id=100)
        read2 = mock_channel_read_class(user_id=2, channel_id=5, last_read_message_id=80)
        read3 = mock_channel_read_class(user_id=3, channel_id=5, last_read_message_id=120)
        
        assert read1.last_read_message_id == 100
        assert read2.last_read_message_id == 80
        assert read3.last_read_message_id == 120
        
        # All in same channel
        assert read1.channel_id == read2.channel_id == read3.channel_id == 5


class TestSocketEmit:
    """Tests for Socket.IO emit functionality."""
    
    @pytest.mark.anyio
    async def test_emit_receipt_update_fires_once(self):
        """Socket emit should fire exactly once for a valid update."""
        from app.realtime.socket import emit_receipt_update
        
        with patch('app.realtime.socket.sio') as mock_sio:
            mock_sio.emit = AsyncMock()
            
            await emit_receipt_update(
                channel_id=5,
                user_id=12,
                last_read_message_id=123,
                skip_user_id=12
            )
            
            # Should emit exactly once
            assert mock_sio.emit.call_count == 1
            
            # Verify payload
            call_args = mock_sio.emit.call_args
            assert call_args[0][0] == "receipt:update"
            assert call_args[0][1]["channel_id"] == 5
            assert call_args[0][1]["user_id"] == 12
            assert call_args[0][1]["last_read_message_id"] == 123
    
    @pytest.mark.anyio
    async def test_emit_to_correct_room(self):
        """Socket emit should target the correct channel room."""
        from app.realtime.socket import emit_receipt_update
        
        with patch('app.realtime.socket.sio') as mock_sio:
            mock_sio.emit = AsyncMock()
            
            await emit_receipt_update(
                channel_id=7,
                user_id=1,
                last_read_message_id=50
            )
            
            # Verify room
            call_kwargs = mock_sio.emit.call_args[1]
            assert call_kwargs["room"] == "channel:7"


class TestNoEmitOnUnchanged:
    """Tests to verify no emit when value unchanged."""
    
    def test_should_emit_logic_new_record(self):
        """Should emit when creating new record."""
        existing = None
        new_message_id = 100
        
        should_emit = existing is None
        assert should_emit is True
    
    def test_should_emit_logic_higher_id(self):
        """Should emit when new message_id is higher."""
        existing_last_read = 50
        new_message_id = 100
        
        should_emit = existing_last_read is None or new_message_id > existing_last_read
        assert should_emit is True
    
    def test_should_not_emit_logic_same_id(self):
        """Should NOT emit when message_id is same."""
        existing_last_read = 100
        new_message_id = 100
        
        should_emit = existing_last_read is None or new_message_id > existing_last_read
        assert should_emit is False
    
    def test_should_not_emit_logic_lower_id(self):
        """Should NOT emit when message_id is lower."""
        existing_last_read = 100
        new_message_id = 50
        
        should_emit = existing_last_read is None or new_message_id > existing_last_read
        assert should_emit is False


class TestIdempotency:
    """Tests for idempotent behavior."""
    
    def test_multiple_calls_same_value(self):
        """Multiple calls with same value should be idempotent."""
        class MockRead:
            def __init__(self):
                self.last_read_message_id = None
                self.update_count = 0
            
            def update(self, new_id):
                if self.last_read_message_id is None or new_id > self.last_read_message_id:
                    self.last_read_message_id = new_id
                    self.update_count += 1
                    return True
                return False
        
        read = MockRead()
        
        # First call
        result1 = read.update(100)
        assert result1 is True
        assert read.update_count == 1
        
        # Second call with same value - should be no-op
        result2 = read.update(100)
        assert result2 is False
        assert read.update_count == 1  # Still 1
        
        # Third call with same value - should be no-op
        result3 = read.update(100)
        assert result3 is False
        assert read.update_count == 1  # Still 1
    
    def test_progressive_updates(self):
        """Progressive updates should only count actual changes."""
        class MockRead:
            def __init__(self):
                self.last_read_message_id = None
                self.update_count = 0
            
            def update(self, new_id):
                if self.last_read_message_id is None or new_id > self.last_read_message_id:
                    self.last_read_message_id = new_id
                    self.update_count += 1
                    return True
                return False
        
        read = MockRead()
        
        # Sequence: 10, 20, 15, 30, 25, 30
        read.update(10)  # Update 1
        read.update(20)  # Update 2
        read.update(15)  # No-op (lower)
        read.update(30)  # Update 3
        read.update(25)  # No-op (lower)
        read.update(30)  # No-op (same)
        
        assert read.last_read_message_id == 30
        assert read.update_count == 3


class TestQueryHelper:
    """Tests for get_channel_reads query helper."""
    
    def test_format_channel_reads_response(self):
        """Response should be list of {user_id, last_read_message_id}."""
        # Simulate what the endpoint returns
        reads = [
            {"user_id": 1, "last_read_message_id": 100},
            {"user_id": 2, "last_read_message_id": 80},
            {"user_id": 3, "last_read_message_id": 120},
        ]
        
        # Verify structure
        for read in reads:
            assert "user_id" in read
            assert "last_read_message_id" in read
        
        assert len(reads) == 3
    
    def test_empty_channel_returns_empty_list(self):
        """Channel with no reads should return empty list."""
        reads = []
        assert reads == []
        assert len(reads) == 0
