"""
Knowledge Base MCP Client - Main Entry Point
=============================================

This file is the MCP CLIENT - it connects to an MCP server and interacts with it.
Think of the client as a "consumer" that uses the server's capabilities.

WHAT IS AN MCP CLIENT?
----------------------
An MCP client is software that:
1. Connects to an MCP server (via HTTP or STDIO)
2. Discovers what the server offers (tools, resources, prompts)
3. Calls tools, reads resources, uses prompts
4. Handles server requests (sampling, elicitation)

REAL-WORLD CLIENTS:
------------------
- Claude Desktop (built-in MCP client)
- VS Code extensions
- Custom integrations
- This demo client!

CLIENT-SERVER COMMUNICATION:
---------------------------
All communication uses JSON-RPC 2.0 over the chosen transport:

    Client                          Server
       |                              |
       |-- initialize --------------->|  "Hello, I'm client X"
       |<-- capabilities -------------|  "I offer tools, resources, prompts"
       |                              |
       |-- tools/list --------------->|  "What tools do you have?"
       |<-- tool definitions ---------|  "Here's the list..."
       |                              |
       |-- tools/call --------------->|  "Run search_articles"
       |<-- result -------------------|  "Found 5 articles..."

JSON-RPC FORMAT:
---------------
Request:
{
    "jsonrpc": "2.0",        # Protocol version (always 2.0)
    "id": 1,                 # Unique request ID
    "method": "tools/list",  # What we're asking for
    "params": {}             # Parameters (if any)
}

Response:
{
    "jsonrpc": "2.0",
    "id": 1,                 # Matches request ID
    "result": { ... }        # The data we asked for
}

THIS CLIENT DEMONSTRATES:
------------------------
- Connecting to an MCP server over HTTP
- Discovering and using tools
- Reading resources
- Using prompt templates
- Interactive CLI interface

RUNNING THE CLIENT:
------------------
    # First, start the server:
    python -m server.main --transport http --port 8080

    # Then, run this client:
    python -m client.main --server-url http://localhost:8080

    # With custom headers (e.g., for authentication):
    python -m client.main --server-url http://localhost:8080 --headers "Authorization: Bearer xxx"
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

import click
import httpx

# Add parent to path so we can import from sibling packages
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import our handler classes (for sampling, roots, elicitation)
from client.handlers import SamplingHandler, RootsProvider, ElicitationHandler


class MCPClient:
    """
    MCP Client for HTTP transport.

    This class handles all communication with an MCP server over HTTP.
    It implements the client side of the MCP protocol.

    Key Responsibilities:
    - Sending JSON-RPC requests to the server
    - Managing request IDs
    - Parsing responses
    - Handling errors

    Attributes:
        server_url: Base URL of the MCP server
        headers: HTTP headers to include (e.g., Authorization)
        http_client: The httpx client for making requests
        server_info: Information about the server (after initialize)
        capabilities: Server's capabilities (tools, resources, etc.)
    """

    def __init__(
        self,
        server_url: str,
        headers: dict[str, str] | None = None,
    ):
        """
        Initialize the MCP client.

        Args:
            server_url: Base URL of the MCP server (e.g., "http://localhost:8080")
            headers: Optional HTTP headers (e.g., for authentication)
        """
        # Remove trailing slash for consistent URL building
        self.server_url = server_url.rstrip("/")
        self.headers = headers or {}

        # Create HTTP client with reasonable timeout
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # Request ID counter - each request needs a unique ID
        self.request_id = 0

        # ─────────────────────────────────────────────────────────────────────
        # Client-side handlers
        # These handle requests FROM the server TO the client
        # (reverse direction from normal request/response)
        # ─────────────────────────────────────────────────────────────────────
        self.sampling_handler = SamplingHandler()
        self.roots_provider = RootsProvider()
        self.elicitation_handler = ElicitationHandler(auto_approve=True)

        # Server info (populated after initialize)
        self.server_info: dict[str, Any] = {}
        self.capabilities: dict[str, Any] = {}

    async def close(self) -> None:
        """Close the HTTP client and clean up resources."""
        await self.http_client.aclose()

    def _next_id(self) -> int:
        """
        Generate the next unique request ID.

        JSON-RPC requires each request to have a unique ID so responses
        can be matched to requests (important for async/parallel requests).
        """
        self.request_id += 1
        return self.request_id

    async def _send_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> Any:
        """
        Send a JSON-RPC request to the server and return the result.

        This is the core method that all other methods use.
        It handles the JSON-RPC protocol details.

        Args:
            method: The MCP method to call (e.g., "tools/list", "tools/call")
            params: Parameters to send with the request

        Returns:
            The "result" field from the server's response

        Raises:
            Exception: If the server returns an error
        """
        # Build JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params:
            request["params"] = params

        # Send HTTP POST to /message endpoint
        response = await self.http_client.post(
            f"{self.server_url}/message",
            json=request,
            headers=self.headers,
        )

        # Check HTTP status
        response.raise_for_status()

        # Parse JSON response
        data = response.json()

        # Check for JSON-RPC error
        if "error" in data:
            raise Exception(f"Server error: {data['error']}")

        return data.get("result")

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    async def initialize(self) -> dict[str, Any]:
        """
        Initialize the MCP session with the server.

        This MUST be the first call after connecting. It:
        1. Tells the server our protocol version
        2. Tells the server our capabilities
        3. Gets the server's capabilities in return
        4. Sends "initialized" notification to confirm

        Returns:
            Server's initialization response (capabilities, serverInfo)
        """
        result = await self._send_request(
            "initialize",
            {
                # MCP protocol version we support
                "protocolVersion": "2024-11-05",
                # Our capabilities (what we can do for the server)
                "capabilities": {
                    "roots": {"listChanged": True},  # We can provide filesystem roots
                    "sampling": {},  # We can handle sampling requests
                },
                # Who we are
                "clientInfo": {
                    "name": "knowledge-base-client",
                    "version": "1.0.0",
                },
            },
        )

        # Store server info for later reference
        self.server_info = result.get("serverInfo", {})
        self.capabilities = result.get("capabilities", {})

        # Send "initialized" notification to confirm we're ready
        # This is a notification (no response expected)
        await self._send_request("notifications/initialized")

        return result

    # =========================================================================
    # TOOLS API
    # =========================================================================

    async def list_tools(self) -> list[dict[str, Any]]:
        """
        List all tools available on the server.

        Tools are actions the AI can perform. Each tool has:
        - name: Unique identifier
        - description: What the tool does
        - inputSchema: JSON Schema defining expected arguments

        Returns:
            List of tool definitions
        """
        result = await self._send_request("tools/list")
        return result.get("tools", [])

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Call (execute) a tool on the server.

        This sends arguments to the server, the server runs the tool,
        and returns the result.

        Args:
            name: Name of the tool to call (e.g., "search_articles")
            arguments: Arguments to pass to the tool

        Returns:
            List of content items (usually TextContent with result)
        """
        result = await self._send_request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        return result.get("content", [])

    # =========================================================================
    # RESOURCES API
    # =========================================================================

    async def list_resources(self) -> list[dict[str, Any]]:
        """
        List all resources available on the server.

        Resources are data the AI can read (like files).
        Each resource has:
        - uri: Unique identifier
        - name: Human-readable name
        - description: What the resource contains
        - mimeType: Content type

        Returns:
            List of resource definitions
        """
        result = await self._send_request("resources/list")
        return result.get("resources", [])

    async def read_resource(self, uri: str) -> list[dict[str, Any]]:
        """
        Read the content of a specific resource.

        Args:
            uri: Resource URI (e.g., "kb://articles/art-001")

        Returns:
            List of content items (the resource data)
        """
        result = await self._send_request("resources/read", {"uri": uri})
        return result.get("contents", [])

    # =========================================================================
    # PROMPTS API
    # =========================================================================

    async def list_prompts(self) -> list[dict[str, Any]]:
        """
        List all prompts available on the server.

        Prompts are templates for common tasks. Each prompt has:
        - name: Unique identifier
        - description: What the prompt helps with
        - arguments: Parameters the prompt accepts

        Returns:
            List of prompt definitions
        """
        result = await self._send_request("prompts/list")
        return result.get("prompts", [])

    async def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Get a prompt with arguments filled in.

        The server fills in the template with your arguments
        and returns ready-to-use messages.

        Args:
            name: Prompt name (e.g., "summarize_article")
            arguments: Values for the prompt's parameters

        Returns:
            List of message objects (for sending to an LLM)
        """
        result = await self._send_request(
            "prompts/get",
            {"name": name, "arguments": arguments or {}},
        )
        return result.get("messages", [])


# =============================================================================
# INTERACTIVE SESSION
# =============================================================================


async def interactive_session(client: MCPClient) -> None:
    """
    Run an interactive CLI session with the MCP server.

    This provides a simple command-line interface to explore
    the MCP server's capabilities.
    """
    print("\n" + "=" * 60)
    print("Knowledge Base MCP Client - Interactive Session")
    print("=" * 60)

    # ─────────────────────────────────────────────────────────────────────────
    # Initialize connection
    # ─────────────────────────────────────────────────────────────────────────
    print("\nInitializing connection...")
    await client.initialize()
    print(f"Connected to: {client.server_info.get('name', 'unknown')}")
    print(f"Capabilities: {list(client.capabilities.keys())}")

    # Show available commands
    commands = """
Commands:
  tools           - List available tools
  call <tool>     - Call a tool (interactive)
  resources       - List available resources
  read <uri>      - Read a resource
  prompts         - List available prompts
  prompt <name>   - Get a prompt (interactive)
  search <query>  - Quick search articles
  help            - Show this help
  quit            - Exit
"""
    print(commands)

    # ─────────────────────────────────────────────────────────────────────────
    # Command loop
    # ─────────────────────────────────────────────────────────────────────────
    while True:
        try:
            user_input = input("\n> ").strip()
            if not user_input:
                continue

            # Parse command and argument
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            # ─────────────────────────────────────────────────────────────────
            # EXIT commands
            # ─────────────────────────────────────────────────────────────────
            if cmd in ("quit", "exit"):
                print("Goodbye!")
                break

            # ─────────────────────────────────────────────────────────────────
            # HELP command
            # ─────────────────────────────────────────────────────────────────
            elif cmd == "help":
                print(commands)

            # ─────────────────────────────────────────────────────────────────
            # TOOLS command - list all tools
            # ─────────────────────────────────────────────────────────────────
            elif cmd == "tools":
                tools = await client.list_tools()
                print(f"\nAvailable tools ({len(tools)}):")
                for t in tools:
                    print(f"  - {t['name']}: {t.get('description', 'No description')}")

            # ─────────────────────────────────────────────────────────────────
            # CALL command - execute a tool
            # ─────────────────────────────────────────────────────────────────
            elif cmd == "call":
                # If no tool name provided, show selection menu
                if not arg:
                    tools = await client.list_tools()
                    print("Available tools:")
                    for i, t in enumerate(tools, 1):
                        print(f"  {i}. {t['name']}")
                    choice = input("Select tool number: ").strip()
                    try:
                        tool = tools[int(choice) - 1]
                        arg = tool["name"]
                    except (ValueError, IndexError):
                        print("Invalid selection")
                        continue

                # Get tool schema to know what arguments to ask for
                tools = await client.list_tools()
                tool = next((t for t in tools if t["name"] == arg), None)
                if not tool:
                    print(f"Tool not found: {arg}")
                    continue

                # Collect arguments based on the tool's input schema
                schema = tool.get("inputSchema", {})
                properties = schema.get("properties", {})
                required = schema.get("required", [])
                arguments = {}

                print(f"\nCalling tool: {arg}")
                for prop_name, prop_def in properties.items():
                    is_required = prop_name in required
                    desc = prop_def.get("description", "")

                    # Build prompt
                    prompt = f"  {prop_name}"
                    if is_required:
                        prompt += " (required)"
                    prompt += f" [{desc}]: "

                    value = input(prompt).strip()
                    if value:
                        # Parse arrays and numbers based on schema type
                        if prop_def.get("type") == "array":
                            arguments[prop_name] = [v.strip() for v in value.split(",")]
                        elif prop_def.get("type") == "integer":
                            arguments[prop_name] = int(value)
                        else:
                            arguments[prop_name] = value
                    elif is_required:
                        print(f"  {prop_name} is required!")
                        continue

                # Execute the tool
                result = await client.call_tool(arg, arguments)
                print("\nResult:")
                for content in result:
                    if content.get("type") == "text":
                        print(content.get("text", ""))

            # ─────────────────────────────────────────────────────────────────
            # RESOURCES command - list all resources
            # ─────────────────────────────────────────────────────────────────
            elif cmd == "resources":
                resources = await client.list_resources()
                print(f"\nAvailable resources ({len(resources)}):")
                for r in resources:
                    print(f"  - {r['uri']}: {r.get('name', 'Unnamed')}")

            # ─────────────────────────────────────────────────────────────────
            # READ command - read a resource
            # ─────────────────────────────────────────────────────────────────
            elif cmd == "read":
                # If no URI provided, show selection menu
                if not arg:
                    resources = await client.list_resources()
                    print("Available resources:")
                    for i, r in enumerate(resources, 1):
                        print(f"  {i}. {r['uri']}")
                    choice = input("Select resource number: ").strip()
                    try:
                        resource = resources[int(choice) - 1]
                        arg = resource["uri"]
                    except (ValueError, IndexError):
                        print("Invalid selection")
                        continue

                contents = await client.read_resource(arg)
                print(f"\nResource: {arg}")
                print("-" * 40)
                for content in contents:
                    print(content.get("text", ""))

            # ─────────────────────────────────────────────────────────────────
            # PROMPTS command - list all prompts
            # ─────────────────────────────────────────────────────────────────
            elif cmd == "prompts":
                prompts = await client.list_prompts()
                print(f"\nAvailable prompts ({len(prompts)}):")
                for p in prompts:
                    print(f"  - {p['name']}: {p.get('description', 'No description')}")

            # ─────────────────────────────────────────────────────────────────
            # PROMPT command - get a specific prompt
            # ─────────────────────────────────────────────────────────────────
            elif cmd == "prompt":
                # If no prompt name provided, show selection menu
                if not arg:
                    prompts = await client.list_prompts()
                    print("Available prompts:")
                    for i, p in enumerate(prompts, 1):
                        print(f"  {i}. {p['name']}")
                    choice = input("Select prompt number: ").strip()
                    try:
                        selected = prompts[int(choice) - 1]
                        arg = selected["name"]
                    except (ValueError, IndexError):
                        print("Invalid selection")
                        continue

                # Get prompt definition
                prompts = await client.list_prompts()
                selected = next((p for p in prompts if p["name"] == arg), None)
                if not selected:
                    print(f"Prompt not found: {arg}")
                    continue

                # Collect arguments
                arguments = {}
                for param in selected.get("arguments", []):
                    param_name = param["name"]
                    is_required = param.get("required", False)
                    desc = param.get("description", "")

                    prompt_text = f"  {param_name}"
                    if is_required:
                        prompt_text += " (required)"
                    prompt_text += f" [{desc}]: "

                    value = input(prompt_text).strip()
                    if value:
                        arguments[param_name] = value
                    elif is_required:
                        print(f"  {param_name} is required!")
                        continue

                # Get the filled-in prompt
                messages = await client.get_prompt(arg, arguments)
                print(f"\nPrompt: {arg}")
                print("-" * 40)
                for msg in messages:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", {})
                    if isinstance(content, dict):
                        text = content.get("text", "")
                    else:
                        text = str(content)
                    print(f"[{role}]:\n{text}\n")

            # ─────────────────────────────────────────────────────────────────
            # SEARCH command - quick search shortcut
            # ─────────────────────────────────────────────────────────────────
            elif cmd == "search":
                if not arg:
                    arg = input("Search query: ").strip()
                if arg:
                    result = await client.call_tool("search_articles", {"query": arg})
                    for content in result:
                        if content.get("type") == "text":
                            print(content.get("text", ""))

            # ─────────────────────────────────────────────────────────────────
            # UNKNOWN command
            # ─────────────────────────────────────────────────────────────────
            else:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")

        except KeyboardInterrupt:
            print("\nUse 'quit' to exit")
        except Exception as e:
            print(f"Error: {e}")


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


@click.command()
@click.option(
    "--server-url",
    default="http://localhost:8080",
    help="MCP server URL",
)
@click.option(
    "--headers",
    multiple=True,
    help="HTTP headers in 'Key: Value' format (can be repeated)",
)
def main(server_url: str, headers: tuple[str, ...]) -> None:
    """
    Run the Knowledge Base MCP Client.

    Examples:
        # Connect to local server:
        python -m client.main --server-url http://localhost:8080

        # With authentication header:
        python -m client.main --server-url http://localhost:8080 \\
            --headers "Authorization: Bearer token123"
    """
    # Parse headers from "Key: Value" format to dict
    header_dict = {}
    for h in headers:
        if ":" in h:
            key, value = h.split(":", 1)
            header_dict[key.strip()] = value.strip()

    async def run():
        client = MCPClient(server_url, headers=header_dict)
        try:
            await interactive_session(client)
        finally:
            await client.close()

    asyncio.run(run())


if __name__ == "__main__":
    main()
