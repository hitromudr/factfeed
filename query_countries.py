import asyncio
from sqlalchemy import select
from factfeed.db.session import AsyncSessionLocal
from factfeed.db.models import Source
async def main():
    async with AsyncSessionLocal() as session:
        stmt = select(Source.country_code).distinct()
        result = await session.execute(stmt)
        countries = [r[0] for r in result]
        print(countries)
asyncio.run(main())
