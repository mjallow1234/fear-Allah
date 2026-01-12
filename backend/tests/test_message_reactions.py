"""
Tests for Phase 9.3 - Emoji Reactions (Backend)

Covers:
- Add reaction
- Toggle remove (re-add removes)
- Duplicate prevention (via toggle)
- Two users reacting same emoji
- Reaction removed when message deleted
- Unauthorized user blocked (not channel member)
- Validation (empty emoji, long emoji)
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


# ============================================================
# Helper functions
# ============================================================

async def register_and_login(client: AsyncClient, email: str, username: str, password: str = "testpass123"):
    """Register a user and return auth headers."""
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "username": username, "operational_role": "agent"}
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"identifier": email, "password": password}
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def create_channel_and_message(client: AsyncClient, headers: dict, channel_name: str = "test-channel"):
    """Create a channel and post a message, return (channel_id, message_id).

    Some deployments require admin privileges to create public channels in tests
    (the API may return 403). In that case, fall back to creating a DM with a
    freshly-registered buddy user so the calling user can still post a message.
    """
    # Try to create a public channel
    ch_resp = await client.post(
        "/api/channels",
        json={"name": channel_name, "type": "public"},
        headers=headers
    )

    if ch_resp.status_code == 403:
        # Create a buddy user and then create a DM channel between the two users
        buddy_email = f"{channel_name}-buddy@test.com"
        buddy_username = f"{channel_name}_buddy"
        await client.post(
            "/api/auth/register",
            json={"email": buddy_email, "password": "testpass123", "username": buddy_username, "operational_role": "agent"}
        )
        # Fetch buddy id
        user_resp = await client.get(f"/api/users/by-username/{buddy_username}", headers=headers)
        user_resp.raise_for_status()
        buddy = user_resp.json()
        buddy_id = buddy["id"]
        dm_resp = await client.post("/api/channels/direct", json={"user_id": buddy_id}, headers=headers)
        dm_resp.raise_for_status()
        channel_id = dm_resp.json()["id"]
    else:
        ch_resp.raise_for_status()
        channel_id = ch_resp.json()["id"]

    # Post a message
    msg_resp = await client.post(
        "/api/messages/",
        json={"content": "Test message for reactions", "channel_id": channel_id},
        headers=headers
    )
    msg_resp.raise_for_status()
    message_id = msg_resp.json()["id"]

    return channel_id, message_id


# ============================================================
# Test: Add Reaction
# ============================================================

@pytest.mark.anyio
async def test_add_reaction(client: AsyncClient):
    """Test adding a reaction to a message."""
    headers = await register_and_login(client, "react1@test.com", "reactor1")
    channel_id, message_id = await create_channel_and_message(client, headers)
    
    # Add reaction
    response = await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": "👍"},
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "added"
    assert data["emoji"] == "👍"
    assert data["message_id"] == message_id
    
    # Verify reaction is in the list
    assert len(data["reactions"]) == 1
    assert data["reactions"][0]["emoji"] == "👍"
    assert data["reactions"][0]["count"] == 1


# ============================================================
# Test: Toggle Remove (Re-POST removes)
# ============================================================

@pytest.mark.anyio
async def test_toggle_reaction_removes(client: AsyncClient):
    """Test that posting the same reaction again removes it (toggle behavior)."""
    headers = await register_and_login(client, "toggle@test.com", "toggler")
    channel_id, message_id = await create_channel_and_message(client, headers)
    
    # Add reaction
    resp1 = await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": "❤️"},
        headers=headers
    )
    assert resp1.json()["action"] == "added"
    
    # Toggle (remove) by posting again
    resp2 = await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": "❤️"},
        headers=headers
    )
    assert resp2.status_code == 200
    assert resp2.json()["action"] == "removed"
    assert resp2.json()["reactions"] == []  # No reactions left


# ============================================================
# Test: No Duplicates (toggle ensures this)
# ============================================================

@pytest.mark.anyio
async def test_no_duplicate_reactions(client: AsyncClient):
    """Test that a user cannot have duplicate reactions (toggle handles this)."""
    headers = await register_and_login(client, "nodup@test.com", "noduper")
    channel_id, message_id = await create_channel_and_message(client, headers)
    
    # Add reaction
    await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": "😂"},
        headers=headers
    )
    
    # Get reactions - should have count 1
    get_resp = await client.get(
        f"/api/messages/{message_id}/reactions",
        headers=headers
    )
    reactions = get_resp.json()
    assert len(reactions) == 1
    assert reactions[0]["count"] == 1


# ============================================================
# Test: Two Users Same Emoji
# ============================================================

@pytest.mark.anyio
async def test_two_users_same_emoji(client: AsyncClient):
    """Test that two different users can react with the same emoji."""
    # User 1 creates channel and message
    headers1 = await register_and_login(client, "user1@test.com", "user1")
    channel_id, message_id = await create_channel_and_message(client, headers1)
    
    # User 1 adds reaction
    await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": "🎉"},
        headers=headers1
    )
    
    # User 2 registers and joins channel
    headers2 = await register_and_login(client, "user2@test.com", "user2")
    await client.post(
        f"/api/channels/{channel_id}/join",
        headers=headers2
    )
    
    # User 2 adds same emoji
    resp = await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": "🎉"},
        headers=headers2
    )
    
    assert resp.status_code == 200
    assert resp.json()["action"] == "added"
    
    # Verify count is now 2
    reactions = resp.json()["reactions"]
    party_reaction = next((r for r in reactions if r["emoji"] == "🎉"), None)
    assert party_reaction is not None
    assert party_reaction["count"] == 2
    assert len(party_reaction["users"]) == 2


# ============================================================
# Test: Reaction Removed When Message Deleted
# ============================================================

@pytest.mark.anyio
async def test_reaction_cascade_on_message_delete(client: AsyncClient):
    """Test that reactions are removed when the message is deleted."""
    headers = await register_and_login(client, "cascade@test.com", "cascader")
    channel_id, message_id = await create_channel_and_message(client, headers)
    
    # Add reaction
    await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": "👀"},
        headers=headers
    )
    
    # Delete the message
    del_resp = await client.delete(
        f"/api/messages/{message_id}",
        headers=headers
    )
    assert del_resp.status_code == 200
    
    # Try to get reactions on deleted message - should fail
    get_resp = await client.get(
        f"/api/messages/{message_id}/reactions",
        headers=headers
    )
    # Should return 404 since message is deleted
    assert get_resp.status_code == 404


# ============================================================
# Test: Cannot React to Deleted Message
# ============================================================

@pytest.mark.anyio
async def test_cannot_react_to_deleted_message(client: AsyncClient):
    """Test that users cannot react to a deleted message."""
    headers = await register_and_login(client, "nodelete@test.com", "nodeleter")
    channel_id, message_id = await create_channel_and_message(client, headers)
    
    # Delete the message
    await client.delete(f"/api/messages/{message_id}", headers=headers)
    
    # Try to add reaction
    resp = await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": "💀"},
        headers=headers
    )
    assert resp.status_code == 403
    assert "deleted" in resp.json()["detail"].lower()


# ============================================================
# Test: Unauthorized User (Not Channel Member)
# ============================================================

@pytest.mark.anyio
async def test_non_member_cannot_react(client: AsyncClient):
    """Test that a user who is not a channel member cannot react."""
    # User 1 creates channel and message
    headers1 = await register_and_login(client, "owner@test.com", "owner")
    channel_id, message_id = await create_channel_and_message(client, headers1, "private-channel")
    
    # User 2 registers but does NOT join the channel
    headers2 = await register_and_login(client, "outsider@test.com", "outsider")
    
    # User 2 tries to react
    resp = await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": "🚫"},
        headers=headers2
    )
    
    assert resp.status_code == 403
    assert "member" in resp.json()["detail"].lower()


# ============================================================
# Test: Empty Emoji Validation
# ============================================================

@pytest.mark.anyio
async def test_empty_emoji_rejected(client: AsyncClient):
    """Test that empty emoji is rejected."""
    headers = await register_and_login(client, "empty@test.com", "emptier")
    channel_id, message_id = await create_channel_and_message(client, headers)
    
    resp = await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": ""},
        headers=headers
    )
    
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_whitespace_emoji_rejected(client: AsyncClient):
    """Test that whitespace-only emoji is rejected."""
    headers = await register_and_login(client, "space@test.com", "spacer")
    channel_id, message_id = await create_channel_and_message(client, headers)
    
    resp = await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": "   "},
        headers=headers
    )
    
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


# ============================================================
# Test: Long Emoji Validation
# ============================================================

@pytest.mark.anyio
async def test_long_emoji_rejected(client: AsyncClient):
    """Test that emoji longer than 32 chars is rejected."""
    headers = await register_and_login(client, "long@test.com", "longer")
    channel_id, message_id = await create_channel_and_message(client, headers)
    
    # Create a string longer than 32 characters
    long_emoji = "🎉" * 20  # Each emoji is multiple bytes but still >32 chars
    
    resp = await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": long_emoji},
        headers=headers
    )
    
    assert resp.status_code == 400
    assert "32" in resp.json()["detail"]


# ============================================================
# Test: Get Reactions Endpoint
# ============================================================

@pytest.mark.anyio
async def test_get_reactions(client: AsyncClient):
    """Test getting reactions for a message."""
    headers = await register_and_login(client, "getter@test.com", "getter")
    channel_id, message_id = await create_channel_and_message(client, headers)
    
    # Add multiple reactions
    await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": "👍"},
        headers=headers
    )
    await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": "❤️"},
        headers=headers
    )
    
    # Get reactions
    resp = await client.get(
        f"/api/messages/{message_id}/reactions",
        headers=headers
    )
    
    assert resp.status_code == 200
    reactions = resp.json()
    assert len(reactions) == 2
    
    # Verify structure
    emojis = {r["emoji"] for r in reactions}
    assert "👍" in emojis
    assert "❤️" in emojis


# ============================================================
# Test: Delete Endpoint
# ============================================================

@pytest.mark.anyio
async def test_delete_reaction_endpoint(client: AsyncClient):
    """Test the DELETE endpoint for removing reactions."""
    headers = await register_and_login(client, "deleter@test.com", "deleter")
    channel_id, message_id = await create_channel_and_message(client, headers)
    
    # Add reaction
    await client.post(
        f"/api/messages/{message_id}/reactions",
        json={"emoji": "🔥"},
        headers=headers
    )
    
    # Delete via DELETE endpoint
    resp = await client.delete(
        f"/api/messages/{message_id}/reactions/🔥",
        headers=headers
    )
    
    assert resp.status_code == 200
    assert resp.json()["emoji"] == "🔥"
    
    # Verify it's gone
    get_resp = await client.get(
        f"/api/messages/{message_id}/reactions",
        headers=headers
    )
    assert get_resp.json() == []


# ============================================================
# Test: Nonexistent Message
# ============================================================

@pytest.mark.anyio
async def test_react_to_nonexistent_message(client: AsyncClient):
    """Test reacting to a message that doesn't exist."""
    headers = await register_and_login(client, "ghost@test.com", "ghost")
    
    resp = await client.post(
        "/api/messages/999999/reactions",
        json={"emoji": "👻"},
        headers=headers
    )
    
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
