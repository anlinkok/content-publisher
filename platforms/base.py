"""
平台工具基类
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool
    data: Dict[str, Any] = {}
    error: Optional[str] = None
    post_id: Optional[str] = None
    post_url: Optional[str] = None


class PlatformTool(ABC):
    """
    平台发布工具基类
    参考 Claude Code Tool 架构设计
    """
    name: str = ""
    description: str = ""
    platform_type: str = ""
    
    def __init__(self, account: Optional[Any] = None):
        self.account = account
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self._is_authenticated = False
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """认证/登录"""
        pass
    
    @abstractmethod
    async def publish(self, article: Any) -> ToolResult:
        """发布文章"""
        pass
    
    @abstractmethod
    async def check_status(self, post_id: str) -> ToolResult:
        """检查发布状态"""
        pass
    
    async def init_browser(self, headless: bool = True):
        """初始化浏览器"""
        from playwright.async_api import async_playwright
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        
        # 反检测配置
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
        )
        
        # 注入反检测脚本
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });
        """)
        
        self.page = await self.context.new_page()
        
    async def close(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def save_session(self):
        """保存登录会话"""
        if self.context and self.account:
            try:
                storage = await self.context.storage_state()
                from sqlmodel import Session
                from models import engine
                
                with Session(engine) as session:
                    self.account.cookies = json.dumps(storage)
                    session.add(self.account)
                    session.commit()
                    logger.info(f"{self.platform_type}: 会话已保存")
            except Exception as e:
                logger.error(f"保存会话失败: {e}")
    
    async def load_session(self) -> bool:
        """加载登录会话"""
        if self.account and self.account.cookies:
            try:
                storage = json.loads(self.account.cookies)
                if self.browser and not self.context:
                    self.context = await self.browser.new_context(storage_state=storage)
                    self.page = await self.context.new_page()
                    logger.info(f"{self.platform_type}: 会话已加载")
                    return True
            except Exception as e:
                logger.warning(f"加载会话失败: {e}")
        return False
    
    async def upload_image(self, image_path: str) -> Optional[str]:
        """上传图片到平台图床，返回图片URL"""
        # 子类可以覆盖此方法实现图片上传
        logger.warning(f"{self.platform_type}: 未实现图片上传功能")
        return None
    
    async def upload_images_in_article(self, article) -> None:
        """处理文章中的图片上传"""
        import re
        import os
        
        # 查找所有本地图片路径
        img_pattern = r'!\[.*?\]\((.+?)\)'
        local_images = re.findall(img_pattern, article.content)
        
        for img_path in local_images:
            # 跳过网络图片
            if img_path.startswith('http'):
                continue
            
            # 解析相对路径
            if img_path.startswith('./'):
                img_path = img_path[2:]
            
            full_path = os.path.join('articles', img_path)
            if not os.path.exists(full_path):
                logger.warning(f"图片不存在: {full_path}")
                continue
            
            # 上传图片
            logger.info(f"上传图片: {full_path}")
            image_url = await self.upload_image(full_path)
            
            if image_url:
                # 替换内容中的图片路径
                article.content = article.content.replace(f'({img_path})', f'({image_url})')
                article.html_content = article.html_content.replace(f'"{img_path}"', f'"{image_url}"')
                logger.info(f"图片上传成功: {image_url}")
            else:
                logger.warning(f"图片上传失败: {full_path}")
