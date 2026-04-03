"""
百家号发布工具 - 按最新录制代码
"""

import asyncio
import json
import os
import logging
import re
from pathlib import Path
from platforms.base import PlatformTool, ToolResult
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)

COOKIE_DIR = Path("data/cookies")
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


def log(msg):
    try:
        with open("baijiahao_debug.log", "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
            f.flush()
    except:
        pass


class BaijiahaoTool(PlatformTool):
    name = "BaijiahaoPublisher"
    description = "Publish articles to Baidu Baijiahao platform"
    platform_type = "baijiahao"
    
    def __init__(self, account=None):
        super().__init__(account)
        self.cookie_file = COOKIE_DIR / "baijiahao.json"
        try:
            with open("baijiahao_debug.log", "w", encoding="utf-8") as f:
                f.write("=== 百家号发布调试日志 ===\n")
        except:
            pass
    
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
    
    async def is_logged_in(self) -> bool:
        try:
            await self.page.goto("https://baijiahao.baidu.com/builder/rc/home", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            current_url = self.page.url
            if "/login" in current_url:
                return False
            return True
        except Exception as e:
            return False
    
    async def authenticate(self) -> bool:
        if not self.page:
            await self.init_browser(headless=False, load_cookie=True)
        
        console.print("[yellow]检查百家号登录状态...[/yellow]")
        if await self.is_logged_in():
            console.print("[green]✓ 已是登录状态[/green]")
            self._is_authenticated = True
            return True
        
        console.print("[yellow]未登录，请扫码或账号登录...[/yellow]")
        await self.page.goto("https://baijiahao.baidu.com/builder/theme/bjh/login")
        
        start_time = asyncio.get_event_loop().time()
        timeout = 120
        while asyncio.get_event_loop().time() - start_time < timeout:
            await asyncio.sleep(2)
            if await self.is_logged_in():
                console.print("[green]✓ 登录成功！[/green]")
                await self.save_cookie()
                self._is_authenticated = True
                return True
        
        return False
    
    async def close_guide(self):
        """关闭引导和风险检测提示"""
        # 点击我知道了
        for text in ["我知道了"]:
            try:
                btn = await self.page.wait_for_selector(f'button:has-text("{text}")', timeout=3000)
                if btn and await btn.is_visible():
                    await btn.click()
                    log(f"已点击: {text}")
                    await asyncio.sleep(1)
            except:
                pass
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        if not self._is_authenticated:
            if not await self.authenticate():
                return ToolResult(success=False, error="登录失败")
        
        try:
            original_file = file_path or getattr(article, 'source_file', None)
            if not original_file or not os.path.exists(original_file):
                return ToolResult(success=False, error="找不到原始文件")
            
            log("进入百家号首页...")
            try:
                await self.page.goto("https://baijiahao.baidu.com/builder/rc/home", wait_until="domcontentloaded", timeout=60000)
            except:
                pass
            await asyncio.sleep(3)
            
            # 关闭首页弹窗
            try:
                await self.page.locator("._7c78f7c013adb338-closeIcon").click()
                log("已关闭首页弹窗")
                await asyncio.sleep(0.5)
            except:
                pass
            
            # 点击折叠菜单（新增）
            try:
                await self.page.locator("._4f4cb3a3b81b55a5-foldContent").click()
                log("已点击折叠菜单")
                await asyncio.sleep(1)
            except Exception as e:
                log(f"点击折叠菜单失败: {e}")
            
            # 处理风险检测提示
            try:
                await self.page.get_by_text("我知道了").click()
                log("已点击风险检测我知道了")
                await asyncio.sleep(1)
            except:
                pass
            
            # 关闭引导
            await self.close_guide()
            await asyncio.sleep(1)
            
            # 点击空白按钮（发布按钮）
            try:
                await self.page.get_by_role("button").filter(has_text=re.compile(r"^$")).click()
                log("已点击发布按钮")
                await asyncio.sleep(2)
            except Exception as e:
                log(f"点击发布按钮失败: {e}")
                # 备用：直接访问编辑页
                await self.page.goto("https://baijiahao.baidu.com/builder/rc/edit")
                await asyncio.sleep(2)
            
            # === 插入 -> 导入文档 ===
            log("点击'插入'...")
            await self.page.get_by_text("插入").click()
            log("已点击'插入'")
            await asyncio.sleep(2)
            
            log("点击'导入文档'...")
            await self.page.locator("div").filter(has_text=re.compile(r"^导入文档$")).first.click()
            log("已点击'导入文档'")
            await asyncio.sleep(2)
            
            # 上传文件（直接操作input，避免系统弹窗）
            log(f"上传文件: {original_file}")
            try:
                # 直接找 file input 设置文件，不点击"选择文档"按钮
                file_inputs = await self.page.locator('input[type="file"]').all()
                for inp in file_inputs:
                    accept = await inp.get_attribute('accept') or ''
                    if 'video' not in accept and ('doc' in accept or 'word' in accept or accept == ''):
                        await inp.set_input_files(original_file)
                        log("文件已上传")
                        break
                await asyncio.sleep(2)  # 等待系统弹窗关闭
            except Exception as e:
                log(f"上传失败: {e}")
                return ToolResult(success=False, error=f"上传失败: {e}")
            
            await asyncio.sleep(8)  # 等待导入
            
            # 全部采纳
            log("点击'全部采纳'...")
            try:
                await self.page.get_by_role("button", name="全部采纳").click()
                log("已点击全部采纳")
            except Exception as e:
                log(f"点击全部采纳失败: {e}")
            
            await asyncio.sleep(2)
            
            # 填写标题（从文章提取）
            title = article.title if hasattr(article, 'title') and article.title else ""
            if title:
                log(f"填写标题: {title}")
                try:
                    title_input = await self.page.wait_for_selector('input[placeholder*="标题"], [contenteditable="true"]', timeout=10000)
                    await title_input.fill(title)
                    log("标题已填写")
                except Exception as e:
                    log(f"填写标题失败: {e}")
                await asyncio.sleep(1)
            
            # === 再次插入 -> 商品 ===
            log("插入商品...")
            try:
                await self.page.get_by_text("插入").click()
                log("已点击插入（商品）")
                await asyncio.sleep(1)
                
                await self.page.get_by_text("商品", exact=True).click()
                log("已点击商品")
                await asyncio.sleep(2)
                
                # 添加第一个商品
                goods_frame = self.page.locator("#goods_iframepc_goods_component1").content_frame
                await goods_frame.get_by_text("添加").first.click()
                await asyncio.sleep(1)
                await goods_frame.get_by_role("button", name="添 加").click()
                log("已添加第一个商品")
                await asyncio.sleep(1)
                
                # 关闭商品选择（点击圆圈）
                try:
                    await self.page.locator("#edui41_state circle").click()
                    log("已关闭商品选择")
                except:
                    pass
                await asyncio.sleep(1)
                
                # 添加第二个商品
                try:
                    await goods_frame.get_by_text("添加").nth(1).click()
                    await asyncio.sleep(1)
                    await goods_frame.get_by_role("button", name="添 加").click()
                    log("已添加第二个商品")
                except:
                    log("添加第二个商品失败或只有一个")
                
                await asyncio.sleep(1)
            except Exception as e:
                log(f"插入商品失败: {e}")
            
            # 选择封面
            log("选择封面...")
            try:
                await self.page.locator("div").filter(has_text=re.compile(r"^选择封面$")).nth(5).click()
                log("已打开封面选择")
                await asyncio.sleep(2)
                
                # 点击确定
                await self.page.get_by_role("button", name="确定 (1)").click()
                log("封面已确定")
            except Exception as e:
                log(f"选择封面失败: {e}")
            
            await asyncio.sleep(2)
            
            # 发布（点击两次）
            log("点击发布...")
            try:
                await self.page.get_by_test_id("publish-btn").click()
                log("已点击发布（第一次）")
                await asyncio.sleep(2)
                await self.page.get_by_test_id("publish-btn").click()
                log("已点击发布（第二次）")
            except Exception as e:
                log(f"点击发布失败: {e}")
            
            await asyncio.sleep(5)
            
            current_url = self.page.url
            log(f"发布后URL: {current_url}")
            
            article_id = None
            match = re.search(r'[?&]id=([^&]+)', current_url)
            if match:
                article_id = match.group(1)
            
            if "/builder" in current_url or article_id:
                return ToolResult(success=True, post_id=article_id, post_url=current_url)
            else:
                return ToolResult(success=False, error="发布状态不确定")
            
        except Exception as e:
            log(f"发布失败: {e}")
            import traceback
            log(traceback.format_exc())
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        try:
            url = f"https://baijiahao.baidu.com/s?id={post_id}"
            await self.page.goto(url)
            await asyncio.sleep(2)
            return ToolResult(success=True, data={"status": "published", "url": url})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
