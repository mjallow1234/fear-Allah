# DB Changes and Operational Notes (Enum Normalization and Admin/Test User Updates)

This document records the ad-hoc operational DB changes performed during PHASE 6 verification and the accompanying tests.

## Overview
- Problem: The PostgreSQL database used by the backend did not contain lowercase labels for enumerated types used by the application. Inserts from the app were using lowercase enum labels (e.g., 'online'), while the Postgres enum types only had uppercase labels, which caused errors (e.g., "invalid input value for enum userstatus: 'offline'").
- Fix: Added lowercase enum labels and normalized existing rows, then altered columns to the enum types. Backend deployment was restarted to clear prepared-statement caches.

## SQL Changes Applied (idempotent)
The following SQL blocks were executed inside the Postgres pod to add lowercase labels if missing and to normalize existing rows. They are idempotent (safe to re-run):

```sql
DO $$ BEGIN
  ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'online';
  ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'offline';
  ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'away';
EXCEPTION WHEN duplicate_object THEN NULL; END; $$;

DO $$ BEGIN
  ALTER TYPE channeltype ADD VALUE IF NOT EXISTS 'direct';
  ALTER TYPE channeltype ADD VALUE IF NOT EXISTS 'public';
  ALTER TYPE channeltype ADD VALUE IF NOT EXISTS 'private';
EXCEPTION WHEN duplicate_object THEN NULL; END; $$;

DO $$ BEGIN
  ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'member';
  ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'team_admin';
  ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'system_admin';
  ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'guest';
EXCEPTION WHEN duplicate_object THEN NULL; END; $$;
```

Additionally, the values in relevant tables were normalized, e.g.:

```sql
UPDATE users SET status = lower(status)::userstatus WHERE status <> lower(status);
UPDATE channels SET type = lower(type)::channeltype WHERE type <> lower(type);
```

After applying the changes, the backend deployment was restarted to clear any prepared-statement cache that might conflict with schema changes.

To build and push the backend image to GHCR:

```bash
docker build -t ghcr.io/<OWNER>/fearallah-backend:latest ./backend
docker push ghcr.io/<OWNER>/fearallah-backend:latest
kubectl -n fear-allah set image deployment/backend backend=ghcr.io/<OWNER>/fearallah-backend:latest
kubectl -n fear-allah rollout status deployment/backend
```

## Alembic Migration
A new migration was added under `backend/alembic/versions/006_normalize_enum_lowercase.py` that performs the idempotent `ALTER TYPE ... ADD VALUE IF NOT EXISTS` operations for enums. It does not remove labels on downgrade.

## Admin & Test User Modifications
- `admin@fearallah.com` was confirmed to exist and its password was safely reset using bcrypt generated locally (the script used base64 + convert approach to avoid quoting issues when writing to the DB inside the Postgres pod). The `is_system_admin` and `is_active` flags remain set to `true`.
- Created test users during the tests:
  - `testuser1` (id 6), used to test DMs and presence.
  - `testuser2` (id 7), created during the Admin endpoint test script and later banned/unbanned for verification.

## Test Artifacts and Results
- WebSocket presence testing: Verified `/ws/presence` accepts a `token` and returns `presence_update` and `presence_list` events. Workflows validated: connect, broadcast presence, disconnect, offline broadcast.
- Chat WS testing: Verified `/ws/chat/{channel_id}` performs message broadcast, mention notifications, and triggers `message` events to connected clients. Message caching in Redis (key: `messages:{channel_id}`) was observed.
- Redis checks: `user:{id}` keys hold `status` entries with TTL ~300 seconds after presence connects. Typing sets `typing:{channel_id}` were created with short TTL (5s) and cleared shortly after typing stops.
- Notification persistence: Notifications were created in Postgres (`notifications` table) for mentions and delivered in real-time.

## How to Reproduce
1. Ensure the backend is port-forwarded: `kubectl -n fear-allah port-forward svc/backend 8000:8000`.
2. Run `scripts/admin_endpoint_tests.ps1` with the admin token (`$env:ADMIN_TOKEN`) set to run admin endpoint validations.
3. Run `python scripts/presence_timeline_test.py --admin-email admin@fearallah.com --admin-pass <password> --user-email testuser1@example.com --user-pass <password> --channel 5 --duration 60` to reproduce presence and Redis timeline checks. The script writes to `scripts/presence_timeline_output.json`.

## Notes & Next Steps
- The presence timeline test showed timing/race conditions. The server writes `status=online` to Redis on connect and sets `offline` on disconnect; polls may see `offline` if they happen before the write completes. No evidence of stale `offline` while connections remain open was found in the tests.
 - For debugging: temporary server-side debug logs were added locally to capture timing around `set_user_status` and later removed. Historical debug traces were archived under `scripts/archive/` in the repository; the main codebase no longer contains debug prints.
- Consider adding an Alembic migration to always include lowercase labels (already added) and include any additional normalization needed for existing rows.

## Example SQL snippets
Examples of SQL used:

```sql
UPDATE users SET status = lower(status)::userstatus WHERE status <> lower(status);
ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'online';
```

## Authors / Operators
- Changes made by the testing operator using `kubectl` and in-development scripts.
