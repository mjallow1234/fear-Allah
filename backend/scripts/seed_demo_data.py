"""
Idempotent demo data seeder for local development (Docker-only manual run).

Run manually inside the backend container or with:

  docker-compose exec backend python scripts/seed_demo_data.py

This script:
 - Creates users, teams, channels, DMs
 - Seeds messages (some edited / deleted / pinned / threads)
 - Adds reactions, attachments, notifications
 - Creates orders/tasks/automation tasks (various statuses)

Safety: idempotent (skips existing rows) and prints summary counts.
"""

import asyncio
import os
from datetime import datetime, timedelta
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.database import async_session
from app.db.models import (
    User, Team, TeamMember, Channel, ChannelMember, Message,
    FileAttachment, MessageReaction, Notification, Order, Task, AutomationTask,
    Inventory
)
from app.db.enums import ChannelType, NotificationType, AutomationTaskType, AutomationTaskStatus, TaskStatus
from app.core.security import get_password_hash

UPLOAD_DIR = Path(__file__).resolve().parents[1] / 'uploads' / 'demo'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Demo users to create
DEMO_USERS = [
    {"username": "admin", "email": "admin@fearallah.com", "role": "system_admin", "skip_if_exists": True},
    {"username": "owner1", "email": "owner1@example.com", "role": "team_admin"},
    {"username": "manager1", "email": "manager1@example.com", "role": "member"},
    {"username": "manager2", "email": "manager2@example.com", "role": "member"},
    {"username": "agent1", "email": "agent1@example.com", "role": "member"},
    {"username": "agent2", "email": "agent2@example.com", "role": "member"},
    {"username": "support1", "email": "support1@example.com", "role": "member"},
    {"username": "support2", "email": "support2@example.com", "role": "member"},
    {"username": "viewer1", "email": "viewer1@example.com", "role": "member"},
    {"username": "viewer2", "email": "viewer2@example.com", "role": "member"},
    {"username": "automation_bot", "email": "automation_bot@example.com", "role": "member"},
    {"username": "testuser", "email": "testuser@example.com", "role": "member"},
    # Team testing scenario users
    {"username": "foreman1", "email": "foreman1@example.com", "role": "member"},
    {"username": "delivery1", "email": "delivery1@example.com", "role": "member"},
    {"username": "storekeeper1", "email": "storekeeper1@example.com", "role": "member"},
    {"username": "customer1", "email": "customer1@example.com", "role": "member"},
]
PASSWORD = "Password123!"

# Teams
TEAMS = [
    {"name": "main", "display_name": "Main Team"},
    {"name": "sales", "display_name": "Sales Team"},
]

# Channels to create (global and team-scoped)
CHANNELS = [
    {"name": "general", "display_name": "General", "type": ChannelType.public.value, "team": None},
    {"name": "announcements", "display_name": "Announcements", "type": ChannelType.public.value, "team": None},
    {"name": "random", "display_name": "Random", "type": ChannelType.public.value, "team": None},
    {"name": "management", "display_name": "Management", "type": ChannelType.private.value, "team": "main"},
    {"name": "support-internal", "display_name": "Support Internal", "type": ChannelType.private.value, "team": None},
    {"name": "sales", "display_name": "Sales", "type": ChannelType.public.value, "team": "sales"},
    {"name": "sales-leads", "display_name": "Sales Leads", "type": ChannelType.public.value, "team": "sales"},
]

# DM pairs (username pairs)
DM_PAIRS = [
    ("admin", "agent1"),
    ("manager1", "support1"),
    ("agent1", "agent2"),
]

# Helper utilities
async def get_user_by_username(db, username):
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()

async def get_team_by_name(db, name):
    result = await db.execute(select(Team).where(Team.name == name))
    return result.scalar_one_or_none()

async def get_channel_by_name(db, name, team_id=None):
    query = select(Channel).where(Channel.name == name)
    if team_id is None:
        query = query.where(Channel.team_id.is_(None))
    else:
        query = query.where(Channel.team_id == team_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_user_id_by_username(db, username):
    """Return integer id for username or None."""
    result = await db.execute(select(User.id).where(User.username == username))
    return result.scalar_one_or_none()

async def create_demo_files():
    files = []
    # Create small demo files
    txt = UPLOAD_DIR / 'demo.txt'
    txt.write_text('This is a demo text file for attachments.')
    files.append(txt)
    png = UPLOAD_DIR / 'demo.png'
    with open(png, 'wb') as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"DEMOPNG")
    files.append(png)
    jpg = UPLOAD_DIR / 'demo.jpg'
    with open(jpg, 'wb') as f:
        f.write(b"\xff\xd8\xff\xe0" + b"DEMOJPG")
    files.append(jpg)
    pdf = UPLOAD_DIR / 'demo.pdf'
    pdf.write_bytes(b"%PDF-1.4\n%DEMOPDF\n")
    files.append(pdf)
    return files

async def seed():
    created = {"users": 0, "teams": 0, "channels": 0, "dms": 0, "messages": 0, "attachments": 0, "reactions": 0, "notifications": 0, "orders": 0, "tasks": 0, "automation_tasks": 0}

    async with async_session() as db:
        # Users
        for u in DEMO_USERS:
            exists = await db.execute(select(User).where((User.email == u["email"]) | (User.username == u["username"])))
            if exists.scalar_one_or_none():
                print(f"User exists: {u['username']}")
                continue
            user = User(
                username=u["username"],
                email=u["email"],
                hashed_password=get_password_hash(PASSWORD),
                display_name=u["username"].capitalize(),
                is_active=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            created["users"] += 1
            print(f"Created user: {user.username}")

        # Teams
        team_map = {}
        for t in TEAMS:
            existing = await db.execute(select(Team).where(Team.name == t["name"]))
            team = existing.scalar_one_or_none()
            if team:
                print(f"Team exists: {t['name']}")
            else:
                team = Team(name=t["name"], display_name=t["display_name"], description=f"Demo team {t['display_name']}")
                db.add(team)
                await db.commit()
                await db.refresh(team)
                created["teams"] += 1
                print(f"Created team: {team.name}")
            team_map[t["name"]] = team

        # Team members
        # owner1 -> owner of main, manager1 manager, agents/support/viewers members, manager2 -> sales manager
        async def add_team_member(username, team_name, role="member"):
            user = await get_user_by_username(db, username)
            team = team_map.get(team_name)
            if not user or not team:
                return
            exists = await db.execute(select(TeamMember).where(TeamMember.user_id == user.id, TeamMember.team_id == team.id))
            if exists.scalar_one_or_none():
                return
            tm = TeamMember(user_id=user.id, team_id=team.id, role=role)
            db.add(tm)
            await db.commit()
            print(f"Added TeamMember: {username} -> {team_name} ({role})")

        await add_team_member('owner1', 'main', role='owner')
        await add_team_member('manager1', 'main', role='manager')
        for name in ['agent1','agent2','support1','support2','viewer1','viewer2','testuser']:
            await add_team_member(name, 'main', role='member')
        await add_team_member('manager2', 'sales', role='manager')
        for name in ['agent1','agent2','viewer1','viewer2']:
            await add_team_member(name, 'sales', role='member')

        # Channels
        channel_map = {}
        for ch in CHANNELS:
            team_id = None
            if ch["team"]:
                team = team_map.get(ch["team"])
                team_id = team.id
            existing = await get_channel_by_name(db, ch["name"], team_id=team_id)
            if existing:
                print(f"Channel exists: {ch['name']} (team {ch['team']})")
                channel_map[(ch['name'], ch['team'])] = existing
                continue
            channel = Channel(
                name=ch["name"],
                display_name=ch.get("display_name"),
                description=f"Demo channel {ch['display_name']}",
                type=ch["type"],
                team_id=team_id,
            )
            db.add(channel)
            await db.commit()
            await db.refresh(channel)
            created["channels"] += 1
            channel_map[(ch['name'], ch['team'])] = channel
            print(f"Created channel: {channel.name} (team {ch['team']})")

        # Add memberships (idempotent, per rules)
        # Track added counts per channel for summary logging
        membership_counts = {}

        async def add_channel_member(username, channel):
            """Idempotent add: returns True if added, False if already present or missing."""
            user = await get_user_by_username(db, username)
            if not user or not channel:
                return False
            exists = await db.execute(select(ChannelMember).where(ChannelMember.user_id == user.id, ChannelMember.channel_id == channel.id))
            if exists.scalar_one_or_none():
                return False
            cm = ChannelMember(user_id=user.id, channel_id=channel.id)
            db.add(cm)
            await db.commit()
            membership_counts[channel.name] = membership_counts.get(channel.name, 0) + 1
            print(f"Added channel member: {username} -> {channel.name}")
            return True

        # === Public channels: add ALL non-banned users ===
        public_users = ['admin','owner1','manager1','manager2','agent1','agent2','support1','support2','viewer1','viewer2','testuser']
        for cname in ['general','announcements','random']:
            ch = channel_map.get((cname, None))
            if not ch:
                continue
            for username in public_users:
                await add_channel_member(username, ch)

        # === Private channels ===
        # management → owner + managers + admin
        mng = channel_map.get(('management','main'))
        if mng:
            for username in ['admin','owner1','manager1','manager2']:
                await add_channel_member(username, mng)

        # support-internal → support + managers + admin
        sup = channel_map.get(('support-internal', None))
        if sup:
            for username in ['support1','support2','manager1','manager2','admin']:
                await add_channel_member(username, sup)

        # === Sales channels ===
        # sales & sales-leads → agents + managers + admin
        sales_ch = channel_map.get(('sales','sales'))
        sales_leads = channel_map.get(('sales-leads','sales'))
        sales_members = ['agent1','agent2','manager1','manager2','admin']
        if sales_ch:
            for username in sales_members:
                await add_channel_member(username, sales_ch)
        if sales_leads:
            for username in sales_members:
                await add_channel_member(username, sales_leads)

        # === Direct message channels: ensure exactly two members ===
        for a, b in DM_PAIRS:
            # find or create DM channel named dm-min-max
            u1 = await get_user_by_username(db, a)
            u2 = await get_user_by_username(db, b)
            if not u1 or not u2:
                continue
            names = sorted([u1.id, u2.id])
            dm_name = f"dm-{names[0]}-{names[1]}"
            existing = await db.execute(select(Channel).where(Channel.name == dm_name, Channel.type == ChannelType.direct.value))
            dm = existing.scalar_one_or_none()
            if not dm:
                dm = Channel(name=dm_name, display_name=f"DM {u1.username}-{u2.username}", type=ChannelType.direct.value)
                db.add(dm)
                await db.commit()
                await db.refresh(dm)
                created['dms'] += 1
                print(f"Created DM channel: {dm.name}")

            # ensure both members exist
            added_a = await add_channel_member(a, dm)
            added_b = await add_channel_member(b, dm)

            # prune any other members so DM channels have exactly 2 members
            res = await db.execute(select(ChannelMember).where(ChannelMember.channel_id == dm.id))
            members = res.scalars().all()
            for m in members:
                if m.user_id not in {u1.id, u2.id}:
                    # remove extra membership
                    await db.delete(m)
                    await db.commit()
                    print(f"Removed extra DM member user {m.user_id} from {dm.id}")

            print(f"Added DM members for channel {dm.id}")

        # Membership summary logs
        for ch_name, cnt in membership_counts.items():
            print(f"Added {cnt} users to channel #{ch_name}")

        # Create demo files and attachments
        demo_files = await create_demo_files()

        # Seed messages in each public/team channel
        async def post_message(author_username, channel, content, **kwargs):
            user = await get_user_by_username(db, author_username)
            if not user or not channel:
                return None
            msg = Message(content=content, channel_id=channel.id, author_id=user.id)
            if kwargs.get('is_edited'):
                msg.is_edited = True
                msg.edited_at = datetime.utcnow()
            if kwargs.get('is_deleted'):
                msg.is_deleted = True
                msg.deleted_at = datetime.utcnow()
            if kwargs.get('is_pinned'):
                msg.is_pinned = True
            db.add(msg)
            await db.commit()
            await db.refresh(msg)
            created['messages'] += 1
            print(f"Created message {msg.id} in {channel.name} by {author_username}")
            return msg

        # Post some messages to #general
        general = channel_map.get(('general', None))
        general_id = None
        if general:
            general_id = general.id
            authors = ['admin','owner1','manager1','agent1','support1','viewer1']
            for i in range(6):
                await post_message(authors[i%len(authors)], general, f"Demo message {i+1} in #general by {authors[i%len(authors)]}")
            # Add one edited, one deleted, one pinned
            m1 = await post_message('agent2', general, "I will edit this shortly")
            if m1:
                m1.is_edited = True
                m1.edited_at = datetime.utcnow()
                db.add(m1)
                await db.commit()
            m2 = await post_message('support1', general, "This message will be soft-deleted")
            if m2:
                m2.is_deleted = True
                m2.deleted_at = datetime.utcnow()
                db.add(m2)
                await db.commit()
            mp = await post_message('owner1', general, "Important pinned announcement")
            if mp:
                mp.is_pinned = True
                db.add(mp)
                await db.commit()

        # Post to sales channel
        if sales_ch:
            for i in range(8):
                await post_message(['agent1','agent2','manager2'][i%3], sales_ch, f"Sales note {i+1}")

        # Create thread reply example
        parent = await post_message('manager1', mng or general, "Please review this thread")
        if parent:
            reply = Message(content="Reply 1", channel_id=parent.channel_id, author_id=(await get_user_by_username(db,'owner1')).id, parent_id=parent.id)
            db.add(reply)
            parent.thread_count = (parent.thread_count or 0) + 1
            await db.commit()
            created['messages'] += 1
            print(f"Created thread reply in {parent.channel_id}")

        # Attach demo files to some messages
        attachments_made = 0
        if demo_files and general_id:
            # Attach demo.txt to the first message in general if exists
            msg_for_attach = await db.execute(select(Message).where(Message.channel_id == general_id))
            msg = msg_for_attach.scalars().first()
            if msg:
                for fpath in demo_files:
                    fa = FileAttachment(message_id=msg.id, channel_id=general_id, user_id=msg.author_id, filename=fpath.name, file_path=str(fpath), storage_path=str(fpath), file_size=os.path.getsize(fpath), mime_type='application/octet-stream')
                    db.add(fa)
                    await db.commit()
                    await db.refresh(fa)
                    attachments_made += 1
            created['attachments'] += attachments_made
            if attachments_made:
                print(f"Created {attachments_made} attachments for message {msg.id}")

        # Reactions - add some reactions to the first message
        first_msg = await db.execute(select(Message).where(Message.channel_id == general_id).order_by(Message.id))
        first_msg = first_msg.scalars().first()
        if first_msg:
            first_msg_id = first_msg.id
            emos = ['👍','❤️','😂','🔥','😮']
            users_for_react = ['agent1','agent2','support1','viewer1']
            for i, u in enumerate(users_for_react):
                user = await get_user_by_username(db, u)
                if user:
                    uid = user.id
                    mr = MessageReaction(message_id=first_msg_id, user_id=uid, emoji=emos[i%len(emos)])
                    try:
                        db.add(mr)
                        await db.commit()
                        created['reactions'] += 1
                    except IntegrityError:
                        await db.rollback()
            print(f"Added {created['reactions']} reactions to message {first_msg_id}")

        # Notifications (use ids to avoid lazy loads)
        viewer_id = await get_user_id_by_username(db,'viewer1')
        agent_id = await get_user_id_by_username(db,'agent1')
        if viewer_id and agent_id and first_msg:
            notif = Notification(user_id=viewer_id, type=NotificationType.mention.value, title='You were mentioned', content='@viewer1 please check', channel_id=general_id, message_id=first_msg_id, sender_id=agent_id)
            db.add(notif)
            await db.commit()
            created['notifications'] += 1
            print("Created a mention notification for viewer1")

        # Orders / Tasks / AutomationTasks
        order = Order(order_type='AGENT_RESTOCK', status='SUBMITTED', meta='{}', items='[]')
        db.add(order)
        await db.commit()
        await db.refresh(order)
        created['orders'] += 1
        # Task linked to order
        task = Task(order_id=order.id, step_key='restock-1', title='Restock item #123', assigned_user_id=(await get_user_by_username(db,'agent1')).id, status=TaskStatus.pending.value)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        created['tasks'] += 1
        # Automation task
        at = AutomationTask(task_type=AutomationTaskType.restock.value, status=AutomationTaskStatus.pending.value, title='Auto restock trigger', created_by_id=(await get_user_by_username(db,'automation_bot')).id, related_order_id=order.id)
        db.add(at)
        await db.commit()
        await db.refresh(at)
        created['automation_tasks'] += 1
        print(f"Created order {order.id}, task {task.id}, automation task {at.id}")

        # Seed inventory items for team testing (Phase 6.3)
        DEMO_INVENTORY = [
            {"product_id": 1, "product_name": "Widget A", "total_stock": 100, "low_stock_threshold": 10},
            {"product_id": 2, "product_name": "Widget B", "total_stock": 50, "low_stock_threshold": 5},
            {"product_id": 3, "product_name": "Premium Package", "total_stock": 25, "low_stock_threshold": 5},
            {"product_id": 4, "product_name": "Bulk Item Pack", "total_stock": 200, "low_stock_threshold": 20},
            {"product_id": 5, "product_name": "Standard Kit", "total_stock": 75, "low_stock_threshold": 10},
            {"product_id": 6, "product_name": "Express Service", "total_stock": 30, "low_stock_threshold": 5},
            {"product_id": 7, "product_name": "Basic Supply", "total_stock": 150, "low_stock_threshold": 15},
            {"product_id": 8, "product_name": "Premium Supply", "total_stock": 40, "low_stock_threshold": 8},
            {"product_id": 9, "product_name": "Economy Pack", "total_stock": 300, "low_stock_threshold": 30},
            {"product_id": 10, "product_name": "Starter Bundle", "total_stock": 60, "low_stock_threshold": 10},
        ]
        created['inventory'] = 0
        for inv_data in DEMO_INVENTORY:
            existing = await db.execute(select(Inventory).where(Inventory.product_id == inv_data["product_id"]))
            if existing.scalar_one_or_none():
                print(f"Inventory exists for product_id {inv_data['product_id']}")
                continue
            inv = Inventory(
                product_id=inv_data["product_id"],
                product_name=inv_data["product_name"],
                total_stock=inv_data["total_stock"],
                total_sold=0,
                low_stock_threshold=inv_data["low_stock_threshold"],
            )
            db.add(inv)
            await db.commit()
            created['inventory'] += 1
            print(f"Created inventory: {inv_data['product_name']} (product_id={inv_data['product_id']}, stock={inv_data['total_stock']})")
        
        if created['inventory']:
            print(f"Seeded {created['inventory']} inventory items for team testing")

    # Summary
    print('\nDemo seeding complete:')
    for k, v in created.items():
        print(f"  {k}: {v}")
    print('Demo data seeded successfully')


if __name__ == '__main__':
    asyncio.run(seed())
