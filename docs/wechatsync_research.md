# Wechatsync 研究总结与优化方案

## 一、Wechatsync 架构分析

### 1.1 核心架构

```
Wechatsync/
├── packages/
│   ├── extension/       # Chrome 扩展 (MV3) - 用户界面
│   ├── core/            # 核心逻辑层 - 平台适配器、同步引擎
│   ├── mcp-server/      # MCP Server - AI 集成接口
│   └── cli/             # 命令行工具
```

### 1.2 适配器架构 (BaseAdapter)

所有平台适配器继承 `BaseAdapter`，实现 5 个核心方法：

| 方法 | 功能 | 说明 |
|------|------|------|
| `getMetaData()` | 获取用户信息 | 验证登录状态，获取平台元数据 |
| `preEditPost(post)` | 内容预处理 | 转换格式、处理特殊标签 |
| `addPost(post)` | 创建文章 | 发布新文章到平台 |
| `uploadFile(file)` | 上传图片 | 处理图片上传并返回 URL |
| `editPost(post_id, post)` | 更新文章 | 编辑已发布的文章 |

### 1.3 工作流程

```
用户发起同步
    ↓
Chrome 扩展读取浏览器 Cookie
    ↓
调用目标平台官方 Web API
    ↓
适配器处理格式转换
    ↓
内容发布到目标平台
```

## 二、Wechatsync vs 我们的方案对比

| 维度 | Wechatsync | 我们的方案 (ContentPublisher) |
|------|------------|-------------------------------|
| **技术栈** | TypeScript + Chrome Extension | Python + Playwright |
| **运行环境** | 浏览器扩展 | 独立 Python 脚本 |
| **登录方式** | 复用浏览器 Cookie | 单独 Playwright 浏览器实例 |
| **平台数量** | 29+ 平台 | 3 平台（知乎、头条、百家号） |
| **AI 集成** | MCP Server | 暂无 |
| **内容提取** | 智能提取网页正文 | Word 文档导入 |
| **数据存储** | 浏览器本地存储 | 本地 Cookie 文件 |

## 三、优化建议

### 方案 A：直接集成 Wechatsync MCP（最快）

**做法**：
1. 用户安装 Wechatsync Chrome 扩展
2. 启用 MCP 连接并设置 Token
3. 通过 MCP 调用 Wechatsync 的发布功能

**优点**：
- 立即支持 29+ 平台
- 无需自己维护适配器
- 利用浏览器 Cookie，更稳定

**缺点**：
- 依赖浏览器扩展
- 需要用户额外安装

**实现步骤**：

```bash
# 1. 安装 Wechatsync CLI
npm install -g @wechatsync/cli

# 2. 在 Chrome 扩展中启用 MCP 并获取 Token
# 3. 设置环境变量
export WECHATSYNC_TOKEN="your-token"

# 4. 使用 CLI 发布
wechatsync sync article.md -p zhihu,juejin,csdn
```

### 方案 B：参考 Wechatsync 适配器架构重构（推荐）

**做法**：
1. 保持 Python + Playwright 架构
2. 引入 Wechatsync 的适配器设计思想
3. 将平台代码重构为 Adapter 模式
4. 添加 MCP Server 支持

**优点**：
- 保持现有架构优势
- 代码更清晰、可扩展
- 可作为独立 Skill 分发

**重构后的项目结构**：

```
content-publisher/
├── publisher.py              # 主程序入口 (CLI)
├── adapters/                 # 适配器目录
│   ├── __init__.py
│   ├── base.py              # BaseAdapter 基类
│   ├── zhihu.py             # 知乎适配器
│   ├── toutiao.py           # 头条适配器
│   ├── baijiahao.py         # 百家号适配器
│   └── wechatsync_bridge.py # Wechatsync 桥接适配器
├── core/                     # 核心逻辑
│   ├── sync_engine.py       # 同步引擎
│   ├── content_processor.py # 内容处理器
│   └── mcp_server.py        # MCP Server 实现
├── parsers/                  # 内容解析器
│   ├── word_parser.py
│   ├── markdown_parser.py
│   └── html_parser.py
├── drivers/                  # Web 驱动
│   └── playwright_driver.py
└── utils/
    └── logger.py
```

**BaseAdapter 基类设计**：

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict

@dataclass
class Article:
    title: str
    content: str
    html_content: Optional[str] = None
    markdown_content: Optional[str] = None
    cover_image: Optional[str] = None
    images: List[str] = None
    tags: List[str] = None
    source_file: Optional[str] = None

@dataclass
class PublishResult:
    success: bool
    platform: str
    post_id: Optional[str] = None
    post_url: Optional[str] = None
    draft_url: Optional[str] = None
    error: Optional[str] = None

class BaseAdapter(ABC):
    """平台适配器基类"""
    
    # 平台信息
    platform_name: str = ""
    platform_id: str = ""  # 英文标识
    platform_type: str = ""  # article/video/short
    
    def __init__(self, driver=None):
        self.driver = driver
        self.is_authenticated = False
    
    @abstractmethod
    async def get_metadata(self) -> Dict:
        """获取平台元数据和用户信息"""
        pass
    
    @abstractmethod
    async def check_auth(self) -> bool:
        """检查是否已登录"""
        pass
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """引导用户登录"""
        pass
    
    def pre_edit_post(self, article: Article) -> Article:
        """内容预处理（可选重写）"""
        return article
    
    @abstractmethod
    async def add_post(self, article: Article) -> PublishResult:
        """发布文章"""
        pass
    
    @abstractmethod
    async def upload_file(self, file_path: str) -> str:
        """上传图片/文件，返回 URL"""
        pass
    
    async def edit_post(self, post_id: str, article: Article) -> PublishResult:
        """编辑文章（可选实现）"""
        raise NotImplementedError
```

### 方案 C：混合方案（最佳）

**结合 A 和 B 的优点**：

1. **核心层**：Python + Playwright 适配器架构
2. **扩展层**：通过 Wechatsync Bridge 支持 29+ 平台
3. **AI 层**：MCP Server 支持

**工作流程**：

```
用户请求
    ↓
ContentPublisher Core
    ↓
├─ 原生适配器 → 知乎、头条、百家号（Playwright）
├─ Wechatsync Bridge → 掘金、CSDN、简书等 25+ 平台
└─ MCP Server → AI 工作流集成
```

## 四、MCP Server 集成方案

### 4.1 MCP 工具列表

参考 Wechatsync MCP Server，实现以下工具：

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `list_platforms` | 列出所有平台及登录状态 | - |
| `check_auth` | 检查指定平台登录状态 | `platform: str` |
| `sync_article` | 同步文章到指定平台 | `title, content, platforms[]` |
| `extract_article` | 从 URL 提取文章 | `url: str` |
| `upload_image` | 上传图片 | `file_path: str` |
| `get_sync_status` | 获取同步状态 | `task_id: str` |

### 4.2 MCP Server 配置

```python
# mcp_server.py
from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("content-publisher")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="list_platforms",
            description="列出所有支持的自媒体平台及其登录状态",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="sync_article",
            description="将文章同步发布到多个自媒体平台",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "platforms": {"type": "array", "items": {"type": "string"}},
                    "cover_image": {"type": "string"}
                },
                "required": ["title", "content", "platforms"]
            }
        ),
    ]

@server.call_tool()
async def call_tool(name, arguments):
    if name == "list_platforms":
        # 返回平台列表
        pass
    elif name == "sync_article":
        # 执行同步
        pass
```

## 五、实施路线图

### Phase 1: 重构适配器架构（1-2 天）

- [ ] 创建 `BaseAdapter` 基类
- [ ] 将现有平台代码重构为 Adapter 模式
- [ ] 添加统一的 `SyncEngine`

### Phase 2: MCP Server（1 天）

- [ ] 实现 MCP Server
- [ ] 添加工具：list_platforms, sync_article
- [ ] 测试与 Claude Code 集成

### Phase 3: 扩展平台支持（2-3 天）

- [ ] 添加掘金、CSDN、简书适配器
- [ ] 实现 Wechatsync Bridge
- [ ] 支持从 URL 提取文章内容

### Phase 4: 优化与打包（1 天）

- [ ] 完善错误处理
- [ ] 打包为 Skill
- [ ] 编写文档

## 六、参考资源

1. **Wechatsync GitHub**: https://github.com/wechatsync/Wechatsync
2. **适配器开发文档**: https://developer.wechatsync.com/
3. **MCP 协议**: https://modelcontextprotocol.io/
4. **示例适配器**: 
   - 知乎: https://github.com/wechatsync/Wechatsync/blob/main/packages/core/src/platforms/zhihu.ts
   - 头条: https://github.com/wechatsync/Wechatsync/blob/main/packages/core/src/platforms/toutiao.ts

## 七、结论

**推荐采用方案 B + 方案 C 的混合模式**：

1. 保持 Python + Playwright 架构，稳定性好
2. 引入 Wechatsync 的适配器设计思想，代码更清晰
3. 添加 MCP Server，与 AI 工作流无缝集成
4. 未来可通过 Bridge 模式接入 Wechatsync 的 29+ 平台

这样既能立即改善代码结构，又能为未来的平台扩展打下基础。
