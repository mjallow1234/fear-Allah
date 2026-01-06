import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Channel, ChannelMember, Message, FileAttachment
from app.core.security import create_access_token, get_password_hash

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_channel_member_can_download(client: AsyncClient, test_session: AsyncSession):
    # Create users: uploader and member
    uploader = User(email="uploader@test.com", username="uploader", hashed_password=get_password_hash("pass"), is_active=True)
    member = User(email="member@test.com", username="member", hashed_password=get_password_hash("pass"), is_active=True)
    test_session.add_all([uploader, member])
    await test_session.commit()
    await test_session.refresh(uploader)
    await test_session.refresh(member)

    # Create private channel and add both users
    channel = Channel(name="private-chan", display_name="Private", type="private")
    test_session.add(channel)
    await test_session.commit()
    await test_session.refresh(channel)

    membership1 = ChannelMember(user_id=uploader.id, channel_id=channel.id)
    membership2 = ChannelMember(user_id=member.id, channel_id=channel.id)
    test_session.add_all([membership1, membership2])
    await test_session.commit()

    # Create a message and an attachment record directly (avoid file-upload path in tests)
    message = Message(content="", channel_id=channel.id, author_id=uploader.id)
    test_session.add(message)
    await test_session.commit()
    await test_session.refresh(message)

    # Write file to storage path
    from app.storage.local import get_full_path
    storage_path = f"channel_{channel.id}/20250101/test.txt"
    full_path = get_full_path(storage_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(b"hello world")

    attachment = FileAttachment(message_id=message.id, channel_id=channel.id, user_id=uploader.id, filename="test.txt", file_path=storage_path, storage_path=storage_path, file_size=11, mime_type="text/plain")
    test_session.add(attachment)
    await test_session.commit()
    await test_session.refresh(attachment)

    attachment_id = attachment.id

    # Member should be able to download
    member_token = create_access_token({"sub": str(member.id), "username": member.username})
    dl = await client.get(f"/api/attachments/download/{attachment_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert dl.status_code == 200
    assert dl.content == b"hello world"

    # Cleanup file
    full_path.unlink()


@pytest.mark.anyio
async def test_non_member_gets_403(client: AsyncClient, test_session: AsyncSession):
    # Create users: uploader and outsider
    uploader = User(email="u2@test.com", username="u2", hashed_password=get_password_hash("pass"), is_active=True)
    outsider = User(email="out@example.com", username="outsider", hashed_password=get_password_hash("pass"), is_active=True)
    test_session.add_all([uploader, outsider])
    await test_session.commit()
    await test_session.refresh(uploader)
    await test_session.refresh(outsider)

    # Create private channel and add only uploader
    channel = Channel(name="private-chan-2", display_name="Private2", type="private")
    test_session.add(channel)
    await test_session.commit()
    await test_session.refresh(channel)

    membership = ChannelMember(user_id=uploader.id, channel_id=channel.id)
    test_session.add(membership)
    await test_session.commit()

    # Create message and write file to storage
    message = Message(content="", channel_id=channel.id, author_id=uploader.id)
    test_session.add(message)
    await test_session.commit()
    await test_session.refresh(message)

    from app.storage.local import get_full_path
    storage_path = f"channel_{channel.id}/20250101/secret.txt"
    full_path = get_full_path(storage_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(b"topsecret")

    attachment = FileAttachment(message_id=message.id, channel_id=channel.id, user_id=uploader.id, filename="secret.txt", file_path=storage_path, storage_path=storage_path, file_size=9, mime_type="text/plain")
    test_session.add(attachment)
    await test_session.commit()
    await test_session.refresh(attachment)

    attachment_id = attachment.id

    # Outsider should get 403
    outsider_token = create_access_token({"sub": str(outsider.id), "username": outsider.username})
    dl = await client.get(f"/api/attachments/download/{attachment_id}", headers={"Authorization": f"Bearer {outsider_token}"})
    assert dl.status_code == 403

    # Cleanup file
    full_path.unlink()


@pytest.mark.anyio
async def test_unauthenticated_gets_401_or_403(client: AsyncClient, test_session: AsyncSession):
    # Create user and channel and upload file
    uploader = User(email="u3@test.com", username="u3", hashed_password=get_password_hash("pass"), is_active=True)
    test_session.add(uploader)
    await test_session.commit()
    await test_session.refresh(uploader)

    channel = Channel(name="private-chan-3", display_name="Private3", type="private")
    test_session.add(channel)
    await test_session.commit()
    await test_session.refresh(channel)

    membership = ChannelMember(user_id=uploader.id, channel_id=channel.id)
    test_session.add(membership)
    await test_session.commit()

    # Create message and write file to storage
    message = Message(content="", channel_id=channel.id, author_id=uploader.id)
    test_session.add(message)
    await test_session.commit()
    await test_session.refresh(message)

    from app.storage.local import get_full_path
    storage_path = f"channel_{channel.id}/20250101/hello.txt"
    full_path = get_full_path(storage_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(b"hi")

    attachment = FileAttachment(message_id=message.id, channel_id=channel.id, user_id=uploader.id, filename="hello.txt", file_path=storage_path, storage_path=storage_path, file_size=2, mime_type="text/plain")
    test_session.add(attachment)
    await test_session.commit()
    await test_session.refresh(attachment)

    attachment_id = attachment.id

    # No auth header
    dl = await client.get(f"/api/attachments/download/{attachment_id}")
    assert dl.status_code in (401, 403)

    # Cleanup file
    full_path.unlink()


@pytest.mark.anyio
async def test_uploader_and_admin_can_download(client: AsyncClient, test_session: AsyncSession):
    # Create uploader and admin
    uploader = User(email="u4@test.com", username="u4", hashed_password=get_password_hash("pass"), is_active=True)
    admin = User(email="admin@test.com", username="adminuser", hashed_password=get_password_hash("pass"), is_active=True, is_system_admin=True)
    member = User(email="memb@test.com", username="memb", hashed_password=get_password_hash("pass"), is_active=True)
    test_session.add_all([uploader, admin, member])
    await test_session.commit()
    await test_session.refresh(uploader)
    await test_session.refresh(admin)
    await test_session.refresh(member)

    # Create private channel and add uploader and member
    channel = Channel(name="private-chan-4", display_name="Private4", type="private")
    test_session.add(channel)
    await test_session.commit()
    await test_session.refresh(channel)

    membership1 = ChannelMember(user_id=uploader.id, channel_id=channel.id)
    membership2 = ChannelMember(user_id=member.id, channel_id=channel.id)
    test_session.add_all([membership1, membership2])
    await test_session.commit()

    # Create message and file
    message = Message(content="", channel_id=channel.id, author_id=uploader.id)
    test_session.add(message)
    await test_session.commit()
    await test_session.refresh(message)

    from app.storage.local import get_full_path
    storage_path = f"channel_{channel.id}/20250101/file.txt"
    full_path = get_full_path(storage_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(b"ok")

    attachment = FileAttachment(message_id=message.id, channel_id=channel.id, user_id=uploader.id, filename="file.txt", file_path=storage_path, storage_path=storage_path, file_size=2, mime_type="text/plain")
    test_session.add(attachment)
    await test_session.commit()
    await test_session.refresh(attachment)

    attachment_id = attachment.id

    # Uploader can download
    token = create_access_token({"sub": str(uploader.id), "username": uploader.username})
    dl_uploader = await client.get(f"/api/attachments/download/{attachment_id}", headers={"Authorization": f"Bearer {token}"})
    assert dl_uploader.status_code == 200

    # Admin (not a member) can download
    admin_token = create_access_token({"sub": str(admin.id), "username": admin.username})
    dl_admin = await client.get(f"/api/attachments/download/{attachment_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert dl_admin.status_code == 200

    # Cleanup file
    full_path.unlink()
