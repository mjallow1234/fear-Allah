import pytest
from app.core.security import create_access_token
from app.db.models import User, Channel, ChannelMember
from datetime import datetime

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_non_admin_cannot_add_or_remove_member(client, test_session):
    # Create users
    admin = User(username='adminuser', email='a@example.com', hashed_password='x')
    admin.is_system_admin = True
    alice = User(username='alice', email='alice@example.com', hashed_password='x')
    bob = User(username='bob', email='bob@example.com', hashed_password='x')
    test_session.add_all([admin, alice, bob])

    # Create channel as admin
    from app.core.security import create_access_token
    await test_session.flush()
    admin_token = create_access_token({'sub': str(admin.id), 'username': admin.username})
    create = await client.post('/api/channels/', json={'name': 'manage-test', 'display_name': 'Manage Test'}, headers={'Authorization': f'Bearer {admin_token}'})
    assert create.status_code == 201
    channel_id = create.json()['id']

    # Non-admin (alice) tries to add bob
    alice_token = create_access_token({'sub': str(alice.id), 'username': alice.username})
    resp = await client.post(f'/api/channels/{channel_id}/members', json={'user_id': bob.id}, headers={'Authorization': f'Bearer {alice_token}'})
    assert resp.status_code == 403
    assert resp.json().get('detail') == "You do not have permission to manage this channel."

    # Non-admin tries to remove user
    # First admin adds bob for cleanup
    admin_headers = {'Authorization': f'Bearer {admin_token}'}
    add = await client.post(f'/api/channels/{channel_id}/members', json={'user_id': bob.id}, headers=admin_headers)
    assert add.status_code == 200 or add.status_code == 201

    resp2 = await client.delete(f'/api/channels/{channel_id}/members/{bob.id}', headers={'Authorization': f'Bearer {alice_token}'})
    assert resp2.status_code == 403
    assert resp2.json().get('detail') == "You do not have permission to manage this channel."


@pytest.mark.anyio
async def test_admin_can_add_and_remove_member(client, test_session):
    admin = User(username='superadmin', email='s@example.com', hashed_password='x')
    admin.is_system_admin = True
    u1 = User(username='u1', email='u1@example.com', hashed_password='x')
    u2 = User(username='u2', email='u2@example.com', hashed_password='x')
    test_session.add_all([admin, u1, u2])
    await test_session.flush()

    admin_token = create_access_token({'sub': str(admin.id), 'username': admin.username})
    create = await client.post('/api/channels/', json={'name': 'admin-manage', 'display_name': 'Admin Manage'}, headers={'Authorization': f'Bearer {admin_token}'})
    channel_id = create.json()['id']

    # Add u1
    add = await client.post(f'/api/channels/{channel_id}/members', json={'user_id': u1.id}, headers={'Authorization': f'Bearer {admin_token}'})
    assert add.status_code == 200 or add.status_code == 201

    # Remove u1
    rem = await client.delete(f'/api/channels/{channel_id}/members/{u1.id}', headers={'Authorization': f'Bearer {admin_token}'})
    assert rem.status_code == 200


@pytest.mark.anyio
async def test_non_admin_cannot_change_channel_privacy(client, test_session):
    admin = User(username='root', email='root@example.com', hashed_password='x')
    admin.is_system_admin = True
    alice = User(username='alice2', email='alice2@example.com', hashed_password='x')
    test_session.add_all([admin, alice])
    await test_session.flush()

    admin_token = create_access_token({'sub': str(admin.id), 'username': admin.username})
    create = await client.post('/api/channels/', json={'name': 'priv-toggle', 'display_name': 'Priv Toggle'}, headers={'Authorization': f'Bearer {admin_token}'})
    channel_id = create.json()['id']

    # Non-admin tries to change channel via admin endpoint
    alice_token = create_access_token({'sub': str(alice.id), 'username': alice.username})
    resp = await client.put(f'/api/admin/channels/{channel_id}', json={'type': 'private'}, headers={'Authorization': f'Bearer {alice_token}'})
    assert resp.status_code == 403
    assert resp.json().get('detail') == "You do not have permission to manage this channel."


@pytest.mark.anyio
async def test_dm_visibility_and_creation(client, test_session):
    # Users: a, b, c
    a = User(username='dm_a', email='a@ex', hashed_password='x')
    b = User(username='dm_b', email='b@ex', hashed_password='x')
    c = User(username='dm_c', email='c@ex', hashed_password='x')
    test_session.add_all([a,b,c])
    await test_session.flush()

    a_token = create_access_token({'sub': str(a.id), 'username': a.username})
    b_token = create_access_token({'sub': str(b.id), 'username': b.username})
    c_token = create_access_token({'sub': str(c.id), 'username': c.username})

    # A creates DM with B
    resp = await client.post('/api/channels/direct', json={'user_id': b.id}, headers={'Authorization': f'Bearer {a_token}'})
    assert resp.status_code == 200
    dm_id = resp.json()['id']

    # A and B see it in direct list
    la = await client.get('/api/channels/direct/list', headers={'Authorization': f'Bearer {a_token}'})
    lb = await client.get('/api/channels/direct/list', headers={'Authorization': f'Bearer {b_token}'})
    assert any(d['id'] == dm_id for d in la.json())
    assert any(d['id'] == dm_id for d in lb.json())

    # C does not see it
    lc = await client.get('/api/channels/direct/list', headers={'Authorization': f'Bearer {c_token}'})
    assert all(d['id'] != dm_id for d in lc.json())

    # DM not visible in global channel list
    gl = await client.get('/api/channels/', headers={'Authorization': f'Bearer {a_token}'})
    assert all(ch.get('type') != 'direct' for ch in gl.json())
