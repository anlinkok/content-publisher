"""
数据模型定义
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from sqlmodel import SQLModel, Field, create_engine, Session, select


class ArticleStatus(str, Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class Account(SQLModel, table=True):
    """平台账号"""
    __tablename__ = "accounts"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    platform: str = Field(index=True)
    username: str
    cookies: str = Field(default="")
    is_active: bool = Field(default=True)
    last_login: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)


class Article(SQLModel, table=True):
    """文章"""
    __tablename__ = "articles"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str
    html_content: str = Field(default="")
    platforms: str  # JSON list
    status: str = Field(default=ArticleStatus.DRAFT)
    cover_image: Optional[str] = None
    tags: str = Field(default="[]")
    scheduled_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class PublishRecord(SQLModel, table=True):
    """发布记录"""
    __tablename__ = "publish_records"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    article_id: int = Field(foreign_key="articles.id")
    platform: str
    status: str
    post_id: Optional[str] = None
    post_url: Optional[str] = None
    error_message: Optional[str] = None
    published_at: Optional[datetime] = None
    retry_count: int = Field(default=0)


# 数据库引擎
engine = create_engine("sqlite:///data/publisher.db", echo=False)


def init_db():
    """初始化数据库"""
    SQLModel.metadata.create_all(engine)
