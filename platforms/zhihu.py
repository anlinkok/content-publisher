"""
知乎平台实现 - 使用文档导入功能
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from platforms.base import PlatformTool, ToolResult

logger = logging.getLogger(__name__)

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
        from playwright.async_api import async_playwright
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'locale': 'zh-CN',
        }
        
        if load_cookie and self.cookie_file.exists():
            try:
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    context_options['storage_state'] = json.load(f)
            except:
                pass
        
        self.context = await self.browser.new_context(**context_options)
        await self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.page = await self.context.new_page()
    
    async def save_cookie(self):
        if self.context:
            storage = await self.context.storage_state()
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(storage, f, ensure_ascii=False, indent=2)
    
    async def authenticate(self) -> bool:
        if not self.page:
            await self.init_browser(headless=False, load_cookie=True)
            await self.page.goto("https://www.zhihu.com")
            await asyncio.sleep(2)
            
            try:
                await self.page.wait_for_selector('.AppHeader-profile img', timeout=5000)
                self._is_authenticated = True
                return True
            except:
                pass
        
        from rich.console import Console
        Console().print("[yellow]请在浏览器中完成知乎登录...[/yellow]")
        await self.page.goto("https://www.zhihu.com/signin")
        input("登录完成后请按回车键继续...")
        await self.save_cookie()
        self._is_authenticated = True
        return True
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """使用文档导入功能发布"""
        if not self._is_authenticated:
            if not await self.authenticate():
                return ToolResult(success=False, error="登录失败")
        
        try:
            original_file = file_path or getattr(article, 'source_file', None)
            
            if not original_file or not os.path.exists(original_file):
                return ToolResult(success=False, error=f"找不到原始文件: {original_file}")
            
            logger.info("进入知乎创作页面...")
            await self.page.goto("https://zhuanlan.zhihu.com/write")
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)
            
            # 第1步：找到文件上传input并上传文件（后台上传）
            logger.info("上传文件到知乎...")
            file_inputs = await self.page.query_selector_all('input[type="file"]')
            target_input = None
            
            for inp in file_inputs:
                accept = await inp.get_attribute('accept')
                if accept and '.docx' in accept:
                    target_input = inp
                    break
            
            if not target_input:
                target_input = await self.page.wait_for_selector('input[type="file"]', timeout=10000)
            
            await target_input.set_input_files(original_file)
            logger.info("文件已上传，等待处理...")
            
            # 第2步：等待文件列表弹窗出现
            await asyncio.sleep(5)
            
            # 第3步：在弹窗中选择文件
            try:
                file_name = os.path.basename(original_file)
                logger.info(f"在弹窗中查找文件: {file_name}")
                
                # 等待弹窗出现（检查"选择文件"标题）
                await self.page.wait_for_selector('text=选择文件', timeout=10000)
                logger.info("文件选择弹窗已出现")
                
                # 点击文件名所在行
                file_row = await self.page.wait_for_selector(
                    f'text={file_name}',
                    timeout=10000
                )
                await file_row.click()
                logger.info("已点击文件")
                await asyncio.sleep(2)
                
                # 点击"请选择文件"按钮
                confirm_btn = await self.page.wait_for_selector(
                    'button:has-text("请选择文件")',
                    timeout=10000
                )
                await confirm_btn.click()
                logger.info("已点击请选择文件按钮")
                
                # 等待导入完成
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"选择文件失败: {e}")
                return ToolResult(success=False, error=f"选择文件失败: {e}")
            
            # 第4步：发布
            logger.info("点击发布按钮...")
            publish_btn = await self.page.wait_for_selector('button:has-text("发布")', timeout=10000)
            await publish_btn.click()
            await asyncio.sleep(3)
            
            # 确认弹窗
            try:
                publish_buttons = await self.page.query_selector_all('button:has-text("发布")')
                if len(publish_buttons) >= 2:
                    await publish_buttons[-1].click()
            except:
                pass
            
            await asyncio.sleep(5)
            current_url = self.page.url
            
            if "/p/" in current_url:
                post_id = current_url.split("/p/")[1].split("?")[0]
                return ToolResult(success=True, post_id=post_id, post_url=current_url)
            return ToolResult(success=True, post_url=current_url)
            
        except Exception as e:
            logger.exception("知乎发布失败")
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        try:
            url = f"https://zhuanlan.zhihu.com/p/{post_id}"
            await self.page.goto(url)
            await asyncio.sleep(2)
            if await self.page.query_selector('.ErrorPage'):
                return ToolResult(success=False, error="文章不存在")
            return ToolResult(success=True, data={"status": "published", "url": url})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
