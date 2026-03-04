import asyncio
from sqlalchemy import select, func
from factfeed.db.session import AsyncSessionLocal
from factfeed.db.models import Source, Article
async def main():
    async with AsyncSessionLocal() as session:
        stmt = select(Source.country_code, func.count(Article.id)).join(Article).group_by(Source.country_code)
        result = await session.execute(stmt)
        for row in result:
            print(row)
asyncio.run(main())
