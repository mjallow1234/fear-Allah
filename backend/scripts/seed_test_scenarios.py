#!/usr/bin/env python3
"""
Seed Test Scenarios for Team Role-Play Testing
===============================================

This script creates realistic test data scenarios for the team to use
when testing slash commands and automation workflows.

Scenarios:
1. Multi-step order workflow (restock with 4 tasks)
2. Sale triggering low-stock alert
3. Task completion unlocking next task

Usage:
    python scripts/seed_test_scenarios.py

NO external services (Make.com, webhooks) - purely internal testing.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.db.database import async_engine, async_session
from app.db.models import User, Channel, AutomationTask, Sale, Inventory, InventoryTransaction
from app.db.enums import AutomationTaskStatus, AutomationTaskType
import json
from datetime import datetime, timedelta


async def get_or_create_test_users(db):
    """Create test users for different roles."""
    users = {}
    
    # System admin
    admin = await db.execute(select(User).where(User.username == 'test_admin'))
    admin = admin.scalar_one_or_none()
    if not admin:
        admin = User(
            username='test_admin',
            email='admin@example.com',
            hashed_password='test_hash',
            role='system_admin',
            is_system_admin=True,
            is_active=True,
        )
        db.add(admin)
    users['admin'] = admin
    
    # Agent user
    agent = await db.execute(select(User).where(User.username == 'agent_sarah'))
    agent = agent.scalar_one_or_none()
    if not agent:
        agent = User(
            username='agent_sarah',
            email='agent_sarah@example.com',
            hashed_password='test_hash',
            role='agent',
            is_active=True,
        )
        db.add(agent)
    users['agent'] = agent
    
    # Another agent for assignment testing
    agent2 = await db.execute(select(User).where(User.username == 'agent_mike'))
    agent2 = agent2.scalar_one_or_none()
    if not agent2:
        agent2 = User(
            username='agent_mike',
            email='agent_mike@example.com',
            hashed_password='test_hash',
            role='agent',
            is_active=True,
        )
        db.add(agent2)
    users['agent2'] = agent2
    
    # Regular user (no slash command access)
    regular = await db.execute(select(User).where(User.username == 'customer_john'))
    regular = regular.scalar_one_or_none()
    if not regular:
        regular = User(
            username='customer_john',
            email='customer_john@example.com',
            hashed_password='test_hash',
            role='customer',
            is_active=True,
        )
        db.add(regular)
    users['customer'] = regular
    
    await db.flush()
    return users


async def get_or_create_test_channel(db, users):
    """Create a test channel for slash command testing."""
    channel = await db.execute(select(Channel).where(Channel.name == 'slash-commands-test'))
    channel = channel.scalar_one_or_none()
    if not channel:
        channel = Channel(
            name='slash-commands-test',
            description='Testing channel for slash commands and automation',
            is_public=True,
            created_by_id=users['admin'].id,
        )
        db.add(channel)
        await db.flush()
    return channel


async def get_or_create_test_products(db):
    """Placeholder for test products; returns empty dict (inventory used instead)."""
    return {}


async def get_or_create_inventory_seeds(db):
    """Seed Inventory table with real product entries for testing."""
    seeds = [
        {'product_id': 1001, 'product_name': 'Cement Bag 25kg', 'stock': 200, 'low_stock_threshold': 20},
        {'product_id': 1002, 'product_name': 'Cement Bag 50kg', 'stock': 150, 'low_stock_threshold': 20},
        {'product_id': 1003, 'product_name': 'Sand Pack', 'stock': 500, 'low_stock_threshold': 50},
        {'product_id': 1004, 'product_name': 'Iron Rod 12mm', 'stock': 300, 'low_stock_threshold': 30},
        {'product_id': 1005, 'product_name': 'Gravel Pack', 'stock': 400, 'low_stock_threshold': 40},
    ]

    from app.db.models import Inventory
    created = []
    for s in seeds:
        q = select(Inventory).where(Inventory.product_id == s['product_id'])
        res = await db.execute(q)
        inv = res.scalar_one_or_none()
        if not inv:
            inv = Inventory(
                product_id=s['product_id'],
                product_name=s['product_name'],
                total_stock=s['stock'],
                total_sold=0,
                low_stock_threshold=s['low_stock_threshold'],
            )
            db.add(inv)
            created.append(inv)
    await db.flush()
    return created


async def create_scenario_1_multistep_order(db, users, products):
    """
    Scenario 1: Multi-step Order Workflow
    
    Creates an order with a full workflow of dependent tasks:
    1. Verify inventory availability (pending)
    2. Prepare items for shipping (blocked by #1)
    3. Generate shipping label (blocked by #2)
    4. Notify customer (blocked by #3)
    
    Team can test: task completion unlocking next task
    """
    print("\n📦 Creating Scenario 1: Multi-step Order Workflow...")
    
    # Create parent order task
    order_metadata = json.dumps({
        'order_type': 'AGENT_RESTOCK',
        'product': 'Premium Package',
        'amount': '5',
        'scenario': 'multi_step_workflow',
    })
    
    # Task 1: Verify inventory (can be started immediately)
    task1 = AutomationTask(
        title='[TEST] Verify inventory availability',
        description='Check warehouse stock for Premium Package x5',
        task_type=AutomationTaskType.INVENTORY_CHECK,
        status=AutomationTaskStatus.PENDING,
        task_metadata=order_metadata,
        priority=1,
        created_by_id=users['admin'].id,
    )
    db.add(task1)
    await db.flush()
    
    # Task 2: Prepare items (depends on task 1)
    task2 = AutomationTask(
        title='[TEST] Prepare items for shipping',
        description='Pick and pack Premium Package x5',
        task_type=AutomationTaskType.ORDER_FULFILLMENT,
        status=AutomationTaskStatus.BLOCKED,  # Blocked until task 1 completes
        task_metadata=order_metadata,
        priority=2,
        created_by_id=users['admin'].id,
        depends_on_task_id=task1.id,
    )
    db.add(task2)
    await db.flush()
    
    # Task 3: Generate shipping label (depends on task 2)
    task3 = AutomationTask(
        title='[TEST] Generate shipping label',
        description='Create shipping label and tracking number',
        task_type=AutomationTaskType.ORDER_FULFILLMENT,
        status=AutomationTaskStatus.BLOCKED,
        task_metadata=order_metadata,
        priority=3,
        created_by_id=users['admin'].id,
        depends_on_task_id=task2.id,
    )
    db.add(task3)
    await db.flush()
    
    # Task 4: Notify customer (depends on task 3)
    task4 = AutomationTask(
        title='[TEST] Notify customer of shipment',
        description='Send tracking information to customer',
        task_type=AutomationTaskType.NOTIFICATION,
        status=AutomationTaskStatus.BLOCKED,
        task_metadata=order_metadata,
        priority=4,
        created_by_id=users['admin'].id,
        depends_on_task_id=task3.id,
    )
    db.add(task4)
    
    print(f"  ✅ Created 4 dependent tasks (Task IDs: {task1.id}, {task2.id}, {task3.id}, {task4.id})")
    print(f"     → Complete task {task1.id} to unlock the chain")
    
    return [task1, task2, task3, task4]


async def create_scenario_2_low_stock_alert(db, users, products):
    """
    Scenario 2: Sale Triggering Low-Stock Alert
    
    Creates a sale that would trigger a low-stock automation.
    Product 'Widget B (Low Stock)' has only 5 units.
    
    Team can test: /sale record triggering inventory alerts
    """
    print("\n🚨 Creating Scenario 2: Low-Stock Alert Setup...")
    
    # Find an inventory item that is near or below its low stock threshold
    q = select(Inventory).order_by(Inventory.total_stock.asc()).limit(1)
    res = await db.execute(q)
    low_stock_product = res.scalar_one_or_none()
    if not low_stock_product:
        print("  ⚠️ Could not find inventory product, skipping low-stock scenario")
        return None

    alert_metadata = json.dumps({
        'product_id': low_stock_product.product_id,
        'product_name': low_stock_product.product_name,
        'current_stock': low_stock_product.total_stock,
        'threshold': low_stock_product.low_stock_threshold,
        'scenario': 'low_stock_alert',
    })

    alert_task = AutomationTask(
        title=f"[TEST] Low Stock Alert: {low_stock_product.product_name}",
        description=f"{low_stock_product.product_name} has only {low_stock_product.total_stock} units remaining (threshold: {low_stock_product.low_stock_threshold}). Reorder needed.",
        task_type=AutomationTaskType.RESTOCK_REQUEST,
        status=AutomationTaskStatus.PENDING,
        task_metadata=alert_metadata,
        priority=1,  # High priority
        created_by_id=users['admin'].id,
    )
    db.add(alert_task)

    print(f"  ✅ Created low-stock alert task for {low_stock_product.product_name}")
    print(f"     → Use: /sale record product={low_stock_product.product_id} qty=3 price=49.99")
    print(f"     → This will reduce stock and may trigger restock automation")

    return alert_task


async def create_scenario_3_task_completion_chain(db, users):
    """
    Scenario 3: Task Completion Unlocking Next Task
    
    Creates a simple 2-task chain to demonstrate completion workflow:
    1. Review order details (pending) 
    2. Approve and process (blocked until #1 completes)
    
    Team can test: /task complete functionality
    """
    print("\n✅ Creating Scenario 3: Task Completion Chain...")
    
    chain_metadata = json.dumps({
        'scenario': 'completion_chain',
        'purpose': 'Demonstrate task unlock on completion',
    })
    
    # Task 1: Review (completable)
    review_task = AutomationTask(
        title='[TEST] Review order details',
        description='Review the order for accuracy before processing',
        task_type=AutomationTaskType.ORDER_REVIEW,
        status=AutomationTaskStatus.PENDING,
        task_metadata=chain_metadata,
        priority=2,
        created_by_id=users['admin'].id,
    )
    db.add(review_task)
    await db.flush()
    
    # Task 2: Approve (blocked)
    approve_task = AutomationTask(
        title='[TEST] Approve and process order',
        description='Final approval and begin fulfillment',
        task_type=AutomationTaskType.ORDER_FULFILLMENT,
        status=AutomationTaskStatus.BLOCKED,
        task_metadata=chain_metadata,
        priority=2,
        created_by_id=users['admin'].id,
        depends_on_task_id=review_task.id,
    )
    db.add(approve_task)
    
    print(f"  ✅ Created 2-task completion chain")
    print(f"     → Complete task {review_task.id} using: /task complete id={review_task.id}")
    print(f"     → Task {approve_task.id} will automatically unblock")
    
    return [review_task, approve_task]


async def print_test_commands(users, products):
    """Print example commands for team testing."""
    print("\n" + "="*60)
    print("📋 EXAMPLE SLASH COMMANDS FOR TESTING")
    print("="*60)
    
    print("\n🔍 DRY-RUN MODE (safe testing - no DB changes):")
    print("─" * 40)
    print("/order create type=AGENT_RESTOCK product=\"Test Item\" amount=10 dry_run=true")
    print("/sale record product=1 qty=5 price=29.99 dry_run=true")
    
    print("\n📦 ORDER COMMANDS (requires agent role):")
    print("─" * 40)
    print("/order create type=AGENT_RESTOCK product=\"Widget A\" amount=20")
    print("/order create type=AGENT_RETAIL product=\"Premium Package\" amount=2")
    
    print("\n💰 SALE COMMANDS (requires agent role):")
    print("─" * 40)
    low_stock = products.get('WIDGET-B')
    if low_stock:
        print(f"/sale record product={low_stock.id} qty=3 price=49.99  # Triggers low-stock!")
    print("/sale record product=1 qty=10 price=29.99 channel=online")
    
    print("\n🔧 AUTOMATION TESTING (requires system_admin):")
    print("─" * 40)
    print("/automation test event=order_created")
    print("/automation test event=sale_recorded")
    print("/automation test event=low_stock_alert")
    
    print("\n✅ TASK COMPLETION:")
    print("─" * 40)
    print("/task complete id=<task_id>")
    print("/task complete id=<task_id> note=\"Verified and approved\"")
    
    print("\n" + "="*60)
    print("💡 TIPS:")
    print("  • Use dry_run=true to preview any command safely")
    print("  • Debug output shows events, tasks, and assignments")
    print("  • Check task dependencies to see unlock chains")
    print("="*60)


async def main():
    """Main function to seed all test scenarios."""
    print("🌱 Seeding Test Scenarios for Slash Commands")
    print("=" * 50)
    
    async with async_session() as db:
        try:
            # Create test users
            print("\n👥 Setting up test users...")
            users = await get_or_create_test_users(db)
            print(f"  ✅ Users: {', '.join(users.keys())}")
            
            # Create test channel
            print("\n📢 Setting up test channel...")
            channel = await get_or_create_test_channel(db, users)
            print(f"  ✅ Channel: {channel.name}")
            
            # Create test products
            print("\n📦 Setting up test products...")
            products = await get_or_create_test_products(db)
            print(f"  ✅ Products: {len(products)} items")

            # Seed inventory with real product entries
            print("\n📦 Seeding inventory items...")
            created_inv = await get_or_create_inventory_seeds(db)
            print(f"  ✅ Inventory seeded: {len(created_inv)} items")
            
            # Create scenarios
            await create_scenario_1_multistep_order(db, users, products)
            await create_scenario_2_low_stock_alert(db, users, products)
            await create_scenario_3_task_completion_chain(db, users)
            
            # Commit all changes
            await db.commit()
            
            # Print example commands
            await print_test_commands(users, products)
            
            print("\n✅ All test scenarios seeded successfully!")
            print("   Team members can now test slash commands with realistic data.")
            
        except Exception as e:
            print(f"\n❌ Error seeding scenarios: {e}")
            await db.rollback()
            raise



if __name__ == '__main__':
    asyncio.run(main())
