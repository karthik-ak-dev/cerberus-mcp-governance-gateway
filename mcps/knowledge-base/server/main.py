"""
Knowledge Base MCP Server - Main Entry Point
=============================================

This file is the entry point for the MCP (Model Context Protocol) server.
Think of the MCP server as a "backend" that AI assistants can connect to
and use to perform actions or retrieve information.

WHAT IS MCP?
------------
MCP (Model Context Protocol) is a standard way for AI assistants (like Claude)
to interact with external tools, data sources, and services. It defines:

1. TOOLS     - Actions the AI can perform (like functions it can call)
2. RESOURCES - Data the AI can read (like files or database records)
3. PROMPTS   - Pre-made templates that help the AI with specific tasks
4. SAMPLING  - Way for the server to ask the AI to generate text

TRANSPORT TYPES:
---------------
MCP supports two ways for clients to connect:

1. STDIO (Standard I/O):
   - Communication happens through stdin/stdout
   - Used when the server runs as a child process
   - Example: Claude Desktop spawns this server and talks to it via pipes

2. HTTP:
   - Communication happens over HTTP requests
   - Server runs independently on a port
   - Client sends JSON-RPC requests to /message endpoint
   - Great for debugging and testing

HOW THIS FILE IS ORGANIZED:
--------------------------
1. Import required libraries
2. create_server() - Creates and configures the MCP server
3. run_stdio_server() - Runs server with STDIO transport
4. run_http_server() - Runs server with HTTP transport
5. main() - CLI entry point (choose transport via --transport flag)

RUNNING THE SERVER:
------------------
    # STDIO mode (for production with Claude Desktop):
    python -m server.main --transport stdio

    # HTTP mode (for development/testing):
    python -m server.main --transport http --port 8080

    # Then connect with client:
    python -m client.main --server-url http://localhost:8080
"""
# pylint: disable=too-many-statements

import asyncio
import json
import logging
import sys
from pathlib import Path

import click
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

# ─────────────────────────────────────────────────────────────────────────────
# MCP SDK Imports
# These are the core building blocks from the official MCP Python SDK
# ─────────────────────────────────────────────────────────────────────────────
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ─────────────────────────────────────────────────────────────────────────────
# Local Imports - Our capability implementations
# Each file registers handlers for a specific MCP capability
# ─────────────────────────────────────────────────────────────────────────────

# Add parent to path so Python can find our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# pylint: disable=wrong-import-position
from server.tools import register_tools  # Registers tool handlers
from server.resources import register_resources  # Registers resource handlers
from server.prompts import register_prompts  # Registers prompt handlers
# pylint: enable=wrong-import-position

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mcp.http")


# =============================================================================
# SERVER CREATION
# =============================================================================


def create_server() -> Server:
    """
    Create and configure the MCP server instance.

    This function:
    1. Creates a new MCP Server with a name identifier
    2. Registers all our capability handlers (tools, resources, prompts)

    The server name ("knowledge-base") is sent to clients during initialization
    so they know what server they're connected to.

    Returns:
        Server: Configured MCP server ready to handle requests
    """
    # Create the server with an identifier name
    # This name is sent to clients in the serverInfo during handshake
    server = Server("knowledge-base")

    # Register all our capabilities
    # Each function adds handlers to the server for different MCP features
    register_tools(server)  # Add tools like search_articles, get_article
    register_resources(server)  # Add resources like kb://articles/{id}
    register_prompts(server)  # Add prompts like summarize_article

    return server


# =============================================================================
# STDIO TRANSPORT
# =============================================================================


async def run_stdio_server() -> None:
    """
    Run the MCP server using STDIO (Standard Input/Output) transport.

    STDIO TRANSPORT EXPLAINED:
    -------------------------
    When using STDIO, the server communicates through stdin and stdout.
    This is how Claude Desktop and other MCP hosts typically run servers:

    1. The host (Claude Desktop) spawns this server as a child process
    2. The host sends JSON-RPC messages to the server's stdin
    3. The server sends responses back through stdout
    4. stderr is used for logging (won't interfere with protocol)

    This is the most common production transport because:
    - No network ports to manage
    - Automatic process lifecycle management
    - Secure (no network exposure)

    FLOW:
    -----
    Host (Claude)              Server (this code)
         |                           |
         |-- spawn process --------->|
         |                           |
         |-- initialize (stdin) ---->|
         |<-- capabilities (stdout)--|
         |                           |
         |-- tools/list (stdin) ---->|
         |<-- tool list (stdout) ----|
         |                           |
         |-- tools/call (stdin) ---->|
         |<-- result (stdout) -------|
    """
    server = create_server()

    # stdio_server() is an async context manager that:
    # - Sets up stdin/stdout streams
    # - Handles proper encoding (UTF-8)
    # - Manages stream lifecycle
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,  # Server reads client requests from here
            write_stream,  # Server writes responses here
            server.create_initialization_options(),  # Default capabilities
        )


# =============================================================================
# HTTP TRANSPORT
# =============================================================================


async def run_http_server(host: str, port: int) -> None:
    """
    Run the MCP server using HTTP transport.

    HTTP TRANSPORT EXPLAINED:
    ------------------------
    Instead of stdin/stdout, communication happens over HTTP:

    - Client sends POST requests to /message with JSON-RPC body
    - Server responds with JSON-RPC response
    - Optional: SSE endpoint (/sse) for server-to-client push messages

    This transport is great for:
    - Development and debugging (can use tools like curl/Postman)
    - Remote servers (not on same machine as client)
    - Testing (can run server independently)

    JSON-RPC FORMAT:
    ---------------
    Request:
        {
            "jsonrpc": "2.0",
            "id": 1,                    # Unique request ID
            "method": "tools/list",     # MCP method to call
            "params": {}                # Method parameters
        }

    Response:
        {
            "jsonrpc": "2.0",
            "id": 1,                    # Matches request ID
            "result": { ... }           # Method result
        }

    ENDPOINTS:
    ----------
    POST /message  - Handle JSON-RPC requests from client
    GET  /sse      - Server-Sent Events for push messages (optional)
    GET  /health   - Health check endpoint

    Args:
        host: Host to bind to (0.0.0.0 for all interfaces)
        port: Port number to listen on
    """
    server = create_server()

    # Store active SSE sessions (for server-to-client push messages)
    sessions: dict[str, asyncio.Queue] = {}

    # -------------------------------------------------------------------------
    # SSE Endpoint Handler
    # -------------------------------------------------------------------------
    async def handle_sse(request):
        """
        Handle Server-Sent Events (SSE) connection.

        SSE allows the server to push messages to the client without
        the client having to poll. This is used for:
        - Notifications (e.g., "a resource changed")
        - Progress updates during long operations
        - Sampling requests (server asking client's LLM to generate)

        Note: In this simple example, SSE is implemented but not heavily used.
        """
        session_id = request.query_params.get("session_id", "default")

        # Create a queue for this session's outbound messages
        queue: asyncio.Queue = asyncio.Queue()
        sessions[session_id] = queue

        async def event_generator():
            """Yield events from the queue as SSE messages."""
            try:
                while True:
                    message = await queue.get()
                    yield {
                        "event": "message",
                        "data": json.dumps(message),
                    }
            except asyncio.CancelledError:
                pass
            finally:
                # Clean up when client disconnects
                sessions.pop(session_id, None)

        return EventSourceResponse(event_generator())

    # -------------------------------------------------------------------------
    # Message Endpoint Handler (Main JSON-RPC Handler)
    # -------------------------------------------------------------------------
    # pylint: disable=too-many-branches,too-many-statements
    async def handle_message(request):
        """
        Handle incoming JSON-RPC messages from clients.

        This is the main endpoint where all MCP communication happens.
        The client sends JSON-RPC requests, we route them to the appropriate
        handler, and return the result.

        MCP METHODS WE HANDLE:
        ----------------------
        - initialize        : Client wants to start a session
        - tools/list        : Client wants to see available tools
        - tools/call        : Client wants to execute a tool
        - resources/list    : Client wants to see available resources
        - resources/read    : Client wants to read a resource
        - prompts/list      : Client wants to see available prompts
        - prompts/get       : Client wants a specific prompt template
        """
        try:
            body = await request.json()
        except (ValueError, TypeError, json.JSONDecodeError):
            # JSON parsing failed - return parse error
            logger.error("❌ Failed to parse JSON request body")
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Parse error"},
                    "id": None,
                },
                status_code=400,
            )

        # Extract JSON-RPC fields
        method = body.get("method", "")  # Which MCP method to call
        params = body.get("params", {})  # Parameters for the method
        msg_id = body.get("id")  # Request ID (for matching response)

        # ─────────────────────────────────────────────────────────────────────
        # LOG INCOMING REQUEST
        # ─────────────────────────────────────────────────────────────────────
        logger.info("=" * 70)
        logger.info("📥 INCOMING REQUEST")
        logger.info("=" * 70)
        logger.debug(
            "Raw JSON-RPC Request:\n%s", json.dumps(body, indent=2, default=str)
        )
        logger.info("Method: %s", method)
        logger.info("Request ID: %s", msg_id)
        if params:
            logger.info("Params: %s", json.dumps(params, indent=2, default=str))

        try:
            # ─────────────────────────────────────────────────────────────────
            # Route to appropriate handler based on method name
            # ─────────────────────────────────────────────────────────────────

            if method == "initialize":
                # ─────────────────────────────────────────────────────────────
                # INITIALIZE - First message in any MCP session
                #
                # The client sends this to:
                # 1. Tell us what protocol version it speaks
                # 2. Tell us what capabilities it has
                # 3. Get our capabilities in return
                #
                # We respond with:
                # - protocolVersion: What MCP version we support
                # - capabilities: What features we offer (tools, resources, etc.)
                # - serverInfo: Our name and version
                # ─────────────────────────────────────────────────────────────
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True},  # We have tools
                        "resources": {
                            "subscribe": False,  # No subscriptions
                            "listChanged": True,  # Resources can change
                        },
                        "prompts": {"listChanged": True},  # We have prompts
                    },
                    "serverInfo": {
                        "name": "knowledge-base",
                        "version": "1.0.0",
                    },
                }

            elif method == "tools/list":
                # ─────────────────────────────────────────────────────────────
                # TOOLS/LIST - Client wants to know what tools we have
                #
                # Returns a list of all available tools with:
                # - name: Unique identifier for the tool
                # - description: What the tool does (shown to users)
                # - inputSchema: JSON Schema defining what arguments it accepts
                # ─────────────────────────────────────────────────────────────
                # Create a request object and call the handler
                handler = server.request_handlers.get(types.ListToolsRequest)
                if handler:
                    request = types.ListToolsRequest(method="tools/list")
                    response = await handler(request)
                    result = response.root.model_dump(mode="json")
                else:
                    result = {"tools": []}

            elif method == "tools/call":
                # ─────────────────────────────────────────────────────────────
                # TOOLS/CALL - Client wants to execute a tool
                #
                # params contains:
                # - name: Which tool to call
                # - arguments: The arguments to pass to the tool
                #
                # We return the tool's output as "content" (text, images, etc.)
                # ─────────────────────────────────────────────────────────────
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})
                handler = server.request_handlers.get(types.CallToolRequest)
                if handler:
                    request = types.CallToolRequest(
                        method="tools/call",
                        params=types.CallToolRequestParams(
                            name=tool_name, arguments=tool_args
                        ),
                    )
                    response = await handler(request)
                    result = response.root.model_dump(mode="json")
                else:
                    result = {"content": [], "isError": True}

            elif method == "resources/list":
                # ─────────────────────────────────────────────────────────────
                # RESOURCES/LIST - Client wants to know what resources we have
                #
                # Resources are like "files" or "data sources" the AI can read.
                # Each resource has:
                # - uri: Unique identifier (like kb://articles/123)
                # - name: Human-readable name
                # - description: What the resource contains
                # - mimeType: Content type (text/plain, application/json, etc.)
                # ─────────────────────────────────────────────────────────────
                handler = server.request_handlers.get(types.ListResourcesRequest)
                if handler:
                    request = types.ListResourcesRequest(method="resources/list")
                    response = await handler(request)
                    result = response.root.model_dump(mode="json")
                else:
                    result = {"resources": []}

            elif method == "resources/read":
                # ─────────────────────────────────────────────────────────────
                # RESOURCES/READ - Client wants to read a specific resource
                #
                # params contains:
                # - uri: Which resource to read
                #
                # We return the resource content (text, binary, etc.)
                # ─────────────────────────────────────────────────────────────
                uri = params.get("uri", "")
                handler = server.request_handlers.get(types.ReadResourceRequest)
                if handler:
                    request = types.ReadResourceRequest(
                        method="resources/read",
                        params=types.ReadResourceRequestParams(uri=uri),
                    )
                    response = await handler(request)
                    result = response.root.model_dump(mode="json")
                else:
                    result = {"contents": []}

            elif method == "prompts/list":
                # ─────────────────────────────────────────────────────────────
                # PROMPTS/LIST - Client wants to see available prompt templates
                #
                # Prompts are pre-made templates that help the AI with specific
                # tasks. Each prompt has:
                # - name: Unique identifier
                # - description: What the prompt helps with
                # - arguments: What parameters the prompt accepts
                # ─────────────────────────────────────────────────────────────
                handler = server.request_handlers.get(types.ListPromptsRequest)
                if handler:
                    request = types.ListPromptsRequest(method="prompts/list")
                    response = await handler(request)
                    result = response.root.model_dump(mode="json")
                else:
                    result = {"prompts": []}

            elif method == "prompts/get":
                # ─────────────────────────────────────────────────────────────
                # PROMPTS/GET - Client wants a specific prompt filled in
                #
                # params contains:
                # - name: Which prompt to get
                # - arguments: Values to fill into the prompt template
                #
                # We return the filled-in prompt as chat messages
                # ─────────────────────────────────────────────────────────────
                prompt_name = params.get("name", "")
                prompt_args = params.get("arguments", {})
                handler = server.request_handlers.get(types.GetPromptRequest)
                if handler:
                    request = types.GetPromptRequest(
                        method="prompts/get",
                        params=types.GetPromptRequestParams(
                            name=prompt_name, arguments=prompt_args
                        ),
                    )
                    response = await handler(request)
                    result = response.root.model_dump(mode="json")
                else:
                    result = {"messages": []}

            elif method == "notifications/initialized":
                # ─────────────────────────────────────────────────────────────
                # NOTIFICATIONS/INITIALIZED - Client confirms initialization done
                #
                # This is a notification (no response expected), but we
                # acknowledge it to keep the HTTP contract simple.
                # ─────────────────────────────────────────────────────────────
                return JSONResponse({"status": "ok"})

            else:
                # Unknown method - return error
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}",
                        },
                        "id": msg_id,
                    }
                )

            # ─────────────────────────────────────────────────────────────────
            # LOG OUTGOING RESPONSE
            # ─────────────────────────────────────────────────────────────────
            response_body = {"jsonrpc": "2.0", "result": result, "id": msg_id}
            logger.info("-" * 70)
            logger.info("📤 OUTGOING RESPONSE")
            logger.info("-" * 70)
            logger.info("Response ID: %s (matches request)", msg_id)
            logger.info(
                "Result keys: %s",
                list(result.keys()) if isinstance(result, dict) else type(result),
            )
            logger.debug(
                "Full JSON-RPC Response:\n%s",
                json.dumps(response_body, indent=2, default=str)[
                    :2000
                ],  # Truncate for readability
            )
            logger.info("=" * 70)

            # Return successful result
            return JSONResponse(response_body)

        except (RuntimeError, ValueError, KeyError, AttributeError) as e:
            # Something went wrong - return internal error
            logger.error("❌ EXCEPTION: %s", str(e), exc_info=True)
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": str(e)},
                    "id": msg_id,
                },
                status_code=500,
            )

    # -------------------------------------------------------------------------
    # Health Check Endpoint
    # -------------------------------------------------------------------------
    async def health_check(_request):
        """
        Simple health check endpoint.

        Useful for:
        - Load balancers to check if server is alive
        - Monitoring systems
        - Quick "is it running?" checks during development
        """
        return JSONResponse({"status": "healthy", "server": "knowledge-base"})

    # -------------------------------------------------------------------------
    # Create and Run Starlette App
    # -------------------------------------------------------------------------
    app = Starlette(
        routes=[
            Route("/health", health_check),  # GET /health
            Route("/sse", handle_sse),  # GET /sse
            Route("/message", handle_message, methods=["POST"]),  # POST /message
        ],
    )

    # Run with uvicorn (production-ready ASGI server)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server_instance = uvicorn.Server(config)
    await server_instance.serve()


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


@click.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio", "http"]),
    default="stdio",
    help="Transport type: 'stdio' for production, 'http' for development",
)
@click.option("--host", default="0.0.0.0", help="HTTP server host (http mode only)")
@click.option(
    "--port", default=8080, type=int, help="HTTP server port (http mode only)"
)
def main(transport: str = "stdio", host: str = "0.0.0.0", port: int = 8080) -> None:
    """
    Run the Knowledge Base MCP Server.

    Examples:
        # Run with STDIO (for Claude Desktop):
        python -m server.main --transport stdio

        # Run with HTTP (for testing):
        python -m server.main --transport http --port 8080
    """
    if transport == "stdio":
        print("Starting Knowledge Base MCP Server (stdio)...", file=sys.stderr)
        asyncio.run(run_stdio_server())
    else:
        print(
            f"Starting Knowledge Base MCP Server (HTTP) on {host}:{port}...",
            file=sys.stderr,
        )
        asyncio.run(run_http_server(host, port))


if __name__ == "__main__":
    main()
