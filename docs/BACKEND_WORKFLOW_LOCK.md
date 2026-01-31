LOCK: Backend workflow logic (Phase 6.*)

"Backend workflow logic is correct and frozen. Do not refactor, extend, or reinterpret it."

Date: 2026-01-31

Scope:
- This note applies to the automation and order-workflow code that drives task lifecycles and notifications.

Key modules (do NOT change without explicit approval from project leads):
- backend/app/services/task_engine.py (WORKFLOWS, order->task creation, task activation/completion)
- backend/app/automation/order_triggers.py (ORDER_TASK_TEMPLATES, order->automation triggers)
- backend/app/automation/service.py (Assignment completion, claim flows, task status updates)
- backend/app/automation/notification_hooks.py (task/order notification hooks)
- backend/app/services/notification_emitter.py (notification emission)

Guidelines:
- Do NOT refactor, extend, or reinterpret the above modules without prior approval.
- Any bug fixes or changes must be small, well-tested, and reviewed by the automation owners.
- Open an issue or contact the code owners before making changes: @project-owners

Verification:
- Before merging any PR which touches the above files, run the full automation test suite (`pytest tests/test_automation.py` and `pytest tests/test_order_automation.py`) and include test results in the PR description.

Purpose:
- Prevent accidental regressions to the workflow rules that implement the multi-step order flows (agent/foreman/delivery/requester patterns described in the project docs and scenarios).

If you believe a change is necessary, open an issue and discuss it with the code owners; do not push unreviewed changes.
