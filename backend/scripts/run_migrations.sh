#!/bin/bash
set -e
cd /app
alembic upgrade head
