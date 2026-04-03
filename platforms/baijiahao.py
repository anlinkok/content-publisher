"""
百家号发布工具 - 简化版，严格按录制代码
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
            await self.page.goto("https://baijiahao.baidu.com/builder/rc/home", wait_until="domcontentloaded")
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
        """关闭引导"""
        for _ in range(10):
            for text in ["我知道了", "下一步", "完成"]:
                try:
                    btn = await self.page.wait_for_selector(f'button:has-text("{text}")', timeout=2000)
                    if btn and await btn.is_visible():
                        await btn.click()
                        log(f"已点击: {text}")
                        await asyncio.sleep(0.5)
                except:
                    continue
    
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
                # 如果超时，继续执行
                pass
            await asyncio.sleep(3)
            
            # 关闭首页弹窗
            try:
                await self.page.locator("._7c78f7c013adb338-closeIcon").first.click()
                log("已关闭首页弹窗")
                await asyncio.sleep(0.5)
            except:
                pass
            
            # 点击发布图文
            log("点击'发布图文'...")
            try:
                await self.page.locator("svg").nth(5).click()
                log("已点击发布图文")
            except:
                await self.page.goto("https://baijiahao.baidu.com/builder/rc/edit")
            
            await asyncio.sleep(3)
            
            # 关闭引导
            await self.close_guide()
            await asyncio.sleep(1)
            
            # === 核心：按录制代码点击插入和导入文档 ===
            log("点击'插入'...")
            await self.page.get_by_text("插入").click()
            log("已点击'插入'")
            await asyncio.sleep(2)
            
            log("点击'导入文档'...")
            await self.page.get_by_text("导入文档").click(force=True)
            log("已点击'导入文档'")
            await asyncio.sleep(2)
            
            # 上传文件（直接操作input，不点击按钮避免弹窗）
            log(f"上传文件: {original_file}")
            try:
                # 直接找 file input 并设置文件，不点击"选择文档"按钮
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
            
            # 填写标题（从文章提取）
            title = article.title if hasattr(article, 'title') and article.title else ""
            if title:
                log(f"填写标题: {title}")
                try:
                    # 等待标题输入框出现并填写
                    title_input = await self.page.wait_for_selector('input[placeholder*="标题"], input[placeholder*="文章标题"], [contenteditable="true"]', timeout=10000)
                    await title_input.fill(title)
                    log("标题已填写")
                except Exception as e:
                    log(f"填写标题失败: {e}")
                    # 备用：尝试JS填写
                    try:
                        await self.page.evaluate(f"""
                            const inputs = document.querySelectorAll('input[placeholder*="标题"], input[placeholder*="文章标题"], [contenteditable="true"]');
                            for (const input of inputs) {{
                                if (input.offsetParent !== null) {{  // 可见元素
                                    input.value = "{title}";
                                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    break;
                                }}
                            }}
                        """)
                        log("标题已通过JS填写")
                    except Exception as e2:
                        log(f"JS填写标题也失败: {e2}")
                await asyncio.sleep(1)
            
            # 全部采纳
            log("点击'全部采纳'...")
            try:
                await self.page.get_by_role("button", name="全部采纳").first.click()
                log("已点击全部采纳")
            except:
                await self.page.locator('button:has-text("全部采纳")').first.click()
            
            await asyncio.sleep(2)
            
            # === 插入商品（按录制代码）===
            log("插入商品...")
            try:
                # 点击商品图标
                await self.page.locator(".l-icon.l-icon-BjhBasicShanpin > svg").click()
                log("已点击商品图标")
                await asyncio.sleep(2)
                
                # 在 iframe 中选择商品
                goods_frame = self.page.locator("#goods_iframepc_goods_component1").content_frame
                
                # 添加第一个商品
                await goods_frame.get_by_text("添加").first.click()
                await asyncio.sleep(1)
                await goods_frame.get_by_role("button", name="添 加").click()
                log("已添加第一个商品")
                await asyncio.sleep(1)
                
                # 关闭商品选择弹窗
                await self.page.locator("div:nth-child(2) > ._9d63bce81e3a0b19-icon").first.click()
                log("已关闭商品选择")
                await asyncio.sleep(1)
                
                # 再添加第二个（可选）
                # await goods_frame.get_by_text("添加").nth(1).click()
                # await goods_frame.get_by_role("button", name="添 加").click()
                
                # 关闭商品面板
                await self.page.locator("._73a3a52aab7e3a36-icon").click()
                log("已关闭商品面板")
                await asyncio.sleep(1)
                
                # 确认商品选择
                await self.page.get_by_role("button", name=re.compile(r"确定 \(\d+\)")).click()
                log("已确认商品")
                await asyncio.sleep(1)
            except Exception as e:
                log(f"插入商品失败或跳过: {e}")
            
            # 选择单图封面
            log("选择单图封面...")
            try:
                await self.page.get_by_text("单图").click()
                log("已选择单图")
                await asyncio.sleep(2)  # 增加等待
                
                # 点击选择封面
                await self.page.locator("div").filter(has_text=re.compile(r"^选择封面$")).nth(4).click()
                log("已打开封面选择")
                await asyncio.sleep(3)  # 等待封面加载
                
                # 选择第1张，重试3次
                for i in range(3):
                    try:
                        await self.page.locator("div:nth-child(2) > .e8c90bfac9d4eab4-checkbox").first.click()
                        log(f"已选择封面 (尝试{i+1})")
                        await asyncio.sleep(2)
                        break
                    except Exception as e:
                        log(f"选择封面失败 (尝试{i+1}): {e}")
                        await asyncio.sleep(2)
                
                # 多点几次确定
                for i in range(3):
                    try:
                        await self.page.get_by_role("button", name=re.compile(r"确定 \(\d+\)")).click()
                        log(f"已点击确定 (尝试{i+1})")
                        await asyncio.sleep(2)
                        break
                    except Exception as e:
                        log(f"点击确定失败 (尝试{i+1}): {e}")
                        await asyncio.sleep(1)
                        
                log("封面已确定")
            except Exception as e:
                log(f"选择封面失败（可能已自动）: {e}")
            
            await asyncio.sleep(2)
            
            # 关闭可能的弹窗
            log("关闭弹窗...")
            try:
                # 尝试点击关闭按钮
                await self.page.locator('.cheetah-modal-close, .cheetah-icon-close, [class*="close"]').first.click()
                log("已关闭弹窗")
                await asyncio.sleep(1)
            except:
                pass
            
            # 发布
            log("点击发布...")
            try:
                await self.page.get_by_test_id("publish-btn").click()
                log("已点击发布")
            except:
                # 备用：JS点击
                await self.page.evaluate("document.querySelector('[data-testid=\"publish-btn\"]').click()")
                log("已通过JS点击发布")
            
            await asyncio.sleep(5)
            
            current_url = self.page.url
            log(f"发布后URL: {current_url}")
            
            # 提取文章ID
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
