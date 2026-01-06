"""
Test scenarios for team testing
"""
import asyncio
from app.db.database import async_session
from app.db.models import User, Order, Task, AutomationTask
from app.services.task_engine import create_order, complete_task, WORKFLOWS
from sqlalchemy import select

async def test_all_scenarios():
    print("=" * 70)
    print("TESTING ALL ORDER SCENARIOS")
    print("=" * 70)
    
    # Show all workflow configurations
    print("\n📋 WORKFLOW CONFIGURATIONS:")
    for order_type, steps in WORKFLOWS.items():
        print(f"\n  {order_type}:")
        for i, step in enumerate(steps):
            print(f"    {i+1}. {step['title']} ({step['step_key']})")
    
    async with async_session() as db:
        # Get test users
        users = {}
        for uname in ['agent1', 'foreman1', 'delivery1', 'storekeeper1', 'customer1']:
            result = await db.execute(select(User).where(User.username == uname))
            u = result.scalar_one_or_none()
            if u:
                users[uname] = u
                print(f"✅ Found user: {uname} (id={u.id})")
            else:
                print(f"❌ Missing user: {uname}")
        
        if 'agent1' not in users:
            print("ERROR: agent1 user required for testing")
            return
        
        # ============================================================
        # SCENARIO 1: AGENT_RESTOCK
        # ============================================================
        print("\n" + "=" * 70)
        print("SCENARIO 1: AGENT_RESTOCK")
        print("=" * 70)
        
        order = await create_order(
            db, 
            'AGENT_RESTOCK', 
            items='Cement Bags', 
            metadata='{"product": "Cement Bags", "amount": 50}', 
            created_by_id=users['agent1'].id
        )
        print(f"✅ Order created: ID={order.id}, Type={order.order_type}, Status={order.status}")
        
        result = await db.execute(select(Task).where(Task.order_id == order.id).order_by(Task.id))
        tasks = result.scalars().all()
        print(f"   Tasks created: {len(tasks)}")
        for t in tasks:
            status_icon = "🟢" if t.status == "active" else "⚪"
            print(f"   {status_icon} Task #{t.id}: {t.title} | Status: {t.status}")
        
        expected_tasks = ["Assemble Items", "Pickup Items", "Deliver Items", "Confirm Received"]
        actual_tasks = [t.title for t in tasks]
        if actual_tasks == expected_tasks:
            print("   ✅ PASS: Correct task chain created")
        else:
            print(f"   ❌ FAIL: Expected {expected_tasks}, got {actual_tasks}")
        
        # ============================================================
        # SCENARIO 2: AGENT_RETAIL
        # ============================================================
        print("\n" + "=" * 70)
        print("SCENARIO 2: AGENT_RETAIL")
        print("=" * 70)
        
        order2 = await create_order(
            db, 
            'AGENT_RETAIL', 
            items='Water Bottles', 
            metadata='{"product": "Water Bottles", "amount": 100, "location": "123 Main St"}', 
            created_by_id=users['agent1'].id
        )
        print(f"✅ Order created: ID={order2.id}, Type={order2.order_type}, Status={order2.status}")
        
        result = await db.execute(select(Task).where(Task.order_id == order2.id).order_by(Task.id))
        tasks2 = result.scalars().all()
        print(f"   Tasks created: {len(tasks2)}")
        for t in tasks2:
            status_icon = "🟢" if t.status == "active" else "⚪"
            print(f"   {status_icon} Task #{t.id}: {t.title} | Status: {t.status}")
        
        expected_tasks2 = ["Accept Delivery", "Deliver Items"]
        actual_tasks2 = [t.title for t in tasks2]
        if actual_tasks2 == expected_tasks2:
            print("   ✅ PASS: Correct task chain created")
        else:
            print(f"   ❌ FAIL: Expected {expected_tasks2}, got {actual_tasks2}")
        
        # ============================================================
        # SCENARIO 3: STORE_KEEPER_RESTOCK
        # ============================================================
        print("\n" + "=" * 70)
        print("SCENARIO 3: STORE_KEEPER_RESTOCK")
        print("=" * 70)
        
        order3 = await create_order(
            db, 
            'STORE_KEEPER_RESTOCK', 
            items='Rice Bags 50kg', 
            metadata='{"product": "Rice Bags 50kg", "amount": 20}', 
            created_by_id=users.get('storekeeper1', users['agent1']).id
        )
        print(f"✅ Order created: ID={order3.id}, Type={order3.order_type}, Status={order3.status}")
        
        result = await db.execute(select(Task).where(Task.order_id == order3.id).order_by(Task.id))
        tasks3 = result.scalars().all()
        print(f"   Tasks created: {len(tasks3)}")
        for t in tasks3:
            status_icon = "🟢" if t.status == "active" else "⚪"
            print(f"   {status_icon} Task #{t.id}: {t.title} | Status: {t.status}")
        
        expected_tasks3 = ["Assemble Items", "Pickup Items", "Deliver Items", "Confirm Received"]
        actual_tasks3 = [t.title for t in tasks3]
        if actual_tasks3 == expected_tasks3:
            print("   ✅ PASS: Correct task chain created")
        else:
            print(f"   ❌ FAIL: Expected {expected_tasks3}, got {actual_tasks3}")
        
        # ============================================================
        # SCENARIO 4: CUSTOMER_WHOLESALE
        # ============================================================
        print("\n" + "=" * 70)
        print("SCENARIO 4: CUSTOMER_WHOLESALE")
        print("=" * 70)
        
        order4 = await create_order(
            db, 
            'CUSTOMER_WHOLESALE', 
            items='Cooking Oil Cartons', 
            metadata='{"product": "Cooking Oil Cartons", "amount": 30}', 
            created_by_id=users.get('customer1', users['agent1']).id
        )
        print(f"✅ Order created: ID={order4.id}, Type={order4.order_type}, Status={order4.status}")
        
        result = await db.execute(select(Task).where(Task.order_id == order4.id).order_by(Task.id))
        tasks4 = result.scalars().all()
        print(f"   Tasks created: {len(tasks4)}")
        for t in tasks4:
            status_icon = "🟢" if t.status == "active" else "⚪"
            print(f"   {status_icon} Task #{t.id}: {t.title} | Status: {t.status}")
        
        expected_tasks4 = ["Assemble Items", "Pickup Items", "Deliver Items"]
        actual_tasks4 = [t.title for t in tasks4]
        if actual_tasks4 == expected_tasks4:
            print("   ✅ PASS: Correct task chain created (no Confirm Received for wholesale)")
        else:
            print(f"   ❌ FAIL: Expected {expected_tasks4}, got {actual_tasks4}")
        
        # ============================================================
        # SUMMARY
        # ============================================================
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"""
| Scenario              | Order Created | Tasks | Status    |
|-----------------------|---------------|-------|-----------|
| Agent Restock         | #{order.id:<12} | {len(tasks):<5} | {'✅ PASS' if actual_tasks == expected_tasks else '❌ FAIL':<9} |
| Agent Retail          | #{order2.id:<12} | {len(tasks2):<5} | {'✅ PASS' if actual_tasks2 == expected_tasks2 else '❌ FAIL':<9} |
| Store Keeper Restock  | #{order3.id:<12} | {len(tasks3):<5} | {'✅ PASS' if actual_tasks3 == expected_tasks3 else '❌ FAIL':<9} |
| Customer Wholesale    | #{order4.id:<12} | {len(tasks4):<5} | {'✅ PASS' if actual_tasks4 == expected_tasks4 else '❌ FAIL':<9} |
""")
        
        # Task flow test for Scenario 1
        print("\n" + "=" * 70)
        print("TASK FLOW TEST: Completing AGENT_RESTOCK chain")
        print("=" * 70)
        
        # Reload tasks
        result = await db.execute(select(Task).where(Task.order_id == order.id).order_by(Task.id))
        tasks = result.scalars().all()
        
        for i, task in enumerate(tasks):
            print(f"\n📌 Step {i+1}: Complete '{task.title}' (Task #{task.id})")
            print(f"   Before: status={task.status}")
            
            if task.status == 'active':
                await complete_task(db, task.id, users['agent1'].id)
                await db.refresh(task)
                print(f"   After:  status={task.status}")
                
                # Check if next task activated
                if i < len(tasks) - 1:
                    await db.refresh(tasks[i+1])
                    print(f"   Next task '{tasks[i+1].title}' status: {tasks[i+1].status}")
            else:
                print(f"   Skipping (not active)")
        
        # Check final order status
        await db.refresh(order)
        print(f"\n📦 Final order status: {order.status}")
        if order.status == 'completed':
            print("✅ PASS: Order completed when all tasks done")
        else:
            print(f"⚠️  Order status is {order.status} (expected: completed)")

if __name__ == "__main__":
    asyncio.run(test_all_scenarios())
