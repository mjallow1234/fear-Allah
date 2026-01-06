# Team Testing Scenarios

Ready-made test scripts for all order and sales workflows. Each team member follows their role's steps.

---

## Test Accounts Setup

| Username | Role | Acts As |
|----------|------|---------|
| `agent1` | agent | Field Agent |
| `agent2` | agent | Field Agent |
| `foreman1` | agent | Foreman (assembles products) |
| `delivery1` | agent | Delivery Guy |
| `storekeeper1` | agent | Store Keeper |
| `customer1` | member | Customer |
| `admin` | system_admin | Admin/Sales Team |

> **Note:** Create these users if they don't exist, or use existing usernames. Tasks are assigned by username.

---

# ORDER SCENARIOS

---

## Scenario 1: Agent Restock

**Flow:** Agent orders → Foreman (2 steps) → Delivery (2 steps) → Agent (1 step) → System marks COMPLETED

| Role | Steps | Button Labels |
|------|-------|---------------|
| Foreman | 2 | "Assembled", "Handed Over For Delivery" |
| Delivery | 2 | "Received from Foreman", "Delivered to Agent" |
| Agent | 1 | "Received" |

### Step 1: Agent Creates Order

**Who:** Field Agent (`agent1`)

```
/order create type=AGENT_RESTOCK product="Cement Bags" amount=50
```

**Expected Response:**
```
✅ Order created (ID: XXX)
Workflow steps: 5
• Assemble Items (Foreman)
• Hand Over to Delivery (Foreman)
• Receive from Foreman (Delivery)
• Deliver to Agent (Delivery)
• Confirm Receipt (Agent)
```

---

### Step 2: Foreman - Assembled

**Who:** Foreman (`foreman1`)

1. Open task from notifications/Task Inbox
2. Click button: **"Assembled"**
3. Add note: "50 cement bags assembled and ready"

**Verify:** Next step becomes ACTIVE

---

### Step 3: Foreman - Handed Over For Delivery

**Who:** Foreman (`foreman1`)

1. Click button: **"Handed Over For Delivery"**
2. Add note: "Products handed to delivery1"

**Accountability:** Records foreman gave products to delivery guy

**Verify:** Delivery guy's step becomes ACTIVE

---

### Step 4: Delivery - Received from Foreman

**Who:** Delivery Guy (`delivery1`)

1. Open task from notifications
2. Click button: **"Received from Foreman"**
3. Add note: "Received 50 bags from foreman1"

**Accountability:** Delivery confirms receipt from foreman

**Verify:** Next delivery step becomes ACTIVE

---

### Step 5: Delivery - Delivered to Agent

**Who:** Delivery Guy (`delivery1`)

1. Click button: **"Delivered to Agent"**
2. Add note: "Delivered to agent1 at location"

**Accountability:** Delivery confirms handover to agent

**Verify:** Agent's step becomes ACTIVE

---

### Step 6: Agent - Received

**Who:** Field Agent (`agent1`)

1. Open task from notifications
2. Click button: **"Received"**
3. Add note: "All 50 bags received in good condition"

**Accountability:** Agent confirms final receipt

**Verify:**
- [ ] All 5 steps show DONE ✓
- [ ] Order status: **COMPLETED**
- [ ] Full accountability chain:
  1. ✓ Foreman: Assembled
  2. ✓ Foreman: Handed Over For Delivery
  3. ✓ Delivery: Received from Foreman
  4. ✓ Delivery: Delivered to Agent
  5. ✓ Agent: Received

---

## Scenario 2: Agent Retail Delivery

**Flow:** Agent orders → Delivery acknowledges → Delivery delivers → Done

### Step 1: Agent Creates Order

**Who:** Field Agent (`agent1`)

```
/order create type=AGENT_RETAIL product="Water Bottles" amount=100 location="Customer Site - 123 Main St"
```

**Expected Response:**
```
✅ Order created (ID: XXX)
Tasks created: 2
• Acknowledge Order (assigned to delivery)
• Deliver Items (assigned to delivery)
```

**Verify:**
- [ ] Order appears in Orders tab
- [ ] 2 tasks created
- [ ] Delivery Guy notified

---

### Step 2: Delivery Acknowledges

**Who:** Delivery Guy (`delivery1`)

```
/task complete id=<TASK_ID> note="Order seen, preparing for delivery"
```

**Expected Response:**
```
✅ Task completed
Task: Acknowledge Order
Status: COMPLETED
Unlocked tasks: 1
• Deliver Items
```

---

### Step 3: Delivery Completes

**Who:** Delivery Guy (`delivery1`)

```
/task complete id=<TASK_ID> note="Delivered to customer at 123 Main St"
```

**Expected Response:**
```
✅ Task completed
Task: Deliver Items
Status: COMPLETED
Order #XXX marked as COMPLETED
```

**Verify:**
- [ ] Order marked COMPLETED
- [ ] All tasks done

---

## Scenario 3: Store Keeper Restock

**Flow:** Store Keeper orders → Foreman assembles → Delivery acknowledges handover → Delivery delivers → Store Keeper confirms

### Step 1: Store Keeper Creates Order

**Who:** Store Keeper (`storekeeper1`)

```
/order create type=STORE_KEEPER_RESTOCK product="Rice Bags 50kg" amount=20
```

**Expected Response:**
```
✅ Order created (ID: XXX)
Tasks created: 4
• Assemble Items (assigned to foreman)
• Acknowledge Handover (assigned to delivery)
• Deliver Items (assigned to delivery)
• Confirm Received (assigned to storekeeper)
```

**Verify:**
- [ ] Order appears in Orders tab
- [ ] 4 tasks created
- [ ] Foreman and Delivery Guy notified

---

### Step 2: Foreman Assembles

**Who:** Foreman (`foreman1`)

1. Open "Assemble Items" task
2. Click "Complete My Assignment"
3. Add note: "20 rice bags assembled"

---

### Step 3: Delivery Acknowledges Handover

**Who:** Delivery Guy (`delivery1`)

1. Open "Acknowledge Handover" task
2. Click "Complete My Assignment"
3. Add note: "Received 20 rice bags from foreman"

**Accountability:** Confirms delivery received products from foreman

---

### Step 4: Delivery Delivers

**Who:** Delivery Guy (`delivery1`)

1. Open "Deliver Items" task
2. Click "Complete My Assignment"
3. Add note: "Delivered to store"

---

### Step 5: Store Keeper Confirms

**Who:** Store Keeper (`storekeeper1`)

1. Open "Confirm Received" task
2. Click "Complete My Assignment"
3. Add note: "All 20 bags received and stored"

**Accountability:** Confirms store keeper received products from delivery

**Verify:**
- [ ] Order marked COMPLETED
- [ ] All 4 tasks COMPLETED
- [ ] Full accountability chain recorded

---

## Scenario 4: Customer Wholesale Order

**Flow:** Customer orders → Foreman assembles → Delivery acknowledges handover → Delivery delivers → Done

### Step 1: Customer Creates Order

**Who:** Customer (`customer1`)

```
/order create type=CUSTOMER_WHOLESALE product="Cooking Oil Cartons" amount=30
```

**Expected Response:**
```
✅ Order created (ID: XXX)
Tasks created: 3
• Assemble Items (assigned to foreman)
• Acknowledge Handover (assigned to delivery)
• Deliver Items (assigned to delivery)
```

**Verify:**
- [ ] Order created
- [ ] 3 tasks created
- [ ] Foreman and Delivery notified

---

### Step 2: Foreman Assembles

**Who:** Foreman (`foreman1`)

1. Open "Assemble Items" task
2. Click "Complete My Assignment"
3. Add note: "30 cartons packed"

**Verify:**
- [ ] Delivery Guy notified (NOT customer for wholesale)

---

### Step 3: Delivery Acknowledges Handover

**Who:** Delivery Guy (`delivery1`)

1. Open "Acknowledge Handover" task
2. Click "Complete My Assignment"
3. Add note: "Received 30 cartons from foreman"

**Accountability:** Confirms delivery received products from foreman

---

### Step 4: Delivery Delivers

**Who:** Delivery Guy (`delivery1`)

1. Open "Deliver Items" task
2. Click "Complete My Assignment"
3. Add note: "Delivered to customer address"

**Verify:**
- [ ] Order marked COMPLETED
- [ ] All tasks COMPLETED
- [ ] System closed automatically (no customer confirmation needed for wholesale)

---

# SALES SCENARIOS

---

## Sales 1: Agent Field Sale

**Who:** Field Agent (`agent1`)

After making a sale in the field:

```
/sale record product="Cement Bag 25kg" qty=10 price=500 channel=field
```

**Expected Response:**
```
✅ Sale recorded
Product: Cement Bags
Quantity: 10
Total: 5000

📊 Inventory Updated:
• Previous stock: 150
• Sold: 10
• New stock: 140

📈 Agent Stats:
• Today's sales: 15
• Today's revenue: 7500
```

**Verify:**
- [ ] Sales team notified
- [ ] Inventory updated
- [ ] Agent's sales count updated
- [ ] Appears in sales reports

---

## Sales 2: Store Keeper Sale

**Who:** Store Keeper (`storekeeper1`)

When a customer buys at the store:

```
/sale record product="Rice Bags 50kg" qty=2 price=2500 channel=store
```

**Expected Response:**
```
✅ Sale recorded
Product: Rice Bags 50kg
Quantity: 2
Total: 5000

📊 Inventory Updated:
• Previous stock: 45
• Sold: 2
• New stock: 43
```

**Verify:**
- [ ] Sales team notified
- [ ] Store inventory updated
- [ ] Store keeper's sales count updated

---

## Sales 3: Direct to Consumer (Post-Delivery)

**Who:** Store Keeper (`storekeeper1`)

After a wholesale delivery is complete, record the sale:

```
/sale record product="Cooking Oil Cartons" qty=30 price=1200 channel=delivery customer="ABC Restaurant"
```

**Expected Response:**
```
✅ Sale recorded
Product: Cooking Oil Cartons
Quantity: 30
Total: 36000
Customer: ABC Restaurant

📊 Inventory Updated:
• Previous stock: 100
• Sold: 30
• New stock: 70
```

**Verify:**
- [ ] Sales team notified
- [ ] Inventory updated
- [ ] Linked to delivery order (if applicable)

---

# QUICK REFERENCE CARDS

Print these for each team member.

---

## 📋 Agent Quick Card

```
ORDER RESTOCK:
/order create type=AGENT_RESTOCK product="<name>" amount=<qty>

ORDER RETAIL:
/order create type=AGENT_RETAIL product="<name>" amount=<qty>

COMPLETE TASK:
/task complete id=<task_id> note="<message>"

RECORD SALE:
/sale record product="<name>" qty=<qty> price=<unit_price>
```

---

## 📋 Foreman Quick Card

```
COMPLETE ASSEMBLY:
/task complete id=<task_id> note="Products assembled and ready"

CHECK MY TASKS:
(Go to Orders tab → filter by assigned to me)
```

---

## 📋 Delivery Guy Quick Card

```
ACKNOWLEDGE ORDER:
/task complete id=<task_id> note="Order received, preparing"

PICKUP COMPLETE:
/task complete id=<task_id> note="Picked up from warehouse"

DELIVERY COMPLETE:
/task complete id=<task_id> note="Delivered to <location>"
```

---

## 📋 Store Keeper Quick Card

```
ORDER RESTOCK:
/order create type=STORE_KEEPER_RESTOCK product="<name>" amount=<qty>

CONFIRM RECEIVED:
/task complete id=<task_id> note="Received and stored"

RECORD SALE (Walk-in):
/sale record product="<name>" qty=<qty> price=<unit_price> channel=store

RECORD SALE (Delivery):
/sale record product="<name>" qty=<qty> price=<unit_price> channel=delivery customer="<name>"
```

---

# TESTING CHECKLIST

## Pre-Test Setup
- [ ] All test users created
- [ ] Inventory seeded with products
- [ ] All team members logged in
- [ ] Everyone in the same channel

## Order Flow Tests

| Scenario | Created | Tasks Generated | All Tasks Completed | Order Closed |
|----------|---------|-----------------|---------------------|--------------|
| Agent Restock | ☐ | ☐ | ☐ | ☐ |
| Agent Retail | ☐ | ☐ | ☐ | ☐ |
| Store Keeper Restock | ☐ | ☐ | ☐ | ☐ |
| Customer Wholesale | ☐ | ☐ | ☐ | ☐ |

## Notification Tests

| Event | Notification Sent | Received By |
|-------|-------------------|-------------|
| Order created | ☐ | Foreman, Delivery |
| Assembly done | ☐ | Delivery, Requester |
| Pickup done | ☐ | Requester |
| Delivery done | ☐ | Requester |

## Sales Flow Tests

| Scenario | Sale Recorded | Inventory Updated | Team Notified |
|----------|---------------|-------------------|---------------|
| Agent Field Sale | ☐ | ☐ | ☐ |
| Store Walk-in Sale | ☐ | ☐ | ☐ |
| Direct to Consumer | ☐ | ☐ | ☐ |

---

# TROUBLESHOOTING

## "Task not found"
- Double-check the task ID
- Ensure the task is assigned to YOUR user
- Check if task is still BLOCKED (dependency not met)

## "Permission denied"
- Verify you're logged in as the correct user
- Check your role allows the command

## "Order type invalid"
Valid types:
- `AGENT_RESTOCK`
- `AGENT_RETAIL`
- `STORE_KEEPER_RESTOCK`
- `CUSTOMER_WHOLESALE`

## "Inventory not updating"
- Check if product name matches exactly
- Verify inventory was seeded for that product
- Check sales team notifications for errors

## Task stuck on BLOCKED
- A dependency task hasn't been completed yet
- Follow the task chain in order
- Check previous task's status

---

# DRY-RUN TESTING

Before running with real data, test with dry-run:

```
/order create type=AGENT_RESTOCK product="Test Product" amount=5 dry_run=true
```

This shows what WOULD happen without creating anything.
