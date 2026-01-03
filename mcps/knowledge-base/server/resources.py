"""
MCP Resources Implementation for Knowledge Base Server
======================================================

This file defines the RESOURCES that our MCP server offers to AI clients.

WHAT ARE MCP RESOURCES?
-----------------------
Resources are like "files" or "data sources" that AI assistants can read.
Unlike tools (which perform actions), resources are for passive data access.

Think of resources as:
- Files in a filesystem
- Records in a database
- Content from an API

Each resource has:
1. URI         - Unique identifier (e.g., "kb://articles/art-001")
2. NAME        - Human-readable name for display
3. DESCRIPTION - What the resource contains
4. MIME TYPE   - Content type (text/plain, application/json, etc.)

RESOURCES VS TOOLS:
------------------
- RESOURCES: Read-only data access, AI can browse and read
- TOOLS: Actions that might have side effects (create, update, delete)

Use resources when:
- AI just needs to read data (no modifications)
- Data can be represented as a document/file
- You want AI to have browse/read access to content

Use tools when:
- Action might modify data
- Operation needs specific parameters
- You need to return structured operation results

RESOURCE URI SCHEME:
-------------------
We use a custom "kb://" URI scheme:
- kb://articles/{id}      → Individual article content
- kb://categories/{id}    → All articles in a category
- kb://summary            → Overview of entire knowledge base

RESOURCE LIFECYCLE:
------------------
1. Client calls resources/list → Server returns list of all resources
2. AI picks a resource to read based on name/description
3. Client calls resources/read with the URI
4. Server returns the resource content

RESOURCES IN THIS FILE:
-----------------------
- kb://articles/{id}    : Full content of each article (markdown)
- kb://categories/{id}  : JSON listing of articles in a category
- kb://summary          : Overview with stats and top articles
"""

import json

from pydantic import AnyUrl

from mcp.server import Server
from mcp.types import Resource

from server.data_store import get_store


def register_resources(server: Server) -> None:
    """
    Register resource handlers with the MCP server.

    This function:
    1. Registers a handler for resources/list (returns available resources)
    2. Registers a handler for resources/read (returns resource content)

    Args:
        server: The MCP server instance to register resources with
    """

    # =========================================================================
    # RESOURCES/LIST Handler
    # =========================================================================

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        """
        Return the list of available resources.

        This is called when a client sends "resources/list".
        We dynamically build the list based on what's in our data store.

        Returns:
            List of Resource objects, each describing an available resource
        """
        store = get_store()
        resources = []

        # ─────────────────────────────────────────────────────────────────────
        # ARTICLE RESOURCES
        # Each article in the knowledge base becomes a resource
        # ─────────────────────────────────────────────────────────────────────
        for article in store.articles.values():
            resources.append(
                Resource(
                    # URI is the unique identifier for this resource
                    # Format: kb://articles/{article_id}
                    uri=f"kb://articles/{article.id}",
                    # Human-readable name (shown in UIs)
                    name=article.title,
                    # Description helps AI understand what this resource contains
                    description=f"Article: {article.title} ({article.category})",
                    # MIME type tells client how to interpret the content
                    # text/markdown because we return formatted markdown
                    mimeType="text/markdown",
                )
            )

        # ─────────────────────────────────────────────────────────────────────
        # CATEGORY RESOURCES
        # Each category gets a resource that lists its articles
        # ─────────────────────────────────────────────────────────────────────
        for category in store.categories.values():
            resources.append(
                Resource(
                    uri=f"kb://categories/{category.id}",
                    name=f"Category: {category.name}",
                    description=f"All articles in {category.name}",
                    # application/json because we return JSON
                    mimeType="application/json",
                )
            )

        # ─────────────────────────────────────────────────────────────────────
        # SUMMARY RESOURCE
        # A special resource that gives an overview of the entire KB
        # ─────────────────────────────────────────────────────────────────────
        resources.append(
            Resource(
                uri="kb://summary",
                name="Knowledge Base Summary",
                description="Overview of the entire knowledge base with stats and categories",
                mimeType="text/markdown",
            )
        )

        return resources

    # =========================================================================
    # RESOURCES/READ Handler
    # =========================================================================

    @server.read_resource()
    async def read_resource(uri: AnyUrl) -> str:
        """
        Read and return the content of a specific resource.

        This is called when a client sends "resources/read" with a URI.
        We parse the URI to determine what content to return.

        Args:
            uri: The resource URI (e.g., "kb://articles/art-001")

        Returns:
            The resource content as a string

        Raises:
            ValueError: If the URI is unknown or resource not found
        """
        store = get_store()

        # Convert AnyUrl to string for string operations
        uri_str = str(uri)

        # ─────────────────────────────────────────────────────────────────────
        # ARTICLE RESOURCE: kb://articles/{id}
        # Returns the full article content as formatted markdown
        # ─────────────────────────────────────────────────────────────────────
        if uri_str.startswith("kb://articles/"):
            # Extract article ID from URI
            article_id = uri_str.replace("kb://articles/", "")

            # Look up the article (don't track view - this is resource read, not tool)
            article = store.get_article(article_id)
            if not article:
                raise ValueError(f"Article not found: {article_id}")

            # Format as markdown document
            content = f"# {article.title}\n\n"
            content += f"**Author:** {article.author}  \n"
            content += f"**Category:** {article.category}  \n"
            content += f"**Tags:** {', '.join(article.tags)}  \n"
            content += f"**Created:** {article.created_at.isoformat()}  \n"
            content += f"**Updated:** {article.updated_at.isoformat()}  \n"
            content += f"**Views:** {article.views}\n\n"
            content += "---\n\n"
            content += article.content

            return content

        # ─────────────────────────────────────────────────────────────────────
        # CATEGORY RESOURCE: kb://categories/{id}
        # Returns JSON with category info and list of articles
        # ─────────────────────────────────────────────────────────────────────
        if uri_str.startswith("kb://categories/"):
            category_id = uri_str.replace("kb://categories/", "")

            category = store.get_category(category_id)
            if not category:
                raise ValueError(f"Category not found: {category_id}")

            # Get all articles in this category
            articles = store.list_articles(category=category_id)

            # Return as JSON
            return json.dumps(
                {
                    "category": {
                        "id": category.id,
                        "name": category.name,
                        "description": category.description,
                    },
                    "articles": [
                        {
                            "id": a.id,
                            "title": a.title,
                            "slug": a.slug,
                            "author": a.author,
                            "views": a.views,
                        }
                        for a in articles
                    ],
                    "total": len(articles),
                },
                indent=2,
            )

        # ─────────────────────────────────────────────────────────────────────
        # SUMMARY RESOURCE: kb://summary
        # Returns an overview of the entire knowledge base
        # ─────────────────────────────────────────────────────────────────────
        if uri_str == "kb://summary":
            categories = store.list_categories()
            all_articles = store.list_articles(limit=1000)

            # Build a markdown summary
            content = "# Knowledge Base Summary\n\n"
            content += f"**Total Articles:** {len(all_articles)}  \n"
            content += f"**Total Categories:** {len(categories)}  \n"
            content += f"**Total Views:** {sum(a.views for a in all_articles)}\n\n"

            content += "## Categories\n\n"
            for cat in categories:
                # Count articles in this category
                cat_articles = [a for a in all_articles if a.category == cat.id]
                content += f"### {cat.name} ({len(cat_articles)} articles)\n"
                content += f"{cat.description}\n\n"

                # Show top 5 articles in this category
                for article in cat_articles[:5]:
                    article_url = f"kb://articles/{article.id}"
                    content += f"- [{article.title}]({article_url}) - {article.views} views\n"
                content += "\n"

            return content

        # ─────────────────────────────────────────────────────────────────────
        # UNKNOWN URI
        # ─────────────────────────────────────────────────────────────────────
        raise ValueError(f"Unknown resource URI: {uri_str}")
