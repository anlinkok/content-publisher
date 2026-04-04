"""
开源中国 (OSChina) 平台适配器
参考 Wechatsync 的 oschina.ts 实现
"""
import asyncio
import json
from typing import Optional
from playwright.async_api import Page

from platforms.base import PlatformTool, ToolResult


class OschinaTool(PlatformTool):
    """开源中国平台适配器"""
    
    platform_name = "oschina"
    platform_id = "oschina"
    platform_type = "article"
    
    # 开源中国使用 Markdown 格式
    output_format = "markdown"
    
    def __init__(self, account=None):
        super().__init__(account)
        self.user_id: Optional[str] = None
    
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
            result = await self.page.evaluate("""
                async () => {
                    const res = await fetch('https://apiv1.oschina.net/oschinapi/user/myDetails', {
                        credentials: 'include',
                    });
                    return await res.json();
                }
            """)
            
            if result.get('success') and result.get('result', {}).get('userId'):
                self.user_id = str(result['result']['userId'])
                return {
                    'is_authenticated': True,
                    'user_id': self.user_id,
                    'username': result['result'].get('userVo', {}).get('name', self.user_id),
                    'avatar': result['result'].get('userVo', {}).get('portraitUrl'),
                }
            return {'is_authenticated': False}
        except Exception as e:
            return {'is_authenticated': False, 'error': str(e)}
    
    async def is_logged_in(self) -> bool:
        """检查是否已登录"""
        result = await self.check_auth()
        return result.get('is_authenticated', False)
    
    async def authenticate(self) -> bool:
        """登录开源中国"""
        await self.init_browser(headless=False)
        
        # 打开登录页
        await self.page.goto('https://www.oschina.net/home/login')
        
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
        """上传图片到开源中国"""
        try:
            # 读取图片
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # 转为 base64
            import base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # 获取文件名
            filename = image_path.split('/')[-1].split('\\')[-1]
            ext = filename.split('.')[-1].lower()
            if ext == 'jpg':
                ext = 'jpeg'
            mime_type = f'image/{ext}'
            
            # 上传图片
            result = await self.page.evaluate(f"""
                async () => {{
                    const blob = await fetch('data:{mime_type};base64,{image_base64}').then(r => r.blob());
                    
                    const formData = new FormData();
                    formData.append('file', blob, '{filename}');
                    
                    const res = await fetch('https://apiv1.oschina.net/oschinapi/ai/creation/project/uploadDetail', {{
                        method: 'POST',
                        credentials: 'include',
                        body: formData,
                    }});
                    
                    return await res.json();
                }}
            """)
            
            if result and result.get('success') and result.get('result'):
                return result['result']
            
            return image_path
            
        except Exception as e:
            print(f"开源中国图片上传失败: {e}")
            return image_path
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """发布文章到开源中国"""
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
            
            log(f"已登录，用户ID: {self.user_id}")
            
            # 准备内容
            title = getattr(article, 'title', '无标题')
            markdown_content = getattr(article, 'markdown_content', '')
            html_content = getattr(article, 'html_content', '')
            
            if not markdown_content and file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
            
            # 判断使用 Markdown 还是 HTML
            use_markdown = len(markdown_content.strip()) > 0
            content = markdown_content if use_markdown else html_content
            content_type = 1 if use_markdown else 2  # 1=markdown, 2=html
            
            # 保存草稿
            log("保存草稿...")
            save_result = await self.page.evaluate(f"""
                async () => {{
                    const res = await fetch('https://apiv1.oschina.net/oschinapi/api/draft/save_draft', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify({{
                            title: {json.dumps(title)},
                            user: Number({self.user_id}),
                            content: {json.dumps(content)},
                            contentType: {content_type},
                            catalog: 0,
                            originUrl: '',
                            privacy: true,
                            disableComment: false,
                        }}),
                    }});
                    return await res.json();
                }}
            """)
            
            log(f"保存响应: {save_result}")
            
            if not save_result or not save_result.get('success'):
                error_msg = save_result.get('message') if isinstance(save_result, dict) else '保存草稿失败'
                return ToolResult(success=False, error=error_msg)
            
            draft_id = str(save_result['result']['id'])
            draft_url = f"https://my.oschina.net/u/{self.user_id}/blog/write/draft/{draft_id}"
            log(f"草稿保存成功: {draft_url}")
            
            await self.close()
            
            return ToolResult(
                success=True,
                post_id=draft_id,
                post_url=draft_url,
                data={'platform': 'oschina', 'draft_url': draft_url}
            )
            
        except Exception as e:
            log(f"发布失败: {str(e)}")
            await self.close()
            return ToolResult(success=False, error=str(e))
