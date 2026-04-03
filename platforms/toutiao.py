"""
头条号平台实现
"""

import asyncio
import logging
from platforms.base import PlatformTool, ToolResult

logger = logging.getLogger(__name__)


class ToutiaoTool(PlatformTool):
    """头条号发布工具"""
    name = "ToutiaoPublisher"
    description = "Publish articles to Toutiao platform"
    platform_type = "toutiao"
    
    async def authenticate(self) -> bool:
        """头条号登录"""
        if not self.page:
            await self.init_browser(headless=False)
        
        if await self.load_session():
            await self.page.goto("https://mp.toutiao.com/")
            await asyncio.sleep(2)
            
            try:
                await self.page.wait_for_selector('.user-name', timeout=5000)
                self._is_authenticated = True
                return True
            except:
                pass
        
        from rich.console import Console
        console = Console()
        console.print("[yellow]请在浏览器中完成头条号登录...[/yellow]")
        await self.page.goto("https://mp.toutiao.com/")
        
        try:
            await self.page.wait_for_selector('.user-name', timeout=120000)
            self._is_authenticated = True
            await self.save_session()
            return True
        except:
            return False
    
    async def publish(self, article) -> ToolResult:
        """发布到头条号"""
        if not self._is_authenticated:
            if not await self.authenticate():
                return ToolResult(success=False, error="登录失败")
        
        try:
            await self.page.goto("https://mp.toutiao.com/profile_v4/graphic/publish")
            await asyncio.sleep(3)
            
            # 填写标题
            title_input = await self.page.wait_for_selector('input[placeholder*="标题"]')
            await title_input.fill(article.title)
            
            # 填写内容
            content_editor = await self.page.wait_for_selector('.ProseMirror')
            await content_editor.click()
            await self.page.keyboard.press('Control+a')
            await self.page.keyboard.press('Delete')
            
            safe_html = article.html_content.replace('`', '`')
            await self.page.evaluate(f"""
                document.querySelector('.ProseMirror').innerHTML = `{safe_html}`;
            """)
            
            await asyncio.sleep(2)
            
            # 发布
            publish_btn = await self.page.wait_for_selector('button:has-text("发布")')
            await publish_btn.click()
            
            await asyncio.sleep(5)
            
            return ToolResult(success=True, data={"url": self.page.url})
            
        except Exception as e:
            logger.exception("头条号发布失败")
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        return ToolResult(success=True)
