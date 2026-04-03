#!/usr/bin/env python3
"""
ContentPublisher Web 控制面板
提供HTTP API和Web界面管理发布任务
"""

import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

# 导入项目模块
import sys
sys.path.insert(0, str(Path(__file__).parent))

from models import init_db, Article, Account, PublishRecord, ArticleStatus, engine
from sqlmodel import Session, select
from publisher import ArticleManager, ContentPublisher, PLATFORM_TOOLS


app = FastAPI(title="ContentPublisher API", version="2.0.0")

# 全局发布器实例
publisher_instance: Optional[ContentPublisher] = None


# ============================================================================
# Pydantic Models
# ============================================================================

class ArticleCreate(BaseModel):
    title: str
    content: str
    platforms: List[str]
    tags: Optional[List[str]] = []
    schedule: Optional[str] = None  # ISO format


class ArticleResponse(BaseModel):
    id: int
    title: str
    status: str
    platforms: List[str]
    created_at: str


class PublishRequest(BaseModel):
    article_id: int
    platforms: Optional[List[str]] = None


class PlatformStatus(BaseModel):
    platform: str
    enabled: bool
    logged_in: bool


# ============================================================================
# HTML 模板
# ============================================================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ContentPublisher Pro</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        header { 
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 30px;
            border-radius: 16px;
            margin-bottom: 30px;
            border: 1px solid #2a2a4a;
        }
        h1 { font-size: 2rem; background: linear-gradient(90deg, #00d4ff, #7b2cbf); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card {
            background: #1a1a1a;
            border-radius: 12px;
            padding: 24px;
            border: 1px solid #2a2a2a;
            transition: transform 0.2s, border-color 0.2s;
        }
        .card:hover { transform: translateY(-2px); border-color: #3a3a5a; }
        .card h3 { color: #00d4ff; margin-bottom: 16px; font-size: 1.2rem; }
        .stat { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #2a2a2a; }
        .stat:last-child { border-bottom: none; }
        .stat-value { font-weight: bold; color: #fff; }
        .platform-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; margin-top: 16px; }
        .platform-item {
            background: #252525;
            padding: 16px;
            border-radius: 8px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
        }
        .platform-item:hover { background: #303050; }
        .platform-item.active { border: 2px solid #00d4ff; }
        .platform-item.logged-in { background: #1a3a2a; }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            transition: opacity 0.2s;
        }
        .btn:hover { opacity: 0.9; }
        .btn-secondary {
            background: #2a2a4a;
            margin-left: 10px;
        }
        textarea, input {
            width: 100%;
            background: #1a1a1a;
            border: 1px solid #3a3a3a;
            color: #e0e0e0;
            padding: 12px;
            border-radius: 8px;
            margin-top: 8px;
            font-family: inherit;
        }
        textarea { min-height: 200px; resize: vertical; }
        .article-list { margin-top: 20px; }
        .article-item {
            background: #1a1a1a;
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 12px;
            border: 1px solid #2a2a2a;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 500;
        }
        .status-draft { background: #3a3a3a; }
        .status-queued { background: #4a4a00; }
        .status-published { background: #004a00; }
        .status-failed { background: #4a0000; }
        .tabs { display: flex; gap: 4px; margin-bottom: 20px; }
        .tab {
            padding: 12px 24px;
            background: #1a1a1a;
            border: none;
            color: #888;
            cursor: pointer;
            border-radius: 8px 8px 0 0;
        }
        .tab.active { background: #2a2a4a; color: #fff; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 ContentPublisher Pro</h1>
            <p style="color: #888; margin-top: 8px;">多平台内容分发管理系统</p>
        </header>

        <div class="grid">
            <div class="card">
                <h3>📊 发布统计</h3>
                <div id="stats">
                    <div class="stat"><span>总文章</span><span class="stat-value" id="total-articles">-</span></div>
                    <div class="stat"><span>已发布</span><span class="stat-value" id="published-count">-</span></div>
                    <div class="stat"><span>待发布</span><span class="stat-value" id="pending-count">-</span></div>
                    <div class="stat"><span>失败</span><span class="stat-value" id="failed-count">-</span></div>
                </div>
            </div>

            <div class="card">
                <h3>🔧 平台状态</h3>
                <div class="platform-grid" id="platform-status">
                    <!-- 动态生成 -->
                </div>
            </div>

            <div class="card">
                <h3>➕ 新建文章</h3>
                <input type="text" id="new-title" placeholder="文章标题">
                <textarea id="new-content" placeholder="文章内容 (支持Markdown)"></textarea>
                <div style="margin-top: 12px;">
                    <button class="btn" onclick="createArticle()">创建文章</button>
                </div>
            </div>
        </div>

        <div class="card" style="margin-top: 30px;">
            <div class="tabs">
                <button class="tab active" onclick="switchTab('articles')">📄 文章列表</button>
                <button class="tab" onclick="switchTab('publish')">📤 批量发布</button>
                <button class="tab" onclick="switchTab('logs')">📝 发布日志</button>
            </div>

            <div id="articles-tab" class="tab-content active">
                <div class="article-list" id="article-list"></div>
            </div>

            <div id="publish-tab" class="tab-content">
                <p style="color: #888; margin-bottom: 16px;">选择要发布的平台和文章</p>
                <div id="publish-platforms"></div>
                <button class="btn" style="margin-top: 16px;" onclick="batchPublish()">开始批量发布</button>
            </div>

            <div id="logs-tab" class="tab-content">
                <div id="publish-logs"></div>
            </div>
        </div>
    </div>

    <script>
        // 加载统计数据
        async function loadStats() {
            const res = await fetch('/api/stats');
            const data = await res.json();
            document.getElementById('total-articles').textContent = data.total;
            document.getElementById('published-count').textContent = data.published;
            document.getElementById('pending-count').textContent = data.pending;
            document.getElementById('failed-count').textContent = data.failed;
        }

        // 加载平台状态
        async function loadPlatforms() {
            const res = await fetch('/api/platforms');
            const platforms = await res.json();
            const container = document.getElementById('platform-status');
            container.innerHTML = platforms.map(p => `
                <div class="platform-item ${p.logged_in ? 'logged-in' : ''}" onclick="loginPlatform('${p.platform}')">
                    <div style="font-size: 1.5rem;">${getPlatformIcon(p.platform)}</div>
                    <div style="margin-top: 8px; font-size: 0.9rem;">${p.platform}</div>
                    <div style="font-size: 0.75rem; color: ${p.logged_in ? '#0f0' : '#888'}; margin-top: 4px;">
                        ${p.logged_in ? '已登录' : '未登录'}
                    </div>
                </div>
            `).join('');
        }

        function getPlatformIcon(platform) {
            const icons = {
                'zhihu': '🔵',
                'toutiao': '🔴',
                'xiaohongshu': '🔴',
                'baijiahao': '🔵',
                'wangyi': '🔴',
                'qiehao': '🟢'
            };
            return icons[platform] || '📱';
        }

        // 加载文章列表
        async function loadArticles() {
            const res = await fetch('/api/articles');
            const articles = await res.json();
            const container = document.getElementById('article-list');
            container.innerHTML = articles.map(a => `
                <div class="article-item">
                    <div>
                        <div style="font-weight: bold;">${a.title}</div>
                        <div style="font-size: 0.85rem; color: #888; margin-top: 4px;">
                            ${a.platforms.join(', ')} | ${new Date(a.created_at).toLocaleString()}
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span class="status-badge status-${a.status}">${a.status}</span>
                        <button class="btn btn-secondary" onclick="publishArticle(${a.id})">发布</button>
                    </div>
                </div>
            `).join('');
        }

        // 创建文章
        async function createArticle() {
            const title = document.getElementById('new-title').value;
            const content = document.getElementById('new-content').value;
            if (!title || !content) return alert('请填写标题和内容');

            await fetch('/api/articles', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title, content, platforms: ['zhihu', 'toutiao']})
            });

            document.getElementById('new-title').value = '';
            document.getElementById('new-content').value = '';
            loadArticles();
            loadStats();
        }

        // 发布文章
        async function publishArticle(id) {
            await fetch(`/api/articles/${id}/publish`, {method: 'POST'});
            alert('发布任务已提交');
            loadArticles();
        }

        // 登录平台
        async function loginPlatform(platform) {
            alert(`请在服务器终端执行: python3 publisher.py login --platform ${platform}`);
        }

        // 切换标签
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(`${tab}-tab`).classList.add('active');
        }

        // 初始化
        loadStats();
        loadPlatforms();
        loadArticles();
        setInterval(loadStats, 30000); // 每30秒刷新
    </script>
</body>
</html>
'''


# ============================================================================
# API Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Web界面"""
    return HTMLResponse(content=HTML_TEMPLATE)


@app.get("/api/stats")
async def get_stats():
    """获取统计数据"""
    with Session(engine) as session:
        total = len(session.exec(select(Article)).all())
        published = len(session.exec(select(Article).where(Article.status == ArticleStatus.PUBLISHED)).all())
        pending = len(session.exec(select(Article).where(Article.status == ArticleStatus.QUEUED)).all())
        failed = len(session.exec(select(Article).where(Article.status == ArticleStatus.FAILED)).all())
    
    return {
        "total": total,
        "published": published,
        "pending": pending,
        "failed": failed
    }


@app.get("/api/platforms")
async def get_platforms():
    """获取平台状态"""
    with Session(engine) as session:
        platforms = []
        for name in PLATFORM_TOOLS.keys():
            account = session.exec(select(Account).where(Account.platform == name)).first()
            platforms.append({
                "platform": name,
                "enabled": True,
                "logged_in": account is not None and bool(account.cookies)
            })
    return platforms


@app.get("/api/articles", response_model=List[ArticleResponse])
async def list_articles():
    """列出所有文章"""
    articles = ArticleManager.list_articles()
    return [
        {
            "id": a.id,
            "title": a.title,
            "status": a.status,
            "platforms": json.loads(a.platforms),
            "created_at": a.created_at.isoformat()
        }
        for a in articles
    ]


@app.post("/api/articles")
async def create_article(article: ArticleCreate):
    """创建文章"""
    from models import Article
    
    new_article = Article(
        title=article.title,
        content=article.content,
        html_content=article.content,  # 简化处理
        platforms=json.dumps(article.platforms),
        tags=json.dumps(article.tags or []),
        scheduled_at=datetime.fromisoformat(article.schedule) if article.schedule else None,
        status=ArticleStatus.SCHEDULED if article.schedule else ArticleStatus.QUEUED
    )
    
    article_id = ArticleManager.save_article(new_article)
    return {"id": article_id, "message": "文章创建成功"}


@app.post("/api/articles/{article_id}/publish")
async def publish_article(article_id: int, background_tasks: BackgroundTasks):
    """发布文章"""
    with Session(engine) as session:
        article = session.get(Article, article_id)
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
    
    async def do_publish():
        publisher = ContentPublisher()
        try:
            await publisher.publish_article(article)
        finally:
            await publisher.close_all()
    
    background_tasks.add_task(do_publish)
    return {"message": "发布任务已启动"}


@app.post("/api/platforms/{platform}/login")
async def platform_login(platform: str):
    """触发平台登录（返回指引）"""
    if platform not in PLATFORM_TOOLS:
        raise HTTPException(status_code=404, detail="未知平台")
    
    return {
        "message": f"请在服务器终端执行: python3 publisher.py login --platform {platform}",
        "command": f"python3 publisher.py login --platform {platform}"
    }


# ============================================================================
# Main Entry
# ============================================================================

if __name__ == "__main__":
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8080)
