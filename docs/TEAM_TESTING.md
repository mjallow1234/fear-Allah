# Team Testing Guide

Step-by-step scripts for testing slash commands and automation workflows.

---

## Prerequisites

- Backend running with seeded data (`python scripts/seed_demo_data.py`)
- Frontend running and logged in
- User account with appropriate role (see each scenario)

---

## Scenario 1 — Order → Tasks

**Role Required:** Agent (username starts with `agent` or role = `agent`)

### Steps

1. **Open any channel** (e.g., #general)

2. **Run the slash command:**
   ```
   /order create type=AGENT_RESTOCK product="Test Widget" amount=5
   ```

3. **Observe the response** in chat

4. **Navigate to Orders tab** (sidebar)

5. **Verify the order appears** in the list

### ✅ Expected Success Output

```
┌─────────────────────────────────────────────────┐
│ ✅ SUCCESS                                       │
├─────────────────────────────────────────────────┤
│ ✅ Order created (ID: 123)                       │
│                                                 │
│ 📊 Automation Debug:                            │
│ • Event: order.created                          │
│ • Tasks created: 1                              │
│ • Task titles: Restock Order #123               │
│ • Assigned to: (users)                          │
│ • Notifications queued: 1                       │
│ • Dry-run: false                                │
└─────────────────────────────────────────────────┘
```

**What to verify:**
- [ ] Green success container in chat
- [ ] Order ID is shown
- [ ] Tasks created count > 0
- [ ] Order appears in Orders tab without page refresh
- [ ] "Recent Automation Events" panel shows the event

### ❌ What Failure Looks Like

**Permission denied:**
```
┌─────────────────────────────────────────────────┐
│ ❌ ERROR                                         │
├─────────────────────────────────────────────────┤
│ ❌ Permission denied                             │
└─────────────────────────────────────────────────┘
```
→ **Fix:** Log in as an agent user (username starting with `agent`)

**Invalid arguments:**
```
┌─────────────────────────────────────────────────┐
│ ❌ ERROR                                         │
├─────────────────────────────────────────────────┤
│ ❌ Invalid arguments: missing type, product      │
└─────────────────────────────────────────────────┘
```
→ **Fix:** Include all required arguments: `type`, `product`

**Invalid order type:**
```
┌─────────────────────────────────────────────────┐
│ ❌ ERROR                                         │
├─────────────────────────────────────────────────┤
│ ❌ Invalid order type                            │
└─────────────────────────────────────────────────┘
```
→ **Fix:** Use valid type: `AGENT_RESTOCK`, `AGENT_RETAIL`, `STORE_KEEPER_RESTOCK`, `CUSTOMER_WHOLESALE`

---

## Scenario 2 — Task Chaining

**Role Required:** Any authenticated user (task must be assigned to you)

### Setup

First, create an order to generate tasks (see Scenario 1), or use seeded test data.

### Steps

1. **Find your assigned task ID** from:
   - Orders tab → Order details → Tasks section
   - Or from the "Recent Automation Events" panel

2. **Run the complete command:**
   ```
   /task complete id=<task_id>
   ```
   Example:
   ```
   /task complete id=42
   ```

3. **Observe the response**

4. **Check if dependent tasks unlocked**

### ✅ Expected Success Output

```
┌─────────────────────────────────────────────────┐
│ ✅ SUCCESS                                       │
├─────────────────────────────────────────────────┤
│ ✅ Task completed                                │
│                                                 │
│ Task: Verify inventory availability             │
│ Status: COMPLETED                               │
│                                                 │
│ Unlocked tasks: 1                               │
│ • Pack and prepare items                        │
└─────────────────────────────────────────────────┘
```

**What to verify:**
- [ ] Green success container
- [ ] Task status changed to COMPLETED
- [ ] Dependent tasks (if any) now show as PENDING instead of BLOCKED
- [ ] Order progress updated

### ❌ What Failure Looks Like

**Task not found:**
```
┌─────────────────────────────────────────────────┐
│ ❌ ERROR                                         │
├─────────────────────────────────────────────────┤
│ ❌ Invalid task assignment id                    │
└─────────────────────────────────────────────────┘
```
→ **Fix:** Verify the task ID exists and is assigned to you

**Missing ID:**
```
┌─────────────────────────────────────────────────┐
│ ❌ ERROR                                         │
├─────────────────────────────────────────────────┤
│ ❌ Invalid arguments: missing id                 │
└─────────────────────────────────────────────────┘
```
→ **Fix:** Include the task ID: `/task complete id=123`

**Permission denied:**
```
┌─────────────────────────────────────────────────┐
│ ❌ ERROR                                         │
├─────────────────────────────────────────────────┤
│ ❌ Permission denied                             │
└─────────────────────────────────────────────────┘
```
→ **Fix:** You can only complete tasks assigned to you (unless you're system_admin)

---

## Scenario 3 — Automation Preview (Dry-Run)

**Role Required:** System Admin

### Steps

1. **Open any channel**

2. **Run the automation test command:**
   ```
   /automation test event=order_created
   ```

3. **Observe the dry-run preview**

4. **Verify NO database changes occurred**

### ✅ Expected Success Output

```
┌─────────────────────────────────────────────────┐
│ 🔍 DRY-RUN PREVIEW                              │
├─────────────────────────────────────────────────┤
│ 🔍 Automation test triggered                     │
│                                                 │
│ Event: order_created                            │
│ Context: test mode                              │
│                                                 │
│ 📊 Automation Debug:                            │
│ • Event: order_created                          │
│ • Tasks created: 0 (simulated)                  │
│ • Notifications queued: 0                       │
│ • Dry-run: true                                 │
└─────────────────────────────────────────────────┘
```

**What to verify:**
- [ ] Blue dry-run container (not green)
- [ ] "DRY-RUN PREVIEW" header
- [ ] `Dry-run: true` in debug info
- [ ] NO new orders in Orders tab
- [ ] NO new tasks created
- [ ] Event appears in "Recent Automation Events" with "Dry-Run" badge

### Alternative: Order Dry-Run

You can also test order creation in dry-run mode:

```
/order create type=AGENT_RESTOCK product="Test" amount=10 dry_run=true
```

**Expected output:**
```
┌─────────────────────────────────────────────────┐
│ 🔍 DRY-RUN PREVIEW                              │
├─────────────────────────────────────────────────┤
│ 🔍 **DRY-RUN Preview**                          │
│ Order type: AGENT_RESTOCK                       │
│ Product: Test, Amount: 10                       │
│ Workflow steps: 4                               │
│ → Assemble Items                                │
│ → Pickup Items                                  │
│ → Deliver Items                                 │
│ → Confirm Received                              │
│                                                 │
│ 📊 Automation Debug:                            │
│ • Event: order.created                          │
│ • Tasks created: 1                              │
│ • Dry-run: true                                 │
│                                                 │
│ ✅ Validation passed - ready to execute         │
└─────────────────────────────────────────────────┘
```

### ❌ What Failure Looks Like

**Permission denied:**
```
┌─────────────────────────────────────────────────┐
│ ❌ ERROR                                         │
├─────────────────────────────────────────────────┤
│ ❌ Permission denied                             │
└─────────────────────────────────────────────────┘
```
→ **Fix:** Log in as system_admin user

**Missing event:**
```
┌─────────────────────────────────────────────────┐
│ ❌ ERROR                                         │
├─────────────────────────────────────────────────┤
│ ❌ Invalid arguments: missing event              │
└─────────────────────────────────────────────────┘
```
→ **Fix:** Include the event type: `/automation test event=order_created`

---

## Quick Reference

### Command Syntax

| Command | Required Args | Optional Args |
|---------|--------------|---------------|
| `/order create` | `type`, `product` | `amount`, `dry_run=true` |
| `/sale record` | `product`, `qty`, `price` | `channel`, `dry_run=true` |
| `/task complete` | `id` | `note` |
| `/automation test` | `event` | — |

### Valid Order Types

- `AGENT_RESTOCK`
- `AGENT_RETAIL`
- `STORE_KEEPER_RESTOCK`
- `CUSTOMER_WHOLESALE`

### Test Users (from seed data)

| Username | Role | Can Use |
|----------|------|---------|
| `admin` | system_admin | All commands |
| `agent1` | agent | `/order`, `/sale`, `/task` |
| `agent2` | agent | `/order`, `/sale`, `/task` |
| `support1` | member | `/task` (assigned only) |
| `viewer1` | member | `/task` (assigned only) |

### Response Color Guide

| Color | Meaning |
|-------|---------|
| 🟢 Green | Success - changes committed |
| 🔵 Blue | Dry-run - preview only, no changes |
| 🔴 Red | Error - command failed |

---

## Troubleshooting

### "Orders tab not updating"

1. Check browser console for errors
2. Verify the response shows "Order created"
3. Try manual refresh button on Orders page

### "Tasks not showing"

1. Orders are created but tasks may not be assigned to your user
2. Check as admin to see all tasks
3. Verify workflow configuration for the order type

### "Automation debug section missing"

1. Click "Automation Debug (click to expand)" to show details
2. Some commands may not produce debug output
3. Check if command succeeded (green container)

### "Recent events not appearing"

1. Events panel only shows events from current session
2. Page refresh clears all events
3. Only slash command responses are tracked
