"""Quick script to check team memberships."""
import asyncio
from sqlalchemy import select
from app.db.database import async_session
from app.db.models import User, TeamMember, Team

async def main():
    async with async_session() as db:
        # Users
        print("Users:")
        result = await db.execute(select(User))
        for u in result.scalars():
            print(f"  {u.id}: {u.username}")
        
        # Teams
        print("\nTeams:")
        result = await db.execute(select(Team))
        for t in result.scalars():
            print(f"  {t.id}: {t.name}")
        
        # Team Members
        print("\nTeamMembers:")
        result = await db.execute(select(TeamMember))
        members = result.scalars().all()
        if not members:
            print("  (no team memberships found!)")
        for m in members:
            print(f"  user_id={m.user_id}, team_id={m.team_id}")

if __name__ == "__main__":
    asyncio.run(main())
