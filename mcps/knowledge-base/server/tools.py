"""
MCP Tools Implementation for Knowledge Base Server
==================================================

This file defines the TOOLS that our MCP server offers to AI clients.

WHAT ARE MCP TOOLS?
-------------------
Tools are like "functions" that AI assistants can call. They allow the AI to:
- Perform actions (create, update, delete)
- Retrieve data (search, get, list)
- Interact with external systems

Each tool has:
1. NAME        - Unique identifier (e.g., "search_articles")
2. DESCRIPTION - What the tool does (AI reads this to decide when to use it)
3. INPUT SCHEMA - JSON Schema defining what arguments the tool accepts
4. HANDLER     - The actual function that runs when the tool is called

TOOL LIFECYCLE:
--------------
1. Client calls tools/list → Server returns list of all tools with schemas
2. AI looks at descriptions and decides which tool to use
3. Client calls tools/call with tool name and arguments
4. Server validates arguments against schema
5. Server runs the tool handler
6. Server returns result as content (text, images, etc.)

EXAMPLE FLOW:
-------------
    AI: "I need to find articles about Python"

    Client → Server: tools/call
    {
        "name": "search_articles",
        "arguments": {"query": "Python", "limit": 5}
    }

    Server processes, returns:
    {
        "content": [
            {"type": "text", "text": "Found 5 articles:\n1. Python Basics..."}
        ]
    }

    AI reads the result and presents it to the user.

TOOLS IN THIS FILE:
-------------------
- search_articles : Search the knowledge base
- get_article     : Get full content of one article
- list_articles   : List articles (with optional filters)
- create_article  : Create a new article
- update_article  : Update an existing article
- delete_article  : Delete an article
- list_categories : List all categories
"""

from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

from server.data_store import get_store


def register_tools(server: Server) -> None:
    """
    Register all tool handlers with the MCP server.

    This function is called once when the server starts. It:
    1. Registers a handler for tools/list (returns available tools)
    2. Registers a handler for tools/call (executes a tool)

    The @server.list_tools() and @server.call_tool() decorators
    tell the MCP SDK which functions handle which requests.

    Args:
        server: The MCP server instance to register tools with
    """

    # =========================================================================
    # TOOLS/LIST Handler
    # =========================================================================
    # This handler is called when a client sends "tools/list"
    # It returns a list of all available tools and their schemas

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """
        Return the list of available tools.

        Each Tool object contains:
        - name: Unique identifier for the tool
        - description: Human-readable description (AI uses this to decide when to use the tool)
        - inputSchema: JSON Schema defining the expected arguments

        The description is CRITICAL - it's what the AI reads to understand
        when and how to use the tool. Write clear, specific descriptions!
        """
        return [
            # -----------------------------------------------------------------
            # SEARCH_ARTICLES Tool
            # Most commonly used - allows AI to search the knowledge base
            # -----------------------------------------------------------------
            Tool(
                name="search_articles",
                description="Search the knowledge base for articles matching a query. "
                "Returns matching articles with relevance scores and snippets. "
                "Use this when the user wants to find information on a topic.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query - keywords or natural language",
                        },
                        "category": {
                            "type": "string",
                            "description": "Filter by category (python, ai, database, security)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],  # Only query is required
                },
            ),
            # -----------------------------------------------------------------
            # GET_ARTICLE Tool
            # Get the full content of a specific article
            # -----------------------------------------------------------------
            Tool(
                name="get_article",
                description="Get the full content of a specific article by its ID or slug. "
                "Use this when you need to read the complete article content, "
                "not just a search snippet.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "article_id": {
                            "type": "string",
                            "description": "The unique article ID (e.g., 'art-001')",
                        },
                        "slug": {
                            "type": "string",
                            "description": "The article's URL slug (e.g., 'python-basics')",
                        },
                    },
                    # Neither is strictly required - but one should be provided
                },
            ),
            # -----------------------------------------------------------------
            # LIST_ARTICLES Tool
            # Browse articles with filtering and pagination
            # -----------------------------------------------------------------
            Tool(
                name="list_articles",
                description="List articles in the knowledge base with optional filtering. "
                "Use this to browse what's available or see articles in a category.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Optional: Filter by category ID",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum articles to return (default: 20)",
                            "default": 20,
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Skip this many articles for pagination (default: 0)",
                            "default": 0,
                        },
                    },
                },
            ),
            # -----------------------------------------------------------------
            # CREATE_ARTICLE Tool
            # Create a new article in the knowledge base
            # -----------------------------------------------------------------
            Tool(
                name="create_article",
                description="Create a new article in the knowledge base. "
                "Use this when the user wants to add new content.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Article title",
                        },
                        "category": {
                            "type": "string",
                            "description": "Category ID (python, ai, database, security)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Article content (markdown supported)",
                        },
                        "author": {
                            "type": "string",
                            "description": "Author name",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional: Tags for the article",
                        },
                    },
                    "required": ["title", "category", "content", "author"],
                },
            ),
            # -----------------------------------------------------------------
            # UPDATE_ARTICLE Tool
            # Modify an existing article
            # -----------------------------------------------------------------
            Tool(
                name="update_article",
                description="Update an existing article. Only provided fields will be changed.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "article_id": {
                            "type": "string",
                            "description": "ID of the article to update",
                        },
                        "title": {
                            "type": "string",
                            "description": "New title (optional)",
                        },
                        "category": {
                            "type": "string",
                            "description": "New category (optional)",
                        },
                        "content": {
                            "type": "string",
                            "description": "New content (optional)",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "New tags (optional)",
                        },
                    },
                    "required": ["article_id"],
                },
            ),
            # -----------------------------------------------------------------
            # DELETE_ARTICLE Tool
            # Remove an article from the knowledge base
            # -----------------------------------------------------------------
            Tool(
                name="delete_article",
                description="Delete an article from the knowledge base. This cannot be undone.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "article_id": {
                            "type": "string",
                            "description": "ID of the article to delete",
                        },
                    },
                    "required": ["article_id"],
                },
            ),
            # -----------------------------------------------------------------
            # LIST_CATEGORIES Tool
            # Show all available categories
            # -----------------------------------------------------------------
            Tool(
                name="list_categories",
                description="List all available categories in the knowledge base.",
                inputSchema={
                    "type": "object",
                    "properties": {},  # No arguments needed
                },
            ),
        ]

    # =========================================================================
    # TOOLS/CALL Handler
    # =========================================================================
    # This handler is called when a client sends "tools/call"
    # It routes to the appropriate tool implementation based on the name

    # Tool handler functions to keep call_tool clean
    def _handle_search(store, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle search_articles tool."""
        results = store.search_articles(
            query=arguments["query"],
            category=arguments.get("category"),
            limit=arguments.get("limit", 10),
        )
        if not results:
            return [TextContent(type="text", text="No articles found matching your query.")]

        output = f"Found {len(results)} article(s):\n\n"
        for result in results:
            output += f"**{result.title}** (ID: {result.article_id})\n"
            output += f"  Category: {result.category} | Score: {result.relevance_score:.1f}\n"
            output += f"  {result.snippet}\n\n"
        return [TextContent(type="text", text=output)]

    def _handle_get_article(store, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle get_article tool."""
        article = None
        if arguments.get("article_id"):
            article = store.get_article(arguments["article_id"], track_view=True)
        elif arguments.get("slug"):
            article = store.get_article_by_slug(arguments["slug"], track_view=True)

        if not article:
            return [TextContent(type="text", text="Article not found.")]

        output = f"# {article.title}\n\n"
        output += f"**Author:** {article.author}\n"
        output += f"**Category:** {article.category}\n"
        output += f"**Tags:** {', '.join(article.tags)}\n"
        output += f"**Views:** {article.views}\n"
        output += f"**Last Updated:** {article.updated_at.isoformat()}\n\n"
        output += "---\n\n"
        output += article.content
        return [TextContent(type="text", text=output)]

    def _handle_list_articles(store, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle list_articles tool."""
        articles = store.list_articles(
            category=arguments.get("category"),
            limit=arguments.get("limit", 20),
            offset=arguments.get("offset", 0),
        )
        if not articles:
            return [TextContent(type="text", text="No articles found.")]

        output = f"Listing {len(articles)} article(s):\n\n"
        for article in articles:
            output += f"- **{article.title}** (ID: {article.id})\n"
            output += f"  Category: {article.category} | Views: {article.views}\n"
        return [TextContent(type="text", text=output)]

    def _handle_create_article(store, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle create_article tool."""
        article = store.create_article(
            title=arguments["title"],
            category=arguments["category"],
            content=arguments["content"],
            author=arguments["author"],
            tags=arguments.get("tags"),
        )
        return [
            TextContent(
                type="text",
                text=f"Article created successfully!\n\n"
                f"ID: {article.id}\nSlug: {article.slug}\nTitle: {article.title}",
            )
        ]

    def _handle_update_article(store, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle update_article tool."""
        article = store.update_article(
            article_id=arguments["article_id"],
            title=arguments.get("title"),
            category=arguments.get("category"),
            content=arguments.get("content"),
            tags=arguments.get("tags"),
        )
        if not article:
            return [TextContent(type="text", text="Article not found.")]
        return [
            TextContent(
                type="text",
                text=f"Article updated successfully!\n\nID: {article.id}\nTitle: {article.title}",
            )
        ]

    def _handle_delete_article(store, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle delete_article tool."""
        success = store.delete_article(arguments["article_id"])
        if success:
            return [TextContent(type="text", text="Article deleted successfully.")]
        return [TextContent(type="text", text="Article not found.")]

    def _handle_list_categories(store, _arguments: dict[str, Any]) -> list[TextContent]:
        """Handle list_categories tool."""
        categories = store.list_categories()
        output = "Available categories:\n\n"
        for category in categories:
            output += f"- **{category.name}** (`{category.id}`): {category.description}\n"
        return [TextContent(type="text", text=output)]

    # Tool dispatch table
    tool_handlers = {
        "search_articles": _handle_search,
        "get_article": _handle_get_article,
        "list_articles": _handle_list_articles,
        "create_article": _handle_create_article,
        "update_article": _handle_update_article,
        "delete_article": _handle_delete_article,
        "list_categories": _handle_list_categories,
    }

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """
        Execute a tool and return the result.

        This function routes to the appropriate handler based on the tool name.

        Args:
            name: The name of the tool to execute (e.g., "search_articles")
            arguments: Dictionary of arguments passed by the client

        Returns:
            List of TextContent objects containing the result.
        """
        store = get_store()
        handler = tool_handlers.get(name)
        if handler:
            return handler(store, arguments)
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
