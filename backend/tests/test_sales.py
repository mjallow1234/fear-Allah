import pytest
from httpx import AsyncClient, ASGITransport

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_agent_sale(client: AsyncClient, test_session, monkeypatch):
    # Create user
    r = await client.post('/api/auth/register', json={'email': 'agent1@example.com', 'password': 'Password123!', 'username': 'agent1', 'operational_role': 'agent'})
    assert r.status_code == 201
    login = await client.post('/api/auth/login', json={'identifier': 'agent1@example.com', 'password': 'Password123!'})
    token = login.json()['access_token']

    # Create inventory for product 1
    from app.db.models import Inventory, Sale
    inv = Inventory(product_id=1, total_stock=10, total_sold=0)
    test_session.add(inv)
    await test_session.commit()

    # Capture sale events
    import app.services.sales as sales_service
    captured = []

    async def fake_emit(event_name, payload):
        captured.append((event_name, payload))

    monkeypatch.setattr(sales_service, 'emit_event', fake_emit)

    # Post sale
    resp = await client.post('/api/sales/', json={'product_id': 1, 'quantity': 3, 'unit_price': 10.0, 'sale_channel': 'AGENT'}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200 or resp.status_code == 201

    # Verify inventory updated
    res = await test_session.execute(__import__('sqlalchemy').select(Inventory).where(Inventory.product_id == 1))
    inv2 = res.scalar_one()
    assert inv2.total_stock == 7
    assert inv2.total_sold == 3

    # Verify sale row
    res = await test_session.execute(__import__('sqlalchemy').select(Sale).where(Sale.product_id == 1))
    sale = res.scalar_one()
    assert sale.quantity == 3
    assert any(e[0] == 'sale.recorded' for e in captured)


@pytest.mark.anyio
async def test_concurrent_double_sale(test_engine, monkeypatch):
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.db.models import Inventory

    async_session = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    # Setup inventory with limited stock
    async with async_session() as s:
        inv = Inventory(product_id=2, total_stock=5, total_sold=0)
        s.add(inv)
        await s.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as c1, AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as c2:
        # register two users
        await c1.post('/api/auth/register', json={'email': 'r1@example.com', 'password': 'Password123!', 'username': 'r1', 'operational_role': 'agent'})
        await c2.post('/api/auth/register', json={'email': 'r2@example.com', 'password': 'Password123!', 'username': 'r2', 'operational_role': 'agent'})
        l1 = await c1.post('/api/auth/login', json={'identifier': 'r1@example.com', 'password': 'Password123!'})
        l2 = await c2.post('/api/auth/login', json={'identifier': 'r2@example.com', 'password': 'Password123!'})
        t1 = l1.json()['access_token']
        t2 = l2.json()['access_token']

        fut1 = c1.post('/api/sales/', json={'product_id': 2, 'quantity': 3, 'unit_price': 5.0, 'sale_channel': 'AGENT'}, headers={'Authorization': f'Bearer {t1}'})
        fut2 = c2.post('/api/sales/', json={'product_id': 2, 'quantity': 3, 'unit_price': 5.0, 'sale_channel': 'AGENT'}, headers={'Authorization': f'Bearer {t2}'})
        r1, r2 = await __import__('asyncio').gather(fut1, fut2)

        statuses = sorted([r1.status_code, r2.status_code])
        assert statuses == [200, 409] or statuses == [201, 409]


@pytest.mark.anyio
async def test_idempotent_sale(client: AsyncClient, test_session):
    # register and login
    r = await client.post('/api/auth/register', json={'email': 'idemp@example.com', 'password': 'Password123!', 'username': 'idemp', 'operational_role': 'agent'})
    assert r.status_code == 201
    login = await client.post('/api/auth/login', json={'identifier': 'idemp@example.com', 'password': 'Password123!'})
    token = login.json()['access_token']

    # inventory
    from app.db.models import Inventory, Sale
    inv = Inventory(product_id=3, total_stock=10, total_sold=0)
    test_session.add(inv)
    await test_session.commit()

    idempotency_key = 'k-123'

    # first call
    r1 = await client.post('/api/sales/', json={'product_id': 3, 'quantity': 2, 'unit_price': 2.5, 'sale_channel': 'AGENT', 'idempotency_key': idempotency_key}, headers={'Authorization': f'Bearer {token}'})
    assert r1.status_code in (200, 201)
    body1 = r1.json()

    # second call with same idempotency key
    r2 = await client.post('/api/sales/', json={'product_id': 3, 'quantity': 2, 'unit_price': 2.5, 'sale_channel': 'AGENT', 'idempotency_key': idempotency_key}, headers={'Authorization': f'Bearer {token}'})
    assert r2.status_code in (200, 201)
    body2 = r2.json()

    assert body1['sale_id'] == body2['sale_id']

    # inventory should be decremented once
    res = await test_session.execute(__import__('sqlalchemy').select(Inventory).where(Inventory.product_id == 3))
    inv2 = res.scalar_one()
    assert inv2.total_stock == 8


@pytest.mark.anyio
async def test_sale_linked_to_completed_order(client: AsyncClient, test_session):
    # register and login
    r = await client.post('/api/auth/register', json={'email': 'ordok@example.com', 'password': 'Password123!', 'username': 'ordok', 'operational_role': 'agent'})
    assert r.status_code == 201
    login = await client.post('/api/auth/login', json={'identifier': 'ordok@example.com', 'password': 'Password123!'})
    token = login.json()['access_token']

    # create inventory and order
    from app.db.models import Inventory, Order
    inv = Inventory(product_id=10, total_stock=5, total_sold=0)
    test_session.add(inv)
    order = Order(order_type='AGENT_RESTOCK', status='COMPLETED')
    test_session.add(order)
    await test_session.commit()

    # sale linked to completed order should succeed
    resp = await client.post('/api/sales/', json={'product_id': 10, 'quantity': 1, 'unit_price': 10.0, 'sale_channel': 'AGENT', 'related_order_id': order.id}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code in (200, 201)


@pytest.mark.anyio
async def test_sale_linked_to_non_completed_order_conflict(client: AsyncClient, test_session):
    # register and login
    r = await client.post('/api/auth/register', json={'email': 'ordbad@example.com', 'password': 'Password123!', 'username': 'ordbad', 'operational_role': 'agent'})
    assert r.status_code == 201
    login = await client.post('/api/auth/login', json={'identifier': 'ordbad@example.com', 'password': 'Password123!'})
    token = login.json()['access_token']

    # create inventory and a non-completed order
    from app.db.models import Inventory, Order
    inv = Inventory(product_id=11, total_stock=5, total_sold=0)
    test_session.add(inv)
    order = Order(order_type='AGENT_RESTOCK', status='IN_PROGRESS')
    test_session.add(order)
    await test_session.commit()

    # sale linked to non-completed order should return 409
    resp = await client.post('/api/sales/', json={'product_id': 11, 'quantity': 1, 'unit_price': 10.0, 'sale_channel': 'AGENT', 'related_order_id': order.id}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 409
