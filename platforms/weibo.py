"""
微博 (Weibo) 平台适配器
参考 Wechatsync 的 weibo.ts 实现
"""
import asyncio
import json
import base64
import re
from typing import Optional
from datetime import datetime
from playwright.async_api import Page

from platforms.base import PlatformTool, ToolResult


class WeiboTool(PlatformTool):
    """微博平台适配器"""
    
    platform_name = "weibo"
    platform_id = "weibo"
    platform_type = "article"
    
    # 微博使用 HTML 格式
    output_format = "html"
    
    def __init__(self, account=None):
        super().__init__(account)
        self.user_config: Optional[dict] = None
    
    async def init_browser(self, headless: bool = True, load_cookie: bool = True):
        """初始化浏览器"""
        from playwright.async_api import async_playwright
        
        self.playwright = await async_playwright().start()
        
        # 浏览器配置
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
        ]
        
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        # 加载 Cookie
        if load_cookie:
            cookie_file = f"data/cookies/{self.platform_id}.json"
            try:
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                    context_options['storage_state'] = {'cookies': cookies}
            except FileNotFoundError:
                pass
        
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=browser_args
        )
        self.context = await self.browser.new_context(**context_options)
        self.page = await self.context.new_page()
    
    async def get_user_config(self) -> Optional[dict]:
        """获取用户配置（从编辑器页面解析）"""
        if self.user_config:
            return self.user_config
        
        # 访问编辑器页面
        await self.page.goto('https://card.weibo.com/article/v5/editor', wait_until='networkidle')
        await asyncio.sleep(3)  # 等待页面完全加载
        
        html = await self.page.content()
        
        # 解析配置
        config_match = re.search(r"config:\s*JSON\.parse\('(.+?)'\)", html)
        if not config_match:
            return None
        
        try:
            config_json = config_match.group(1).replace(r"\'", "'").replace(r'\\', '\\')
            config = json.loads(config_json)
            
            if not config.get('uid'):
                return None
            
            self.user_config = {
                'uid': str(config['uid']),
                'nick': config.get('nick', ''),
                'avatar_large': config.get('avatar_large', ''),
            }
            
            return self.user_config
        except Exception as e:
            print(f"解析微博配置失败: {e}")
            return None
    
    async def check_auth(self) -> dict:
        """检查登录状态"""
        try:
            config = await self.get_user_config()
            
            if config and config.get('uid'):
                return {
                    'is_authenticated': True,
                    'user_id': config['uid'],
                    'username': config.get('nick', ''),
                    'avatar': config.get('avatar_large', ''),
                }
            
            return {'is_authenticated': False}
        except Exception as e:
            return {'is_authenticated': False, 'error': str(e)}
    
    async def is_logged_in(self) -> bool:
        """检查是否已登录"""
        result = await self.check_auth()
        return result.get('is_authenticated', False)
    
    async def authenticate(self) -> bool:
        """登录微博"""
        await self.init_browser(headless=False)
        
        # 打开登录页
        await self.page.goto('https://weibo.com/login.php')
        
        # 等待登录成功
        max_wait = 300  # 5分钟
        for i in range(max_wait):
            if await self.is_logged_in():
                # 保存 Cookie
                await self.save_cookies()
                await self.close()
                return True
            await asyncio.sleep(1)
        
        await self.close()
        return False
    
    async def save_cookies(self):
        """保存 Cookie"""
        import os
        os.makedirs('data/cookies', exist_ok=True)
        
        storage = await self.context.storage_state()
        with open(f'data/cookies/{self.platform_id}.json', 'w', encoding='utf-8') as f:
            json.dump(storage.get('cookies', []), f, ensure_ascii=False, indent=2)
    
    async def close(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    def generate_req_id(self) -> str:
        """生成请求 ID (SN-REQID)"""
        uid = self.user_config.get('uid', '') if self.user_config else ''
        timestamp = str(int(datetime.now().timestamp() * 1000))
        
        input_str = f"{uid}&{timestamp}"
        base64_str = base64.b64encode(input_str.encode()).decode()
        base64_str = base64_str.replace('+', '-').replace('/', '_').replace('=', '')
        
        chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
        result = base64_str
        while len(result) < 43:
            result += chars[int(datetime.now().timestamp() * 1000) % len(chars)]
        
        return result[:43]
    
    async def wait_for_image_done(self, src: str) -> dict:
        """等待图片上传完成"""
        max_attempts = 30
        
        for i in range(max_attempts):
            req_id = self.generate_req_id()
            
            result = await self.page.evaluate(f"""
                async () => {{
                    const res = await fetch('https://card.weibo.com/article/v5/aj/editor/plugins/asyncimginfo?uid={self.user_config['uid']}&_rid={req_id}', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'accept': 'application/json, text/plain, */*',
                            'SN-REQID': '{req_id}',
                        }},
                        body: new URLSearchParams({{ 'urls[0]': '{src}' }}),
                    }});
                    return await res.json();
                }}
            """)
            
            item = result.get('data', [{}])[0] if result.get('data') else None
            status_code = item.get('task_status_code') if item else None
            
            if status_code == 1 and item:
                return item
            
            if status_code == 2:
                raise Exception('图片上传失败')
            
            await asyncio.sleep(1)
        
        raise Exception('图片上传超时')
    
    async def upload_image_by_url(self, src: str) -> dict:
        """通过 URL 上传图片"""
        if src.startswith('data:'):
            return await self.upload_data_uri(src)
        
        req_id = self.generate_req_id()
        
        # 发起异步上传请求
        try:
            await self.page.evaluate(f"""
                async () => {{
                    await fetch('https://card.weibo.com/article/v5/aj/editor/plugins/asyncuploadimg?uid={self.user_config['uid']}&_rid={req_id}', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'accept': 'application/json, text/plain, */*',
                            'SN-REQID': '{req_id}',
                        }},
                        body: new URLSearchParams({{ 'urls[0]': '{src}' }}),
                    }});
                }}
            """)
        except:
            pass
        
        # 轮询等待上传完成
        img_detail = await self.wait_for_image_done(src)
        img_url = f"https://wx3.sinaimg.cn/large/{img_detail['pid']}.jpg"
        
        return {
            'url': img_url,
            'pid': img_detail['pid'],
        }
    
    async def upload_data_uri(self, data_uri: str) -> dict:
        """上传 Data URI 图片"""
        match = re.match(r'^data:([^;]+);base64,(.+)$', data_uri)
        if not match:
            raise Exception('Invalid data URI format')
        
        mime_type = match.group(1)
        base64_data = match.group(2)
        
        # 转换为 blob 并上传
        req_id = self.generate_req_id()
        upload_url = f"https://picupload.weibo.com/interface/pic_upload.php?app=miniblog&s=json&p=1&data=1&url=&markpos=1&logo=0&nick=&file_source=4&_rid={req_id}"
        
        result = await self.page.evaluate(f"""
            async () => {{
                const base64Data = '{base64_data}';
                const binaryStr = atob(base64Data);
                const bytes = new Uint8Array(binaryStr.length);
                for (let i = 0; i < binaryStr.length; i++) {{
                    bytes[i] = binaryStr.charCodeAt(i);
                }}
                const blob = new Blob([bytes], {{ type: '{mime_type}' }});
                
                const res = await fetch('{upload_url}', {{
                    method: 'POST',
                    credentials: 'include',
                    body: blob,
                }});
                
                return await res.json();
            }}
        """)
        
        if not result or not result.get('data', {}).get('pics', {}).get('pic_1', {}).get('pid'):
            raise Exception(f"图片上传失败: {result}")
        
        pid = result['data']['pics']['pic_1']['pid']
        img_url = f"https://wx3.sinaimg.cn/large/{pid}.jpg"
        
        return {
            'url': img_url,
            'pid': pid,
        }
    
    async def process_weibo_images(self, content: str) -> str:
        """处理微博内容中的图片"""
        # 查找图片
        img_regex = r'<img[^>]+src="([^"]+)"[^>]*>'
        matches = list(re.finditer(img_regex, content))
        
        if not matches:
            return content
        
        print(f"找到 {len(matches)} 张图片需要处理")
        
        result = content
        uploaded_map = {}
        
        for i, match in enumerate(matches):
            full_tag = match.group(0)
            src = match.group(1)
            
            if not src:
                continue
            
            # 跳过微博自己的图片
            if 'sinaimg.cn' in src or 'weibo.com' in src:
                continue
            
            if src.startswith('data:'):
                continue
            
            try:
                if src not in uploaded_map:
                    print(f"上传图片 {i+1}/{len(matches)}: {src}")
                    upload_result = await self.upload_image_by_url(src)
                    uploaded_map[src] = upload_result
                
                img_info = uploaded_map[src]
                replacement = f'<figure class="image"><img src="{img_info["url"]}" data-pid="{img_info["pid"]}" /></figure>'
                result = result.replace(full_tag, replacement)
                
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"图片上传失败: {src}, 错误: {e}")
        
        return result
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """发布文章到微博"""
        debug_log = []
        
        def log(msg):
            debug_log.append(msg)
            print(msg)
        
        try:
            await self.init_browser()
            
            # 获取用户配置
            log("获取用户配置...")
            config = await self.get_user_config()
            if not config or not config.get('uid'):
                log("未登录，请先运行 login 命令")
                return ToolResult(success=False, error="未登录")
            
            log(f"已登录: {config.get('nick')}")
            
            # 准备内容
            title = getattr(article, 'title', '无标题')
            html_content = getattr(article, 'html_content', '')
            
            if not html_content and file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 简单转换为 HTML
                    html_content = f"<p>{content.replace(chr(10), '</p><p>')}</p>"
            
            # 清理 HTML
            html_content = html_content.replace('>\s+<', '><')
            
            # 处理图片
            log("处理图片...")
            html_content = await self.process_weibo_images(html_content)
            
            # 创建草稿
            log("创建草稿...")
            create_req_id = self.generate_req_id()
            
            create_result = await self.page.evaluate(f"""
                async () => {{
                    const res = await fetch('https://card.weibo.com/article/v5/aj/editor/draft/create?uid={config['uid']}&_rid={create_req_id}', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'accept': 'application/json, text/plain, */*',
                            'SN-REQID': '{create_req_id}',
                        }},
                        body: new URLSearchParams({{}}),
                    }});
                    return await res.json();
                }}
            """)
            
            log(f"创建草稿响应: {create_result}")
            
            if create_result.get('code') != 100000 or not create_result.get('data', {}).get('id'):
                error_msg = create_result.get('msg') or '创建草稿失败'
                return ToolResult(success=False, error=error_msg)
            
            post_id = create_result['data']['id']
            log(f"草稿创建成功: {post_id}")
            
            # 上传封面图
            cover_url = ''
            cover_image = getattr(article, 'cover_image', None)
            if cover_image:
                try:
                    log("上传封面图...")
                    import base64
                    with open(cover_image, 'rb') as f:
                        image_data = base64.b64encode(f.read()).decode()
                    ext = cover_image.split('.')[-1].lower()
                    if ext == 'jpg':
                        ext = 'jpeg'
                    mime_type = f'image/{ext}'
                    data_uri = f'data:{mime_type};base64,{image_data}'
                    
                    cover_result = await self.upload_data_uri(data_uri)
                    cover_url = cover_result['url']
                    log(f"封面上传成功: {cover_url}")
                except Exception as e:
                    log(f"封面上传失败: {e}")
            
            # 保存草稿
            log("保存草稿...")
            save_req_id = self.generate_req_id()
            
            # 构建表单数据
            form_data = {
                'id': post_id,
                'title': title,
                'subtitle': '',
                'type': '',
                'status': '0',
                'publish_at': '',
                'error_msg': '',
                'error_code': '0',
                'collection': '[]',
                'free_content': '',
                'content': html_content,
                'cover': cover_url,
                'summary': '',
                'writer': '',
                'extra': 'null',
                'is_word': '0',
                'article_recommend': '[]',
                'follow_to_read': '1',
                'isreward': '1',
                'pay_setting': '{"ispay":0,"isvclub":0}',
                'source': '0',
                'action': '1',
                'content_type': '0',
                'save': '1',
            }
            
            save_result = await self.page.evaluate(f"""
                async () => {{
                    const params = new URLSearchParams({json.dumps(form_data)});
                    const res = await fetch('https://card.weibo.com/article/v5/aj/editor/draft/save?uid={config['uid']}&id={post_id}&_rid={save_req_id}', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'accept': 'application/json, text/plain, */*',
                            'SN-REQID': '{save_req_id}',
                        }},
                        body: params,
                    }});
                    return await res.json();
                }}
            """)
            
            log(f"保存草稿响应: {save_result}")
            
            code = str(save_result.get('code', ''))
            if code != '100000':
                error_msg = save_result.get('msg') or f'保存失败 (错误码: {code})'
                return ToolResult(success=False, error=error_msg)
            
            draft_url = f"https://card.weibo.com/article/v5/editor#/draft/{post_id}"
            log(f"草稿保存成功: {draft_url}")
            
            await self.close()
            
            return ToolResult(
                success=True,
                post_id=post_id,
                post_url=draft_url,
                data={'platform': 'weibo', 'draft_url': draft_url}
            )
            
        except Exception as e:
            log(f"发布失败: {str(e)}")
            await self.close()
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> dict:
        """检查文章发布状态"""
        try:
            await self.init_browser()
            
            if not await self.is_logged_in():
                return {'success': False, 'error': '未登录'}
            
            config = await self.get_user_config()
            uid = config.get('uid') if config else ''
            
            # 查询草稿状态
            req_id = self.generate_req_id()
            result = await self.page.evaluate(f"""
                async () => {{
                    const res = await fetch('https://card.weibo.com/article/v5/aj/editor/draft/list?uid={uid}&page=1&_rid={req_id}', {{
                        method: 'GET',
                        credentials: 'include',
                        headers: {{
                            'accept': 'application/json, text/plain, */*',
                            'SN-REQID': '{req_id}',
                        }},
                    }});
                    return await res.json();
                }}
            """)
            
            await self.close()
            
            if result and result.get('code') == 100000:
                drafts = result.get('data', {}).get('list', [])
                for draft in drafts:
                    if str(draft.get('id')) == post_id:
                        return {
                            'success': True,
                            'status': draft.get('status'),  # 0:草稿, 1:已发布
                            'title': draft.get('title'),
                            'url': f"https://card.weibo.com/article/v5/editor#/draft/{post_id}",
                        }
                
                return {'success': False, 'error': '未找到该文章'}
            
            return {'success': False, 'error': result.get('msg', '查询失败')}
            
        except Exception as e:
            await self.close()
            return {'success': False, 'error': str(e)}
