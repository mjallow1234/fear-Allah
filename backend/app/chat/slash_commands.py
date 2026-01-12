import json
from dataclasses import dataclass, field
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.models import AutomationTask, TaskAssignment, User
from app.services.task_engine import create_order
from app.automation.service import AutomationService, trigger_event
from app.services.audit import log_audit_from_user
from types import SimpleNamespace
from app.db.database import AsyncSession
from app.core.config import logger
from app.db.enums import AutomationTaskType


@dataclass
class AutomationDebugInfo:
    """Debug information about automation triggered by a command."""
    event: str = ""
    tasks_created: int = 0
    task_titles: List[str] = field(default_factory=list)
    assigned_to: List[str] = field(default_factory=list)
    notifications_queued: int = 0
    dry_run: bool = False
    validation_errors: List[str] = field(default_factory=list)
    
    def format_message(self) -> str:
        """Format debug info as a user-friendly message."""
        lines = ["📊 **Automation Debug:**"]
        lines.append(f"• Event: `{self.event}`")
        lines.append(f"• Tasks created: {self.tasks_created}")
        if self.task_titles:
            lines.append(f"• Task titles: {', '.join(self.task_titles)}")
        if self.assigned_to:
            lines.append(f"• Assigned to: {', '.join(self.assigned_to)}")
        lines.append(f"• Notifications queued: {self.notifications_queued}")
        lines.append(f"• Dry-run: {str(self.dry_run).lower()}")
        if self.validation_errors:
            lines.append(f"• ⚠️ Validation issues: {', '.join(self.validation_errors)}")
        return "\n".join(lines)


@dataclass
class SlashCommandResult:
    handled: bool = False
    response_message: Optional[str] = None
    error: Optional[str] = None
    debug_info: Optional[AutomationDebugInfo] = None


async def handle_slash_command(*, raw_text: str, user, channel, db: AsyncSession) -> SlashCommandResult:
    """Detects and routes slash commands from chat.

    Returns SlashCommandResult. If handled is True, caller SHOULD NOT persist the message.
    """
    if not raw_text or not raw_text.strip().startswith('/'):
        return SlashCommandResult(handled=False)

    # Parse command with proper quote handling
    import shlex
    try:
        # Use POSIX mode for consistent behavior across platforms
        tokens = shlex.split(raw_text.strip(), posix=True)
    except ValueError:
        # Fallback to simple split if shlex fails (unmatched quotes)
        tokens = raw_text.strip().split()
    
    if not tokens:
        return SlashCommandResult(handled=False)

    cmd = tokens[0][1:]
    action = tokens[1] if len(tokens) > 1 else None
    arg_tokens = tokens[2:]

    # Parse key=value args (quotes already handled by shlex)
    args = {}
    for t in arg_tokens:
        if '=' in t:
            k, v = t.split('=', 1)
            args[k.strip()] = v.strip().strip('"\'')

    result = SlashCommandResult(handled=True)

    try:
        # Route commands
        if cmd == 'order' and action == 'create':
            # Permission: system_admin, agent, storekeeper, or customer can create orders
            username = getattr(user, 'username', '')
            user_role = getattr(user, 'role', None)
            operational_role = getattr(user, 'operational_role', None)
            allowed_roles = ['agent', 'storekeeper', 'customer']
            is_admin = getattr(user, 'is_system_admin', False)
            has_allowed_role = operational_role in allowed_roles or user_role in allowed_roles
            # Backwards-compat: fallback to username prefix if roles are not set (deprecated)
            has_allowed_prefix = any(username.startswith(prefix) for prefix in allowed_roles) if not operational_role else False
            
            if not (is_admin or has_allowed_role or has_allowed_prefix):
                result.error = '❌ Permission denied'
                # Audit
                await log_audit_from_user(db, user, action='slash_command', target_type='order', meta={'args': args, 'result': 'permission_denied'})
                return result

            # Required args: type, product
            order_type = args.get('type')
            product = args.get('product')
            amount = args.get('amount')
            dry_run = args.get('dry_run', '').lower() == 'true'
            
            # Validation
            validation_errors = []
            if not order_type:
                validation_errors.append("missing type")
            if not product:
                validation_errors.append("missing product")
            
            if validation_errors and not dry_run:
                result.error = f"❌ Invalid arguments: {', '.join(validation_errors)}"
                await log_audit_from_user(db, user, action='slash_command', target_type='order', meta={'args': args, 'result': 'invalid_args'})
                return result
            
            # Initialize debug info
            debug_info = AutomationDebugInfo(
                event="order.created",
                dry_run=dry_run,
                validation_errors=validation_errors,
            )
            
            if dry_run:
                # DRY-RUN MODE: Simulate without DB writes
                from app.services.task_engine import WORKFLOWS
                workflow_steps = WORKFLOWS.get(order_type, [])
                
                debug_info.tasks_created = 1 if order_type else 0  # Automation task
                debug_info.task_titles = [f"Restock Order #(preview)"]
                debug_info.notifications_queued = 1  # Order created notification
                
                # Show workflow steps that would be created
                step_titles = [step['title'] for step in workflow_steps]
                
                result.response_message = f"🔍 **DRY-RUN Preview**\n"
                result.response_message += f"Order type: `{order_type}`\n"
                result.response_message += f"Product: `{product}`, Amount: `{amount or 1}`\n"
                result.response_message += f"Workflow steps: {len(workflow_steps)}\n"
                if step_titles:
                    result.response_message += f"• {chr(10).join('→ ' + t for t in step_titles)}\n"
                result.response_message += f"\n{debug_info.format_message()}"
                
                if validation_errors:
                    result.response_message += f"\n\n⚠️ Would fail due to: {', '.join(validation_errors)}"
                
                await log_audit_from_user(db, user, action='slash_command', target_type='order', meta={'args': args, 'result': 'dry_run', 'validation_errors': validation_errors})
                result.debug_info = debug_info
                return result

            # Build metadata
            metadata = json.dumps({'product': product, 'amount': amount})

            order = await create_order(db, order_type, items=product, metadata=metadata, created_by_id=user.id)

            # Get automation tasks for this order with assignments and their users
            q = await db.execute(
                select(AutomationTask)
                .options(
                    selectinload(AutomationTask.assignments).selectinload(TaskAssignment.user)
                )
                .where(AutomationTask.related_order_id == order.id)
            )
            auto_tasks = q.scalars().all()
            
            # Build debug info
            debug_info.tasks_created = len(auto_tasks)
            debug_info.task_titles = [t.title for t in auto_tasks]
            assigned_users = set()
            for task_item in auto_tasks:
                for assign in task_item.assignments:
                    if assign.user:
                        assigned_users.add(assign.user.username)
            debug_info.assigned_to = list(assigned_users)
            debug_info.notifications_queued = 1  # Order created notification

            result.response_message = f"✅ Order created (ID: {order.id})\n\n{debug_info.format_message()}"
            result.debug_info = debug_info
            await log_audit_from_user(db, user, action='slash_command', target_type='order', meta={'args': args, 'result': 'success', 'order_id': order.id, 'automation_count': len(auto_tasks)})
            return result

        if cmd == 'sale' and action == 'record':
            # Import sales service with proper error types
            from app.services.sales import (
                create_sale_from_command,
                SalesError, ValidationError as SalesValidationError,
                ProductNotFoundError, InsufficientStockError, PermissionDeniedError
            )
            
            # Permission check using effective role logic
            # Admin, storekeeper, agent, foreman, member can record sales
            # Delivery and customer are BLOCKED
            username = getattr(user, 'username', '') or ''
            user_role = getattr(user, 'role', None)
            is_admin = getattr(user, 'is_system_admin', False)
            
            # Determine effective role - prefer operational_role
            operational_role = getattr(user, 'operational_role', None)
            if is_admin or user_role == 'system_admin' or user_role == 'team_admin':
                effective_role = 'admin'
            elif operational_role in ('storekeeper', 'agent', 'foreman', 'delivery', 'customer'):
                effective_role = operational_role
            elif user_role in ('storekeeper', 'agent', 'foreman', 'delivery', 'customer'):
                effective_role = user_role
            else:
                # Fallback to username prefix for backwards compatibility (deprecated)
                username_lower = username.lower()
                if username_lower.startswith('storekeeper'):
                    effective_role = 'storekeeper'
                elif username_lower.startswith('agent'):
                    effective_role = 'agent'
                elif username_lower.startswith('foreman'):
                    effective_role = 'foreman'
                elif username_lower.startswith('delivery'):
                    effective_role = 'delivery'
                elif username_lower.startswith('customer'):
                    effective_role = 'customer'
                else:
                    effective_role = 'member'
            
            # Block delivery and customer
            if effective_role in ('delivery', 'customer'):
                result.error = f'❌ Permission denied - {effective_role} role cannot record sales'
                await log_audit_from_user(db, user, action='slash_command', target_type='sale', meta={'args': args, 'result': 'permission_denied', 'effective_role': effective_role})
                return result

            # Parse arguments
            dry_run = args.get('dry_run', '').lower() == 'true'
            product_arg = args.get('product', '').strip('"\'')
            customer_name = args.get('customer', '').strip('"\'') or None
            channel_arg = args.get('channel')
            
            # Parse numeric values with error handling
            try:
                qty = int(args.get('qty') or args.get('quantity') or 0)
            except (ValueError, TypeError):
                result.error = '❌ Invalid quantity format'
                return result
                
            try:
                price = float(args.get('price')) if 'price' in args else None
            except (ValueError, TypeError):
                result.error = '❌ Invalid price format'
                return result
            
            # Basic validation
            if not product_arg:
                result.error = '❌ Missing required: product'
                return result
            if qty <= 0:
                result.error = '❌ Quantity must be greater than 0'
                return result
            if price is None:
                result.error = '❌ Missing required: price'
                return result

            try:
                # Use high-level service function
                sale_result = await create_sale_from_command(
                    session=db,
                    user_id=user.id,
                    product_ref=product_arg,
                    quantity=qty,
                    unit_price=price,
                    channel=channel_arg,
                    customer_name=customer_name,
                    dry_run=dry_run,
                )
                
                if dry_run:
                    # DRY-RUN response
                    preview_lines = [
                        f"🔍 **DRY-RUN PREVIEW** (Sale Record)",
                        f"",
                        f"**Would record sale:**",
                        f"  • Product: {sale_result.product_name}",
                        f"  • Quantity: {sale_result.quantity}",
                        f"  • Unit Price: ${sale_result.unit_price:.2f}",
                        f"  • Total: ${sale_result.total_amount:.2f}",
                        f"  • Channel: {sale_result.channel}",
                        f"",
                        f"📊 **Inventory Impact:**",
                        f"  • Stock before: {sale_result.stock_before}",
                        f"  • Stock after: {sale_result.stock_after}",
                    ]
                    if customer_name:
                        preview_lines.insert(7, f"  • Customer: {customer_name}")
                    preview_lines.append(f"")
                    preview_lines.append(f"✅ Validation passed - ready to execute without dry_run=true")
                    result.response_message = "\n".join(preview_lines)
                    await log_audit_from_user(db, user, action='slash_command', target_type='sale', meta={'args': args, 'result': 'dry_run'})
                    return result
                
                # SUCCESS response
                response_lines = [
                    f"✅ **Sale recorded** (ID: {sale_result.sale_id})",
                    f"",
                    f"**Product:** {sale_result.product_name}",
                    f"**Quantity:** {sale_result.quantity}",
                    f"**Unit Price:** ${sale_result.unit_price:.2f}",
                    f"**Total:** ${sale_result.total_amount:.2f}",
                    f"**Channel:** {sale_result.channel}",
                ]
                if customer_name:
                    response_lines.append(f"**Customer:** {customer_name}")
                response_lines.append(f"")
                response_lines.append(f"📊 **Inventory Updated:**")
                response_lines.append(f"  • Previous stock: {sale_result.stock_before}")
                response_lines.append(f"  • Sold: {sale_result.quantity}")
                response_lines.append(f"  • New stock: {sale_result.stock_after}")
                
                result.response_message = "\n".join(response_lines)
                await log_audit_from_user(db, user, action='slash_command', target_type='sale', meta={'args': args, 'result': 'success', 'sale_id': sale_result.sale_id})
                return result
                
            except ProductNotFoundError as e:
                result.error = f'❌ Product not found: {e}'
                await log_audit_from_user(db, user, action='slash_command', target_type='sale', meta={'args': args, 'result': 'product_not_found', 'error': str(e)})
                return result
                
            except InsufficientStockError as e:
                result.error = f'❌ Insufficient stock: {e}'
                await log_audit_from_user(db, user, action='slash_command', target_type='sale', meta={'args': args, 'result': 'insufficient_stock', 'error': str(e)})
                return result
                
            except SalesValidationError as e:
                result.error = f'❌ Invalid input: {e}'
                await log_audit_from_user(db, user, action='slash_command', target_type='sale', meta={'args': args, 'result': 'validation_error', 'error': str(e)})
                return result
                
            except SalesError as e:
                result.error = f'❌ Sale failed: {e}'
                logger.error(f"[Sales] Sale command failed: {e}")
                await log_audit_from_user(db, user, action='slash_command', target_type='sale', meta={'args': args, 'result': 'error', 'error': str(e)})
                return result

        if cmd == 'automation' and action == 'test':
            # Permission: system_admin only
            if not (getattr(user, 'is_system_admin', False) or getattr(user, 'role', None) == 'system_admin'):
                result.error = '❌ Permission denied'
                await log_audit_from_user(db, user, action='slash_command', target_type='automation', meta={'args': args, 'result': 'permission_denied'})
                return result

            event = args.get('event') or (arg_tokens[0] if arg_tokens else None) or args.get('type')
            # Allow /automation test <event> as second token
            if not event:
                # maybe form: /automation test order_created
                if len(tokens) >= 3:
                    event = tokens[2]

            if not event:
                result.error = '❌ Invalid arguments: missing event'
                await log_audit_from_user(db, user, action='slash_command', target_type='automation', meta={'args': args, 'result': 'invalid_args'})
                return result

            context = {
                'user_id': user.id,
                'channel_id': channel.id if channel else None,
                'source': 'slash_command',
            }

            # Use module-level trigger_event helper (tests monkeypatch this function)
            # Import at runtime so tests can monkeypatch app.automation.service.trigger_event
            from app import automation
            # Dry-run for test commands: do not mutate DB
            await automation.service.trigger_event(db, event, context, dry_run=True)

            result.response_message = f"✅ Automation event triggered: {event}"
            await log_audit_from_user(db, user, action='slash_command', target_type='automation', meta={'args': args, 'result': 'success', 'event': event})
            return result

        # Task commands
        if cmd == 'task' and action == 'complete':
            # expected arg: id (assignment id)
            try:
                assignment_id = int(args.get('id')) if 'id' in args else None
            except Exception:
                assignment_id = None

            if not assignment_id:
                result.error = '❌ Invalid arguments: missing id'
                await log_audit_from_user(db, user, action='slash_command', target_type='task', meta={'args': args, 'result': 'invalid_args'})
                return result

            from app.db.database import async_session
            
            # Look up assignment using a fresh session to handle snapshot isolation
            async with async_session() as check_s:
                q = await check_s.execute(select(TaskAssignment).where(TaskAssignment.id == assignment_id))
                other = q.scalar_one_or_none()
                if other:
                    assignment = SimpleNamespace(id=other.id, task_id=other.task_id, user_id=other.user_id)
                else:
                    assignment = None

            if not assignment:
                result.error = '❌ Invalid task assignment id'
                await log_audit_from_user(db, user, action='slash_command', target_type='task', meta={'args': args, 'result': 'invalid_args'})
                return result

            # Permission: only assignee or system_admin can complete
            if not (getattr(user, 'is_system_admin', False) or assignment.user_id == user.id):
                result.error = '❌ Permission denied'
                await log_audit_from_user(db, user, action='slash_command', target_type='task', meta={'args': args, 'result': 'permission_denied'})
                return result

            # Complete the assignment via AutomationService
            # Use a fresh session to ensure visibility (handles session isolation in tests)
            try:
                async with async_session() as work_session:
                    await AutomationService.complete_assignment(db=work_session, task_id=assignment.task_id, user_id=user.id, assignment_id=assignment.id)
                result.response_message = f"✅ Task assignment {assignment_id} completed"
                await log_audit_from_user(db, user, action='slash_command', target_type='task', meta={'args': args, 'result': 'success', 'assignment_id': assignment_id})
                return result
            except Exception as e:
                logger.error(f"[Slash] complete_assignment failed: {e}")
                result.error = f"❌ Error completing task: {str(e)}"
                await log_audit_from_user(db, user, action='slash_command', target_type='task', meta={'args': args, 'result': 'error', 'error': str(e)})
                return result

        # Unknown command - not handled
        return SlashCommandResult(handled=False)

    except Exception as e:
        # Log audit with error
        await log_audit_from_user(db, user, action='slash_command', target_type=cmd if cmd else 'slash', meta=json.dumps({'args': args, 'error': str(e)}))
        result.error = f"❌ Error: {str(e)}"
        return result
