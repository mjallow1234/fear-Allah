This directory contains helpful test scripts used during development, including WebSocket & presence tests. These scripts are intended for local/in-cluster testing and diagnostic automation.

Archived logs are placed in `scripts/archive/` to keep the top-level directory clean.

Do not commit production secrets or tokens into these scripts or log files.

Validation:
- Run `python scripts/check_no_debug_prints.py` to ensure there are no leftover `[presence-debug]` debug prints in the repository (it exits non-zero if forbidden traces are found).

Verification:
- `verify_backend_ghcr.ps1` — PowerShell helper to validate GHCR integration for the backend (checks `ghcr-pull-secret`, compares deployment image with expected GHCR image, attempts a test pull, and shows backend pod logs).

Usage:
PowerShell:
```powershell
.\scripts\verify_backend_ghcr.ps1 -namespace fear-allah -deployment backend -owner mjallow1234 -imageName fearallah-backend -tag latest
```

