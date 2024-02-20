# !usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Jackly'

'''
async web application.
'''

import time
import json
import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import orm
from coroweb import add_routes, add_static
from aiohttp import web
from handlers import cookie2user, COOKIE_NAME
import asyncio
from config import configs

import logging
logging.basicConfig(level=logging.INFO)

# 初始化jinja2模板
def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    options = dict(
        autoescape=kw.get('autoescape', True),
        block_start_string=kw.get('block_start_string', '{%'),
        block_end_string=kw.get('block_end_string', '%}'),
        variable_start_string=kw.get('variable_start_string', '{{'),
        variable_end_string=kw.get('variable_end_string', '}}'),
        auto_reload=kw.get('auto_reload', True)
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    # 添加日志语句来检查过滤器是否已经添加
    # logging.info('Current jinja2 filters: %s' % env.filters)
    app['__templating__'] = env  # 这里设置app的templating


@web.middleware
async def logger_factory(request, handler):
    logging.info('Request: %s %s' % (request.method, request.path))
    try:
        response = await handler(request)
        logging.info('Response: %s' % response)
        return response
    except Exception as e:
        logging.error('Error: %s' % str(e))
        raise

@web.middleware
async def auth_factory(app, handler):
    async def auth(request):
        logging.info('check user: %s %s' % (request.method, request.path))
        request.__user__ = None
        cookie_str = request.cookies.get(COOKIE_NAME)
        if cookie_str:
            user = await cookie2user(cookie_str)
            if user:
                logging.info('set current user: %s' % user.email)
                request.__user__ = user
        if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
            return web.HTTpFound('/signin')
        return (await handler(request))
    return auth

@web.middleware
async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request form: %s' % str(request.__data__))
        return (await handler(request))
    return parse_data


@web.middleware
async def response_factory(request, handler):
    try:
        r = await handler(request)
        logging.info('Respone_factory: %s %s' % (request.method, request.path))
        if isinstance(r, web.StreamResponse):
            return r  # 如果是StreamResponse或其子类实例，则直接返回
        if isinstance(r, dict):  # 处理返回字典的情况
            template = r.get('__template__')
            if template:
                response_body = request.app['__templating__'].get_template(
                    template).render(**r).encode('utf-8')
                return web.Response(body=response_body, content_type='text/html;charset=utf-8')
            else:
                # 处理返回JSON的情况
                resp = web.Response(body=json.dumps(
                    r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
        # 处理返回字符串的情况
        if isinstance(r, str):
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            return web.Response(body=r.encode('utf-8'), content_type='text/html;charset=utf-8')
        # 处理返回bytes的情况
        if isinstance(r, bytes):
            return web.Response(body=r, content_type='application/octet-stream')
        if isinstance(r, int) and t >= 100 and t < 600:
            return web.Response(t)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(t, str(m))
        # default:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    except Exception as e:
        logging.exception("Error in response_factory: %s" % str(e))
        return web.Response(text=str(e), status=500)

# 定义datetime_filter
def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)


async def init(loop):
    # await orm.create_pool(loop=loop, user='root', password='password', db='awesome')
    # await orm.create_pool(loop=loop, user='www-data', password='password', db='awesome', host='localhost')
    await orm.create_pool(loop=loop, **configs.db)
    app = web.Application(loop=loop, middlewares=[
        logger_factory, response_factory
    ])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, 'handlers')  # 添加路由
    add_static(app)  # 添加静态文件路径
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

# 获取EventLoop:
loop = asyncio.get_event_loop()
# 初始化数据库连接池和web app:
loop.run_until_complete(init(loop))
# 运行web app:
loop.run_forever()
