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
    except Exception as e:
        # 如果写入失败，至少打印到控制台
        print(f"[LOG ERROR] {e}: {msg}")


class ZhihuTool(PlatformTool):
    """知乎发布工具"""
    name = "ZhihuPublisher"
    description = "Publish articles to Zhihu platform"
    platform_type = "zhihu"
    
    def __init__(self, account=None):
        super().__init__(account)
        self.cookie_file = COOKIE_DIR / "zhihu.json"
        # 确保目录存在
        COOKIE_DIR.mkdir(parents=True, exist_ok=True)
        # 清空日志
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
            
            # 第1步：找到文件上传input
            log("查找文件上传input...")
            file_inputs = await self.page.query_selector_all('input[type="file"]')
            log(f"找到 {len(file_inputs)} 个文件input")
            
            target_input = None
            for i, inp in enumerate(file_inputs):
                accept = await inp.get_attribute('accept')
                log(f"input {i}: accept={accept}")
                if accept and '.docx' in accept:
                    target_input = inp
                    log("找到目标input")
                    break
            
            if not target_input:
                log("没找到.docx input，使用第一个")
                target_input = await self.page.wait_for_selector('input[type="file"]', timeout=10000)
            
            # 第2步：上传文件
            log(f"上传文件: {original_file}")
            await target_input.set_input_files(original_file)
            log("文件已设置到input")
            
            # 第3步：等待弹窗出现
            log("等待5秒让弹窗出现...")
            await asyncio.sleep(5)
            
            # 第4步：检查弹窗是否存在
            log("检查弹窗...")
            try:
                modal = await self.page.query_selector('.Modal, [role="dialog"], .dialog')
                if modal:
                    log("找到弹窗元素")
                    modal_html = await modal.inner_html()
                    log(f"弹窗HTML前500字符: {modal_html[:500]}")
                else:
                    log("没找到弹窗元素")
            except Exception as e:
                log(f"检查弹窗失败: {e}")
            
            # 第5步：点击文件名
            file_name = os.path.basename(original_file)
            log(f"尝试点击文件名: {file_name}")
            try:
                file_row = await self.page.wait_for_selector(f'text={file_name}', timeout=10000)
                await file_row.click()
                log("已点击文件名")
            except Exception as e:
                log(f"点击文件名失败: {e}")
                return ToolResult(success=False, error=f"点击文件名失败: {e}")
            
            await asyncio.sleep(3)
            
            # 第6步：找确认按钮
            log("查找确认按钮...")
            buttons = await self.page.query_selector_all('button')
            log(f"页面上共有 {len(buttons)} 个button")
            
            for i, btn in enumerate(buttons):
                try:
                    text = await btn.text_content()
                    visible = await btn.is_visible()
                    enabled = await btn.is_enabled()
                    log(f"按钮 {i}: text='{text}', visible={visible}, enabled={enabled}")
                except:
                    log(f"按钮 {i}: 无法获取信息")
            
            # 第7步：尝试点击确认按钮
            confirm_clicked = False
            
            selectors = [
                'button:has-text("请选择文件")',
                'button:has-text("选择")',
                'button:has-text("确认")',
                'button:has-text("确定")',
                '.Modal button:last-child',
                '[role="dialog"] button:last-child'
            ]
            
            for selector in selectors:
                try:
                    log(f"尝试选择器: {selector}")
                    btn = await self.page.wait_for_selector(selector, timeout=3000)
                    await btn.click(force=True)
                    log(f"成功点击: {selector}")
                    confirm_clicked = True
                    break
                except Exception as e:
                    log(f"选择器 {selector} 失败: {e}")
                    continue
            
            if not confirm_clicked:
                log("所有选择器都失败，无法点击确认按钮")
                return ToolResult(success=False, error="无法点击确认按钮")
            
            # 第8步：等待导入完成
            log("等待15秒让文档导入完成...")
            await asyncio.sleep(15)
            
            # 第9步：检查编辑器是否有内容
            log("检查编辑器内容...")
            try:
                title_input = await self.page.query_selector('textarea[placeholder*="标题"], input[placeholder*="标题"]')
                if title_input:
                    title_value = await title_input.input_value()
                    log(f"编辑器标题: {title_value}")
                    if not title_value:
                        log("标题为空，可能导入失败")
                        return ToolResult(success=False, error="文档导入后标题为空")
                else:
                    log("没找到标题输入框")
            except Exception as e:
                log(f"检查编辑器失败: {e}")
            
            # 第10步：发布
            log("点击发布按钮...")
            try:
                publish_btn = await self.page.wait_for_selector('button:has-text("发布")', timeout=10000)
                await publish_btn.click()
                log("已点击发布")
            except Exception as e:
                log(f"点击发布按钮失败: {e}")
                return ToolResult(success=False, error=f"点击发布按钮失败: {e}")
            
            await asyncio.sleep(3)
            
            # 确认弹窗
            try:
                publish_buttons = await self.page.query_selector_all('button:has-text("发布")')
                if len(publish_buttons) >= 2:
                    await publish_buttons[-1].click()
                    log("已点击确认发布")
            except:
                pass
            
            # 等待跳转
            log("等待页面跳转到文章链接...")
            try:
                await self.page.wait_for_url("**/p/**", timeout=30000)
                log("页面已跳转")
            except:
                log("等待跳转超时")
            
            await asyncio.sleep(3)
            current_url = self.page.url
            log(f"当前URL: {current_url}")
            
            if "/p/" in current_url:
                post_id = current_url.split("/p/")[1].split("?")[0]
                log(f"发布成功，文章ID: {post_id}")
                return ToolResult(success=True, post_id=post_id, post_url=current_url)
            else:
                log("URL不包含/p/，可能发布未成功")
                return ToolResult(success=False, error="发布未完成，页面未跳转到文章")
            
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
