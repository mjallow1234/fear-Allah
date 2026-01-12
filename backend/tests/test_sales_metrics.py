import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_daily_sales_totals(client: AsyncClient, test_session):
    # create user and inventory
    r = await client.post('/api/auth/register', json={'email': 'm1@example.com', 'password': 'Password123!', 'username': 'm1', 'operational_role': 'agent'})
    assert r.status_code == 201
    login = await client.post('/api/auth/login', json={'identifier': 'm1@example.com', 'password': 'Password123!'})
    token = login.json()['access_token']

    from app.db.models import Inventory
    inv = Inventory(product_id=20, total_stock=100, total_sold=0)
    test_session.add(inv)
    await test_session.commit()

    # create two sales today
    await client.post('/api/sales/', json={'product_id': 20, 'quantity': 2, 'unit_price': 5.0, 'sale_channel': 'AGENT'}, headers={'Authorization': f'Bearer {token}'})
    await client.post('/api/sales/', json={'product_id': 20, 'quantity': 3, 'unit_price': 5.0, 'sale_channel': 'AGENT'}, headers={'Authorization': f'Bearer {token}'})

    # query daily totals
    resp = await client.get('/api/sales/metrics/daily')
    assert resp.status_code == 200
    body = resp.json()
    assert body['total_quantity'] == 5
    assert abs(body['total_amount'] - 25.0) < 0.001


@pytest.mark.anyio
async def test_inventory_remaining_endpoint(client: AsyncClient, test_session):
    # create inventory
    from app.db.models import Inventory
    inv = Inventory(product_id=30, total_stock=50, total_sold=0)
    test_session.add(inv)
    await test_session.commit()

    # no sales yet
    resp = await client.get('/api/sales/inventory')
    assert resp.status_code == 200
    rows = resp.json()
    found = [r for r in rows if r['product_id'] == 30]
    assert found and found[0]['remaining'] == 50

    # make a sale to reduce inventory
    r = await client.post('/api/auth/register', json={'email': 'm2@example.com', 'password': 'Password123!', 'username': 'm2', 'operational_role': 'agent'})
    login = await client.post('/api/auth/login', json={'identifier': 'm2@example.com', 'password': 'Password123!'})
    token = login.json()['access_token']
    await client.post('/api/sales/', json={'product_id': 30, 'quantity': 5, 'unit_price': 2.0, 'sale_channel': 'AGENT'}, headers={'Authorization': f'Bearer {token}'})

    resp = await client.get('/api/sales/inventory')
    rows = resp.json()
    found = [r for r in rows if r['product_id'] == 30]
    assert found and found[0]['total_sold'] == 5 and found[0]['remaining'] == 45


@pytest.mark.anyio
async def test_sales_grouped_endpoints(client: AsyncClient, test_session):
    # create two users and sales
    await client.post('/api/auth/register', json={'email': 'g1@example.com', 'password': 'Password123!', 'username': 'g1', 'operational_role': 'agent'})
    await client.post('/api/auth/register', json={'email': 'g2@example.com', 'password': 'Password123!', 'username': 'g2', 'operational_role': 'agent'})
    l1 = await client.post('/api/auth/login', json={'identifier': 'g1@example.com', 'password': 'Password123!'})
    l2 = await client.post('/api/auth/login', json={'identifier': 'g2@example.com', 'password': 'Password123!'})
    t1 = l1.json()['access_token']
    t2 = l2.json()['access_token']

    from app.db.models import Inventory
    inv1 = Inventory(product_id=40, total_stock=20, total_sold=0)
    inv2 = Inventory(product_id=41, total_stock=30, total_sold=0)
    test_session.add_all([inv1, inv2])
    await test_session.commit()

    # g1 sells 2 via AGENT
    await client.post('/api/sales/', json={'product_id': 40, 'quantity': 2, 'unit_price': 10.0, 'sale_channel': 'AGENT'}, headers={'Authorization': f'Bearer {t1}'})
    # g2 sells 3 via STORE (insert directly because API requires special roles)
    from app.db.models import Sale
    sale = Sale(product_id=41, quantity=3, unit_price=5.0, total_amount=15.0, sold_by_user_id=2, sale_channel='STORE')
    test_session.add(sale)
    await test_session.commit()
    # g1 sells 1 via AGENT
    await client.post('/api/sales/', json={'product_id': 40, 'quantity': 1, 'unit_price': 10.0, 'sale_channel': 'AGENT'}, headers={'Authorization': f'Bearer {t1}'})

    # grouped by channel
    r = await client.get('/api/sales/grouped/channel')
    assert r.status_code == 200
    by_channel = {item['channel']: item for item in r.json()}
    assert by_channel['AGENT']['total_quantity'] == 3
    assert abs(by_channel['AGENT']['total_amount'] - 30.0) < 0.001
    assert by_channel['STORE']['total_quantity'] == 3

    # grouped by user
    # Promote g1 to system admin so they can view all users' sales
    from sqlalchemy import select
    from app.db.models import User
    q = select(User).where(User.username == 'g1')
    res = await test_session.execute(q)
    user = res.scalar_one()
    user.is_system_admin = True
    test_session.add(user)
    await test_session.commit()

    r = await client.get('/api/sales/grouped/user', headers={'Authorization': f'Bearer {t1}'})
    assert r.status_code == 200
    by_user = {item['username']: item for item in r.json() if item['username']}
    assert by_user['g1']['total_quantity'] == 3
    assert by_user['g2']['total_quantity'] == 3
