"""
CSDN 平台适配器
参考 Wechatsync 的 csdn.ts 实现
"""
import asyncio
import json
import hashlib
import hmac
import base64
import uuid
from datetime import datetime
from typing import Optional
from playwright.async_api import Page

from platforms.base import PlatformTool, ToolResult


class CSDNTool(PlatformTool):
    """CSDN 平台适配器"""
    
    platform_name = "csdn"
    platform_id = "csdn"
    platform_type = "article"
    
    # CSDN 使用 Markdown 格式
    output_format = "markdown"
    
    # CSDN API 签名密钥
    API_KEY = '203803574'
    API_SECRET = '9znpamsyl2c7cdrr9sas0le9vbc3r6ba'
    
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
            # 生成签名
            api_path = '/blog-console-api/v3/editor/getBaseInfo'
            headers = await self._generate_sign_headers(api_path, 'GET')
            
            result = await self.page.evaluate(f"""
                async () => {{
                    const res = await fetch('https://bizapi.csdn.net{api_path}', {{
                        method: 'GET',
                        credentials: 'include',
                        headers: {json.dumps(headers)},
                    }});
                    return await res.json();
                }}
            """)
            
            if result.get('code') == 200 and result.get('data', {}).get('name'):
                return {
                    'is_authenticated': True,
                    'user_id': result['data']['name'],
                    'username': result['data'].get('nickname') or result['data']['name'],
                    'avatar': result['data'].get('avatar'),
                }
            return {'is_authenticated': False}
        except Exception as e:
            return {'is_authenticated': False, 'error': str(e)}
    
    async def is_logged_in(self) -> bool:
        """检查是否已登录"""
        result = await self.check_auth()
        return result.get('is_authenticated', False)
    
    async def authenticate(self) -> bool:
        """登录 CSDN"""
        await self.init_browser(headless=False)
        
        # 打开登录页
        await self.page.goto('https://passport.csdn.net/login')
        
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
    
    async def _generate_sign_headers(self, api_path: str, method: str = 'POST') -> dict:
        """生成 CSDN API 签名
        签名格式: METHOD\nAccept\nContent-MD5\nContent-Type\n\nHeaders\nPath
        """
        nonce = str(uuid.uuid4())
        
        # 构建签名字符串
        if method == 'GET':
            sign_str = f"GET\n*/*\n\n\n\nx-ca-key:{self.API_KEY}\nx-ca-nonce:{nonce}\n{api_path}"
        else:
            sign_str = f"POST\n*/*\n\napplication/json\n\nx-ca-key:{self.API_KEY}\nx-ca-nonce:{nonce}\n{api_path}"
        
        # HMAC-SHA256 签名
        signature = base64.b64encode(
            hmac.new(
                self.API_SECRET.encode('utf-8'),
                sign_str.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        headers = {
            'accept': '*/*',
            'x-ca-key': self.API_KEY,
            'x-ca-nonce': nonce,
            'x-ca-signature': signature,
            'x-ca-signature-headers': 'x-ca-key,x-ca-nonce',
        }
        
        if method == 'POST':
            headers['content-type'] = 'application/json'
        
        return headers
    
    async def upload_image(self, image_path: str) -> str:
        """上传图片到 CSDN 图床"""
        try:
            # 读取图片
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            ext = image_path.split('.')[-1].lower()
            if ext == 'jpg':
                ext = 'jpeg'
            
            # 转为 base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            mime_type = f'image/{ext}'
            
            # 使用浏览器上传
            result = await self.page.evaluate(f"""
                async () => {{
                    const blob = await fetch('data:{mime_type};base64,{image_base64}').then(r => r.blob());
                    
                    // 获取上传签名
                    const signRes = await fetch('https://bizapi.csdn.net/resource-api/v1/image/direct/upload/signature', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/json',
                            'x-ca-key': '{self.API_KEY}',
                        }},
                        body: JSON.stringify({{
                            imageTemplate: '',
                            appName: 'direct_blog_markdown',
                            imageSuffix: '{ext}',
                        }}),
                    }});
                    
                    const signData = await signRes.json();
                    if (signData.code !== 200) {{
                        return null;
                    }}
                    
                    const uploadData = signData.data;
                    
                    // 上传到华为云 OBS
                    const formData = new FormData();
                    formData.append('key', uploadData.filePath);
                    formData.append('policy', uploadData.policy);
                    formData.append('signature', uploadData.signature);
                    formData.append('AccessKeyId', uploadData.accessId);
                    formData.append('file', blob, 'image.{ext}');
                    
                    const obsRes = await fetch(uploadData.host, {{
                        method: 'POST',
                        body: formData,
                    }});
                    
                    const obsData = await obsRes.json();
                    return obsData.data?.imageUrl || null;
                }}
            """)
            
            if result:
                return result
            
            return image_path
            
        except Exception as e:
            print(f"CSDN 图片上传失败: {e}")
            return image_path
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """发布文章到 CSDN"""
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
            
            # 准备内容
            title = getattr(article, 'title', '无标题')
            markdown_content = getattr(article, 'markdown_content', '')
            html_content = getattr(article, 'html_content', '')
            
            if not markdown_content and file_path:
                # 从文件读取
                with open(file_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
            
            # 生成签名
            api_path = '/blog-console-api/v3/mdeditor/saveArticle'
            headers = await self._generate_sign_headers(api_path)
            
            # 保存文章
            log("保存草稿...")
            save_result = await self.page.evaluate(f"""
                async () => {{
                    const res = await fetch('https://bizapi.csdn.net{api_path}', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {json.dumps(headers)},
                        body: JSON.stringify({{
                            title: {json.dumps(title)},
                            markdowncontent: {json.dumps(markdown_content)},
                            content: {json.dumps(html_content)},
                            readType: 'public',
                            level: 0,
                            tags: '',
                            status: 2,
                            categories: '',
                            type: 'original',
                            original_link: '',
                            authorized_status: false,
                            not_auto_saved: '1',
                            source: 'pc_mdeditor',
                            cover_images: [],
                            cover_type: 1,
                            is_new: 1,
                            vote_id: 0,
                            resource_id: '',
                            pubStatus: 'draft',
                            creator_activity_id: '',
                        }}),
                    }});
                    return await res.json();
                }}
            """)
            
            log(f"保存响应: {save_result}")
            
            if save_result.get('code') != 200:
                error_msg = save_result.get('msg') or save_result.get('message') or '未知错误'
                return ToolResult(success=False, error=f"保存失败: {error_msg}")
            
            post_id = save_result.get('data', {}).get('id')
            if not post_id:
                return ToolResult(success=False, error="保存失败: 无 post_id")
            
            draft_url = f"https://editor.csdn.net/md?articleId={post_id}"
            log(f"草稿保存成功: {draft_url}")
            
            await self.close()
            
            return ToolResult(
                success=True,
                post_id=post_id,
                post_url=draft_url,
                data={'platform': 'csdn', 'draft_url': draft_url}
            )
            
        except Exception as e:
            log(f"发布失败: {str(e)}")
            await self.close()
            return ToolResult(success=False, error=str(e))
