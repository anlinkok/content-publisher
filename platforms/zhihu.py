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
        self._file_path = None  # 保存文件路径
    
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
            # 获取原始文件路径（优先使用传入的参数）
            original_file = file_path or getattr(article, 'source_file', None)
            
            if not original_file or not os.path.exists(original_file):
                return ToolResult(success=False, error=f"找不到原始文件: {original_file}")
            
            # 进入创作页面
            await self.page.goto("https://zhuanlan.zhihu.com/write")
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)
            
            # 查找并点击"导入"按钮
            logger.info("点击导入按钮...")
            try:
                # 右上角工具栏的"导入"按钮
                import_btn = await self.page.wait_for_selector(
                    'button:has-text("导入"), [aria-label="导入"], .Toolbar-import',
                    timeout=10000
                )
                await import_btn.click()
                await asyncio.sleep(2)
                
                # 点击下拉菜单中的"文档导入"选项
                try:
                    doc_import = await self.page.wait_for_selector(
                        'text=文档导入, [role="menuitem"]:has-text("文档"), li:has-text("文档")',
                        timeout=5000
                    )
                    await doc_import.click()
                    await asyncio.sleep(2)
                except:
                    logger.info("没有下拉菜单")
            except Exception as e:
                logger.warning(f"点击导入按钮失败: {e}")
            
            # 等待"选择文件"弹窗出现
            logger.info("等待文件选择弹窗...")
            await asyncio.sleep(3)
            
            # 方法1: 尝试直接找到文件input（隐藏）
            try:
                # 找到接受 .docx 的文件输入框
                file_inputs = await self.page.query_selector_all('input[type="file"]')
                file_input = None
                for inp in file_inputs:
                    accept = await inp.get_attribute('accept')
                    if accept and '.docx' in accept:
                        file_input = inp
                        break
                
                if file_input:
                    logger.info(f"直接上传文件: {original_file}")
                    await file_input.set_input_files(original_file)
                else:
                    # 方法2: 点击弹窗里的"请选择文件"按钮
                    logger.info("点击弹窗里的选择文件按钮...")
                    select_btn = await self.page.wait_for_selector(
                        'button:has-text("请选择文件"), .Upload-select-btn',
                        timeout=10000
                    )
                    await select_btn.click()
                    await asyncio.sleep(2)
                    
                    # 等待文件输入框出现
                    file_input = await self.page.wait_for_selector('input[type="file"]', timeout=10000)
                    await file_input.set_input_files(original_file)
            except Exception as e:
                logger.error(f"文件上传失败: {e}")
                raise
            
            # 等待导入完成
            logger.info("等待文档导入完成...")
            await asyncio.sleep(10)
            
            # 等待导入完成的提示
            try:
                await self.page.wait_for_selector('textarea[placeholder*="标题"]', timeout=30000)
                title_input = await self.page.query_selector('textarea[placeholder*="标题"]')
                title_value = await title_input.input_value()
                if title_value:
                    logger.info(f"文档导入成功，标题: {title_value}")
            except Exception as e:
                logger.warning(f"等待导入完成超时: {e}")
            
            await asyncio.sleep(3)
            
            # 发布
            logger.info("点击发布按钮...")
            publish_btn = await self.page.wait_for_selector('button:has-text("发布")', timeout=10000)
            await publish_btn.click()
            await asyncio.sleep(3)
            
            # 弹窗确认
            try:
                publish_buttons = await self.page.query_selector_all('button:has-text("发布")')
                if len(publish_buttons) >= 2:
                    await publish_buttons[-1].click()
                    logger.info("点击了确认发布按钮")
            except:
                pass
            
            # 等待跳转
            try:
                await self.page.wait_for_url("**/p/**", timeout=30000)
                logger.info("发布成功")
            except:
                pass
            
            await asyncio.sleep(3)
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
