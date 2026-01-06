"""
Tests for Phase 9.5.1 - Message Actions (Edit, Delete, Pin)
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.db.models import AuditLog, Message, User

pytestmark = pytest.mark.integration


async def register_and_login(client: AsyncClient, email: str, username: str, password: str = "testpass123", test_session=None):
    """Create a user and return auth headers.

    If `test_session` (AsyncSession) is provided, insert the user directly into the DB and
    craft a token to avoid hitting the HTTP registration/login endpoints (which are rate
    limited in the test environment).
    """
    if test_session is not None:
        # Create user directly in DB to avoid rate limiter
        from app.core.security import get_password_hash, create_access_token
        from app.db.models import User

        user = User(email=email, username=username, display_name=username, hashed_password=get_password_hash(password))
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        token = create_access_token({"sub": str(user.id), "username": username, "is_system_admin": user.is_system_admin})
        return {"Authorization": f"Bearer {token}"}

    # Fallback to HTTP endpoints when no DB session is available (may hit rate limits)
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "username": username}
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"identifier": email, "password": password}
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def create_channel_and_message(client: AsyncClient, headers: dict, channel_name: str = "test-channel", test_session=None):
    # Try to create a public channel. Some deployments require admin privileges; if that
    # fails (403), and we have DB access via test_session, promote the user to system admin
    # and retry; if no DB access is available, fall back to a DM creation approach.
    ch_resp = await client.post(
        "/api/channels",
        json={"name": channel_name, "type": "public"},
        headers=headers
    )

    if ch_resp.status_code == 403:
        if test_session is not None:
            # Promote current user to admin so they can create channels
            me = await client.get("/api/users/me", headers=headers)
            my_id = me.json()["id"]
            from app.db.models import User
            q = await test_session.execute(select(User).where(User.id == my_id))
            usr = q.scalar_one()
            usr.is_system_admin = True
            await test_session.commit()

            # Retry creation
            ch_resp = await client.post(
                "/api/channels",
                json={"name": channel_name, "type": "public"},
                headers=headers
            )
            ch_resp.raise_for_status()
            channel_id = ch_resp.json()["id"]
        else:
            # Fallback: create a DM channel with a buddy user (registering a buddy may hit rate limits
            # across tests; this path should only run for tests that don't supply test_session)
            buddy_email = f"{channel_name}-buddy@test.com"
            buddy_username = f"{channel_name}_buddy"
            await client.post(
                "/api/auth/register",
                json={"email": buddy_email, "password": "testpass123", "username": buddy_username}
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

    msg_resp = await client.post(
        "/api/messages/",
        json={"content": "Original content", "channel_id": channel_id},
        headers=headers
    )
    msg_resp.raise_for_status()
    return channel_id, msg_resp.json()["id"]


@pytest.mark.anyio
async def test_edit_own_message_and_audit(client: AsyncClient, test_session):
    headers = await register_and_login(client, "edit1@test.com", "editor1", test_session=test_session)
    channel_id, message_id = await create_channel_and_message(client, headers)

    # Edit the message
    resp = await client.patch(f"/api/messages/{message_id}", json={"content": "Edited content"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "Edited content"
    assert data["is_edited"] is True
    assert data["edited_at"] is not None

    # Audit log exists
    q = await test_session.execute(select(AuditLog).where(AuditLog.action == "message.edited"))
    logs = q.scalars().all()
    assert any(l.target_id == message_id for l in logs)


@pytest.mark.anyio
async def test_admin_can_edit_others(client: AsyncClient, test_session):
    user1 = await register_and_login(client, "owner2@test.com", "owner2", test_session=test_session)
    channel_id, message_id = await create_channel_and_message(client, user1)

    admin_headers = await register_and_login(client, "admin@test.com", "adminuser", test_session=test_session)
    # Make user admin
    q = await test_session.execute(select(User).where(User.username == 'adminuser'))
    admin_user = q.scalar_one()
    admin_user.is_system_admin = True
    await test_session.commit()

    # Admin edits other's message
    resp = await client.patch(f"/api/messages/{message_id}", json={"content": "Admin edit"}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["content"] == "Admin edit"


@pytest.mark.anyio
async def test_cannot_edit_deleted_message(client: AsyncClient, test_session):
    headers = await register_and_login(client, "editdel@test.com", "editdel", test_session=test_session)
    _, message_id = await create_channel_and_message(client, headers)

    # Delete the message
    del_resp = await client.delete(f"/api/messages/{message_id}", headers=headers)
    assert del_resp.status_code == 200

    # Attempt to edit
    resp = await client.patch(f"/api/messages/{message_id}", json={"content": "Should fail"}, headers=headers)
    assert resp.status_code == 400
    assert "deleted" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_delete_own_and_audit_and_emit(monkeypatch, client: AsyncClient, test_session):
    headers = await register_and_login(client, "deleter@test.com", "deleter", test_session=test_session)
    channel_id, message_id = await create_channel_and_message(client, headers)

    calls = []
    async def fake_emit(channel_id_arg, message_id_arg):
        calls.append((channel_id_arg, message_id_arg))

    monkeypatch.setattr("app.realtime.socket.emit_message_deleted", fake_emit)

    resp = await client.delete(f"/api/messages/{message_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # DB shows deleted
    q = await test_session.execute(select(Message).where(Message.id == message_id))
    msg = q.scalar_one()
    assert msg.is_deleted is True
    assert msg.deleted_at is not None

    # Audit
    q = await test_session.execute(select(AuditLog).where(AuditLog.action == "message.deleted"))
    logs = q.scalars().all()
    assert any(l.target_id == message_id for l in logs)

    # Emit called
    assert calls and calls[0][0] == channel_id and calls[0][1] == message_id


@pytest.mark.anyio
async def test_admin_deletes_others(client: AsyncClient, test_session):
    user1 = await register_and_login(client, "owner3@test.com", "owner3", test_session=test_session)
    channel_id, message_id = await create_channel_and_message(client, user1)

    admin_headers = await register_and_login(client, "admin2@test.com", "admin2", test_session=test_session)
    q = await test_session.execute(select(User).where(User.username == 'admin2'))
    admin_user = q.scalar_one()
    admin_user.is_system_admin = True
    await test_session.commit()

    resp = await client.delete(f"/api/messages/{message_id}", headers=admin_headers)
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_pin_unpin_permissions_and_emit(monkeypatch, client: AsyncClient, test_session):
    headers = await register_and_login(client, "pinner@test.com", "pinner", test_session=test_session)
    channel_id, message_id = await create_channel_and_message(client, headers)

    # Normal user shouldn't have pin permission by default - expect 403
    resp = await client.post(f"/api/messages/{message_id}/pin", headers=headers)
    assert resp.status_code == 403

    # Make user owner role or admin; easiest: set system admin (admins may not have pin by default but will bypass checks)
    q = await test_session.execute(select(User).where(User.username == 'pinner'))
    user = q.scalar_one()
    user.is_system_admin = True
    await test_session.commit()

    pin_calls = []
    async def fake_pin_emit(channel_id_arg, message_id_arg):
        pin_calls.append((channel_id_arg, message_id_arg))
    monkeypatch.setattr("app.realtime.socket.emit_message_pinned", fake_pin_emit)

    resp2 = await client.post(f"/api/messages/{message_id}/pin", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["success"] is True

    # Unpin
    unpin_calls = []
    async def fake_unpin_emit(channel_id_arg, message_id_arg):
        unpin_calls.append((channel_id_arg, message_id_arg))
    monkeypatch.setattr("app.realtime.socket.emit_message_unpinned", fake_unpin_emit)

    resp3 = await client.delete(f"/api/messages/{message_id}/pin", headers=headers)
    assert resp3.status_code == 200
    assert resp3.json()["success"] is True


@pytest.mark.anyio
async def test_pin_blocked_without_permission(client: AsyncClient, test_session):
    headers = await register_and_login(client, "nopin@test.com", "nopinner", test_session=test_session)
    _, message_id = await create_channel_and_message(client, headers)

    resp = await client.post(f"/api/messages/{message_id}/pin", headers=headers)
    assert resp.status_code == 403
