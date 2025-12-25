"""Add all users to the default team."""
import asyncio
from sqlalchemy import select
from app.db.database import async_session
from app.db.models import User, TeamMember, Team

async def main():
    async with async_session() as db:
        # Get default team
        result = await db.execute(select(Team).where(Team.name == "default"))
        team = result.scalar_one_or_none()
        
        if not team:
            print("No default team found!")
            return
        
        print(f"Found team: {team.id} - {team.name}")
        
        # Get all users
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        # Check existing memberships
        result = await db.execute(select(TeamMember.user_id).where(TeamMember.team_id == team.id))
        existing_member_ids = set(r[0] for r in result.all())
        
        added = 0
        for user in users:
            if user.id not in existing_member_ids:
                membership = TeamMember(
                    user_id=user.id,
                    team_id=team.id,
                    role="admin" if user.is_system_admin else "member"
                )
                db.add(membership)
                print(f"  Added {user.username} (id={user.id}) to team {team.name}")
                added += 1
        
        await db.commit()
        print(f"\nAdded {added} users to team '{team.name}'")

if __name__ == "__main__":
    asyncio.run(main())
