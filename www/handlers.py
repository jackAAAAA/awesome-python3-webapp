# !usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Jackly'

' url handlers '

import re
import time
import json
import logging
import hashlib
import base64
import asyncio

import markdown2

from aiohttp import web

from coroweb import get, post
from apis import Page, APIValueError, APIResourceNotFoundError, APIPermissionError

from models import User, Comment, Blog, next_id
from config import configs

import jinja2

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()
    
def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p

def user2cookie(user, max_age):
    """
    Generate cookie str by user.
    """
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.password, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)

async def cookie2user(cookie_str):
    """
    Parse cookie and load user if cookie is valid.
    """
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (user.id, user.password, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest:
            logging.info('invalid sha1')
            return None
        user.password = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None

# blogs.html
@get('/')
async def index(request):
    try:
        summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
        blogs = [
            Blog(id='1', name='Test Blog', summary=summary, create_at=time.time()-120),
            Blog(id='2', name='Something New', summary=summary, create_at=time.time()-3600),
            Blog(id='3', name='Learn Swift', summary=summary, create_at=time.time()-7200)
        ]
        # 打印查询到的博客信息
        logging.info(f'Blogs found: {blogs}')
        # 设置模板环境 / 使用 Flask 应用配置的 Jinja2 环境
        template = request.app['__templating__'].get_template('blogs.html')
        # 渲染模板
        response_body = template.render(blogs=blogs)
        return web.Response(body=response_body.encode('utf-8'), content_type='text/html')
    except Exception as e:
        logging.exception(e)
        return web.Response(text=str(e), status=500)
    
@get('/blog/{id}')
async def get_blog(id, request):
    try:
        blog = await Blog.find(id)
        comments = await Comment.findAll('blog_id=?', [id], orderBy='create_at desc')
        for c in comments:
            c.html_content = text2html(c.content)
        if blog is not None:
            blog.html_content = markdown2.markdown(blog.content)
        template = request.app['__templating__'].get_template('blogs.html')
        response_body = template.render(blog=blog, comments=comments)
        return web.Response(body=response_body.encode('utf-8'), content_type='text/html')
    except Exception as e:
        logging.exception(e)
        return web.Response(text=str(e), status=500)
    
@get('/register')
async def register(request):
    try:
        # 设置模板环境 / 使用 Flask 应用配置的 Jinja2 环境
        template = request.app['__templating__'].get_template('register.html')
        # 渲染模板
        response_body = template.render()
        return web.Response(body=response_body.encode('utf-8'), content_type='text/html')
    except Exception as e:
        logging.exception(e)
        return web.Response(text=str(e), status=500)

@get('/signin')
async def signin(request):
    try:
        # 设置模板环境 / 使用 Flask 应用配置的 Jinja2 环境
        template = request.app['__templating__'].get_template('signin.html')
        # 渲染模板
        response_body = template.render()
        return web.Response(body=response_body.encode('utf-8'), content_type='text/html')
    except Exception as e:
        logging.exception(e)
        return web.Response(text=str(e), status=500)
    
@post('/api/authenticate')
async def authenticate(*, email, password):
    logging.info('api_authenticate called %s', email, password)
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not password:
        raise APIValueError('password', 'Invalid password.')
    users = await User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]
    # check password:
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(password.encode('utf-8'))
    if user.password != sha1.hexdigest():
        raise APIValueError('password', 'Invalid password.')
    # authenticate ok, set cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

@get('/signout')
async def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTpFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r

@get('/manage/blogs')
async def manage_blogs(*, page='1', request):
    try:
        # 设置模板环境 / 使用 Flask 应用配置的 Jinja2 环境
        template = request.app['__templating__'].get_template('manage_blogs.html')
        # 渲染模板
        response_body = template.render(page_index=get_page_index(page))
        return web.Response(body=response_body.encode('utf-8'), content_type='text/html')
    except Exception as e:
        logging.exception(e)
        return web.Response(text=str(e), status=500)
    
@get('/manage/blogs/create')
async def manage_create_blog(request):
    try:
        # 设置模板环境 / 使用 Flask 应用配置的 Jinja2 环境
        template = request.app['__templating__'].get_template('manage_blog_edit.html')
        # 渲染模板
        response_body = template.render(id='', action='/api/blogs')
        return web.Response(body=response_body.encode('utf-8'), content_type='text/html')
    except Exception as e:
        logging.exception(e)
        return web.Response(text=str(e), status=500)

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

# test.html
@post('/api/users')
async def api_register_users(*, email, name, password):
    logging.info('api_register_users called')
    # logging.info('api_user_email: %s ; api_user_name: %s ; api_user_password: %s', email, name, password)
    try:
        if not name or not name.strip():
            raise APIValueError('name')
        if not email or not _RE_EMAIL.match(email):
            raise APIValueError('email')
        if not password or not _RE_SHA1.match(password):
            raise APIValueError('password')
        users = await User.findAll('email=?', [email])
        if len(users) > 0:
            raise APIValueError('register:failed', 'email', 'Email is already in use.')
        uid = next_id()
        sha1_password = '%s:%s' % (uid, password)
        user = User(admin=True, id=uid, name=name.strip(), email=email, password=hashlib.sha1(sha1_password.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
        await user.save()
        logging.info(f'Users found: {users}')
        # make session cookie:
        r = web.Response()
        r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
        user.password = '******'
        r.content_type = 'application/json'
        r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
        return r
    except APIValueError as e:
        logging.error('APIValueError: %s', e)
        raise
    except Exception as e:
        logging.exception('Unexpected error: %s', e)
        raise

@get('/api/blogs')
async def api_bolgs(*, page='1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=())
    blogs = await Blog.findAll(orderBy='create_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)
    

@get('/api/blogs/{id}')
async def api_get_blog(*, id):
    blog = await Blog.find(id)
    return blog

@post('/api/blogs')
async def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image = request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
    await blog.save()
    return blog

# @get('/api/users')
# async def api_get_users(request):
#     try:
#         users = await User.findAll(orderBy='create_at desc')
#         for u in users:
#             u.password = '6666666666'
#         # 打印查询到的用户信息
#         logging.info(f'Users found: {users}')
#         # 设置模板环境 / 使用 Flask 应用配置的 Jinja2 环境
#         template = request.app['__templating__'].get_template('test.html')
#         # 渲染模板
#         response_body = template.render(users=users)
#         return web.Response(body=response_body.encode('utf-8'), content_type='text/html')
#     except Exception as e:
#         logging.exception(e)
#         return web.Response(text=str(e), status=500)

# @get('/')
# async def index(request):
#     try:
#         users = await User.findAll()
#         # 打印查询到的用户信息
#         logging.info(f'Users found: {users}')
#         # 设置模板环境
#         env = jinja2.Environment(loader=jinja2.FileSystemLoader(
#             'D:/CodeRepository/Python_Project/5-LiaoxuefengPython/awesome-python3-webapp/www/templates'))
#         template = env.get_template('test.html')
#         # 渲染模板
#         response_body = template.render(users=users)
#         return web.Response(body=response_body.encode('utf-8'), content_type='text/html')
#     except Exception as e:
#         logging.exception(e)
#         return web.Response(text=str(e), status=500)
