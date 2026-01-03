"""
Client-Side Handlers for MCP Features
=====================================

This file implements handlers for server-to-client requests in MCP.

WHAT ARE CLIENT HANDLERS?
-------------------------
In MCP, communication is mostly client→server (client asks, server answers).
But there are some features where the SERVER asks the CLIENT to do something:

1. SAMPLING - Server asks client to generate text with an LLM
2. ROOTS    - Server asks client what filesystem paths it can access
3. ELICITATION - Server asks client to get user input/confirmation

These are "reverse" requests - the server initiates, the client responds.

WHY DOES THIS EXIST?
--------------------
Sampling: The MCP server might not have direct access to an LLM, but the
    client (e.g., Claude Desktop) does. So the server can ask the client
    to generate text and return it.

Roots: The server might want to know what files the client has access to.
    This helps the server make smarter suggestions.

Elicitation: Some operations need user confirmation (e.g., "Delete this file?").
    The server asks the client to show a prompt and return the user's answer.

WHEN ARE THESE USED?
-------------------
In this simple HTTP client, these handlers are created but not heavily used.
In a full MCP implementation (like Claude Desktop), these would be:

- Sampling: When a server wants Claude to generate a summary or response
- Roots: When a filesystem server wants to know accessible directories
- Elicitation: When a server needs user confirmation for sensitive operations

HOW THEY WORK:
-------------
1. Server sends a request (via SSE or response) asking client to do something
2. Client's handler processes the request
3. Client sends result back to server

For this demo, we implement simple versions:
- Sampling: Returns mock responses (or uses a callback if provided)
- Roots: Returns current working directory
- Elicitation: Auto-approves (for testing) or prompts user
"""

from pathlib import Path
from typing import Callable

from mcp.types import (
    CreateMessageRequest,
    CreateMessageResult,
    TextContent,
    Root,
)


class SamplingHandler:
    """
    Handle sampling (LLM generation) requests from the server.

    WHAT IS SAMPLING?
    -----------------
    "Sampling" in MCP means "generate text with an LLM".
    The server sends a prompt, and expects generated text back.

    USE CASE EXAMPLE:
    ----------------
    Server has an article and wants a summary:
    1. Server sends CreateMessageRequest with article content
    2. Client's SamplingHandler receives it
    3. Handler calls an LLM (or returns mock response)
    4. Handler returns CreateMessageResult with the summary

    FOR TESTING:
    -----------
    This handler can work in two modes:
    1. With llm_callback: Calls a real LLM function you provide
    2. Without callback: Returns mock responses based on keywords

    REAL IMPLEMENTATION:
    -------------------
    In Claude Desktop, this would call Claude to generate.
    In a custom client, you might call OpenAI, local LLM, etc.
    """

    def __init__(self, llm_callback: Callable[[str], str] | None = None):
        """
        Initialize the sampling handler.

        Args:
            llm_callback: Optional function that takes a prompt string
                         and returns generated text. If None, uses mock responses.

        Example:
            # With real LLM:
            handler = SamplingHandler(llm_callback=openai_complete)

            # For testing (mock responses):
            handler = SamplingHandler()
        """
        self.llm_callback = llm_callback

    async def handle_create_message(
        self, request: CreateMessageRequest
    ) -> CreateMessageResult:
        """
        Handle a sampling request from the server.

        This is called when the server wants us to generate text.

        Args:
            request: The sampling request containing:
                - messages: Conversation history (role + content)
                - modelPreferences: Hints about desired model
                - maxTokens: Maximum response length
                - temperature: Creativity setting

        Returns:
            CreateMessageResult with the generated response
        """
        # Build a prompt string from the messages
        prompt = ""
        for msg in request.messages:
            if hasattr(msg.content, "text"):
                prompt += f"{msg.role}: {msg.content.text}\n"

        # Generate response
        if self.llm_callback:
            # Use real LLM
            response_text = self.llm_callback(prompt)
        else:
            # Use mock response
            response_text = self._generate_mock_response(prompt, request)

        return CreateMessageResult(
            role="assistant",
            content=TextContent(type="text", text=response_text),
            model="mock-model",  # Would be actual model name with real LLM
            stopReason="endTurn",
        )

    def _generate_mock_response(
        self, prompt: str, request: CreateMessageRequest
    ) -> str:
        """
        Generate a mock response based on prompt keywords.

        This is for testing when you don't have a real LLM connected.
        The responses are hardcoded based on what the prompt asks for.
        """
        prompt_lower = prompt.lower()

        # Generate different responses based on what's being asked
        if "summary" in prompt_lower or "summarize" in prompt_lower:
            return (
                "This article provides a comprehensive overview of the topic, "
                "covering key concepts, practical examples, and best practices. "
                "It serves as a useful reference for developers at various skill levels."
            )

        elif "question" in prompt_lower:
            return (
                "1. What are the key benefits of this approach?\n"
                "2. How does this compare to alternative methods?\n"
                "3. What are common pitfalls to avoid?\n"
                "4. Can this be applied in production environments?\n"
                "5. What are the performance considerations?"
            )

        elif "improvement" in prompt_lower or "suggest" in prompt_lower:
            return (
                "Here are suggestions for improvement:\n"
                "1. Add more real-world examples\n"
                "2. Include performance benchmarks\n"
                "3. Add a troubleshooting section\n"
                "4. Provide links to related resources\n"
                "5. Include a quick-start guide"
            )

        else:
            # Generic response
            return f"Mock response to: {prompt[:100]}..."


class RootsProvider:
    """
    Provide filesystem roots to the server.

    WHAT ARE ROOTS?
    ---------------
    "Roots" are filesystem directories that the client has access to.
    The server can ask "what directories can you access?" and we tell it.

    USE CASE EXAMPLE:
    ----------------
    A filesystem MCP server might ask for roots to:
    - Know which directories it should scan
    - Restrict file operations to these paths
    - Provide autocomplete for file paths

    DEFAULT BEHAVIOR:
    ----------------
    By default, we expose the current working directory.
    You can add/remove roots dynamically.
    """

    def __init__(self, roots: list[Path] | None = None):
        """
        Initialize the roots provider.

        Args:
            roots: List of filesystem paths to expose.
                  Defaults to current working directory.
        """
        self.roots = roots or [Path.cwd()]

    def get_roots(self) -> list[Root]:
        """
        Get the list of roots to provide to the server.

        Returns:
            List of Root objects with URI and name
        """
        return [
            Root(
                # Convert to file:// URI format
                uri=f"file://{path.absolute()}",
                # Use directory name as the root name
                name=path.name or str(path),
            )
            for path in self.roots
            if path.exists()  # Only include paths that exist
        ]

    def add_root(self, path: Path) -> None:
        """
        Add a new root directory.

        Args:
            path: Directory path to add
        """
        if path.exists() and path not in self.roots:
            self.roots.append(path)

    def remove_root(self, path: Path) -> None:
        """
        Remove a root directory.

        Args:
            path: Directory path to remove
        """
        if path in self.roots:
            self.roots.remove(path)


class ElicitationHandler:
    """
    Handle elicitation (user input) requests from the server.

    WHAT IS ELICITATION?
    -------------------
    Elicitation is when the server needs to ask the user something:
    - "Are you sure you want to delete this?" (confirmation)
    - "What name should we use?" (text input)
    - "Which option do you prefer?" (selection)

    The server can't directly talk to the user, so it asks the client
    to handle the interaction.

    USE CASE EXAMPLES:
    -----------------
    1. Confirmation: Server wants to delete a file
       → Server sends elicitation request
       → Client shows "Delete file.txt? (y/n)"
       → Client returns True/False

    2. Input: Server needs a value from user
       → Server sends elicitation with prompt
       → Client shows prompt, gets user input
       → Client returns the input text

    3. Selection: Server offers multiple options
       → Server sends options list
       → Client shows numbered menu
       → Client returns selected index

    AUTO-APPROVE MODE:
    -----------------
    For testing, you can enable auto_approve to automatically
    approve all confirmations and use default values.
    """

    def __init__(self, auto_approve: bool = False):
        """
        Initialize the elicitation handler.

        Args:
            auto_approve: If True, automatically approve all requests.
                         Useful for automated testing.
        """
        self.auto_approve = auto_approve

    async def handle_confirmation(self, message: str) -> bool:
        """
        Handle a confirmation request (yes/no question).

        Args:
            message: The confirmation message to show

        Returns:
            True if user confirmed, False if declined
        """
        if self.auto_approve:
            print(f"[Auto-approved] {message}")
            return True

        # Show message and get user response
        print(f"\n[Server Request] {message}")
        response = input("Confirm? (y/n): ").strip().lower()
        return response in ("y", "yes")

    async def handle_input(self, prompt: str, default: str | None = None) -> str:
        """
        Handle a text input request.

        Args:
            prompt: The prompt to show the user
            default: Optional default value

        Returns:
            User's input (or default if empty and default provided)
        """
        if self.auto_approve and default:
            print(f"[Auto-input] {prompt}: {default}")
            return default

        print(f"\n[Server Request] {prompt}")
        if default:
            response = input(f"Enter value (default: {default}): ").strip()
            return response if response else default
        return input("Enter value: ").strip()

    async def handle_selection(
        self, message: str, options: list[str], default: int = 0
    ) -> int:
        """
        Handle a selection request (pick from options).

        Args:
            message: The selection message/prompt
            options: List of options to choose from
            default: Default option index (0-based)

        Returns:
            Index of selected option
        """
        if self.auto_approve:
            print(f"[Auto-selected] {message}: {options[default]}")
            return default

        print(f"\n[Server Request] {message}")
        for i, opt in enumerate(options):
            # Mark default option with asterisk
            marker = "*" if i == default else " "
            print(f"  {marker} {i + 1}. {opt}")

        try:
            response = input(
                f"Select (1-{len(options)}, default {default + 1}): "
            ).strip()
            if not response:
                return default
            return int(response) - 1
        except ValueError:
            return default
