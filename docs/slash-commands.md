# Slash Commands Reference

Internal documentation for the slash command system.

---

## Quick Reference

| Command | Action | Required Role | Example |
|---------|--------|--------------|---------|
| `/order` | `create` | agent | `/order create type=AGENT_RESTOCK product="Widget" amount=10` |
| `/sale` | `record` | agent | `/sale record product=1 qty=5 price=29.99` |
| `/automation` | `test` | system_admin | `/automation test event=order_created` |
| `/task` | `complete` | any | `/task complete id=123` |

---

## Commands in Detail

### /order create

Creates a new order and triggers automation workflows.

**Permission:** Agent role (username starts with `agent` or role is `agent`)

**Required Arguments:**
- `type` - Order type: `AGENT_RESTOCK`, `AGENT_RETAIL`, `SHOP_ORDER`, `DIRECT_SALE`
- `product` - Product name or description
- `amount` - Quantity to order

**Optional Arguments:**
- `dry_run=true` - Preview without creating (see [Dry-Run Mode](#dry-run-mode))

**Examples:**
```
/order create type=AGENT_RESTOCK product="Widget A" amount=20
/order create type=AGENT_RETAIL product="Premium Package" amount=5
/order create type=SHOP_ORDER product="Bulk Items" amount=100
```

**Workflow Automation:**

Each order type triggers a specific workflow with multiple tasks:

| Order Type | Workflow Steps |
|------------|---------------|
| AGENT_RESTOCK | Verify inventory → Pack items → Generate label → Notify customer |
| AGENT_RETAIL | Review order → Process payment → Fulfill → Close |
| SHOP_ORDER | Receive → Quality check → Stock → Update inventory |
| DIRECT_SALE | Confirm → Deliver → Collect payment |

---

### /sale record

Records a sale transaction and updates inventory.

**Permission:** Agent role

**Required Arguments:**
- `product` - Product ID (numeric)
- `qty` or `quantity` - Number of units sold
- `price` - Unit price

**Optional Arguments:**
- `channel` - Sales channel (e.g., `online`, `store`, `phone`)
- `dry_run=true` - Preview without recording

**Examples:**
```
/sale record product=1 qty=10 price=29.99
/sale record product=42 qty=5 price=49.99 channel=online
/sale record product=3 quantity=2 price=199.99 channel=store
```

**Automation Triggers:**
- Updates inventory count
- May trigger low-stock alerts if stock falls below threshold
- Records sales metrics

---

### /automation test

Tests automation event triggering (for debugging).

**Permission:** System admin only

**Arguments:**
- `event` or `type` - Event name to test

**Supported Events:**
- `order_created` - Order creation event
- `sale_recorded` - Sale recording event  
- `low_stock_alert` - Inventory alert event
- `task_completed` - Task completion event

**Examples:**
```
/automation test event=order_created
/automation test type=sale_recorded
/automation test low_stock_alert
```

---

### /task complete

Marks a task as completed and unlocks dependent tasks.

**Permission:** Any authenticated user

**Required Arguments:**
- `id` - Task ID to complete

**Optional Arguments:**
- `note` - Completion note or comment

**Examples:**
```
/task complete id=123
/task complete id=456 note="Verified and approved"
```

**Task Dependencies:**
When a task is completed, any tasks that depend on it are automatically unblocked and moved to PENDING status.

---

## Dry-Run Mode

Dry-run mode lets you preview what a command will do **without making any changes** to the database.

### How to Use

Add `dry_run=true` to any supported command:

```
/order create type=AGENT_RESTOCK product="Test" amount=5 dry_run=true
/sale record product=1 qty=10 price=29.99 dry_run=true
```

### What Dry-Run Does

✅ **Validates all input arguments**  
✅ **Checks permissions**  
✅ **Simulates automation workflow**  
✅ **Shows preview of what would happen**

❌ **Does NOT write to database**  
❌ **Does NOT trigger real automations**  
❌ **Does NOT send notifications**

### Example Output

```
🔍 **DRY-RUN PREVIEW** (Order Create)

**Would create order:**
  • Type: AGENT_RESTOCK
  • Product: Widget A
  • Amount: 20

**Workflow would create 4 tasks:**
  1. Verify inventory availability
  2. Pack and prepare items
  3. Generate shipping label
  4. Notify customer of shipment

**Automation Debug Info:**
  • Event: order.created
  • Tasks: 4
  • Assigned to: (simulated)
  • Notifications: 1 queued
  • Dry-run: Yes

✅ Validation passed - ready to execute without dry_run=true
```

### When to Use Dry-Run

- **Learning:** Understand what commands do before using them
- **Testing:** Verify command syntax is correct
- **Team Training:** Demonstrate workflows without side effects
- **Debugging:** Check if validation would pass

---

## Debug Output

Every command now includes automation debug information showing:

| Field | Description |
|-------|-------------|
| Event | The automation event triggered |
| Tasks Created | Number of tasks generated |
| Task Titles | List of task names |
| Assigned To | Users who received assignments |
| Notifications | Number of notifications queued |
| Dry-Run | Whether this was a preview |
| Validation Errors | Any input validation issues |

---

## Role Permissions

### Agent Role

Users with agent permissions can:
- Create orders (`/order create`)
- Record sales (`/sale record`)
- Complete tasks (`/task complete`)

Agent role is granted if:
- Username starts with `agent` (e.g., `agent_sarah`)
- User has `role='agent'` in database

### System Admin Role

System admins have full access including:
- All agent permissions
- Automation testing (`/automation test`)
- Viewing detailed debug output

System admin role is granted if:
- `is_system_admin=true` in database
- User has `role='system_admin'`

### Regular Users

Non-agent users can only:
- Complete tasks assigned to them

They **cannot** use order or sale commands.

---

## Common Errors

### Permission Denied

```
❌ Permission denied
```

**Cause:** User doesn't have required role for the command.

**Solution:** 
- For `/order` and `/sale`: User needs agent role
- For `/automation test`: User needs system_admin role

### Invalid Arguments

```
❌ Invalid arguments: missing type, product or amount
```

**Cause:** Required arguments not provided or invalid.

**Solution:** Check command syntax and provide all required arguments.

### Invalid Order Type

```
❌ Invalid order type
```

**Cause:** Order type not recognized.

**Valid types:** `AGENT_RESTOCK`, `AGENT_RETAIL`, `SHOP_ORDER`, `DIRECT_SALE`

### Task Not Found

```
❌ Task not found
```

**Cause:** Task ID doesn't exist or is already completed.

**Solution:** Verify task ID is correct and task is in PENDING status.

---

## Testing Scenarios

Use the seed script to create test data:

```bash
cd backend
python scripts/seed_test_scenarios.py
```

This creates:

1. **Multi-step workflow** - 4 dependent tasks demonstrating unlock chains
2. **Low-stock scenario** - Product with 5 units to test inventory alerts  
3. **Completion chain** - Simple 2-task chain for testing `/task complete`

### Test Users

| Username | Role | Can Use |
|----------|------|---------|
| `test_admin` | system_admin | All commands |
| `agent_sarah` | agent | order, sale, task |
| `agent_mike` | agent | order, sale, task |
| `customer_john` | customer | None (permission denied) |

---

## Troubleshooting

### Commands Not Working

1. Check you're in a channel (not DM)
2. Verify your user role in the database
3. Use `dry_run=true` to check validation

### Tasks Not Unlocking

1. Verify parent task is COMPLETED (not just PENDING)
2. Check `depends_on_task_id` is set correctly
3. Look for any blocking automation rules

### Debug Output Missing

1. Commands always include debug info now
2. Check the full response message
3. Debug info appears after the success message

---

## API Integration

Slash commands integrate with:

- **Task Engine** - Creates workflow tasks from orders
- **Sales Service** - Records sales and updates inventory
- **Automation Service** - Triggers events and webhooks
- **Audit Log** - Records all command executions

All commands are logged with:
- User who executed
- Arguments provided
- Result (success, error, dry_run)
- Any automation tasks created
