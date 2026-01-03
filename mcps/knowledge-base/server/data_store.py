"""
Knowledge Base Data Store
=========================

This file manages the actual data for our Knowledge Base MCP server.
Think of it as a simple "database" layer that stores and retrieves articles.

WHAT IS THIS FILE?
------------------
This is the data layer - it handles:
- Loading articles from a JSON file
- Searching articles by query
- CRUD operations (Create, Read, Update, Delete)
- Persisting changes back to JSON

In a real application, this would connect to a database (PostgreSQL, MongoDB, etc.).
We use a JSON file here for simplicity and to keep the example self-contained.

DATA STRUCTURE:
--------------
The JSON file (data/articles.json) contains:
{
    "articles": [
        {
            "id": "art-001",
            "title": "Python Basics",
            "slug": "python-basics",
            "category": "python",
            "tags": ["python", "beginner"],
            "content": "...",
            "author": "Jane Doe",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "views": 0
        },
        ...
    ],
    "categories": [
        {"id": "python", "name": "Python", "description": "..."},
        ...
    ]
}

SINGLETON PATTERN:
-----------------
We use a singleton pattern (get_store() function) so all parts of the server
share the same data store instance. This ensures:
- Data consistency across requests
- Single source of truth
- Efficient memory usage

SEARCH ALGORITHM:
----------------
The search is simple text matching with relevance scoring:
- Title match: 10 points
- Tag match: 5 points each
- Content match: 2 points per occurrence (max 8)

In production, you'd use something like Elasticsearch for better search.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from shared.types import Article, Category, SearchResult


class KnowledgeBaseStore:
    """
    In-memory data store backed by a JSON file.

    This class provides all data access methods for the Knowledge Base.
    It loads data from JSON on startup and saves changes back to JSON.

    Attributes:
        data_path: Path to the JSON file
        articles: Dictionary of article_id -> Article
        categories: Dictionary of category_id -> Category
    """

    def __init__(self, data_path: Optional[Path] = None):
        """
        Initialize the store and load data from JSON.

        Args:
            data_path: Path to JSON file. Defaults to data/articles.json
        """
        # Default to data/articles.json relative to this file
        if data_path is None:
            data_path = Path(__file__).parent.parent / "data" / "articles.json"

        self.data_path = data_path

        # In-memory storage (dictionaries for O(1) lookup by ID)
        self.articles: dict[str, Article] = {}
        self.categories: dict[str, Category] = {}

        # Load initial data from JSON file
        self._load_data()

    # =========================================================================
    # DATA PERSISTENCE
    # =========================================================================

    def _load_data(self) -> None:
        """
        Load data from the JSON file into memory.

        Called once during initialization. Parses the JSON and creates
        Article and Category objects from the raw data.
        """
        if not self.data_path.exists():
            # No data file yet - start with empty store
            return

        with open(self.data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Load articles
        for article_data in data.get("articles", []):
            # Pydantic model handles parsing and validation
            article = Article(**article_data)
            self.articles[article.id] = article

        # Load categories
        for category_data in data.get("categories", []):
            category = Category(**category_data)
            self.categories[category.id] = category

    def _save_data(self) -> None:
        """
        Persist current state back to the JSON file.

        Called after any modification (create, update, delete).
        Converts all objects back to JSON and writes to disk.
        """
        data = {
            # Convert Pydantic models to dicts, then to JSON
            # mode="json" ensures datetime objects are serialized properly
            "articles": [a.model_dump(mode="json") for a in self.articles.values()],
            "categories": [c.model_dump() for c in self.categories.values()],
        }

        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    # =========================================================================
    # SEARCH
    # =========================================================================

    def search_articles(  # pylint: disable=too-many-locals
        self, query: str, category: Optional[str] = None, limit: int = 10
    ) -> list[SearchResult]:
        """
        Search articles by query string.

        This is a simple text-matching search with relevance scoring.
        In production, you'd use Elasticsearch or similar for better results.

        SCORING ALGORITHM:
        - Title match: 10 points (title is most important)
        - Tag match: 5 points per matching tag
        - Content match: 2 points per occurrence (capped at 8)

        Args:
            query: Search query (keywords or phrase)
            category: Optional category filter
            limit: Maximum results to return

        Returns:
            List of SearchResult objects, sorted by relevance
        """
        query_lower = query.lower()
        results: list[tuple[float, Article]] = []  # (score, article) pairs

        for article in self.articles.values():
            # Skip if category filter doesn't match
            if category and article.category != category:
                continue

            # Calculate relevance score
            score = 0.0

            # Title match (highest weight - most important signal)
            if query_lower in article.title.lower():
                score += 10.0

            # Tag match (tags are explicit categorization)
            for tag in article.tags:
                if query_lower in tag.lower():
                    score += 5.0

            # Content match (less weight, but count occurrences)
            content_lower = article.content.lower()
            if query_lower in content_lower:
                count = content_lower.count(query_lower)
                score += min(count * 2.0, 8.0)  # Cap at 8 to prevent spam

            # Only include if we found something relevant
            if score > 0:
                results.append((score, article))

        # Sort by score (highest first)
        results.sort(key=lambda x: x[0], reverse=True)

        # Convert to SearchResult objects
        search_results = []
        for score, article in results[:limit]:
            # Extract a snippet around the first match
            content_lower = article.content.lower()
            idx = content_lower.find(query_lower)

            if idx >= 0:
                # Found query in content - extract surrounding text
                start = max(0, idx - 50)
                end = min(len(article.content), idx + 100)
                snippet = article.content[start:end]

                # Add ellipsis if truncated
                if start > 0:
                    snippet = "..." + snippet
                if end < len(article.content):
                    snippet = snippet + "..."
            else:
                # Query not in content - use beginning of article
                snippet = article.content[:150] + "..."

            search_results.append(
                SearchResult(
                    article_id=article.id,
                    title=article.title,
                    slug=article.slug,
                    category=article.category,
                    snippet=snippet,
                    relevance_score=score,
                )
            )

        return search_results

    # =========================================================================
    # ARTICLE CRUD
    # =========================================================================

    def get_article(
        self, article_id: str, track_view: bool = False
    ) -> Optional[Article]:
        """
        Get an article by its ID.

        Args:
            article_id: The article's unique identifier
            track_view: If True, increment the view counter
                        (only True when user explicitly requests article)

        Returns:
            The Article object, or None if not found
        """
        article = self.articles.get(article_id)
        if article and track_view:
            article.views += 1
        return article

    def get_article_by_slug(
        self, slug: str, track_view: bool = False
    ) -> Optional[Article]:
        """
        Get an article by its URL slug.

        Slugs are URL-friendly versions of titles (e.g., "python-basics").

        Args:
            slug: The article's URL slug
            track_view: If True, increment the view counter

        Returns:
            The Article object, or None if not found
        """
        for article in self.articles.values():
            if article.slug == slug:
                if track_view:
                    article.views += 1
                return article
        return None

    def create_article(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        title: str,
        category: str,
        content: str,
        author: str,
        tags: Optional[list[str]] = None,
    ) -> Article:
        """
        Create a new article.

        Automatically generates:
        - Unique ID (8-char UUID prefix)
        - URL slug from title
        - Created/updated timestamps

        Args:
            title: Article title
            category: Category ID (must exist)
            content: Article content (markdown supported)
            author: Author name
            tags: Optional list of tags

        Returns:
            The created Article object
        """
        # Generate unique ID (first 8 chars of UUID for readability)
        article_id = str(uuid.uuid4())[:8]

        # Generate URL slug from title
        # "Python Basics" -> "python-basics"
        slug = title.lower().replace(" ", "-").replace("/", "-")[:50]

        now = datetime.now(timezone.utc)

        article = Article(
            id=article_id,
            title=title,
            slug=slug,
            category=category,
            tags=tags or [],
            content=content,
            author=author,
            created_at=now,
            updated_at=now,
            views=0,
        )

        # Add to store and persist
        self.articles[article_id] = article
        self._save_data()

        return article

    def update_article(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        article_id: str,
        title: Optional[str] = None,
        category: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> Optional[Article]:
        """
        Update an existing article.

        Only provided fields are updated (partial update pattern).

        Args:
            article_id: ID of article to update
            title: New title (optional)
            category: New category (optional)
            content: New content (optional)
            tags: New tags (optional)

        Returns:
            Updated Article, or None if not found
        """
        article = self.articles.get(article_id)
        if not article:
            return None

        # Update only provided fields
        if title is not None:
            article.title = title
            # Regenerate slug when title changes
            article.slug = title.lower().replace(" ", "-").replace("/", "-")[:50]

        if category is not None:
            article.category = category

        if content is not None:
            article.content = content

        if tags is not None:
            article.tags = tags

        # Update timestamp
        article.updated_at = datetime.now(timezone.utc)

        # Persist changes
        self._save_data()

        return article

    def delete_article(self, article_id: str) -> bool:
        """
        Delete an article from the store.

        Args:
            article_id: ID of article to delete

        Returns:
            True if deleted, False if not found
        """
        if article_id in self.articles:
            del self.articles[article_id]
            self._save_data()
            return True
        return False

    def list_articles(
        self, category: Optional[str] = None, limit: int = 20, offset: int = 0
    ) -> list[Article]:
        """
        List articles with optional filtering and pagination.

        Args:
            category: Optional category filter
            limit: Maximum articles to return
            offset: Skip this many articles (for pagination)

        Returns:
            List of Article objects, sorted by updated_at descending
        """
        articles = list(self.articles.values())

        # Filter by category if specified
        if category:
            articles = [a for a in articles if a.category == category]

        # Sort by most recently updated first
        articles.sort(key=lambda a: a.updated_at, reverse=True)

        # Apply pagination
        return articles[offset : offset + limit]

    # =========================================================================
    # CATEGORY OPERATIONS
    # =========================================================================

    def list_categories(self) -> list[Category]:
        """
        List all available categories.

        Returns:
            List of Category objects
        """
        return list(self.categories.values())

    def get_category(self, category_id: str) -> Optional[Category]:
        """
        Get a category by its ID.

        Args:
            category_id: The category's unique identifier

        Returns:
            The Category object, or None if not found
        """
        return self.categories.get(category_id)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================
# We use a module-level singleton so all parts of the server share the same
# data store instance. This ensures data consistency.

_STORE: Optional[KnowledgeBaseStore] = None


def get_store() -> KnowledgeBaseStore:
    """
    Get or create the singleton store instance.

    This is the main entry point for accessing the data store.
    All server code should use this function instead of creating
    KnowledgeBaseStore instances directly.

    Returns:
        The shared KnowledgeBaseStore instance
    """
    global _STORE  # pylint: disable=global-statement
    if _STORE is None:
        _STORE = KnowledgeBaseStore()
    return _STORE
