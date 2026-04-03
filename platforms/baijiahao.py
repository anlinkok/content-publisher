"""
百家号发布工具 - 使用文档导入功能
基于 Playwright codegen 录制
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
    """写入日志文件"""
    try:
        with open("baijiahao_debug.log", "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
            f.flush()
    except:
        pass


class BaijiahaoTool(PlatformTool):
    """百家号发布工具"""
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
        """检查当前是否已登录"""
        try:
            await self.page.goto("https://baijiahao.baidu.com/builder/rc/home", wait_until="domcontentloaded")
            await asyncio.sleep(3)
            
            current_url = self.page.url
            if "/login" in current_url:
                log(f"未登录，URL: {current_url}")
                return False
            
            # 检查是否有发布入口
            try:
                svg_elements = await self.page.locator("svg").count()
                if svg_elements > 0:
                    log(f"检测到页面加载，svg数量: {svg_elements}")
                    return True
            except:
                pass
            
            log("登录状态不确定，假设已登录")
            return True
            
        except Exception as e:
            log(f"检查登录状态失败: {e}")
            return False
    
    async def authenticate(self) -> bool:
        """自动检测登录状态"""
        if not self.page:
            await self.init_browser(headless=False, load_cookie=True)
        
        console.print("[yellow]检查百家号登录状态...[/yellow]")
        if await self.is_logged_in():
            console.print("[green]✓ 已是登录状态[/green]")
            self._is_authenticated = True
            return True
        
        console.print("[yellow]未登录，请在浏览器中完成百家号登录...[/yellow]")
        await self.page.goto("https://baijiahao.baidu.com/builder/theme/bjh/login")
        
        # 点击登录/注册按钮
        try:
            await self.page.get_by_role("button", name="登录/注册百家号").click()
            log("已点击登录按钮")
        except:
            pass
        
        console.print("[cyan]等待登录完成（请在浏览器中操作）...[/cyan]")
        start_time = asyncio.get_event_loop().time()
        timeout = 120
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            await asyncio.sleep(2)
            
            if await self.is_logged_in():
                console.print("[green]✓ 登录成功！[/green]")
                await self.save_cookie()
                self._is_authenticated = True
                return True
            
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            console.print(f"[dim]等待中... {elapsed}s/{timeout}s[/dim]", end="\r")
        
        console.print("\n[red]登录超时，请重试[/red]")
        return False
    
    async def close_guide(self):
        """关闭引导弹窗 - 循环点击直到没有"""
        guide_buttons = [
            'button:has-text("我知道了")',
            'button:has-text("下一步")',
            'button:has-text("完成")',
        ]
        
        for _ in range(10):  # 最多尝试10次
            clicked = False
            for selector in guide_buttons:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=2000)
                    if btn and await btn.is_visible():
                        await btn.click()
                        text = await btn.text_content()
                        log(f"已点击: {text}")
                        clicked = True
                        await asyncio.sleep(0.8)
                except:
                    continue
            
            if not clicked:
                break
        
        log("引导弹窗已关闭")
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """使用文档导入功能发布"""
        if not self._is_authenticated:
            if not await self.authenticate():
                return ToolResult(success=False, error="登录失败")
        
        try:
            original_file = file_path or getattr(article, 'source_file', None)
            
            if not original_file or not os.path.exists(original_file):
                return ToolResult(success=False, error=f"找不到原始文件: {original_file}")
            
            log("进入百家号首页...")
            await self.page.goto("https://baijiahao.baidu.com/builder/rc/home")
            await asyncio.sleep(3)
            
            # 第1步：关闭可能的首页弹窗
            try:
                close_btn = await self.page.locator("._7c78f7c013adb338-closeIcon").first
                if close_btn and await close_btn.is_visible():
                    await close_btn.click()
                    log("已关闭首页弹窗")
                    await asyncio.sleep(0.5)
            except:
                pass
            
            # 第2步：点击发布图文（通过svg图标）
            log("点击'发布图文'...")
            try:
                await self.page.locator("svg").nth(5).click()
                log("已点击发布图文")
            except Exception as e:
                log(f"点击svg失败: {e}")
                # 备用：尝试其他方式
                try:
                    await self.page.goto("https://baijiahao.baidu.com/builder/rc/edit")
                    log("直接访问编辑页面")
                except:
                    return ToolResult(success=False, error="无法进入编辑页面")
            
            await asyncio.sleep(3)
            
            # 第3步：关闭引导弹窗
            log("关闭引导弹窗...")
            await self.close_guide()
            await asyncio.sleep(1)
            
            # 第4步：鼠标悬停"插入"，然后点击"导入文档"
            log("鼠标悬停'插入'，点击'导入文档'...")
            try:
                # 先找到"插入"元素并悬停
                insert_element = await self.page.get_by_text("插入").first
                await insert_element.hover()
                log("已悬停'插入'")
                await asyncio.sleep(1)
                
                # 然后点击"导入文档"
                await self.page.get_by_text("导入文档").click()
                log("已点击导入文档")
            except Exception as e:
                log(f"点击导入文档失败: {e}")
                # 备用：尝试直接点击
                try:
                    await self.page.get_by_text("导入文档").click(force=True)
                    log("已强制点击导入文档")
                except:
                    return ToolResult(success=False, error="找不到导入文档入口")
            
            await asyncio.sleep(2)
            
            # 第5步：选择文档并上传（修复：先点击按钮，再精确定位file input）
            log(f"选择文档: {original_file}")
            try:
                # 先点击"选择文档"按钮
                await self.page.get_by_role("button", name="选择文档").click()
                log("已点击'选择文档'按钮")
                await asyncio.sleep(1)
                
                # 找所有file input，选择文档类型的（不是视频）
                file_inputs = await self.page.locator('input[type="file"]').all()
                doc_input = None
                for inp in file_inputs:
                    try:
                        accept = await inp.get_attribute('accept')
                        if accept and ('doc' in accept.lower() or 'word' in accept.lower()):
                            doc_input = inp
                            log(f"找到文档上传input, accept={accept}")
                            break
                    except:
                        continue
                
                if not doc_input and len(file_inputs) > 0:
                    # 如果只有一个或没找到特定的，用第一个不是video的
                    for inp in file_inputs:
                        accept = await inp.get_attribute('accept') or ''
                        if 'video' not in accept:
                            doc_input = inp
                            log(f"使用非视频input, accept={accept}")
                            break
                
                if doc_input:
                    await doc_input.set_input_files(original_file)
                    log("文件已上传")
                else:
                    raise Exception("找不到文档上传input")
                    
            except Exception as e:
                log(f"上传文件失败: {e}")
                return ToolResult(success=False, error=f"上传文件失败: {e}")
            
            await asyncio.sleep(5)  # 等待导入完成
            
            # 第6步：点击"全部采纳"
            log("点击'全部采纳'...")
            try:
                await self.page.get_by_role("button", name="全部采纳").click()
                log("已点击全部采纳")
            except Exception as e:
                log(f"点击全部采纳失败: {e}")
            
            await asyncio.sleep(2)
            
            # 第7步：选择封面模式（三图）
            log("选择三图封面模式...")
            try:
                await self.page.get_by_text("三图").click()
                log("已选择三图")
            except Exception as e:
                log(f"选择三图失败: {e}")
            
            await asyncio.sleep(1)
            
            # 第8步：选择封面图片
            log("选择封面图片...")
            try:
                # 点击选择封面
                await self.page.locator("div").filter(has_text=re.compile(r"^选择封面$")).nth(4).click()
                await asyncio.sleep(1)
                
                # 选择第2张和第3张图片
                try:
                    checkbox1 = await self.page.locator("div:nth-child(2) > .e8c90bfac9d4eab4-checkbox").first
                    if checkbox1:
                        await checkbox1.click()
                        log("已选择第1张封面")
                except:
                    pass
                
                try:
                    img2 = await self.page.locator("div:nth-child(3) > .e8c90bfac9d4eab4-imgWrapper > .e8c90bfac9d4eab4-img").first
                    if img2:
                        await img2.click()
                        log("已选择第2张封面")
                except:
                    pass
                
                # 点击确定
                await self.page.get_by_role("button", name=re.compile(r"确定 \(\d+\)")).click()
                log("封面已确定")
            except Exception as e:
                log(f"选择封面失败: {e}")
            
            await asyncio.sleep(2)
            
            # 第9步：点击发布
            log("点击发布...")
            try:
                await self.page.get_by_test_id("publish-btn").click()
                log("已点击发布")
            except Exception as e:
                log(f"点击发布按钮失败: {e}")
                # 备用
                try:
                    await self.page.get_by_role("button", name="发布").click()
                    log("已点击发布（备用）")
                except:
                    return ToolResult(success=False, error="找不到发布按钮")
            
            await asyncio.sleep(5)
            
            # 第10步：检查结果
            current_url = self.page.url
            log(f"发布后URL: {current_url}")
            
            # 提取文章ID
            article_id = None
            match = re.search(r'[?&]id=([^&]+)', current_url)
            if match:
                article_id = match.group(1)
            
            if "/builder" in current_url or article_id:
                log("发布成功")
                return ToolResult(success=True, post_id=article_id, post_url=current_url)
            else:
                try:
                    await self.page.screenshot(path="baijiahao_final.png")
                    log("已截图保存")
                except:
                    pass
                return ToolResult(success=False, error="发布状态不确定")
            
        except Exception as e:
            log(f"百家号发布失败: {e}")
            import traceback
            log(traceback.format_exc())
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        """检查文章状态"""
        try:
            url = f"https://baijiahao.baidu.com/s?id={post_id}"
            await self.page.goto(url)
            await asyncio.sleep(2)
            
            error_selectors = ['.error-page', '.not-found', '.404']
            for selector in error_selectors:
                if await self.page.query_selector(selector):
                    return ToolResult(success=False, error="文章不存在")
            
            return ToolResult(success=True, data={"status": "published", "url": url})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
