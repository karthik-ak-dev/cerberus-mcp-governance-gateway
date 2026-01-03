"""Sampling support for Knowledge Base MCP Server.

Sampling allows the server to request the client to generate text using an LLM.
This is useful when the server needs AI-generated content but doesn't have
direct access to an LLM.
"""

from mcp.server import Server
from mcp.types import (
    CreateMessageRequest,
    CreateMessageResult,
    SamplingMessage,
    TextContent,
)

from server.data_store import get_store


class SamplingHelper:
    """Helper class for server-initiated sampling requests."""

    def __init__(self, server: Server):
        self.server = server

    async def request_summary(self, article_id: str) -> str | None:
        """Request the client to generate a summary for an article.

        This demonstrates server-to-client sampling - the server asks
        the client's LLM to generate content.

        Args:
            article_id: ID of article to summarize

        Returns:
            Generated summary or None if sampling failed
        """
        store = get_store()
        article = store.get_article(article_id)

        if not article:
            return None

        # Create sampling request
        request = CreateMessageRequest(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Please provide a concise 2-3 sentence summary of this article:

Title: {article.title}
Content: {article.content}

Summary:""",
                    ),
                )
            ],
            maxTokens=200,
            temperature=0.3,  # Lower temperature for more focused output
            systemPrompt="You are a helpful assistant that creates concise article summaries.",
        )

        try:
            # Send sampling request to client
            result: CreateMessageResult = (
                await self.server.request_context.session.create_message(request)
            )

            if result.content and result.content.type == "text":
                return result.content.text
            return None

        except (RuntimeError, ConnectionError, ValueError) as e:
            # Sampling might not be supported by the client
            print(f"Sampling request failed: {e}")
            return None

    async def request_related_questions(self, article_id: str) -> list[str]:
        """Request the client to generate related questions for an article.

        Args:
            article_id: ID of article

        Returns:
            List of related questions
        """
        store = get_store()
        article = store.get_article(article_id)

        if not article:
            return []

        request = CreateMessageRequest(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Based on this article, generate 5 related questions.

Title: {article.title}
Tags: {', '.join(article.tags)}
Content preview: {article.content[:500]}...

Return only the questions, one per line, numbered 1-5.""",
                    ),
                )
            ],
            maxTokens=300,
            temperature=0.7,
        )

        try:
            result = await self.server.request_context.session.create_message(request)

            if result.content and result.content.type == "text":
                lines = result.content.text.strip().split("\n")
                questions = [
                    line.lstrip("0123456789.-) ").strip()
                    for line in lines
                    if line.strip()
                ]
                return questions[:5]
            return []

        except (RuntimeError, ConnectionError, ValueError):
            return []

    async def request_content_improvement(
        self, article_id: str, improvement_type: str = "clarity"
    ) -> str | None:
        """Request suggestions for improving article content.

        Args:
            article_id: ID of article
            improvement_type: Type of improvement (clarity, depth, examples)

        Returns:
            Improvement suggestions
        """
        store = get_store()
        article = store.get_article(article_id)

        if not article:
            return None

        prompts = {
            "clarity": "How could this article be made clearer and easier to understand?",
            "depth": "What additional depth or detail could be added to this article?",
            "examples": "What practical examples could be added to better illustrate the concepts?",
        }

        prompt = prompts.get(improvement_type, prompts["clarity"])

        request = CreateMessageRequest(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Review this knowledge base article and provide suggestions.

Title: {article.title}
Category: {article.category}
Content:
{article.content}

Question: {prompt}

Please provide 3-5 specific, actionable suggestions.""",
                    ),
                )
            ],
            maxTokens=500,
            temperature=0.5,
        )

        try:
            result = await self.server.request_context.session.create_message(request)

            if result.content and result.content.type == "text":
                return result.content.text
            return None

        except (RuntimeError, ConnectionError, ValueError):
            return None
