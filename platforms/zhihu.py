"""
知乎平台实现
"""

import asyncio
import logging
from platforms.base import PlatformTool, ToolResult

logger = logging.getLogger(__name__)


class ZhihuTool(PlatformTool):
    """知乎发布工具"""
    name = "ZhihuPublisher"
    description = "Publish articles to Zhihu platform"
    platform_type = "zhihu"
    
    async def authenticate(self) -> bool:
        """知乎登录"""
        if not self.page:
            await self.init_browser(headless=False)
        
        # 尝试加载已有会话
        if await self.load_session():
            await self.page.goto("https://www.zhihu.com")
            await asyncio.sleep(2)
            
            # 检查是否已登录
            try:
                await self.page.wait_for_selector('[data-za-detail-view-element_name="UserAvatar"]', timeout=5000)
                self._is_authenticated = True
                logger.info("知乎: 已登录")
                return True
            except:
                pass
        
        # 需要重新登录
        from rich.console import Console
        console = Console()
        console.print("[yellow]请在浏览器中完成知乎登录...[/yellow]")
        await self.page.goto("https://www.zhihu.com/signin")
        
        # 手动确认登录完成
        input("登录完成后请按回车键继续...")
        
        self._is_authenticated = True
        await self.save_session()
        logger.info("知乎: 登录成功")
        return True
    
    async def publish(self, article) -> ToolResult:
        """发布到知乎专栏"""
        if not self._is_authenticated:
            if not await self.authenticate():
                return ToolResult(success=False, error="登录失败")
        
        try:
            # 进入创作页面
            await self.page.goto("https://zhuanlan.zhihu.com/write")
            await asyncio.sleep(3)
            
            # 填写标题
            title_input = await self.page.wait_for_selector('textarea[placeholder*="标题"]')
            await title_input.fill(article.title)
            
            # 填写内容
            content_editor = await self.page.wait_for_selector('.DraftEditor-root')
            await content_editor.click()
            await asyncio.sleep(1)
            
            # 清除现有内容
            await self.page.keyboard.press('Control+a')
            await self.page.keyboard.press('Delete')
            await asyncio.sleep(0.5)
            
            # 输入纯文本内容（去掉HTML标签）
            import re
            text_content = re.sub(r'<[^>]+>', '', article.html_content)
            text_content = text_content.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
            
            # 分段输入
            paragraphs = text_content.split('\n\n')
            for i, para in enumerate(paragraphs):
                if para.strip():
                    await self.page.keyboard.type(para.strip())
                    if i < len(paragraphs) - 1:
                        await self.page.keyboard.press('Enter')
                        await self.page.keyboard.press('Enter')
            
            await asyncio.sleep(2)
            
            # 点击第一个"发布"按钮（工具栏上的）
            publish_btn = await self.page.wait_for_selector('button:has-text("发布")')
            await publish_btn.click()
            logger.info("点击了工具栏发布按钮")
            
            # 等待发布确认弹窗出现
            await asyncio.sleep(3)
            
            # 在弹窗中点击蓝色的"发布"按钮
            # 弹窗里的按钮可能是 type="submit" 或者有特定 class
            try:
                # 查找所有包含"发布"的按钮，点击最后一个（弹窗里的）
                publish_buttons = await self.page.query_selector_all('button:has-text("发布")')
                if len(publish_buttons) >= 2:
                    await publish_buttons[-1].click()
                    logger.info("点击了弹窗中的发布按钮")
                else:
                    # 尝试其他选择器
                    modal_publish = await self.page.wait_for_selector('button[type="submit"]:has-text("发布"), .Modal button:has-text("发布"), [role="dialog"] button:has-text("发布")', timeout=5000)
                    await modal_publish.click()
                    logger.info("点击了弹窗发布按钮(选择器)")
            except Exception as e:
                logger.warning(f"点击弹窗发布按钮失败: {e}")
            
            # 等待发布完成
            await asyncio.sleep(8)
            
            # 获取文章链接
            current_url = self.page.url
            logger.info(f"当前URL: {current_url}")
            
            if "/p/" in current_url:
                post_id = current_url.split("/p/")[1].split("?")[0]
                return ToolResult(
                    success=True,
                    post_id=post_id,
                    post_url=current_url
                )
            
            return ToolResult(success=False, error="文章可能只保存到草稿箱，未正式发布")
            
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
