"""
小红书 (Xiaohongshu) 平台适配器 - 完整长文发布流程
基于 xiaohongshu-longpost-auto Skill 实现
"""
import asyncio
import json
import os
import re
from typing import Optional
from playwright.async_api import Page, expect

from platforms.base import PlatformTool, ToolResult


class XiaohongshuTool(PlatformTool):
    """小红书平台适配器 - 完整自动化"""
    
    platform_name = "xiaohongshu"
    platform_id = "xiaohongshu"
    platform_type = "article"
    output_format = "markdown"
    
    async def init_browser(self, headless: bool = False, load_cookie: bool = True):
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
            'locale': 'zh-CN',
            'timezone_id': 'Asia/Shanghai',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        if load_cookie:
            state_file = f"data/cookies/{self.platform_id}_state.json"
            if os.path.exists(state_file):
                try:
                    with open(state_file, 'r', encoding='utf-8') as f:
                        context_options['storage_state'] = json.load(f)
                    print(f"✓ 已加载登录状态")
                except Exception as e:
                    print(f"加载登录状态失败: {e}")
        
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=browser_args
        )
        self.context = await self.browser.new_context(**context_options)
        self.page = await self.context.new_page()
    
    async def is_logged_in(self) -> bool:
        """检查登录状态"""
        try:
            await self.page.goto('https://creator.xiaohongshu.com/', wait_until='networkidle')
            await asyncio.sleep(2)
            return 'login' not in self.page.url
        except:
            return False
    
    async def authenticate(self) -> bool:
        """扫码登录"""
        await self.init_browser(headless=False)
        print("打开小红书登录页面...")
        await self.page.goto('https://creator.xiaohongshu.com/login')
        print("请扫码登录，等待中...")
        
        for i in range(300):
            if 'login' not in self.page.url:
                print(f"✓ 登录成功: {self.page.url}")
                await self._save_cookies()
                return True
            if i % 10 == 0:
                print(f"等待登录... {i}s")
            await asyncio.sleep(1)
        return False
    
    async def _save_cookies(self):
        """保存登录状态"""
        os.makedirs('data/cookies', exist_ok=True)
        storage = await self.context.storage_state()
        with open(f'data/cookies/{self.platform_id}_state.json', 'w') as f:
            json.dump(storage, f)
        print("✓ 登录状态已保存")
    
    async def close(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    def _preprocess_content(self, content: str, title: str) -> tuple:
        """内容预处理 - 按 Skill 要求分段"""
        # 小红书标题限制20字
        short_title = title[:20] if len(title) <= 20 else title[:18] + "..."
        
        # 分段：每段300-500字
        paragraphs = []
        current_para = []
        current_len = 0
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                if current_para:
                    paragraphs.append('\n'.join(current_para))
                    current_para = []
                    current_len = 0
                continue
            
            if current_len + len(line) > 400:
                if current_para:
                    paragraphs.append('\n'.join(current_para))
                current_para = [line]
                current_len = len(line)
            else:
                current_para.append(line)
                current_len += len(line)
        
        if current_para:
            paragraphs.append('\n\n'.join(current_para))
        
        # 添加表情和格式
        formatted = '\n\n'.join([
            f"✨ {p}" if i == 0 else f"💡 {p}" 
            for i, p in enumerate(paragraphs[:10])  # 最多10段
        ])
        
        # 生成描述（50-100字）
        desc = content[:80] + "..." if len(content) > 80 else content
        desc = desc.replace('\n', ' ')
        
        return short_title, formatted, desc
    
    async def publish(self, article, file_path: str = None) -> ToolResult:
        """完整发布流程"""
        try:
            # 提取内容
            if article:
                title = article.title or "无标题"
                content = article.content or ""
            else:
                title = os.path.splitext(os.path.basename(file_path or ""))[0]
                content = ""
            
            # 预处理
            short_title, formatted_content, description = self._preprocess_content(content, title)
            print(f"标题: {short_title}")
            print(f"内容长度: {len(formatted_content)} 字")
            
            # 1. 初始化浏览器
            print("\n[1/10] 初始化浏览器...")
            await self.init_browser(headless=False)
            
            # 2. 登录检测
            print("[2/10] 检查登录状态...")
            if not await self.is_logged_in():
                print("未登录，需要扫码...")
                await self.close()
                if not await self.authenticate():
                    return ToolResult(success=False, error="登录失败")
                await self.init_browser(headless=False)
            print("✓ 已登录")
            
            page = self.page
            
            # 3. 进入发布页面
            print("[3/10] 进入发布页面...")
            await page.goto("https://creator.xiaohongshu.com/publish/publish?from=homepage")
            await asyncio.sleep(3)
            
            # 4. 点击写长文
            print("[4/10] 选择写长文...")
            await page.get_by_text("写长文").first.click()
            await asyncio.sleep(2)
            
            # 5. 新的创作
            print("[5/10] 点击新的创作...")
            await page.get_by_role("button", name="新的创作").first.click()
            await asyncio.sleep(3)
            
            # 6. 填充标题
            print("[6/10] 填写标题...")
            title_input = page.get_by_role("textbox", name="输入标题")
            await title_input.click()
            await title_input.fill(short_title)
            print(f"✓ 标题: {short_title}")
            
            # 7. 填充正文（使用 evaluate 注入）
            print("[7/10] 填写正文...")
            try:
                # 使用 set_input_files 或直接填充
                # 方案：用 locator 直接填
                editor = page.locator('[contenteditable="true"]').first
                if await editor.count() > 0:
                    await editor.fill(formatted_content)
                    print("✓ 正文已填充")
                else:
                    print("! 未找到编辑器")
            except Exception as e:
                print(f"! 正文填充失败: {e}")
            
            # 8. 一键排版 → 选模板 → 下一步
            print("[8/10] 一键排版...")
            try:
                format_btn = page.get_by_role("button", name="一键排版")
                if await format_btn.count() > 0:
                    await format_btn.click()
                    await asyncio.sleep(2)
                    print("  ✓ 已点击一键排版")
                    
                    # 选择模板（清晰明朗/逻辑结构）
                    template_names = ["逻辑结构", "清晰明朗", "职场干货"]
                    for tmpl_name in template_names:
                        template = page.get_by_text(tmpl_name).first
                        if await template.count() > 0:
                            await template.click()
                            print(f"  ✓ 已选择模板: {tmpl_name}")
                            await asyncio.sleep(1)
                            break
                    
                    # 点击下一步（尝试多种可能的按钮名称）
                    next_btn_names = ["下一步", "确定", "完成", "应用", "确认"]
                    next_clicked = False
                    for btn_name in next_btn_names:
                        try:
                            next_btn = page.get_by_role("button", name=btn_name).first
                            if await next_btn.count() > 0 and await next_btn.is_visible():
                                await next_btn.click()
                                print(f"  ✓ 已点击: {btn_name}")
                                next_clicked = True
                                await asyncio.sleep(2)
                                break
                        except:
                            continue
                    
                    if not next_clicked:
                        print("  - 未找到下一步按钮，继续...")
            except Exception as e:
                print(f"  ! 排版失败: {e}")
            
            # 9. 填写描述（50-100字）
            print("[9/10] 填写描述...")
            try:
                desc_input = page.get_by_placeholder("添加正文描述").first
                if await desc_input.count() > 0:
                    desc_text = description[:80] if len(description) > 80 else description
                    await desc_input.fill(desc_text)
                    print(f"  ✓ 描述: {desc_text[:30]}...")
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"  ! 描述填写失败: {e}")
            
            # 10. 添加标签
            print("[10/10] 添加标签...")
            try:
                # 智能提取标签
                tags = []
                content_lower = (title + content).lower()
                if any(k in content_lower for k in ["ai", "人工智能", "智能"]):
                    tags.extend(["AI", "人工智能"])
                if any(k in content_lower for k in ["就业", "工作", "职场"]):
                    tags.extend(["职场干货", "就业指导"])
                if any(k in content_lower for k in ["2026", "未来", "趋势"]):
                    tags.extend(["未来趋势", "科技改变生活"])
                if not tags:
                    tags = ["干货分享", "职场干货", "AI时代"]
                
                # 点击话题按钮
                topic_btn = page.get_by_role("button", name="话题").first
                if await topic_btn.count() > 0:
                    await topic_btn.click()
                    await asyncio.sleep(1)
                    
                    # 输入标签
                    for tag in tags[:6]:
                        try:
                            tag_input = page.get_by_placeholder("搜索话题").first
                            if await tag_input.count() > 0:
                                await tag_input.fill(tag)
                                await asyncio.sleep(1)
                                # 点击第一个推荐标签
                                first_tag = page.locator("[class*='topic'], [class*='tag']").first
                                if await first_tag.count() > 0:
                                    await first_tag.click()
                                    await asyncio.sleep(0.5)
                        except:
                            pass
                    print(f"  ✓ 标签: {tags}")
            except Exception as e:
                print(f"  ! 标签添加失败: {e}")
            
            # 11. 原创声明
            print("[11/11] 原创声明...")
            try:
                # 找包含"原创"的复选框或按钮
                original_checkbox = page.locator("input[type='checkbox']").locator("xpath=../..").filter(has_text="原创").first
                if await original_checkbox.count() == 0:
                    # 尝试直接找文本
                    original_checkbox = page.get_by_text("声明原创").first
                
                if await original_checkbox.count() > 0:
                    await original_checkbox.click()
                    print("  ✓ 已点击原创声明")
                    await asyncio.sleep(1)
                    
                    # 确认弹窗（如果有）
                    confirm_btn = page.get_by_role("button", name=re.compile("声明|确认|确定")).first
                    if await confirm_btn.count() > 0:
                        await confirm_btn.click()
                        print("  ✓ 已确认原创声明")
                        await asyncio.sleep(1)
            except Exception as e:
                print(f"  ! 原创声明失败: {e}")
            
            # 12. 发布
            print("\n[12/12] 发布...")
            try:
                # 尝试多种可能的发布按钮名称
                publish_btn_names = ["发布", "立即发布", "确认发布", "提交"]
                publish_clicked = False
                
                for btn_name in publish_btn_names:
                    try:
                        publish_btn = page.get_by_role("button", name=btn_name).first
                        if await publish_btn.count() > 0 and await publish_btn.is_visible():
                            await publish_btn.click()
                            print(f"  ✓ 已点击: {btn_name}")
                            publish_clicked = True
                            await asyncio.sleep(5)
                            break
                    except Exception as e:
                        continue
                
                if not publish_clicked:
                    print("  ! 未找到发布按钮，请手动点击")
                    await asyncio.sleep(60)
                    await self.close()
                    return ToolResult(success=False, error="未找到发布按钮")
                
                # 检查成功提示
                success_indicator = page.locator("text=/发布成功|已发布/")
                if await success_indicator.count() > 0:
                    print("✓ 发布成功！")
                
                url = page.url
                await self.close()
                return ToolResult(
                    success=True,
                    data={
                        'platform': 'xiaohongshu',
                        'title': short_title,
                        'url': url
                    }
                )
            except Exception as e:
                print(f"! 发布失败: {e}")
                # 保持浏览器打开让用户手动发布
                print("浏览器保持打开，请手动点击发布...")
                await asyncio.sleep(60)
                await self.close()
                return ToolResult(success=False, error=str(e))
                
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
            await self.close()
            return ToolResult(success=False, error=str(e))
    
    async def check_status(self, post_id: str) -> ToolResult:
        """检查发布状态"""
        return ToolResult(success=True, data={'status': 'unknown'})
