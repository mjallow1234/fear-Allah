# fear-Allah API Documentation

## Base URL
- Local: `http://localhost:8000`
- Production: `http://localhost:9080`

## Authentication

### Register
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword",
  "username": "username"
}
```

**Response:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "username",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Login
```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=securepassword
```

**Response:**
```json
{
  "access_token": "jwt_token",
  "token_type": "bearer"
}
```

## Teams

### Create Team
```http
POST /api/teams/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "My Team",
  "display_name": "My Team",
  "description": "Team description"
}
```

### List Teams
```http
GET /api/teams/
Authorization: Bearer <token>
```

## Channels

### Create Channel
```http
POST /api/channels/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "general",
  "display_name": "General",
  "team_id": 1,
  "type": "public"
}
```

### List Channels
```http
GET /api/channels/?team_id={team_id}
Authorization: Bearer <token>
```

### Get Channel
```http
GET /api/channels/{channel_id}
Authorization: Bearer <token>
```

## Direct Messages

### Create or Get DM Channel
```http
POST /api/channels/direct
Authorization: Bearer <token>
Content-Type: application/json

{
  "user_id": 2
}
```

**Response:**
```json
{
  "id": 5,
  "name": "dm-1-2",
  "display_name": "username",
  "type": "direct",
  "other_user_id": 2,
  "other_username": "username"
}
```

### List DM Channels
```http
GET /api/channels/direct/list
Authorization: Bearer <token>
```

**Response:**
```json
[
  {
    "id": 5,
    "name": "dm-1-2",
    "display_name": "John",
    "type": "direct",
    "other_user_id": 2,
    "other_username": "john"
  }
]
```

## Messages

### Send Message
```http
POST /api/messages/
Authorization: Bearer <token>
Content-Type: application/json

{
  "content": "Hello, World!",
  "channel_id": 1,
  "parent_id": null
}
```

### Get Channel Messages
```http
GET /api/messages/channel/{channel_id}?skip=0&limit=50
Authorization: Bearer <token>
```

### Get Message
```http
GET /api/messages/{message_id}
Authorization: Bearer <token>
```

### Update Message
```http
PUT /api/messages/{message_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "content": "Updated content"
}
```

### Delete Message
```http
DELETE /api/messages/{message_id}
Authorization: Bearer <token>
```

## Thread Replies

### Create Reply
```http
POST /api/messages/{message_id}/reply
Authorization: Bearer <token>
Content-Type: application/json

{
  "content": "This is a reply"
}
```

**Response:**
```json
{
  "id": 10,
  "content": "This is a reply",
  "channel_id": 1,
  "author_id": 1,
  "parent_id": 5,
  "is_edited": false,
  "edited_at": null,
  "thread_count": 0,
  "last_activity_at": "2024-01-01T00:00:00Z",
  "created_at": "2024-01-01T00:00:00Z",
  "author_username": "admin",
  "reactions": [],
  "reply_count": 0
}
```

### Get Thread Replies
```http
GET /api/messages/{message_id}/replies?skip=0&limit=50
Authorization: Bearer <token>
```

## Reactions

### Add Reaction
```http
POST /api/messages/{message_id}/reactions
Authorization: Bearer <token>
Content-Type: application/json

{
  "emoji": "👍"
}
```

### Remove Reaction
```http
DELETE /api/messages/{message_id}/reactions/{emoji}
Authorization: Bearer <token>
```

## Search

### Search Messages
```http
POST /api/messages/search
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "search term",
  "channel_id": 1,
  "limit": 20
}
```

## Notifications

### Get Notifications
```http
GET /api/notifications/?limit=10
Authorization: Bearer <token>
```

### Mark Notification as Read
```http
PUT /api/notifications/{notification_id}/read
Authorization: Bearer <token>
```

### Mark All as Read
```http
PUT /api/notifications/read-all
Authorization: Bearer <token>
```

## Users

### List Users
```http
GET /api/users/
Authorization: Bearer <token>
```

### Get User Profile
```http
GET /api/users/me
Authorization: Bearer <token>
```

### Update User Profile
```http
PUT /api/users/me
Authorization: Bearer <token>
Content-Type: application/json

{
  "display_name": "New Name",
  "avatar_url": "https://..."
}
```

## WebSocket

### Chat WebSocket
```javascript
const ws = new WebSocket('ws://localhost:9080/ws/chat/{channel_id}?token={jwt_token}');
```

### Message Types

**Send Message:**
```json
{
  "type": "message",
  "content": "Hello!"
}
```

**Receive Message:**
```json
{
  "type": "message",
  "id": 1,
  "content": "Hello!",
  "user_id": 1,
  "username": "admin",
  "channel_id": 1,
  "timestamp": "2024-01-01T00:00:00Z",
  "reactions": []
}
```

**Typing Start:**
```json
{ "type": "typing_start" }
```

**Typing Stop:**
```json
{ "type": "typing_stop" }
```

**Add Reaction:**
```json
{
  "type": "reaction_add",
  "message_id": 1,
  "emoji": "👍"
}
```

**Remove Reaction:**
```json
{
  "type": "reaction_remove",
  "message_id": 1,
  "emoji": "👍"
}
```

### Presence WebSocket
```javascript
const ws = new WebSocket('ws://localhost:9080/ws/presence?token={jwt_token}');
```

**Receive Presence List:**
```json
{
  "type": "presence_list",
  "users": [
    { "user_id": "1", "username": "admin", "status": "online" }
  ]
}
```

**Receive Presence Update:**
```json
{
  "type": "presence_update",
  "user_id": "1",
  "username": "admin",
  "status": "online"
}
```
