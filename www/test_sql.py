import asyncio

import orm

from models import User

async def test(loop):

    # await orm.create_pool(user='root', password='password', db='awesome', loop=loop)
    await orm.create_pool(loop=loop, user='www-data', password='password', db='awesome', host='localhost')

    u = User(name='Test', email='test5@example.com', password='1234567890', image='about:blank', admin=False)

    await u.save()

loop = asyncio.get_event_loop()

loop.run_until_complete(test(loop))