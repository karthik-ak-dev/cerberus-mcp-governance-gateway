"""
Shared Type Definitions for Knowledge Base MCP
==============================================

This file contains the data models (schemas) used throughout the application.
We use Pydantic for data validation and serialization.

WHY PYDANTIC?
-------------
Pydantic is a data validation library that:
- Validates data types automatically
- Converts data between formats (JSON ↔ Python objects)
- Provides helpful error messages when validation fails
- Works great with FastAPI and MCP SDK

MODELS IN THIS FILE:
-------------------
- Category     : Knowledge base category (e.g., "Python", "AI")
- Article      : A knowledge base article
- SearchResult : Result item from a search query
- ArticleCreate: Schema for creating new articles (request body)
- ArticleUpdate: Schema for updating articles (partial updates)

MODEL INHERITANCE:
-----------------
All models inherit from BaseModel (Pydantic's base class).
This gives them:
- Automatic __init__ from field definitions
- .model_dump() to convert to dictionary
- .model_validate() to create from dictionary
- JSON serialization support
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Category(BaseModel):
    """
    Represents a knowledge base category.

    Categories help organize articles into logical groups.
    Examples: "Python", "AI/ML", "Databases", "Security"

    Attributes:
        id: Unique identifier (e.g., "python", "ai", "database")
        name: Human-readable name (e.g., "Python Programming")
        description: Brief description of what this category covers
    """

    id: str
    name: str
    description: str


class Article(BaseModel):
    """
    Represents a knowledge base article.

    This is the main content type in our knowledge base.
    Articles contain educational or reference content on various topics.

    Attributes:
        id: Unique identifier (auto-generated, e.g., "a1b2c3d4")
        title: Article title (displayed to users)
        slug: URL-friendly version of title (e.g., "python-basics")
        category: Category ID this article belongs to
        tags: List of tags for additional categorization
        content: The actual article content (markdown supported)
        author: Name of the author
        created_at: When the article was created
        updated_at: When the article was last modified
        views: Number of times the article has been viewed

    Example:
        Article(
            id="art-001",
            title="Python Basics",
            slug="python-basics",
            category="python",
            tags=["python", "beginner", "tutorial"],
            content="# Introduction\\n\\nPython is...",
            author="Jane Doe",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            views=42
        )
    """

    id: str
    title: str
    slug: str
    category: str
    tags: list[str] = Field(default_factory=list)
    content: str
    author: str
    created_at: datetime
    updated_at: datetime
    views: int = 0


class SearchResult(BaseModel):
    """
    Represents a single result from a search query.

    When users search the knowledge base, we return a list of these.
    It includes enough information to display in search results
    without loading the full article content.

    Attributes:
        article_id: ID of the matching article
        title: Article title (for display)
        slug: URL slug (for linking)
        category: Category ID (for filtering/display)
        snippet: Excerpt showing where the match was found
        relevance_score: How well this matches the query (higher = better)

    Example:
        SearchResult(
            article_id="art-001",
            title="Python Basics",
            slug="python-basics",
            category="python",
            snippet="...learning Python is easy because...",
            relevance_score=15.0
        )
    """

    article_id: str
    title: str
    slug: str
    category: str
    snippet: str
    relevance_score: float


class ArticleCreate(BaseModel):
    """
    Schema for creating a new article.

    This is what clients send when they want to create an article.
    We don't include id, slug, created_at, etc. because the server
    generates those automatically.

    Attributes:
        title: Article title (required)
        category: Category ID (required, must exist)
        tags: Optional list of tags
        content: Article content (required)
        author: Author name (required)
    """

    title: str
    category: str
    tags: list[str] = Field(default_factory=list)
    content: str
    author: str


class ArticleUpdate(BaseModel):
    """
    Schema for updating an existing article.

    All fields are optional - only provided fields will be updated.
    This is called a "partial update" pattern.

    Attributes:
        title: New title (optional)
        category: New category (optional)
        tags: New tags (optional, replaces existing)
        content: New content (optional)

    Example:
        # Update just the title
        ArticleUpdate(title="New Title")

        # Update title and content
        ArticleUpdate(title="New Title", content="New content...")
    """

    title: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    content: Optional[str] = None
