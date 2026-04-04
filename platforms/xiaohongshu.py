"""
小红书 (Xiaohongshu) 平台适配器 - 简化版，只填充内容不发布
"""
import asyncio
import json
import os
from typing import Optional
from playwright.async_api import Page

from platforms.base import PlatformTool, ToolResult


class XiaohongshuTool(PlatformTool):
    """小红书平台适配器 - 简化版"""
    
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
        """打开小红书编辑器，上传文档并填充内容（不自动发布）"""
        try:
            await self.init_browser(headless=False)
            
            print("检查登录状态...")
            if not await self.is_logged_in():
                return ToolResult(success=False, error="未登录")
            
            print("✓ 已登录")
            print("\n========== 开始填充内容（请手动点击最终发布）==========\n")
            
            # Step 1: 进入发布页面
            print("Step 1: 打开发布页面...")
            await self.page.goto('https://creator.xiaohongshu.com/new/home')
            await asyncio.sleep(3)
            
            # Step 2: 点击发布笔记
            print("Step 2: 点击发布笔记...")
            try:
                await self.page.get_by_text("发布笔记").first.click()
                await asyncio.sleep(3)
            except:
                pass
            
            # Step 3: 选择写长文
            print("Step 3: 选择写长文...")
            try:
                await self.page.get_by_text("写长文").first.click()
                await asyncio.sleep(3)
            except Exception as e:
                print(f"选择写长文失败: {e}")
            
            # Step 4: 点击新的创作
            print("Step 4: 点击新的创作...")
            try:
                await self.page.get_by_role("button", name="新的创作").first.click()
                await asyncio.sleep(3)
            except Exception as e:
                print(f"点击新的创作失败: {e}")
            
            # Step 5: 上传 Word 文件
            if file_path:
                print(f"Step 5: 上传文件 {os.path.basename(file_path)}...")
                print("请手动点击导入按钮并选择文件，或等待自动上传...")
                
                # 等待30秒让用户手动操作或自动检测
                print("等待30秒，你可以：")
                print("  1. 手动点击导入按钮上传文件")
                print("  2. 等待程序尝试自动检测上传框")
                await asyncio.sleep(5)
                
                # 尝试自动上传
                try:
                    # 点击导入按钮
                    await self.page.locator(".isFromFileRed").click()
                    await asyncio.sleep(2)
                    
                    # 找 file input
                    file_inputs = await self.page.locator('input[type="file"]').all()
                    print(f"检测到 {len(file_inputs)} 个上传框")
                    
                    for inp in file_inputs:
                        try:
                            await inp.set_input_files(file_path)
                            print("✓ 文件已上传，等待解析...")
                            await asyncio.sleep(10)  # 等待解析
                            break
                        except:
                            continue
                except Exception as e:
                    print(f"自动上传失败: {e}")
                    print("请手动完成上传")
            
            # Step 6: 等待用户完成
            print("\n========================================")
            print("✓ 编辑器已打开，请：")
            print("  1. 确认内容已填充")
            print("  2. 检查标题和正文")
            print("  3. 点击【保存草稿】或【发布】")
            print("========================================\n")
            
            # 保持浏览器打开，让用户手动操作
            print("浏览器将保持打开5分钟，你可以手动操作...")
            await asyncio.sleep(300)  # 5分钟
            
            await self.close()
            return ToolResult(
                success=True,
                data={'platform': 'xiaohongshu', 'note': '已在浏览器中打开编辑器，请手动完成发布'}
            )
            
        except Exception as e:
            print(f"错误: {e}")
            await self.close()
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        """检查笔记状态"""
        return ToolResult(success=True, data={'status': 'unknown', 'note': '请访问创作者中心查看'})
