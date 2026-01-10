# Full System Reset

⚠️ **Destructive action — this will erase ALL application data** ⚠️

This procedure drops and recreates the application database so the system behaves like a fresh install (onboarding can then create the first team).

## Preconditions
- This assumes a Docker Compose environment with a `backend` service and a running Postgres service.
- The database connection is derived from the `DATABASE_URL` env var in `backend/app/core/config.py`.
- If `APP_ENV=production`, set `FORCE_RESET=true` **explicitly** to allow the reset.

## Steps (VPS)
1. Stop and remove containers and volumes (this will remove service data and volumes):

   ```bash
   docker compose down -v
   ```

2. Start only the `postgres` service so it accepts connections:

   ```bash
   docker compose up -d postgres
   ```

3. Run the reset script inside a temporary backend container (the script will read connection info from `DATABASE_URL`):

   ```bash
   docker compose run --rm backend python /app/scripts/reset_db.py
   ```

   If your deployment uses `APP_ENV=production` for the backend, you **must** pass `FORCE_RESET=true` in the environment (for safety):

   ```bash
   docker compose run --rm -e FORCE_RESET=true backend python /app/scripts/reset_db.py
   ```

4. Start the rest of the services (this should run migrations on startup if configured):

   ```bash
   docker compose up -d
   ```

5. Verify:
   - Login to the site
   - POST /api/onboarding/first-team should return **201** for the first user
   - No 403 is expected when the DB is freshly created

## Important notes & safety
- This procedure is *destructive* — it will remove **all** data in the application DB.
- Do **NOT** run on a production database unless you understand the consequences and have backups.
- The script refuses to run when `APP_ENV=production` unless `FORCE_RESET=true` is present in the environment to avoid accidental data loss.

## Files added
- `backend/scripts/reset_db.py` — script that drops & recreates the database (reads `DATABASE_URL`)
- `backend/scripts/reset-entrypoint.sh` — Docker-friendly wrapper to run the script

---

Commit message used: `chore(reset): add full database reset script for clean onboarding`
