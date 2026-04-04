"""
博客园 (CNBlogs) 平台适配器
参考 Wechatsync 的 cnblogs.ts 实现
"""
import asyncio
import json
import re
from typing import Optional
from playwright.async_api import Page

from platforms.base import PlatformTool, ToolResult


class CnblogsTool(PlatformTool):
    """博客园平台适配器"""
    
    platform_name = "cnblogs"
    platform_id = "cnblogs"
    platform_type = "article"
    
    # 博客园使用 Markdown 格式
    output_format = "markdown"
    
    def __init__(self, account=None):
        super().__init__(account)
        self.xsrf_token: Optional[str] = None
    
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
    
    async def get_xsrf_token(self) -> Optional[str]:
        """获取 XSRF-TOKEN"""
        if self.xsrf_token:
            return self.xsrf_token
        
        try:
            # 访问编辑页面以触发 cookie 设置
            await self.page.goto('https://i.cnblogs.com/posts/edit', wait_until='domcontentloaded')
            await asyncio.sleep(2)
            
            # 从 cookies 中获取 XSRF-TOKEN
            cookies = await self.context.cookies()
            for cookie in cookies:
                if cookie.get('name') == 'XSRF-TOKEN':
                    self.xsrf_token = cookie.get('value')
                    return self.xsrf_token
            
            return None
        except Exception as e:
            print(f"获取 XSRF-TOKEN 失败: {e}")
            return None
    
    async def check_auth(self) -> dict:
        """检查登录状态"""
        try:
            response = await self.page.evaluate("""
                async () => {
                    const res = await fetch('https://home.cnblogs.com/user/CurrentUserInfo', {
                        method: 'GET',
                        credentials: 'include',
                    });
                    return await res.text();
                }
            """)
            
            # 解析 HTML 获取用户信息
            avatar_match = re.search(r'<img[^>]+class="pfs"[^>]+src="([^"]+)"', response)
            link_match = re.search(r'href="/u/([^/]+)/"', response)
            
            if link_match:
                uid = link_match.group(1)
                avatar = avatar_match.group(1) if avatar_match else None
                return {
                    'is_authenticated': True,
                    'user_id': uid,
                    'username': uid,
                    'avatar': avatar,
                }
            return {'is_authenticated': False}
        except Exception as e:
            return {'is_authenticated': False, 'error': str(e)}
    
    async def is_logged_in(self) -> bool:
        """检查是否已登录"""
        result = await self.check_auth()
        return result.get('is_authenticated', False)
    
    async def authenticate(self) -> bool:
        """登录博客园"""
        await self.init_browser(headless=False)
        
        # 打开登录页
        await self.page.goto('https://account.cnblogs.com/signin')
        
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
        """上传图片到博客园"""
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
                    formData.append('image', blob, 'image.{ext}');
                    formData.append('app', 'blog');
                    formData.append('uploadType', 'Select');
                    
                    const res = await fetch('https://upload.cnblogs.com/v2/images/cors-upload', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{
                            'x-xsrf-token': '{self.xsrf_token or ''}',
                        }},
                        body: formData,
                    }});
                    
                    return await res.json();
                }}
            """)
            
            if result and isinstance(result, dict):
                image_url = result.get('data') or result.get('url') or result.get('imageUrl')
                if image_url:
                    return image_url
            
            return image_path
            
        except Exception as e:
            print(f"博客园图片上传失败: {e}")
            return image_path
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """发布文章到博客园"""
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
            
            # 获取 XSRF-TOKEN
            log("获取 XSRF-TOKEN...")
            xsrf_token = await self.get_xsrf_token()
            if not xsrf_token:
                return ToolResult(success=False, error="获取 XSRF-TOKEN 失败")
            
            self.xsrf_token = xsrf_token
            log(f"XSRF-TOKEN: {xsrf_token[:20]}...")
            
            # 准备内容
            title = getattr(article, 'title', '无标题')
            markdown_content = getattr(article, 'markdown_content', '')
            
            if not markdown_content and file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
            
            # 创建文章
            log("创建草稿...")
            create_result = await self.page.evaluate(f"""
                async () => {{
                    const res = await fetch('https://i.cnblogs.com/api/posts', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/json',
                            'x-xsrf-token': '{xsrf_token}',
                        }},
                        body: JSON.stringify({{
                            id: null,
                            postType: 2,
                            accessPermission: 0,
                            title: {json.dumps(title)},
                            url: null,
                            postBody: {json.dumps(markdown_content)},
                            categoryIds: null,
                            categories: null,
                            collectionIds: [],
                            inSiteCandidate: false,
                            inSiteHome: false,
                            siteCategoryId: null,
                            blogTeamIds: null,
                            isPublished: false,
                            displayOnHomePage: false,
                            isAllowComments: true,
                            includeInMainSyndication: false,
                            isPinned: false,
                            showBodyWhenPinned: false,
                            isOnlyForRegisterUser: false,
                            isUpdateDateAdded: false,
                            entryName: null,
                            description: null,
                            featuredImage: null,
                            tags: null,
                            password: null,
                            publishAt: null,
                            datePublished: new Date().toISOString(),
                            dateUpdated: null,
                            isMarkdown: true,
                            isDraft: true,
                            autoDesc: null,
                            changePostType: false,
                            blogId: 0,
                            author: null,
                            removeScript: false,
                            clientInfo: null,
                            changeCreatedTime: false,
                            canChangeCreatedTime: false,
                            isContributeToImpressiveBugActivity: false,
                            usingEditorId: 5,
                            sourceUrl: null,
                        }}),
                    }});
                    return await res.json();
                }}
            """)
            
            log(f"创建响应: {create_result}")
            
            if not create_result or not create_result.get('id'):
                error_msg = create_result.get('error') if isinstance(create_result, dict) else '创建草稿失败'
                return ToolResult(success=False, error=error_msg)
            
            post_id = str(create_result['id'])
            draft_url = f"https://i.cnblogs.com/articles/edit;postId={post_id}"
            log(f"草稿创建成功: {draft_url}")
            
            await self.close()
            
            return ToolResult(
                success=True,
                post_id=post_id,
                post_url=draft_url,
                data={'platform': 'cnblogs', 'draft_url': draft_url}
            )
            
        except Exception as e:
            log(f"发布失败: {str(e)}")
            await self.close()
            return ToolResult(success=False, error=str(e))
