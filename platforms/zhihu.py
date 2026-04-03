"""
知乎平台实现 - 使用 Playwright storage_state 持久化登录
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from platforms.base import PlatformTool, ToolResult

logger = logging.getLogger(__name__)

# Cookie 文件路径
COOKIE_DIR = Path("data/cookies")
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


class ZhihuTool(PlatformTool):
    """知乎发布工具"""
    name = "ZhihuPublisher"
    description = "Publish articles to Zhihu platform"
    platform_type = "zhihu"
    
    def __init__(self, account=None):
        super().__init__(account)
        self.cookie_file = COOKIE_DIR / "zhihu.json"
    
    async def init_browser(self, headless: bool = True, load_cookie: bool = True):
        """初始化浏览器，支持加载 Cookie"""
        from playwright.async_api import async_playwright
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        
        # 上下文配置
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'locale': 'zh-CN',
            'timezone_id': 'Asia/Shanghai',
        }
        
        # 加载 Cookie 如果存在
        if load_cookie and self.cookie_file.exists():
            try:
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    storage_state = json.load(f)
                context_options['storage_state'] = storage_state
                logger.info("知乎: 已加载保存的 Cookie")
            except Exception as e:
                logger.warning(f"加载 Cookie 失败: {e}")
        
        self.context = await self.browser.new_context(**context_options)
        
        # 注入反检测脚本
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });
        """)
        
        self.page = await self.context.new_page()
    
    async def save_cookie(self):
        """保存 Cookie 到文件"""
        if self.context:
            try:
                storage = await self.context.storage_state()
                with open(self.cookie_file, 'w', encoding='utf-8') as f:
                    json.dump(storage, f, ensure_ascii=False, indent=2)
                logger.info(f"知乎: Cookie 已保存到 {self.cookie_file}")
            except Exception as e:
                logger.error(f"保存 Cookie 失败: {e}")
    
    async def authenticate(self) -> bool:
        """知乎登录"""
        if not self.page:
            # 尝试加载 Cookie 登录
            await self.init_browser(headless=False, load_cookie=True)
            
            # 先尝试访问首页检查登录状态
            await self.page.goto("https://www.zhihu.com")
            await asyncio.sleep(2)
            
            # 检查是否已登录（看是否有用户头像）
            try:
                avatar = await self.page.wait_for_selector('.AppHeader-profile img, [data-za-detail-view-element_name="UserAvatar"]', timeout=5000)
                if avatar:
                    self._is_authenticated = True
                    logger.info("知乎: Cookie 有效，已自动登录")
                    return True
            except:
                logger.info("知乎: Cookie 失效，需要重新登录")
        
        # 需要重新登录
        from rich.console import Console
        console = Console()
        console.print("[yellow]请在浏览器中完成知乎登录...[/yellow]")
        await self.page.goto("https://www.zhihu.com/signin")
        
        # 等待用户手动完成登录
        input("登录完成后请按回车键继续...")
        
        # 保存 Cookie
        await self.save_cookie()
        self._is_authenticated = True
        logger.info("知乎: 登录成功，Cookie 已保存")
        return True
    
    async def publish(self, article) -> ToolResult:
        """发布到知乎专栏"""
        if not self._is_authenticated:
            if not await self.authenticate():
                return ToolResult(success=False, error="登录失败")
        
        try:
            # 进入创作页面
            logger.info("进入知乎创作页面...")
            await self.page.goto("https://zhuanlan.zhihu.com/write")
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)
            
            # 填写标题
            logger.info("填写标题...")
            title_input = await self.page.wait_for_selector('textarea[placeholder*="标题"]', timeout=10000)
            await title_input.fill(article.title)
            await asyncio.sleep(1)
            
            # 填写内容
            logger.info("填写内容...")
            # 知乎用 Draft.js，点击编辑器区域
            editor = await self.page.wait_for_selector('.public-DraftEditor-content', timeout=10000)
            await editor.click()
            await asyncio.sleep(1)
            
            # 清除现有内容
            await self.page.keyboard.press('Control+a')
            await self.page.keyboard.press('Delete')
            await asyncio.sleep(0.5)
            
            # 处理内容：去掉 HTML 标签，纯文本输入
            import re
            text_content = re.sub(r'<[^>]+>', '', article.html_content)
            text_content = text_content.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
            
            # 分段输入，带 delay 模拟人工
            paragraphs = text_content.split('\n\n')
            for i, para in enumerate(paragraphs):
                if para.strip():
                    await self.page.keyboard.type(para.strip(), delay=10)
                    if i < len(paragraphs) - 1:
                        await self.page.keyboard.press('Enter')
                        await self.page.keyboard.press('Enter')
            
            await asyncio.sleep(2)
            
            # 点击发布按钮（工具栏上的）
            logger.info("点击发布按钮...")
            publish_btn = await self.page.wait_for_selector('button:has-text("发布")', timeout=10000)
            await publish_btn.click()
            await asyncio.sleep(3)
            
            # 在弹窗中点击蓝色的发布按钮
            logger.info("确认发布...")
            try:
                # 等待弹窗出现
                await self.page.wait_for_selector('button[type="submit"]:has-text("发布"), .Modal button:has-text("发布")', timeout=5000)
                
                # 查找所有发布按钮，点击最后一个（弹窗里的）
                publish_buttons = await self.page.query_selector_all('button:has-text("发布")')
                if len(publish_buttons) >= 2:
                    await publish_buttons[-1].click()
                    logger.info("已点击弹窗中的发布按钮")
                else:
                    # 备选：直接用选择器
                    modal_publish = await self.page.wait_for_selector('button[type="submit"]:has-text("发布")', timeout=5000)
                    await modal_publish.click()
                    logger.info("已点击确认发布按钮")
            except Exception as e:
                logger.warning(f"点击弹窗发布按钮失败: {e}，可能已经在发布")
            
            # 等待发布完成（页面跳转到文章详情页）
            logger.info("等待发布完成...")
            try:
                await self.page.wait_for_url("**/p/**", timeout=30000)
                logger.info("发布成功，页面已跳转")
            except:
                logger.warning("等待页面跳转超时，检查当前 URL")
            
            await asyncio.sleep(3)
            
            # 获取文章链接
            current_url = self.page.url
            logger.info(f"当前 URL: {current_url}")
            
            if "/p/" in current_url:
                post_id = current_url.split("/p/")[1].split("?")[0]
                return ToolResult(
                    success=True,
                    post_id=post_id,
                    post_url=current_url
                )
            
            # 检查是否发布成功但 URL 不对
            if "just_published=1" in current_url or "write" not in current_url:
                return ToolResult(success=True, post_url=current_url)
            
            return ToolResult(success=False, error="文章可能只保存到草稿箱，请检查")
            
        except Exception as e:
            logger.exception("知乎发布失败")
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        """检查知乎文章状态"""
        try:
            url = f"https://zhuanlan.zhihu.com/p/{post_id}"
            await self.page.goto(url)
            await asyncio.sleep(2)
            
            if await self.page.query_selector('.ErrorPage'):
                return ToolResult(success=False, error="文章不存在")
            
            return ToolResult(success=True, data={"status": "published", "url": url})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
