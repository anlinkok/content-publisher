"""
掘金平台适配器
参考 Wechatsync 的 juejin.ts 实现
"""
import asyncio
import json
import re
import hashlib
import hmac
import base64
from datetime import datetime
from typing import Optional
from playwright.async_api import Page, Locator

from platforms.base import PlatformTool, ToolResult


class JuejinTool(PlatformTool):
    """掘金平台适配器"""
    
    platform_name = "juejin"
    platform_id = "juejin"
    platform_type = "article"
    
    # 掘金使用 Markdown 格式
    output_format = "markdown"
    
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
    
    async def check_auth(self) -> dict:
        """检查登录状态"""
        try:
            response = await self.page.evaluate("""
                async () => {
                    const res = await fetch('https://api.juejin.cn/user_api/v1/user/get', {
                        method: 'GET',
                        credentials: 'include',
                        headers: {
                            'Origin': 'https://juejin.cn',
                            'Referer': 'https://juejin.cn/',
                        }
                    });
                    return await res.json();
                }
            """)
            
            if response.get('data', {}).get('user_id'):
                return {
                    'is_authenticated': True,
                    'user_id': response['data']['user_id'],
                    'username': response['data'].get('user_name'),
                    'avatar': response['data'].get('avatar_large'),
                }
            return {'is_authenticated': False}
        except Exception as e:
            return {'is_authenticated': False, 'error': str(e)}
    
    async def is_logged_in(self) -> bool:
        """检查是否已登录"""
        result = await self.check_auth()
        return result.get('is_authenticated', False)
    
    async def authenticate(self) -> bool:
        """登录掘金"""
        await self.init_browser(headless=False)
        
        # 打开登录页
        await self.page.goto('https://juejin.cn/login')
        
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
    
    async def get_csrf_token(self) -> str:
        """获取 CSRF Token"""
        response = await self.page.evaluate("""
            async () => {
                const res = await fetch('https://api.juejin.cn/user_api/v1/sys/token', {
                    method: 'HEAD',
                    headers: {
                        'x-secsdk-csrf-request': '1',
                        'x-secsdk-csrf-version': '1.2.10',
                    },
                    credentials: 'include',
                });
                return res.headers.get('x-ware-csrf-token');
            }
        """)
        
        if response:
            # Token 格式: "0,{actual_token},86370000,success,{session_id}"
            parts = response.split(',')
            if len(parts) >= 2:
                return parts[1]
        
        raise Exception('Failed to get CSRF token')
    
    async def upload_image(self, image_path: str) -> str:
        """上传图片到掘金图床"""
        try:
            # 读取图片文件
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # 获取图片类型
            ext = image_path.split('.')[-1].lower()
            if ext == 'jpg':
                ext = 'jpeg'
            mime_type = f'image/{ext}'
            
            # 将图片转为 base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            data_uri = f'data:{mime_type};base64,{image_base64}'
            
            # 通过 Page.evaluate 上传图片
            result = await self.page.evaluate(f"""
                async () => {{
                    const blob = await fetch('{data_uri}').then(r => r.blob());
                    
                    // 1. 获取 ImageX Token
                    const tokenRes = await fetch('https://api.juejin.cn/imagex/v2/gen_token?aid=2608&uuid={self._generate_uuid()}&client=web', {{
                        credentials: 'include',
                        headers: {{ 'Content-Type': 'application/json' }}
                    }});
                    const tokenData = await tokenRes.json();
                    
                    if (tokenData.err_no !== 0) {{
                        throw new Error('Failed to get ImageX token');
                    }}
                    
                    const token = tokenData.data.token;
                    
                    // 2. 申请上传 (简化版，实际需要 AWS4 签名)
                    // 这里使用掘金编辑器的直接上传方式
                    const formData = new FormData();
                    formData.append('file', blob, 'image.{ext}');
                    
                    const uploadRes = await fetch('https://api.juejin.cn/imagex/v1/upload', {{
                        method: 'POST',
                        credentials: 'include',
                        body: formData,
                    }});
                    
                    const uploadData = await uploadRes.json();
                    return uploadData.data?.url || null;
                }}
            """)
            
            if result:
                return result
            
            # 如果直接上传失败，返回原路径（可能需要手动上传）
            return image_path
            
        except Exception as e:
            print(f"掘金图片上传失败: {e}")
            return image_path
    
    def _generate_uuid(self) -> str:
        """生成 UUID"""
        import random
        chars = 'xxxxxxxxxxxxxxxx'
        uuid = ''.join([format(random.randint(0, 15), 'x') for _ in chars])
        return uuid + str(int(datetime.now().timestamp() * 1000))
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """发布文章到掘金"""
        debug_log = []
        
        def log(msg):
            debug_log.append(msg)
            print(msg)
        
        try:
            await self.init_browser()
            
            # 检查登录
            log("检查登录状态...")
            if not await self.is_logged_in():
                log("未登录，请先运行 login 命令")
                return ToolResult(success=False, error="未登录")
            
            log("已登录")
            
            # 获取 CSRF Token
            log("获取 CSRF Token...")
            csrf_token = await self.get_csrf_token()
            log(f"CSRF Token: {csrf_token[:20]}...")
            
            # 准备内容
            title = getattr(article, 'title', '无标题')
            markdown_content = getattr(article, 'markdown_content', '')
            
            if not markdown_content and file_path:
                # 从文件读取
                with open(file_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
            
            # 创建草稿
            log("创建草稿...")
            create_result = await self.page.evaluate(f"""
                async () => {{
                    const res = await fetch('https://api.juejin.cn/content_api/v1/article_draft/create', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/json',
                            'x-secsdk-csrf-token': '{csrf_token}',
                        }},
                        body: JSON.stringify({{
                            brief_content: '',
                            category_id: '0',
                            cover_image: '',
                            edit_type: 10,
                            html_content: 'deprecated',
                            link_url: '',
                            mark_content: {json.dumps(markdown_content)},
                            tag_ids: [],
                            title: {json.dumps(title)},
                        }}),
                    }});
                    return await res.json();
                }}
            """)
            
            log(f"创建草稿响应: {create_result}")
            
            if create_result.get('err_no') != 0:
                error_msg = create_result.get('err_msg', '未知错误')
                return ToolResult(success=False, error=f"创建草稿失败: {error_msg}")
            
            draft_id = create_result.get('data', {}).get('id')
            if not draft_id:
                return ToolResult(success=False, error="创建草稿失败: 无 draft_id")
            
            draft_url = f"https://juejin.cn/editor/drafts/{draft_id}"
            log(f"草稿创建成功: {draft_url}")
            
            await self.close()
            
            return ToolResult(
                success=True,
                post_id=draft_id,
                post_url=draft_url,
                data={'platform': 'juejin', 'draft_url': draft_url}
            )
            
        except Exception as e:
            log(f"发布失败: {str(e)}")
            await self.close()
            return ToolResult(success=False, error=str(e))
