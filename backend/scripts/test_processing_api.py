"""Test script for processing API endpoints"""
import json
import urllib.request

BASE_URL = 'http://localhost:8000'

def make_request(method, path, data=None, token=None):
    """Make HTTP request and return response"""
    url = f'{BASE_URL}{path}'
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8') if data else None,
        headers=headers,
        method=method
    )
    
    try:
        response = urllib.request.urlopen(req)
        return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

def test_processing_api():
    print("=" * 60)
    print("PROCESSING API TEST")
    print("=" * 60)
    
    # 1. Login as admin
    print("\n1. Login as admin...")
    status, result = make_request('POST', '/api/auth/login', {'identifier': 'admin', 'password': 'Password123!'})
    if status != 200:
        print(f"   FAILED: {result}")
        return
    token = result['access_token']
    print(f"   SUCCESS: Got token")
    
    # 2. Get recipes (should include the one we just created)
    print("\n2. Get all recipes...")
    status, result = make_request('GET', '/api/processing/recipes', token=token)
    print(f"   Status: {status}, Recipes: {len(result) if isinstance(result, list) else result}")
    
    # 3. Get recipes for product 24 (groundnut paste)
    print("\n3. Get recipes for product 24...")
    status, result = make_request('GET', '/api/processing/recipes/product/24', token=token)
    print(f"   Status: {status}, Recipes: {len(result) if isinstance(result, list) else result}")
    if isinstance(result, list) and len(result) > 0:
        print(f"   Recipe: {result[0]}")
    
    # 4. Calculate requirements for making 10 units
    print("\n4. Calculate requirements for 10 units of groundnut paste...")
    status, result = make_request('POST', '/api/processing/batches/calculate', 
                                  {'finished_product_id': 24, 'quantity_to_produce': 10}, token=token)
    print(f"   Status: {status}")
    if status == 200:
        print(f"   Requirements: {result}")
    else:
        print(f"   Response: {result}")
    
    # 5. Get analytics overview
    print("\n5. Get processing analytics overview...")
    status, result = make_request('GET', '/api/processing/analytics/overview', token=token)
    print(f"   Status: {status}")
    if status == 200:
        print(f"   Overview: {result}")
    else:
        print(f"   Response: {result}")
    
    # 6. Get raw material usage stats
    print("\n6. Get raw material usage stats...")
    status, result = make_request('GET', '/api/processing/analytics/raw-material-usage', token=token)
    print(f"   Status: {status}")
    if status == 200:
        print(f"   Usage stats: {result}")
    else:
        print(f"   Response: {result}")
    
    # 7. Get finished goods yield stats
    print("\n7. Get finished goods yield stats...")
    status, result = make_request('GET', '/api/processing/analytics/finished-goods-yield', token=token)
    print(f"   Status: {status}")
    if status == 200:
        print(f"   Yield stats: {result}")
    else:
        print(f"   Response: {result}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == '__main__':
    test_processing_api()
