import asyncio
from sqlalchemy import delete, select
from factfeed.db.session import AsyncSessionLocal
from factfeed.db.models import Sentence, Article

async def main():
    async with AsyncSessionLocal() as session:
        del_stmt = delete(Sentence).where(
            Sentence.article_id == select(Article.id).where(Article.url_hash == 'test').scalar_subquery()
        )
        print(del_stmt)

asyncio.run(main())
