"""
搜狐号 (Sohu) 平台适配器
参考 Wechatsync 的 sohu.ts 实现
"""
import asyncio
import json
import random
from typing import Optional
from playwright.async_api import Page

from platforms.base import PlatformTool, ToolResult


def generate_device_id() -> str:
    """生成设备 ID"""
    chars = '0123456789abcdef'
    return ''.join([random.choice(chars) for _ in range(32)])


class SohuTool(PlatformTool):
    """搜狐号平台适配器"""
    
    platform_name = "sohu"
    platform_id = "sohu"
    platform_type = "article"
    
    # 搜狐号使用 HTML 格式
    output_format = "html"
    
    def __init__(self, account=None):
        super().__init__(account)
        self.account_info: Optional[dict] = None
        self.device_id: str = generate_device_id()
        self.sp_cm: str = ''
    
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
    
    async def fetch_sp_cm(self):
        """获取 sp-cm 值"""
        try:
            # 从 cookie 中获取 mp-cv
            cookies = await self.context.cookies(['https://mp.sohu.com'])
            for cookie in cookies:
                if cookie.get('name') == 'mp-cv':
                    self.sp_cm = cookie.get('value')
                    return
            
            # fallback: 生成一个
            self.sp_cm = f"100-{int(asyncio.get_event_loop().time() * 1000)}-{self.device_id}"
        except:
            self.sp_cm = f"100-{int(asyncio.get_event_loop().time() * 1000)}-{self.device_id}"
    
    async def check_auth(self) -> dict:
        """检查登录状态"""
        try:
            timestamp = int(asyncio.get_event_loop().time() * 1000)
            
            result = await self.page.evaluate(f"""
                async () => {{
                    const res = await fetch('https://mp.sohu.com/mpbp/bp/account/list?_={timestamp}', {{
                        method: 'GET',
                        credentials: 'include',
                    }});
                    return await res.json();
                }}
            """)
            
            if result.get('code') == 2000000 and result.get('data', {}).get('data', [{}])[0].get('accounts'):
                accounts = []
                for group in result['data']['data']:
                    if group.get('accounts'):
                        accounts.extend(group['accounts'])
                
                if accounts:
                    self.account_info = accounts[0]
                    await self.fetch_sp_cm()
                    
                    display_name = self.account_info.get('nickName', '')
                    if len(accounts) > 1:
                        display_name += f" (共{len(accounts)}个子账号)"
                    
                    return {
                        'is_authenticated': True,
                        'user_id': str(self.account_info.get('id')),
                        'username': display_name,
                        'avatar': self.account_info.get('avatar'),
                    }
            
            return {'is_authenticated': False}
        except Exception as e:
            return {'is_authenticated': False, 'error': str(e)}
    
    async def is_logged_in(self) -> bool:
        """检查是否已登录"""
        result = await self.check_auth()
        return result.get('is_authenticated', False)
    
    async def authenticate(self) -> bool:
        """登录搜狐号"""
        await self.init_browser(headless=False)
        
        # 打开登录页
        await self.page.goto('https://mp.sohu.com/')
        
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
    
    async def upload_image(self, image_path: str) -> str:
        """上传图片到搜狐号"""
        try:
            # 读取图片
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # 转为 base64
            import base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            ext = image_path.split('.')[-1].lower()
            if ext == 'jpg':
                ext = 'jpeg'
            mime_type = f'image/{ext}'
            
            account_id = self.account_info.get('id') if self.account_info else ''
            
            result = await self.page.evaluate(f"""
                async () => {{
                    const blob = await fetch('data:{mime_type};base64,{image_base64}').then(r => r.blob());
                    
                    const formData = new FormData();
                    formData.append('file', blob, 'image.{ext}');
                    formData.append('accountId', '{account_id}');
                    
                    const res = await fetch('https://mp.sohu.com/commons/front/outerUpload/image/file?accountId={account_id}', {{
                        method: 'POST',
                        credentials: 'include',
                        body: formData,
                    }});
                    
                    return await res.json();
                }}
            """)
            
            if result and result.get('url'):
                return result['url']
            
            return image_path
            
        except Exception as e:
            print(f"搜狐号图片上传失败: {e}")
            return image_path
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """发布文章到搜狐号"""
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
            
            log(f"已登录，账号: {self.account_info.get('nickName')}")
            
            # 准备内容
            title = getattr(article, 'title', '无标题')
            html_content = getattr(article, 'html_content', '')
            
            if not html_content and file_path:
                # 读取文件并转换为 HTML
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 简单转换为 HTML
                    html_content = f"<p>{content.replace(chr(10), '</p><p>')}</p>"
            
            # 保存草稿
            log("创建草稿...")
            account_id = self.account_info.get('id')
            
            post_data = {
                'title': title,
                'brief': '',
                'content': html_content,
                'channelId': 24,
                'categoryId': -1,
                'id': 0,
                'userColumnId': 0,
                'columnNewsIds': [],
                'businessCode': 0,
                'declareOriginal': False,
                'cover': '',
                'topicIds': [],
                'isAd': 0,
                'userLabels': '[]',
                'reprint': False,
                'customTags': '',
                'infoResource': 0,
                'sourceUrl': '',
                'visibleToLoginedUsers': 0,
                'attrIds': [],
                'auto': True,
                'accountId': account_id,
            }
            
            create_result = await self.page.evaluate(f"""
                async () => {{
                    const res = await fetch('https://mp.sohu.com/mpbp/bp/news/v4/news/draft/v2?accountId={account_id}', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest',
                            'dv-id': '{self.device_id}',
                            'sp-cm': '{self.sp_cm}',
                        }},
                        body: JSON.stringify({json.dumps(post_data)}),
                    }});
                    return await res.json();
                }}
            """)
            
            log(f"创建响应: {create_result}")
            
            if not create_result or not create_result.get('success'):
                error_msg = create_result.get('msg') if isinstance(create_result, dict) else '保存失败'
                return ToolResult(success=False, error=error_msg)
            
            post_id = str(create_result['data'])
            draft_url = f"https://mp.sohu.com/mpfe/v4/contentManagement/news/addarticle?contentStatus=2&id={post_id}"
            log(f"草稿创建成功: {draft_url}")
            
            await self.close()
            
            return ToolResult(
                success=True,
                post_id=post_id,
                post_url=draft_url,
                data={'platform': 'sohu', 'draft_url': draft_url}
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
            
            # 搜狐号草稿状态检查
            account_id = self.account_info.get('id') if self.account_info else ''
            
            result = await self.page.evaluate(f"""
                async () => {{
                    const res = await fetch('https://mp.sohu.com/mpbp/bp/news/v4/news/draft/list?accountId={account_id}&page=1', {{
                        method: 'GET',
                        credentials: 'include',
                        headers: {{
                            'X-Requested-With': 'XMLHttpRequest',
                        }},
                    }});
                    return await res.json();
                }}
            """)
            
            await self.close()
            
            if result and result.get('success'):
                drafts = result.get('data', {}).get('list', [])
                for draft in drafts:
                    if str(draft.get('id')) == post_id:
                        return {{
                            'success': True,
                            'status': draft.get('contentStatus'),  # 0:草稿, 1:审核中, 2:已发布
                            'title': draft.get('title'),
                            'url': f"https://mp.sohu.com/mpfe/v4/contentManagement/news/addarticle?contentStatus=2&id={post_id}",
                        }}
                return {'success': False, 'error': '未找到该文章'}
            
            return {'success': False, 'error': '查询失败'}
            
        except Exception as e:
            await self.close()
            return {'success': False, 'error': str(e)}
