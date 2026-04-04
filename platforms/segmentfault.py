"""
SegmentFault (思否) 平台适配器
参考 Wechatsync 的 segmentfault.ts 实现
"""
import asyncio
import json
import re
from typing import Optional
from playwright.async_api import Page

from platforms.base import PlatformTool, ToolResult


class SegmentfaultTool(PlatformTool):
    """SegmentFault 平台适配器"""
    
    platform_name = "segmentfault"
    platform_id = "segmentfault"
    platform_type = "article"
    
    # SegmentFault 使用 Markdown 格式
    output_format = "markdown"
    
    def __init__(self, account=None):
        super().__init__(account)
        self.session_token: Optional[str] = None
    
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
    
    async def get_session_token(self) -> str:
        """获取 session token"""
        # 访问写文章页面
        await self.page.goto('https://segmentfault.com/write', wait_until='domcontentloaded')
        await asyncio.sleep(2)
        
        # 从页面 HTML 中提取 token
        html = await self.page.content()
        
        # 新版 token 格式: serverData":{"Token":"xxx"
        token_match = re.search(r'serverData":\s*\{\s*"Token"\s*:\s*"([^"]+)"', html)
        if token_match:
            return token_match.group(1)
        
        # 兼容旧版格式
        mark_str = 'window.g_initialProps = '
        auth_index = html.find(mark_str)
        if auth_index == -1:
            raise Exception('获取 session token 失败')
        
        end_index = html.find(';\n\t\u003c/script\u003e', auth_index)
        if end_index == -1:
            raise Exception('解析 session token 失败')
        
        config_str = html[auth_index + len(mark_str):end_index]
        
        try:
            config = json.loads(config_str)
            token = config.get('global', {}).get('sessionInfo', {}).get('key')
            if not token:
                raise Exception('session token 为空')
            return token
        except Exception as e:
            raise Exception(f'解析 session token 失败: {e}')
    
    async def check_auth(self) -> dict:
        """检查登录状态"""
        try:
            response = await self.page.evaluate("""
                async () => {
                    const res = await fetch('https://segmentfault.com/user/settings', {
                        credentials: 'include',
                    });
                    return await res.text();
                }
            """)
            
            # 匹配用户链接 href="/u/username"
            user_link_match = re.search(r'href="/u/([^"]+)"', response)
            if not user_link_match:
                return {'is_authenticated': False}
            
            uid = user_link_match.group(1)
            
            # 匹配头像 URL
            avatar_match = re.search(r'src="(https://avatar-static\.segmentfault\.com/[^"]+)"', response)
            avatar = avatar_match.group(1) if avatar_match else None
            
            return {
                'is_authenticated': True,
                'user_id': uid,
                'username': uid,
                'avatar': avatar,
            }
        except Exception as e:
            return {'is_authenticated': False, 'error': str(e)}
    
    async def is_logged_in(self) -> bool:
        """检查是否已登录"""
        result = await self.check_auth()
        return result.get('is_authenticated', False)
    
    async def authenticate(self) -> bool:
        """登录 SegmentFault"""
        await self.init_browser(headless=False)
        
        # 打开登录页
        await self.page.goto('https://segmentfault.com/signin')
        
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
        """上传图片到 SegmentFault"""
        try:
            # 读取图片
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # 转为 base64
            import base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # 获取文件扩展名
            ext = image_path.split('.')[-1].lower()
            if ext == 'jpg':
                ext = 'jpeg'
            mime_type = f'image/{ext}'
            
            # 上传图片
            result = await self.page.evaluate(f"""
                async () => {{
                    const blob = await fetch('data:{mime_type};base64,{image_base64}').then(r => r.blob());
                    
                    const formData = new FormData();
                    formData.append('image', blob);
                    
                    const res = await fetch('https://segmentfault.com/gateway/image', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{
                            'token': '{self.session_token or ''}',
                        }},
                        body: formData,
                    }});
                    
                    const text = await res.text();
                    if (text === 'Unauthorized' || text.includes('禁言') || text.includes('锁定')) {{
                        return {{ error: text }};
                    }}
                    
                    try {{
                        const data = JSON.parse(text);
                        // 新版格式: {{ url: "/img/xxx", result: "https://..." }}
                        // 旧版格式: [0, url, id] 或 [1, error_message]
                        if (data.result) {{
                            return {{ url: data.result }};
                        }} else if (Array.isArray(data)) {{
                            if (data[0] === 1) {{
                                return {{ error: data[1] || '上传失败' }};
                            }} else {{
                                return {{ url: data[1] || `https://image-static.segmentfault.com/${{data[2]}}` }};
                            }}
                        }}
                        return {{ error: '无法获取图片URL' }};
                    }} catch (e) {{
                        return {{ error: text }};
                    }}
                }}
            """)
            
            if result and result.get('url'):
                return result['url']
            
            return image_path
            
        except Exception as e:
            print(f"SegmentFault 图片上传失败: {e}")
            return image_path
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """发布文章到 SegmentFault"""
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
            
            # 获取 session token
            log("获取 session token...")
            self.session_token = await self.get_session_token()
            log(f"Token: {self.session_token[:20]}...")
            
            # 准备内容
            title = getattr(article, 'title', '无标题')
            markdown_content = getattr(article, 'markdown_content', '')
            html_content = getattr(article, 'html_content', '')
            
            if not markdown_content and file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
            
            content = markdown_content or html_content or ''
            
            # 发布文章
            log("创建草稿...")
            post_data = {
                'title': title,
                'tags': [],
                'text': content,
                'object_id': '',
                'type': 'article',
            }
            
            create_result = await self.page.evaluate(f"""
                async () => {{
                    const res = await fetch('https://segmentfault.com/gateway/draft', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/json',
                            'token': '{self.session_token}',
                            'accept': '*/*',
                        }},
                        body: JSON.stringify({json.dumps(post_data)}),
                    }});
                    
                    const text = await res.text();
                    if (text === 'Unauthorized' || text.includes('禁言') || text.includes('锁定')) {{
                        return {{ error: text }};
                    }}
                    
                    try {{
                        const data = JSON.parse(text);
                        // 处理数组格式 [1, "error_message"] 或 [0, data]
                        if (Array.isArray(data)) {{
                            if (data[0] === 1) {{
                                return {{ error: data[1] || '发布失败' }};
                            }}
                            return {{ data: data[1] }};
                        }}
                        return {{ data }};
                    }} catch (e) {{
                        return {{ error: text }};
                    }}
                }}
            """)
            
            log(f"创建响应: {create_result}")
            
            if not create_result:
                return ToolResult(success=False, error="创建草稿失败")
            
            if create_result.get('error'):
                return ToolResult(success=False, error=create_result['error'])
            
            # 提取草稿 ID
            data = create_result.get('data', {})
            draft_id = None
            if isinstance(data, dict):
                draft_id = data.get('id')
            
            if not draft_id:
                return ToolResult(success=False, error="无法获取草稿ID")
            
            draft_url = f"https://segmentfault.com/write?draftId={draft_id}"
            log(f"草稿创建成功: {draft_url}")
            
            await self.close()
            
            return ToolResult(
                success=True,
                post_id=str(draft_id),
                post_url=draft_url,
                data={'platform': 'segmentfault', 'draft_url': draft_url}
            )
            
        except Exception as e:
            log(f"发布失败: {str(e)}")
            await self.close()
            return ToolResult(success=False, error=str(e))
