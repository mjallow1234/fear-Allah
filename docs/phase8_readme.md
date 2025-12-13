# Phase 8 — Chat scaffolding

This document describes how to run the new chat scaffolding locally.

Backend
- Create/migrate DB:

  ```powershell
  cd backend
  # If using local Postgres (as configured in alembic.ini), run:
  alembic upgrade head
  ```

- Run backend server:

  ```powershell
  # from repo root
  uvicorn app.main:app --reload --port 8000
  ```

Frontend
- Start dev server:

  ```powershell
  cd frontend
  npm install
  npm run dev
  ```

Testing
- Run unit tests (backend):

  ```powershell
  pytest -q backend/tests/test_chat_roundtrip.py
  ```

Manual test
- Open two browser tabs and open the frontend UI, open a channel and send messages. The frontend stub uses a simple WebSocket hook `useChatWs` pointing to `ws://localhost:8000/ws/chat/{id}`.
