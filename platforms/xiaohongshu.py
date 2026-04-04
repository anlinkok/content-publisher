"""
小红书 (Xiaohongshu) 平台适配器 - 基于 Codegen 录制
"""
import asyncio
import json
import os
from typing import Optional
from playwright.async_api import Page

from platforms.base import PlatformTool, ToolResult


class XiaohongshuTool(PlatformTool):
    """小红书平台适配器 - 基于真实录制"""
    
    platform_name = "xiaohongshu"
    platform_id = "xiaohongshu"
    platform_type = "article"
    output_format = "docx"  # 小红书支持 Word 直接上传
    
    async def init_browser(self, headless: bool = True, load_cookie: bool = True):
        """初始化浏览器"""
        from playwright.async_api import async_playwright
        
        self.playwright = await async_playwright().start()
        
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
        ]
        
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        if load_cookie:
            state_file = f"data/cookies/{self.platform_id}_state.json"
            cookie_file = f"data/cookies/{self.platform_id}.json"
            
            try:
                if os.path.exists(state_file):
                    with open(state_file, 'r', encoding='utf-8') as f:
                        storage = json.load(f)
                        context_options['storage_state'] = storage
                        print(f"已加载完整登录状态: {state_file}")
                elif os.path.exists(cookie_file):
                    with open(cookie_file, 'r', encoding='utf-8') as f:
                        cookies = json.load(f)
                        context_options['storage_state'] = {'cookies': cookies}
                        print(f"已加载Cookie: {cookie_file}")
            except Exception as e:
                print(f"加载登录状态失败: {e}")
        
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=browser_args
        )
        self.context = await self.browser.new_context(**context_options)
        self.page = await self.context.new_page()
    
    async def is_logged_in(self) -> bool:
        """检查是否已登录"""
        try:
            await self.page.goto('https://creator.xiaohongshu.com/', wait_until='domcontentloaded')
            await asyncio.sleep(2)
            current_url = self.page.url
            return 'login' not in current_url and 'creator.xiaohongshu.com' in current_url
        except:
            return False
    
    async def authenticate(self) -> bool:
        """登录小红书"""
        await self.init_browser(headless=False)
        
        print("打开小红书登录页面...")
        await self.page.goto('https://creator.xiaohongshu.com/login')
        print("请在浏览器中扫码登录...")
        
        max_wait = 300
        for i in range(max_wait):
            current_url = self.page.url
            if 'creator.xiaohongshu.com/login' not in current_url and 'creator.xiaohongshu.com' in current_url:
                print(f"\n✓ 登录成功: {current_url}")
                await asyncio.sleep(3)
                await self.save_cookies()
                await self.close()
                return True
            
            if i % 10 == 0 and i > 0:
                print(f"等待登录... {i}秒")
            
            await asyncio.sleep(1)
        
        print("\n登录超时")
        await self.close()
        return False
    
    async def save_cookies(self):
        """保存登录状态"""
        os.makedirs('data/cookies', exist_ok=True)
        storage = await self.context.storage_state()
        with open(f'data/cookies/{self.platform_id}_state.json', 'w', encoding='utf-8') as f:
            json.dump(storage, f, ensure_ascii=False, indent=2)
        print(f"登录状态已保存")
    
    async def close(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """发布到小红书 - 基于 Codegen 录制的精确流程"""
        try:
            await self.init_browser(headless=False)
            
            print("检查登录状态...")
            if not await self.is_logged_in():
                print("未登录，请先登录...")
                await self.close()
                login_success = await self.authenticate()
                if not login_success:
                    return ToolResult(success=False, error="登录失败")
                # 重新初始化浏览器
                await self.init_browser(headless=False)
            
            print("✓ 已登录")
            print("\n========== 小红书自动发布 ==========\n")
            
            page = self.page
            
            # Step 1: 进入发布页面
            print("Step 1: 打开创作者中心...")
            await page.goto("https://creator.xiaohongshu.com/new/home")
            await asyncio.sleep(2)
            
            # Step 2: 点击发布笔记
            print("Step 2: 点击发布笔记...")
            await page.get_by_text("发布笔记").click()
            await asyncio.sleep(2)
            
            # Step 3: 选择写长文
            print("Step 3: 选择写长文...")
            await page.get_by_text("写长文").click()
            await asyncio.sleep(2)
            
            # Step 4: 点击新的创作
            print("Step 4: 点击新的创作...")
            await page.get_by_role("button", name="新的创作").click()
            await asyncio.sleep(2)
            
            # Step 5: 上传 Word 文件（关键：Codegen 发现直接在 body 上 set_input_files）
            if file_path and os.path.exists(file_path):
                print(f"Step 5: 上传文件 {os.path.basename(file_path)}...")
                
                # 先点击导入按钮
                print("  - 点击导入按钮...")
                await page.locator(".isFromFileRed").click()
                await asyncio.sleep(1)
                
                # 点击上传区域
                print("  - 点击上传区域...")
                # 使用 nth(3) 因为页面上可能有多个匹配的元素
                upload_divs = await page.locator("div").filter(has_text="点击或拖拽上传").all()
                if len(upload_divs) > 3:
                    await upload_divs[3].click()
                else:
                    # 尝试点击第一个
                    try:
                        await page.locator("div").filter(has_text="点击或拖拽上传").first.click()
                    except:
                        pass
                await asyncio.sleep(1)
                
                # 关键：在 body 上设置文件
                print("  - 设置文件...")
                await page.locator("body").set_input_files(file_path)
                print("  ✓ 文件已上传，等待解析...")
                await asyncio.sleep(10)  # 等待解析
            
            # Step 6: 填写标题
            print("Step 6: 填写标题...")
            if article and hasattr(article, 'title') and article.title:
                title = article.title
            else:
                title = os.path.splitext(os.path.basename(file_path or ""))[0]
            
            title_input = page.get_by_role("textbox", name="输入标题")
            await title_input.click()
            await title_input.fill(title)
            print(f"  ✓ 标题: {title}")
            
            # Step 7: 检查是否有"一键排版"按钮
            print("Step 7: 检查一键排版...")
            try:
                format_btn = page.get_by_role("button", name="一键排版")
                if await format_btn.count() > 0:
                    await format_btn.click()
                    await asyncio.sleep(2)
                    print("  ✓ 已点击一键排版")
                    
                    # 选择样式（如果有）
                    try:
                        clear_style = page.get_by_text("清晰明朗")
                        if await clear_style.count() > 0:
                            await clear_style.click()
                            await asyncio.sleep(1)
                    except:
                        pass
            except:
                print("  - 一键排版按钮未找到或不需要")
            
            # Step 8: 长文模式可能没有下一步，直接等待用户发布
            print("\n========================================")
            print("✓ 内容已填充完成")
            print(f"  标题: {title}")
            print("  请检查：")
            print("    1. 文档是否已正确解析")
            print("    2. 标题是否正确")
            print("    3. 图片是否正常显示")
            print("  然后点击【发布】或【保存草稿】")
            print("========================================\n")
            
            # 保持浏览器打开，让用户手动操作
            print("浏览器将保持打开5分钟...")
            await asyncio.sleep(300)
            
            await self.close()
            return ToolResult(
                success=True,
                data={'platform': 'xiaohongshu', 'title': title, 'note': '内容已填充，请手动发布'}
            )
            
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
            await self.close()
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        """检查笔记状态"""
        return ToolResult(success=True, data={'status': 'unknown', 'note': '请访问创作者中心查看'})
