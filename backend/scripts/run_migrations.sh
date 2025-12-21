#!/bin/bash
set -e
cd /app
# Run migrations but do not fail startup if migrations error out in dev
if ! alembic upgrade head; then
	echo "alembic upgrade failed; continuing in dev mode"
fi
