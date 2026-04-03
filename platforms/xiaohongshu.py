"""
小红书平台实现
"""

import asyncio
import os
import logging
from platforms.base import PlatformTool, ToolResult

logger = logging.getLogger(__name__)


class XiaohongshuTool(PlatformTool):
    """小红书发布工具"""
    name = "XiaohongshuPublisher"
    description = "Publish notes to Xiaohongshu platform"
    platform_type = "xiaohongshu"
    
    async def authenticate(self) -> bool:
        """小红书登录"""
        if not self.page:
            await self.init_browser(headless=False)
        
        if await self.load_session():
            await self.page.goto("https://creator.xiaohongshu.com/")
            await asyncio.sleep(2)
            
            try:
                await self.page.wait_for_selector('.user-info', timeout=5000)
                self._is_authenticated = True
                return True
            except:
                pass
        
        from rich.console import Console
        console = Console()
        console.print("[yellow]请在浏览器中完成小红书登录...[/yellow]")
        await self.page.goto("https://creator.xiaohongshu.com/login")
        
        try:
            await self.page.wait_for_selector('.user-info', timeout=120000)
            self._is_authenticated = True
            await self.save_session()
            return True
        except:
            return False
    
    async def publish(self, article) -> ToolResult:
        """发布到小红书"""
        if not self._is_authenticated:
            if not await self.authenticate():
                return ToolResult(success=False, error="登录失败")
        
        try:
            await self.page.goto("https://creator.xiaohongshu.com/publish/publish")
            await asyncio.sleep(3)
            
            # 上传图片
            if article.cover_image and os.path.exists(article.cover_image):
                upload_input = await self.page.wait_for_selector('input[type="file"]')
                await upload_input.set_input_files(article.cover_image)
                await asyncio.sleep(3)
            
            # 填写标题
            title_input = await self.page.wait_for_selector('textarea[placeholder*="标题"]')
            await title_input.fill(article.title[:20])
            
            # 填写正文
            content_input = await self.page.wait_for_selector('textarea[placeholder*="正文"]')
            content = article.content[:1000] if len(article.content) > 1000 else article.content
            await content_input.fill(content)
            
            await asyncio.sleep(1)
            
            # 发布
            publish_btn = await self.page.wait_for_selector('button:has-text("发布")')
            await publish_btn.click()
            
            await asyncio.sleep(5)
            
            return ToolResult(success=True)
            
        except Exception as e:
            logger.exception("小红书发布失败")
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        return ToolResult(success=True)
