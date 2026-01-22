import pytest

from sqlalchemy import select
from app.db.models import Role, User, UserRole as UserRoleModel
from app.core.security import create_access_token, get_password_hash


@pytest.mark.asyncio
async def test_agent_cannot_update_inventory(client, test_session):
    # Create agent role
    role = Role(name='agent', is_system=False)
    test_session.add(role)
    await test_session.commit()
    await test_session.refresh(role)

    # Create agent user and assign operational role
    agent = User(email='agent1@example.com', username='agent1', display_name='Agent One', hashed_password=get_password_hash('pass'), is_active=True)
    test_session.add(agent)
    await test_session.commit()
    await test_session.refresh(agent)

    assignment = UserRoleModel(user_id=agent.id, role_id=role.id)
    test_session.add(assignment)
    await test_session.commit()

    # Create an admin user to create an inventory item
    admin = User(email='admin1@example.com', username='admin1', display_name='Admin 1', hashed_password=get_password_hash('pass'), is_active=True, is_system_admin=True)
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    admin_token = create_access_token({"sub": str(admin.id), "username": admin.username})
    # Create inventory item
    resp = await client.post('/api/inventory/', json={'product_name': 'TestProd', 'initial_stock': 10}, headers={'Authorization': f'Bearer {admin_token}'})
    assert resp.status_code == 200
    data = resp.json()
    product_id = data['product_id']

    # Agent attempts to adjust product
    agent_token = create_access_token({"sub": str(agent.id), "username": agent.username})
    resp2 = await client.post(f'/api/inventory/product/{product_id}/adjust', json={'adjustment': 5, 'reason': 'adjustment'}, headers={'Authorization': f'Bearer {agent_token}'})
    assert resp2.status_code == 403


@pytest.mark.asyncio
async def test_delivery_cannot_create_orders(client, test_session):
    # Create delivery role
    role = Role(name='delivery', is_system=False)
    test_session.add(role)
    await test_session.commit()
    await test_session.refresh(role)

    # Create delivery user and assign
    user = User(email='del@example.com', username='del', display_name='Delivery', hashed_password=get_password_hash('pass'), is_active=True)
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    assignment = UserRoleModel(user_id=user.id, role_id=role.id)
    test_session.add(assignment)
    await test_session.commit()

    token = create_access_token({"sub": str(user.id), "username": user.username})
    resp = await client.post('/api/orders/', json={'order_type': 'AGENT_RETAIL', 'items': []}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_foreman_cannot_create_sales(client, test_session):
    # Create foreman role
    role = Role(name='foreman', is_system=False)
    test_session.add(role)
    await test_session.commit()
    await test_session.refresh(role)

    # Create foreman user and assign
    user = User(email='foreman@example.com', username='foreman', display_name='Foreman', hashed_password=get_password_hash('pass'), is_active=True)
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    assignment = UserRoleModel(user_id=user.id, role_id=role.id)
    test_session.add(assignment)
    await test_session.commit()

    token = create_access_token({"sub": str(user.id), "username": user.username})
    # Try to create sale
    resp = await client.post('/api/sales/', json={'product_id': 1, 'quantity': 1, 'unit_price': 10.0, 'sale_channel': 'AGENT'}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_perform_write_actions(client, test_session):
    # Create admin user
    admin = User(email='sysadmin2@example.com', username='sysadmin2', display_name='SysAdmin2', hashed_password=get_password_hash('pass'), is_active=True, is_system_admin=True)
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    token = create_access_token({"sub": str(admin.id), "username": admin.username})

    # Admin can create order
    resp = await client.post('/api/orders/', json={'order_type': 'AGENT_RETAIL', 'items': []}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code in (200, 201)

    # Admin can create inventory
    resp2 = await client.post('/api/inventory/', json={'product_name': 'AdminProd', 'initial_stock': 5}, headers={'Authorization': f'Bearer {token}'})
    assert resp2.status_code == 200
    product_id = resp2.json()['product_id']

    # Admin can restock
    resp3 = await client.post(f'/api/inventory/product/{product_id}/restock', json={'quantity': 10}, headers={'Authorization': f'Bearer {token}'})
    assert resp3.status_code == 200

    # Admin can create raw material
    resp4 = await client.post('/api/inventory/raw-materials/', json={'name': 'RM', 'unit': 'kg', 'current_stock': 10}, headers={'Authorization': f'Bearer {token}'})
    assert resp4.status_code == 200

    # Admin can create sale
    resp5 = await client.post('/api/sales/', json={'product_id': 1, 'quantity': 1, 'unit_price': 1.0, 'sale_channel': 'AGENT'}, headers={'Authorization': f'Bearer {token}'})
    # Sale may fail due to inventory/product constraints in test env; ensure not 403
    assert resp5.status_code != 403
