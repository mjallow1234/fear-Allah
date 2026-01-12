"""Normalize teams: keep 'sidrah-salaam' and remove 'default'

Revision ID: 029_normalize_teams_keep_sidrah_salaam
Revises: 9183aa12ad79
Create Date: 2026-01-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '029_normalize_teams_keep_sidrah_salaam'
down_revision: Union[str, Sequence[str], None] = '9183aa12ad79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """One-time normalization migration:
    - Keep team named 'sidrah-salaam' as canonical
    - Remove team named 'default'
    - Reassign memberships and channels from 'default' -> 'sidrah-salaam'
    - Idempotent and wrapped in a single transaction
    """
    conn = op.get_bind()
    trans = conn.begin()
    try:
        # Resolve team ids by name
        primary = conn.execute(sa.text("SELECT id FROM teams WHERE name = :name LIMIT 1"), {"name": "sidrah-salaam"}).fetchone()
        legacy = conn.execute(sa.text("SELECT id FROM teams WHERE name = :name LIMIT 1"), {"name": "default"}).fetchone()

        if not primary or not legacy:
            # Nothing to do if either team is missing; safe no-op
            print("029_normalize_teams: one or both teams missing; no action taken")
            trans.commit()
            return

        primary_id = primary[0]
        legacy_id = legacy[0]

        if primary_id == legacy_id:
            print("029_normalize_teams: primary and legacy are same id; nothing to do")
            trans.commit()
            return

        # Counts before
        counts_before = {}
        counts_before['members_legacy'] = conn.execute(sa.text("SELECT COUNT(*) FROM team_members WHERE team_id = :t"), {"t": legacy_id}).scalar()
        counts_before['members_primary'] = conn.execute(sa.text("SELECT COUNT(*) FROM team_members WHERE team_id = :t"), {"t": primary_id}).scalar()
        counts_before['channels_legacy'] = conn.execute(sa.text("SELECT COUNT(*) FROM channels WHERE team_id = :t"), {"t": legacy_id}).scalar()
        counts_before['channels_primary'] = conn.execute(sa.text("SELECT COUNT(*) FROM channels WHERE team_id = :t"), {"t": primary_id}).scalar()

        # Move memberships: insert missing memberships into primary for users that are in legacy
        conn.execute(sa.text(
            "INSERT INTO team_members (user_id, team_id, role, created_at) "
            "SELECT tm.user_id, :primary_id, tm.role, tm.created_at FROM team_members tm "
            "WHERE tm.team_id = :legacy_id "
            "AND NOT EXISTS (SELECT 1 FROM team_members t2 WHERE t2.team_id = :primary_id AND t2.user_id = tm.user_id)"
        ), {"primary_id": primary_id, "legacy_id": legacy_id})

        # Reassign channels
        # For each channel in legacy, if a channel with same name exists in primary, merge members/messages into primary channel and delete legacy; otherwise update team_id
        legacy_channels = conn.execute(sa.text("SELECT id, name FROM channels WHERE team_id = :t"), {"t": legacy_id}).fetchall()
        for lc in legacy_channels:
            legacy_ch_id = lc[0]
            name = lc[1]
            primary_ch = conn.execute(sa.text("SELECT id FROM channels WHERE team_id = :t AND name = :name LIMIT 1"), {"t": primary_id, "name": name}).fetchone()
            if primary_ch:
                primary_ch_id = primary_ch[0]
                # Move messages
                conn.execute(sa.text("UPDATE messages SET channel_id = :primary_ch_id WHERE channel_id = :legacy_ch_id"), {"primary_ch_id": primary_ch_id, "legacy_ch_id": legacy_ch_id})
                # Move channel members (insert missing)
                conn.execute(sa.text(
                    "INSERT INTO channel_members (user_id, channel_id, last_read_at, last_viewed_at, created_at) "
                    "SELECT cm.user_id, :primary_ch_id, cm.last_read_at, cm.last_viewed_at, cm.created_at FROM channel_members cm "
                    "WHERE cm.channel_id = :legacy_ch_id "
                    "AND NOT EXISTS (SELECT 1 FROM channel_members c2 WHERE c2.channel_id = :primary_ch_id AND c2.user_id = cm.user_id)"
                ), {"primary_ch_id": primary_ch_id, "legacy_ch_id": legacy_ch_id})
                # Delete legacy channel (members/messages already moved)
                conn.execute(sa.text("DELETE FROM channels WHERE id = :id"), {"id": legacy_ch_id})
            else:
                # No conflict: just update team_id
                conn.execute(sa.text("UPDATE channels SET team_id = :primary_id WHERE id = :id"), {"primary_id": primary_id, "id": legacy_ch_id})

        # Delete legacy team members rows (they've been moved)
        conn.execute(sa.text("DELETE FROM team_members WHERE team_id = :t"), {"t": legacy_id})

        # Finally, delete the legacy team
        conn.execute(sa.text("DELETE FROM teams WHERE id = :t"), {"t": legacy_id})

        # Counts after
        counts_after = {}
        counts_after['members_primary'] = conn.execute(sa.text("SELECT COUNT(*) FROM team_members WHERE team_id = :t"), {"t": primary_id}).scalar()
        counts_after['channels_primary'] = conn.execute(sa.text("SELECT COUNT(*) FROM channels WHERE team_id = :t"), {"t": primary_id}).scalar()

        # Small verification printout (will appear in alembic logs)
        print(f"029_normalize_teams: counts_before={counts_before}, counts_after={counts_after}")

        trans.commit()
    except Exception:
        trans.rollback()
        raise


def downgrade() -> None:
    # Irreversible one-time normalization; no-op on downgrade
    print("029_normalize_teams: downgrade noop (irreversible normalization)")
