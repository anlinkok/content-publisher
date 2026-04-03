"""
知乎平台实现 - 使用文档导入功能
"""

import asyncio
import json
import os
from pathlib import Path
from platforms.base import PlatformTool, ToolResult

COOKIE_DIR = Path("data/cookies")
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


def log(msg):
    """写入日志文件"""
    try:
        with open("zhihu_debug.log", "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
            f.flush()
    except:
        pass


class ZhihuTool(PlatformTool):
    """知乎发布工具"""
    name = "ZhihuPublisher"
    description = "Publish articles to Zhihu platform"
    platform_type = "zhihu"
    
    def __init__(self, account=None):
        super().__init__(account)
        self.cookie_file = COOKIE_DIR / "zhihu.json"
        try:
            with open("zhihu_debug.log", "w", encoding="utf-8") as f:
                f.write("=== 知乎发布调试日志 ===\n")
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
            
            log("进入知乎创作页面...")
            await self.page.goto("https://zhuanlan.zhihu.com/write")
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)
            
            # 第1步：点击"导入"按钮
            log("点击'导入'按钮...")
            try:
                await self.page.get_by_role("button", name="导入").click()
                log("已点击'导入'")
            except:
                await self.page.click('text=导入', timeout=5000)
                log("已点击'导入'（备用）")
            await asyncio.sleep(2)
            
            # 第2步：点击"导入文档"
            log("点击'导入文档'...")
            try:
                await self.page.get_by_role("button", name="导入文档").click()
                log("已点击'导入文档'")
            except:
                await self.page.click('text=导入文档', timeout=5000)
                log("已点击'导入文档'（备用）")
            
            # 第3步：等待弹窗完全加载
            log("等待弹窗加载...")
            await asyncio.sleep(5)
            
            # 第4步：点击"点击选择本地文档或拖动文件到窗口上传"按钮
            # 根据录制代码，按钮文字是"点击选择本地文档或拖动文件到窗口上传"
            log("点击上传按钮...")
            try:
                # 方法1：用 get_by_role 精确匹配（录制代码用的方式）
                await self.page.get_by_role(
                    "button", 
                    name="点击选择本地文档或拖动文件到窗口上传"
                ).click()
                log("已点击上传按钮（方法1）")
            except Exception as e:
                log(f"方法1失败: {e}")
                try:
                    # 方法2：用部分文字匹配
                    await self.page.click(
                        'button:has-text("点击选择本地文档")',
                        timeout=10000
                    )
                    log("已点击上传按钮（方法2）")
                except Exception as e2:
                    log(f"方法2失败: {e2}")
                    try:
                        # 方法3：在弹窗内查找任何可点击的按钮（除了关闭按钮）
                        buttons = await self.page.query_selector_all('.Modal button, [role="dialog"] button')
                        for btn in buttons:
                            text = await btn.text_content()
                            if text and "选择" in text and "关闭" not in text:
                                await btn.click()
                                log(f"已点击按钮: {text}")
                                break
                    except Exception as e3:
                        log(f"方法3也失败: {e3}")
                        return ToolResult(success=False, error="无法点击上传按钮")
            
            # 第5步：等待文件选择对话框或 file input 出现
            log("等待文件选择...")
            await asyncio.sleep(3)
            
            # 第6步：上传文件
            log(f"上传文件: {original_file}")
            try:
                # 查找弹窗内的 file input
                file_input = await self.page.wait_for_selector(
                    '.Modal input[type="file"], [role="dialog"] input[type="file"]',
                    timeout=10000,
                    state='attached'  # 只要元素存在就行，不需要可见
                )
                await file_input.set_input_files(original_file)
                log("文件已上传")
            except Exception as e:
                log(f"弹窗内查找失败: {e}")
                # 备用：全局查找所有 file input
                try:
                    file_inputs = await self.page.query_selector_all('input[type="file"]')
                    if len(file_inputs) > 0:
                        await file_inputs[-1].set_input_files(original_file)  # 用最后一个（通常是弹窗里的）
                        log("文件已上传（备用）")
                    else:
                        return ToolResult(success=False, error="找不到文件上传框")
                except Exception as e2:
                    log(f"备用也失败: {e2}")
                    return ToolResult(success=False, error=f"上传文件失败: {e2}")
            
            # 第7步：等待导入完成
            log("等待导入完成，最多2分钟...")
            try:
                await self.page.wait_for_url("**/p/**/edit", timeout=120000)
                log(f"导入完成，当前URL: {self.page.url}")
            except Exception as e:
                log(f"等待跳转超时: {e}")
                current_url = self.page.url
                if "/p/" not in current_url:
                    return ToolResult(success=False, error="文档导入超时")
            
            # 第8步：发布
            current_url = self.page.url
            post_id = current_url.split("/p/")[1].split("/")[0]
            log(f"文章ID: {post_id}")
            
            log("点击发布...")
            try:
                publish_btn = await self.page.wait_for_selector(
                    'button:has-text("发布")',
                    timeout=10000
                )
                await publish_btn.click()
                log("已点击发布")
            except Exception as e:
                log(f"点击发布失败: {e}")
                return ToolResult(success=False, error=f"点击发布按钮失败: {e}")
            
            await asyncio.sleep(3)
            
            # 确认弹窗
            try:
                confirm_btn = await self.page.wait_for_selector(
                    'button:has-text("发布"):visible',
                    timeout=5000
                )
                await confirm_btn.click()
                log("已点击确认发布")
            except:
                log("没有确认弹窗")
            
            # 第9步：等待完成
            log("等待发布完成...")
            try:
                await self.page.wait_for_url("**/p/**", timeout=60000)
                await asyncio.sleep(2)
                current_url = self.page.url
            except:
                current_url = self.page.url
            
            if "/p/" in current_url:
                post_id = current_url.split("/p/")[1].split("?")[0].split("/")[0]
                log(f"发布成功，文章ID: {post_id}")
                return ToolResult(success=True, post_id=post_id, post_url=current_url)
            else:
                log("发布未成功")
                return ToolResult(success=False, error="发布未完成")
            
        except Exception as e:
            log(f"知乎发布失败: {e}")
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
