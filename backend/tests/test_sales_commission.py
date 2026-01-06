import pytest
from httpx import AsyncClient, ASGITransport

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_commission_agent_eligible(client: AsyncClient, test_session):
    # setup: create user, inventory, and a sale via API
    await client.post('/api/auth/register', json={'email': 'c1@example.com', 'password': 'Password123!', 'username': 'c1'})
    login = await client.post('/api/auth/login', json={'identifier': 'c1@example.com', 'password': 'Password123!'})
    token = login.json()['access_token']

    from app.db.models import Inventory
    inv = Inventory(product_id=50, total_stock=100, total_sold=0)
    test_session.add(inv)
    await test_session.commit()

    r = await client.post('/api/sales/', json={'product_id': 50, 'quantity': 2, 'unit_price': 10.0, 'sale_channel': 'AGENT'}, headers={'Authorization': f'Bearer {token}'})
    assert r.status_code in (200, 201)
    sale_id = r.json()['sale_id']

    # classify
    resp = await client.get(f'/api/sales/{sale_id}/commission')
    assert resp.status_code == 200
    body = resp.json()
    assert body['commission_eligible'] is True
    assert body['exclusion_reason'] is None


@pytest.mark.anyio
async def test_commission_low_amount_excluded(client: AsyncClient, test_session):
    await client.post('/api/auth/register', json={'email': 'c2@example.com', 'password': 'Password123!', 'username': 'c2'})
    login = await client.post('/api/auth/login', json={'identifier': 'c2@example.com', 'password': 'Password123!'})
    token = login.json()['access_token']

    from app.db.models import Inventory
    inv = Inventory(product_id=51, total_stock=100, total_sold=0)
    test_session.add(inv)
    await test_session.commit()

    r = await client.post('/api/sales/', json={'product_id': 51, 'quantity': 1, 'unit_price': 5.0, 'sale_channel': 'AGENT'}, headers={'Authorization': f'Bearer {token}'})
    assert r.status_code in (200, 201)
    sale_id = r.json()['sale_id']

    resp = await client.get(f'/api/sales/{sale_id}/commission')
    assert resp.status_code == 200
    body = resp.json()
    assert body['commission_eligible'] is False
    assert body['exclusion_reason'] == 'amount_below_threshold'


@pytest.mark.anyio
async def test_commission_channel_excluded(client: AsyncClient, test_session):
    await client.post('/api/auth/register', json={'email': 'c3@example.com', 'password': 'Password123!', 'username': 'c3'})
    login = await client.post('/api/auth/login', json={'identifier': 'c3@example.com', 'password': 'Password123!'})
    token = login.json()['access_token']

    from app.db.models import Inventory
    inv = Inventory(product_id=52, total_stock=100, total_sold=0)
    test_session.add(inv)
    await test_session.commit()

    # Insert sale directly to bypass API permissions for STORE channel
    from app.db.models import Sale
    sale = Sale(product_id=52, quantity=2, unit_price=10.0, total_amount=20.0, sold_by_user_id=1, sale_channel='STORE')
    test_session.add(sale)
    await test_session.commit()

    resp = await client.get(f'/api/sales/{sale.id}/commission')
    assert resp.status_code == 200
    body = resp.json()
    assert body['commission_eligible'] is False
    assert body['exclusion_reason'] == 'channel_not_eligible'


@pytest.mark.anyio
async def test_commission_related_order_not_eligible(client: AsyncClient, test_session):
    # create a sale that references a non-completed order by inserting directly
    from app.db.models import Sale, Order, Inventory
    # create a non-completed order
    order = Order(order_type='AGENT_RESTOCK', status='IN_PROGRESS')
    test_session.add(order)
    inv = Inventory(product_id=53, total_stock=10, total_sold=0)
    test_session.add(inv)
    await test_session.flush()

    # insert sale directly (bypassing record_sale) to simulate legacy/edge case
    sale = Sale(product_id=53, quantity=2, unit_price=10.0, total_amount=20.0, sold_by_user_id=1, sale_channel='AGENT', related_order_id=order.id)
    test_session.add(sale)
    await test_session.commit()

    resp = await client.get(f'/api/sales/{sale.id}/commission')
    assert resp.status_code == 200
    body = resp.json()
    assert body['commission_eligible'] is False
    assert body['exclusion_reason'] == 'related_order_not_eligible'