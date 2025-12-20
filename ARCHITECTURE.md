# WebSocket Architecture — Chat and Presence

This document explains the architecture, ownership, and operational rules for the real-time WebSocket system in this repository. It focuses on the strict separation between the chat WebSocket (per-channel) and the presence WebSocket (global presence & admin broadcasts), ownership rules for client-side components and backend services, forbidden patterns to avoid regressions, and the historical rationale behind these choices.

---

## Overview

We run two separate real-time channels:

- **Chat WS** — Per-channel messaging and typing/reaction/file events. Owned by the frontend `ChatSocketProvider` and by the backend `ConnectionManager` (channel connections table).
- **Presence WS** — Global presence and low-volume global events (e.g., `presence_update`, `presence_list`, and administrative broadcasts such as `channel_created`). Implemented in `usePresence()` on the frontend and broadcast via the backend presence broadcaster.

This strict separation enables robust reconnection strategies, avoids interdependent reconnect loops, and makes ownership clear for feature authors.

---

## Key Files & Components (quick reference)

- Frontend
  - Chat socket provider: `frontend/src/contexts/ChatSocketContext.tsx` (the authoritative Chat WS owner)
  - Presence hook: `frontend/src/services/useWebSocket.ts` → `usePresence()` (global presence + event dispatch)
  - Sidebar event hook: `Sidebar.tsx` subscribes to presence event handlers (`presence.onEvent(...)`) to receive `channel_created` updates
- Backend
  - WebSocket manager / connection layer: `backend/app/api/ws.py` — `ConnectionManager` manages channel connections, presence subscribers, and `broadcast_presence()`
  - Channels API: `backend/app/api/channels.py` — creates channels, adds creator as member, and calls `ws_manager.broadcast_presence({ type: 'channel_created', channel })`

---

## ChatSocketProvider — Ownership & Lifecycle

Responsibilities
- Owns the WebSocket used for chat (one connection per active channel).
- Manages connect/disconnect, heartbeat (25s), backoff reconnect policy, and local typing-users state.
- Exposes an API for consumers: connectChannel, sendMessage, sendTyping, sendReaction, onMessage, reconnect.
- Cleans up sockets and timers on unmount or token removal.

Lifecycle Rules
- Connect only when a valid token and channel id are present.
- If a connection for the same channel is already OPEN, do not reconnect.
- On network close or error, schedule backoff-based reconnects (exponential backoff with jitter, capped). Reconnect only when the channel is still current.
- Heartbeat must be cleared on close/unmount.
- Externally: use `useChatSocket()` only inside `ChatSocketProvider`. The provider is the single, authoritative owner of the chat WebSocket.

Why this matters
- Avoids reconnection storms and flapping when network or auth state changes.
- Prevents multiple components from racing to open/close the same socket.

---

## Presence WS — Ownership & Purpose

Responsibilities
- Global presence (online/offline), presence lists, presence updates, and low-frequency global broadcasts (e.g., `channel_created`).
- Exposes `onEvent(handler)` to register handlers for presence events; it is not intended for message-level chat traffic.

Rules
- Presence connection is started and managed by `usePresence()` and is global to the app.
- Presence must be used to broadcast and listen for presence-style events only. Do not piggy-back high-volume chat messages through presence.

Why separate from chat
- Presence messages and chat messages have different scaling, semantics, and reconnection behaviour.
- Separation prevents presence flapping from causing chat WS reconnect cycles.

---

## Explicit Ownership Rules (short checklist)

- Chat WS
  - Owner: `ChatSocketProvider` (frontend)
  - Only this provider may open/close chat sockets for channel messaging.
  - Backoff & heartbeat logic belong to the provider.

- Presence WS
  - Owner: `usePresence()` (frontend)
  - All presence subscriptions go through `onEvent()` handlers.

- Backend
  - `ConnectionManager` implements per-channel connection sets and presence subscribers.
  - `broadcast_presence()` is the authorized mechanism for global broadcasts.

Enforcement: if you need to implement a feature that requires notifying clients, prefer broadcasting relevant events via presence (low-volume events like `channel_created`) rather than reinventing per-component socket wiring.

---

## Communication Contracts (examples)

- channel_created (broadcast via presence)
  ```json
  { "type": "channel_created", "channel": { "id": 123, "name": "foo", "display_name": "Foo" } }
  ```

- Typing and message (chat WS)
  - Typing start/stop: `{ "type": "typing_start" }` / `{ "type": "typing_stop" }`
  - Message send: `{ "type": "message", "content": "...", "timestamp": "..." }`

Document and test any message schema changes — backwards compatibility matters for running clients.

---

## Forbidden Patterns (Do NOT)

- Do NOT tie the chat WebSocket lifecycle to the presence WebSocket. (For example: do not close or reopen the chat socket in response to presence reconnects.)
- Do NOT reuse a single socket instance for both presence and chat messages. Keep them separate physically and conceptually.
- Do NOT call `window.location.reload()` to force UI updates on real-time events. Use event-driven updates (insert channel into sidebar and navigate programmatically).
- Do NOT let multiple components independently open the same channel WS — only the `ChatSocketProvider` should manage that connection.
- Do NOT silence or swallow WebSocket errors — log and classify them, then handle with backoff or graceful fallbacks.
- Do NOT remove heartbeats or backoff logic to "fix" flaky reconnects — that usually hides the problem and causes greater instability.

These prohibitions were derived from explicit regressions and flapping behavior observed in past incidents (see Historical Context below).

---

## Testing & Verification Guidance

- E2E tests should validate:
  - Create Channel flow (admin): POST `/api/channels` produces `201`, UI closes modal, sidebar inserts the channel and navigates there without reload.
  - Create Channel blocked (non-admin): UI shows disabled '+' and correct tooltip.
  - Chat WS stability: ensure the chat WS does not reconnect repeatedly when presence updates happen (we have `chat-ws-stability.spec.ts` covering this).
- Unit tests: ensure `usePresence()` dispatches events to subscribers (e.g., Sidebar unit test that injects `channel_created`).
- Backend tests: ensure `create_channel` endpoint adds creator as member and calls `broadcast_presence()`.

---

## Historical Context (why this architecture exists)

Early in development we experimented with a unified real-time connection to simplify wiring. This introduced several hard-to-observe failures:

- **Reconnection loops**: presence reconnects (short lived) caused the chat lifecycle to re-evaluate and reconnect immediately, producing exponential reconnect storms during network instability.
- **Flapping presence updates**: noisy presence-refresh traffic caused UI flicker and unintended navigation or socket churn.
- **Race conditions during auth changes**: a global socket sometimes attempted token refreshes while a channel socket was still open, leading to unauthorized closures.

To address these, we moved to a *separation of concerns* model:
- **Per-channel Chat WS** for high-volume, latency-sensitive messaging with aggressive backoff and heartbeats
- **Global Presence WS** for presence lists and administrative broadcasts (low-frequency)

This model has proven more stable in tests and CI and allows independent tuning of reconnect and heartbeat policies.

---

## How to Add or Change Behavior (short guide)

- Need a new global notification (e.g., channel created, feature toggle)? Broadcast via `broadcast_presence()` from the backend and consume via `usePresence().onEvent(...)` in frontend components that need it.
- Need to add chat-level messages? Add new chat message types and implement handling in `ChatSocketProvider`'s onmessage dispatch and listener registration via `onMessage()`.
- When adding tests, include an E2E path that validates: server action → WebSocket broadcast → UI update (no reload).

---

## Appendix: Tests & Files of Interest

- Frontend E2E: `frontend/tests/e2e/create-channel.spec.ts`, `frontend/tests/e2e/chat-ws-stability.spec.ts`
- Frontend: `frontend/src/contexts/ChatSocketContext.tsx`, `frontend/src/services/useWebSocket.ts` (presence)
- Backend: `backend/app/api/ws.py` (ConnectionManager), `backend/app/api/channels.py` (POST /api/channels & broadcast)

---

If you want, I can add a short README badge or note linking to this file in the repo README so feature authors discover this guidance when touching the real-time codepaths. ✨
