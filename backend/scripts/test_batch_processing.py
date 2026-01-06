"""Test batch processing - actual manufacturing run"""
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

def test_batch_processing():
    print("=" * 60)
    print("BATCH PROCESSING TEST")
    print("=" * 60)
    
    # 1. Login as admin
    print("\n1. Login as admin...")
    status, result = make_request('POST', '/api/auth/login', {'identifier': 'admin', 'password': 'Password123!'})
    if status != 200:
        print(f"   FAILED: {result}")
        return
    token = result['access_token']
    print(f"   SUCCESS: Got token")
    
    # 2. Check current inventory levels
    print("\n2. Check current inventory levels...")
    # Raw material (Groundnut - id 1)
    status, result = make_request('GET', '/api/raw-materials/1', token=token)
    if status == 200:
        print(f"   Raw Material (Groundnut): {result.get('quantity', 'N/A')} available")
    else:
        print(f"   Could not get raw material: {result}")
    
    # Finished good (Groundnut Paste - product_id 24)
    status, result = make_request('GET', '/api/inventory/24', token=token)
    if status == 200:
        print(f"   Finished Good (Groundnut Paste): {result.get('total_stock', 'N/A')} in stock")
    else:
        print(f"   Could not get inventory: {result}")
    
    # 3. Calculate what we need for 5 units
    print("\n3. Calculate requirements for 5 units...")
    status, result = make_request('POST', '/api/processing/batches/calculate', 
                                  {'finished_product_id': 24, 'quantity_to_produce': 5}, token=token)
    print(f"   Status: {status}")
    if status == 200:
        print(f"   Requirements: {result}")
        if not result.get('can_process'):
            print("   WARNING: Cannot process - insufficient raw materials!")
            return
    else:
        print(f"   Response: {result}")
        return
    
    # 4. Execute the batch!
    print("\n4. Process batch (5 units of groundnut paste)...")
    status, result = make_request('POST', '/api/processing/batches', {
        'finished_product_id': 24,
        'quantity_to_produce': 5,
        'batch_reference': 'BATCH-2026-001',
        'notes': 'First production run test'
    }, token=token)
    print(f"   Status: {status}")
    if status in (200, 201):
        print(f"   Batch created: {result}")
        batch_id = result.get('id')
    else:
        print(f"   Failed: {result}")
        return
    
    # 5. Check updated inventory levels
    print("\n5. Check updated inventory levels...")
    status, result = make_request('GET', '/api/raw-materials/1', token=token)
    if status == 200:
        print(f"   Raw Material (Groundnut): {result.get('quantity', 'N/A')} available (should be 27 less)")
    
    status, result = make_request('GET', '/api/inventory/24', token=token)
    if status == 200:
        print(f"   Finished Good (Groundnut Paste): {result.get('total_stock', 'N/A')} in stock (should be 5 more)")
    
    # 6. Get updated analytics
    print("\n6. Check analytics after batch...")
    status, result = make_request('GET', '/api/processing/analytics/overview', token=token)
    print(f"   Overview: {result}")
    
    status, result = make_request('GET', '/api/processing/analytics/raw-material-usage', token=token)
    print(f"   Raw Material Usage: {result}")
    
    status, result = make_request('GET', '/api/processing/analytics/finished-goods-yield', token=token)
    print(f"   Finished Goods Yield: {result}")
    
    # 7. Get the batch details
    if batch_id:
        print(f"\n7. Get batch {batch_id} details...")
        status, result = make_request('GET', f'/api/processing/batches/{batch_id}', token=token)
        print(f"   Batch: {result}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == '__main__':
    test_batch_processing()
