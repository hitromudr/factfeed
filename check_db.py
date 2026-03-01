import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from factfeed.db.session import AsyncSessionLocal
from factfeed.db.models import Article, Sentence

async def main():
    async with AsyncSessionLocal() as db:
        stmt = select(Article).options(selectinload(Article.sentences)).limit(5)
        result = await db.execute(stmt)
        for a in result.scalars():
            print(f"ID: {a.id}")
            print(f"Title: {a.title}")
            print(f"Body: {a.body[:100]}...")
            print(f"Sentences count: {len(a.sentences)}")
            if a.sentences:
                print(f"S0: {a.sentences[0].text}")
            print("-" * 40)

asyncio.run(main())
