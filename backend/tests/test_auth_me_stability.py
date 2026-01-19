import pytest


@pytest.mark.asyncio
async def test_me_unexpected_error_returns_401(client, monkeypatch):
    # Monkeypatch the DB-resolving get_current_user used by the /me route to raise
    async def broken_get_current_user(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.api.auth.get_current_user", broken_get_current_user)

    # Login as seeded admin to get a valid token
    resp = await client.post('/api/auth/login', json={'identifier': 'admin', 'password': 'admin123'})
    assert resp.status_code == 200
    token = resp.json()['access_token']

    # The /me route should catch the unexpected error and return 401 instead of 500
    resp2 = await client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert resp2.status_code == 401
