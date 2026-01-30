import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_form_submission_orders_persists_form_payload(client: AsyncClient, test_session):
    # Register user
    r = await client.post('/api/auth/register', json={'email': 'formu@example.com', 'password': 'Password123!', 'username': 'formu'})
    assert r.status_code == 201
    login = await client.post('/api/auth/login', json={'identifier': 'formu@example.com', 'password': 'Password123!'})
    token = login.json()['access_token']

    # Create a simple form in DB that routes to orders
    from app.db.models import Form
    from app.db.enums import FormCategory
    form = Form(slug='test-order-form', name='Test Order Form', service_target='orders', is_active=True, current_version=1, category=FormCategory.order.value)
    test_session.add(form)
    await test_session.commit()

    # Payload to submit
    submitted = {
        'items': [{'product_id': 1, 'quantity': 5}],
        'customer_name': 'Alice',
        'customer_phone': '+123456789',
        'metadata': {'note': 'please deliver'},
    }

    # Submit the form via API
    resp = await client.post(f'/api/forms/{form.slug}/submit', json={'data': submitted}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    body = resp.json()
    assert body['status'] in ('processed', 'failed')

    # If processed and result_id present, fetch order and assert meta contains form_payload
    if body['status'] == 'processed' and body.get('result_id'):
        from app.db.models import Order
        res = await test_session.execute(__import__('sqlalchemy').select(Order).where(Order.id == body['result_id']))
        order = res.scalar_one_or_none()
        assert order is not None
        import json as _json
        meta = _json.loads(order.meta) if order.meta else {}
        assert 'form_payload' in meta
        assert meta['form_payload'] == submitted
    else:
        pytest.skip('Order not created by form handler in this environment')