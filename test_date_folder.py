#!/usr/bin/env python3
"""
测试日期文件夹功能 (简化版，无需依赖)
"""

import os
import re
from pathlib import Path
from datetime import datetime

print("=" * 60)
print("ContentPublisher Pro - 日期文件夹功能测试")
print("=" * 60)

# 测试1: 创建日期文件夹结构
print("\n[测试1] 创建日期文件夹...")
today = datetime.now()
date_str = today.strftime('%Y-%m-%d')
date_folder = Path(f'/root/.openclaw/workspace/content-publisher/articles/{date_str}')

date_folder.mkdir(parents=True, exist_ok=True)
print(f"✓ 文件夹已创建: {date_folder}")

# 测试2: 创建测试Markdown文章
print("\n[测试2] 创建测试Markdown文章...")
md_content = f"""---
title: "{date_str} 测试文章 - 科技前沿"
platforms:
  - zhihu
  - toutiao
  - xiaohongshu
tags:
  - 科技
  - 人工智能
  - 测试
---

# {date_str} 科技前沿报道

这是今天的测试文章内容，介绍最新的人工智能技术突破。

## 主要内容

### 1. AI发展趋势

人工智能正在快速发展，主要表现在：

- **大语言模型**: GPT、Claude等模型不断突破
- **多模态能力**: 文本、图像、视频统一理解
- **应用场景**: 从聊天到编程、设计、医疗

### 2. 技术细节

```python
# AI代码示例
def ai_analysis(data):
    model = load_model('gpt-4')
    result = model.process(data)
    return result
```

### 3. 未来展望

> AI将继续改变我们的工作和生活方式。

## 表格示例

| 平台 | 特点 | 适合内容 |
|------|------|----------|
| 知乎 | 深度长文 | 技术解析 |
| 头条 | 大众化 | 热点新闻 |
| 小红书 | 图文笔记 | 生活分享 |

## 图片占位

![示例图片](./images/example.png)

---

**总结**: 这是一篇测试文章，用于验证日期文件夹功能。

<!-- 测试结束 -->
"""

md_file = date_folder / 'test-article.md'
with open(md_file, 'w', encoding='utf-8') as f:
    f.write(md_content)
print(f"✓ Markdown文件已创建: {md_file}")

# 测试3: 解析Markdown文件
print("\n[测试3] 解析Markdown文章...")
def parse_markdown_simple(file_path):
    """简单解析Markdown文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取frontmatter
    frontmatter_match = re.search(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    if frontmatter_match:
        frontmatter_text = frontmatter_match.group(1)
        body = content[frontmatter_match.end():]
        
        # 解析frontmatter
        metadata = {}
        for line in frontmatter_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                # 处理数组
                if value.startswith('['):
                    value = [v.strip().strip('"') for v in value[1:-1].split(',')]
                else:
                    value = value.strip('"')
                metadata[key] = value
        
        return metadata, body
    
    return {}, content

metadata, body = parse_markdown_simple(str(md_file))
print(f"✓ 解析成功")
print(f"  标题: {metadata.get('title', 'N/A')}")
print(f"  平台: {metadata.get('platforms', [])}")
print(f"  标签: {metadata.get('tags', [])}")
print(f"  内容长度: {len(body)} 字符")

# 测试4: 创建Word格式测试文件
print("\n[测试4] 模拟Word文档...")
print("  注: 实际Word文档需要用真实 .docx 文件")
print("  Word文档会被自动转换为Markdown并提取图片")

# 测试5: 扫描文件夹
print("\n[测试5] 扫描日期文件夹...")
def scan_folder(folder_path):
    """扫描文件夹中的所有文章"""
    folder = Path(folder_path)
    if not folder.exists():
        return []
    
    articles = []
    for ext in ['*.md', '*.docx', '*.doc']:
        for file_path in folder.glob(ext):
            articles.append({
                'name': file_path.name,
                'path': str(file_path),
                'type': 'markdown' if ext == '*.md' else 'word'
            })
    return articles

articles = scan_folder(date_folder)
if articles:
    print(f"✓ 发现 {len(articles)} 个文件:")
    for article in articles:
        print(f"  - {article['name']} ({article['type']})")
else:
    print("✗ 没有发现文章文件")

# 测试6: 创建明天的文件夹
print("\n[测试6] 创建明天的测试文件夹...")
tomorrow = datetime.now()
tomorrow = tomorrow.replace(day=tomorrow.day + 1)
tomorrow_str = tomorrow.strftime('%Y-%m-%d')
tomorrow_folder = Path(f'/root/.openclaw/workspace/content-publisher/articles/{tomorrow_str}')
tomorrow_folder.mkdir(parents=True, exist_ok=True)

# 创建明天的文章
md_content_2 = f"""---
title: "{tomorrow_str} - 明日计划"
platforms:
  - xiaohongshu
  - toutiao
tags:
  - 生活
  - 计划
---

# {tomorrow_str} 明日计划

明天的内容安排：

1. 早晨发布小红书笔记
2. 下午更新头条号文章
3. 晚上整理本周总结

## 重点内容

- 分享生活小技巧
- 记录工作心得
- 总结学习成果
"""

tomorrow_file = tomorrow_folder / 'tomorrow-plan.md'
with open(tomorrow_file, 'w', encoding='utf-8') as f:
    f.write(md_content_2)
print(f"✓ 明天文件夹已创建: {tomorrow_folder}")
print(f"✓ 明天文章已创建: {tomorrow_file}")

# 测试7: 显示目录结构
print("\n[测试7] 当前articles目录结构:")
def show_tree(path, prefix=""):
    path = Path(path)
    if not path.exists():
        print(f"路径不存在: {path}")
        return
    
    items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        print(f"{prefix}{connector}{item.name}")
        if item.is_dir():
            extension = "    " if is_last else "│   "
            show_tree(item, prefix + extension)

show_tree('/root/.openclaw/workspace/content-publisher/articles')

# 测试8: 模拟发布流程
print("\n[测试8] 模拟发布流程...")
print("  1. 扫描日期文件夹 ✓")
print("  2. 解析文章文件 ✓")
print("  3. 提取标题和内容 ✓")
print("  4. 上传到各平台... (需要登录后才能执行)")
print("  5. 记录发布结果... (需要数据库)")

print("\n" + "=" * 60)
print("测试完成！文件夹结构已准备就绪")
print("=" * 60)

print(f"""
使用方法:

  [方式1] 发布今天文件夹里的所有文章:
     python3 publisher.py publish-today

  [方式2] 发布指定日期文件夹的文章:
     python3 publisher.py publish-today -d {date_str}

  [方式3] 启动定时调度器 (每天早上8点自动发布):
     python3 publisher.py scheduler
     # 或指定日期
     python3 publisher.py scheduler -d {date_str}

  [方式4] 发布单个文件 (支持 .md 和 .docx):
     python3 publisher.py publish articles/{date_str}/test-article.md

  [方式5] 查看系统状态:
     python3 publisher.py status

  [方式6] 查看文章列表:
     python3 publisher.py list

  [方式7] 登录平台:
     python3 publisher.py login --platform zhihu

文件夹结构:
  articles/
  ├── {date_str}/           # 今天的文章
  │   └── test-article.md
  ├── {tomorrow_str}/       # 明天的文章
  │   └── tomorrow-plan.md
  └── example.md
""")
