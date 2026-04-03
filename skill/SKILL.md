---
name: content-publisher
description: 多平台自媒体内容分发工具，支持知乎、头条号、百家号。通过浏览器自动化实现文章一键发布到多个自媒体平台。使用 Playwright 模拟真实用户操作，支持 Word 文档导入、Cookie 持久化、商品插入等功能。适用于需要批量发布内容到多个平台的自媒体运营者。
---

# Content Publisher - 多平台自媒体分发工具

一个基于浏览器自动化的多平台自媒体内容分发工具，支持知乎、头条号、百家号。

## 支持平台

- **知乎 (zhihu)** - 知乎专栏文章发布
- **头条号 (toutiao)** - 今日头条文章发布
- **百家号 (baijiahao)** - 百度百家号文章发布，支持商品插入

## 核心功能

- Word 文档 (.docx) 自动解析和发布
- 浏览器 Cookie 持久化登录
- 自动提取文章标题并填写
- 百家号支持商品自动插入
- 批量多平台同时发布

## 安装要求

```bash
pip install playwright python-docx click rich
playwright install chromium
```

## 使用方式

### 1. 登录平台

首次使用需要先登录各平台：

```bash
python publisher.py login -p zhihu
python publisher.py login -p toutiao
python publisher.py login -p baijiahao
```

### 2. 发布文章

```bash
# 发布到所有平台
python publisher.py publish "文章.docx"

# 发布到指定平台
python publisher.py publish "文章.docx" -p zhihu
python publisher.py publish "文章.docx" -p toutiao
python publisher.py publish "文章.docx" -p baijiahao
```

### 3. 查看状态

```bash
python publisher.py status
```

## 项目结构

```
content-publisher/
├── publisher.py          # 主程序入口
├── platforms/            # 平台实现
│   ├── __init__.py
│   ├── base.py          # 平台基类
│   ├── zhihu.py         # 知乎平台
│   ├── toutiao.py       # 头条号平台
│   └── baijiahao.py     # 百家号平台
├── data/                # 数据目录
│   └── cookies/         # Cookie 文件
└── requirements.txt     # 依赖列表
```

## 技术实现

### 浏览器自动化

使用 Playwright 进行浏览器自动化：
- 模拟真实用户操作
- 自动处理弹窗和引导
- 支持 Cookie 持久化
- 反检测脚本注入

### Word 文档支持

自动解析 .docx 文件：
- 提取文本内容
- 提取图片资源
- 转换为 Markdown
- 保留原有格式

### 错误处理

- 详细的调试日志（`{platform}_debug.log`）
- 截图保存失败现场
- 自动重试机制
- 多种选择器备用方案

## 配置说明

### Cookie 存储

登录状态保存在 `data/cookies/{platform}.json`，无需每次重新登录。

### 调试日志

每个平台有独立的调试日志文件：
- `zhihu_debug.log`
- `toutiao_debug.log`
- `baijiahao_debug.log`

## 注意事项

1. **首次登录**需要人工扫码或账号密码登录
2. **百家号**支持商品自动插入（可选）
3. **头条号**需要设置标题
4. 发布前请检查文章内容和封面图片

## 扩展开发

添加新平台的步骤：

1. 在 `platforms/` 下创建 `{platform}.py`
2. 继承 `PlatformTool` 基类
3. 实现 `is_logged_in()`、`authenticate()`、`publish()` 方法
4. 使用 `playwright codegen` 录制操作流程
5. 在 `__init__.py` 中注册平台

## 许可证

MIT License
