"""
MCP Prompts Implementation for Knowledge Base Server
====================================================

This file defines the PROMPTS that our MCP server offers to AI clients.

WHAT ARE MCP PROMPTS?
---------------------
Prompts are pre-made templates that help AI assistants with specific tasks.
They combine:
- Instructions on what to do
- Context from the knowledge base
- Formatting guidelines

Think of prompts as "recipes" for common tasks:
- "Summarize this article"
- "Answer a question using the knowledge base"
- "Compare two articles"

Each prompt has:
1. NAME        - Unique identifier (e.g., "summarize_article")
2. DESCRIPTION - What the prompt helps with
3. ARGUMENTS   - Parameters the prompt accepts (like function parameters)

HOW PROMPTS WORK:
----------------
1. Client calls prompts/list → Server returns available prompts
2. User/AI selects a prompt and provides arguments
3. Client calls prompts/get with name and arguments
4. Server fills in the template and fetches relevant context
5. Server returns ready-to-use messages for the AI

PROMPTS VS TOOLS:
----------------
- TOOLS: Execute actions and return results
- PROMPTS: Generate messages for the AI to process

Use prompts when:
- You want to give AI structured instructions
- Task needs context from your data
- You want consistent formatting for similar tasks

PROMPT OUTPUT FORMAT:
--------------------
Prompts return a list of "messages" (like chat messages):
[
    {
        "role": "user",           # Who is "saying" this
        "content": {
            "type": "text",
            "text": "Please summarize..."  # The actual prompt text
        }
    }
]

The AI then processes these messages as if a user sent them.

PROMPTS IN THIS FILE:
---------------------
- question_answer   : Answer questions using KB content
- summarize_article : Generate article summaries
- compare_articles  : Compare two articles
- generate_tutorial : Create tutorials from KB content
"""

from mcp.server import Server
from mcp.types import (
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
    GetPromptResult,
)

from server.data_store import get_store


def register_prompts(server: Server) -> None:
    """
    Register prompt handlers with the MCP server.

    This function:
    1. Registers a handler for prompts/list (returns available prompts)
    2. Registers a handler for prompts/get (returns filled-in prompt)

    Args:
        server: The MCP server instance to register prompts with
    """

    # =========================================================================
    # PROMPTS/LIST Handler
    # =========================================================================

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        """
        Return the list of available prompts.

        Each Prompt object contains:
        - name: Unique identifier
        - description: What the prompt helps with (AI uses this to decide when to suggest it)
        - arguments: List of parameters the prompt accepts
        """
        return [
            # -----------------------------------------------------------------
            # QUESTION_ANSWER Prompt
            # For answering questions using knowledge base content
            # -----------------------------------------------------------------
            Prompt(
                name="question_answer",
                description="Answer a question using relevant knowledge base articles. "
                "The system will automatically find and include relevant context.",
                arguments=[
                    PromptArgument(
                        name="question",
                        description="The question to answer",
                        required=True,
                    ),
                    PromptArgument(
                        name="category",
                        description="Optional: Focus on a specific category",
                        required=False,
                    ),
                ],
            ),
            # -----------------------------------------------------------------
            # SUMMARIZE_ARTICLE Prompt
            # For generating summaries of articles
            # -----------------------------------------------------------------
            Prompt(
                name="summarize_article",
                description="Generate a summary of a specific article. "
                "Supports different summary styles: brief, detailed, or bullet-points.",
                arguments=[
                    PromptArgument(
                        name="article_id",
                        description="ID of the article to summarize",
                        required=True,
                    ),
                    PromptArgument(
                        name="style",
                        description="Summary style: 'brief', 'detailed', or 'bullet-points'",
                        required=False,
                    ),
                ],
            ),
            # -----------------------------------------------------------------
            # COMPARE_ARTICLES Prompt
            # For comparing two articles side by side
            # -----------------------------------------------------------------
            Prompt(
                name="compare_articles",
                description="Compare two articles, highlighting similarities and differences.",
                arguments=[
                    PromptArgument(
                        name="article_id_1",
                        description="First article ID",
                        required=True,
                    ),
                    PromptArgument(
                        name="article_id_2",
                        description="Second article ID",
                        required=True,
                    ),
                ],
            ),
            # -----------------------------------------------------------------
            # GENERATE_TUTORIAL Prompt
            # For creating tutorials based on KB content
            # -----------------------------------------------------------------
            Prompt(
                name="generate_tutorial",
                description="Generate a tutorial on a topic using KB content as reference.",
                arguments=[
                    PromptArgument(
                        name="topic",
                        description="Topic for the tutorial",
                        required=True,
                    ),
                    PromptArgument(
                        name="skill_level",
                        description="Target skill level: 'beginner', 'intermediate', or 'advanced'",
                        required=False,
                    ),
                ],
            ),
        ]

    # =========================================================================
    # PROMPTS/GET Handler
    # =========================================================================

    def _handle_question_answer(store, arguments: dict[str, str]) -> GetPromptResult:
        """Handle question_answer prompt."""
        question = arguments.get("question", "")
        category = arguments.get("category")
        results = store.search_articles(query=question, category=category, limit=3)

        context = "## Relevant Knowledge Base Articles\n\n"
        if results:
            for result in results:
                article = store.get_article(result.article_id)
                if article:
                    context += f"### {article.title}\n{article.content[:500]}...\n\n"
        else:
            context += "No directly relevant articles found.\n\n"

        prompt_text = f"""Based on the following knowledge base content, answer this question:

**Question:** {question}

{context}

Please provide a clear, accurate answer based on the knowledge base content above.
If the answer isn't fully covered in the content, indicate what might be missing."""

        return GetPromptResult(
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ]
        )

    def _handle_summarize_article(store, arguments: dict[str, str]) -> GetPromptResult:
        """Handle summarize_article prompt."""
        article_id = arguments.get("article_id", "")
        style = arguments.get("style", "brief")
        article = store.get_article(article_id)

        if not article:
            return GetPromptResult(
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=f"Article with ID '{article_id}' not found.",
                        ),
                    )
                ]
            )

        style_instructions = {
            "brief": "Provide a 2-3 sentence summary.",
            "detailed": "Provide a comprehensive summary covering all main points.",
            "bullet-points": "Summarize as a bulleted list of key points.",
        }

        prompt_text = f"""Please summarize the following article.

**Title:** {article.title}
**Author:** {article.author}
**Category:** {article.category}

**Content:**
{article.content}

**Instructions:** {style_instructions.get(style, style_instructions['brief'])}"""

        return GetPromptResult(
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ]
        )

    def _handle_compare_articles(store, arguments: dict[str, str]) -> GetPromptResult:
        """Handle compare_articles prompt."""
        article_id_1 = arguments.get("article_id_1", "")
        article_id_2 = arguments.get("article_id_2", "")
        article_1 = store.get_article(article_id_1)
        article_2 = store.get_article(article_id_2)

        if not article_1 or not article_2:
            missing = []
            if not article_1:
                missing.append(article_id_1)
            if not article_2:
                missing.append(article_id_2)
            return GetPromptResult(
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=f"Article(s) not found: {', '.join(missing)}",
                        ),
                    )
                ]
            )

        prompt_text = f"""Compare these two articles, noting similarities and differences:

## Article 1: {article_1.title}
**Category:** {article_1.category}
**Tags:** {', '.join(article_1.tags)}

{article_1.content}

---

## Article 2: {article_2.title}
**Category:** {article_2.category}
**Tags:** {', '.join(article_2.tags)}

{article_2.content}

---

Please provide:
1. Key similarities between the articles
2. Main differences
3. Which article is better suited for which use case"""

        return GetPromptResult(
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ]
        )

    def _handle_generate_tutorial(store, arguments: dict[str, str]) -> GetPromptResult:
        """Handle generate_tutorial prompt."""
        topic = arguments.get("topic", "")
        skill_level = arguments.get("skill_level", "beginner")
        results = store.search_articles(query=topic, limit=5)

        context = ""
        if results:
            for result in results:
                article = store.get_article(result.article_id)
                if article:
                    context += f"### {article.title}\n{article.content}\n\n"

        content_text = context if context else "No specific content found."
        prompt_text = f"""Generate a {skill_level}-level tutorial about "{topic}".

Use the following knowledge base content as reference:

{content_text}

---

**Requirements:**
- Skill level: {skill_level}
- Include practical examples
- Add exercises or practice problems
- Structure with clear headings
- Include common pitfalls to avoid"""

        return GetPromptResult(
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ]
        )

    # Prompt dispatch table
    prompt_handlers = {
        "question_answer": _handle_question_answer,
        "summarize_article": _handle_summarize_article,
        "compare_articles": _handle_compare_articles,
        "generate_tutorial": _handle_generate_tutorial,
    }

    @server.get_prompt()
    async def get_prompt(
        name: str, arguments: dict[str, str] | None
    ) -> GetPromptResult:
        """
        Get a specific prompt with arguments filled in.

        Args:
            name: Which prompt to get (e.g., "summarize_article")
            arguments: User-provided values for the prompt's arguments

        Returns:
            GetPromptResult containing list of PromptMessage objects
        """
        store = get_store()
        args = arguments or {}

        handler = prompt_handlers.get(name)
        if handler:
            return handler(store, args)

        return GetPromptResult(
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=f"Unknown prompt: {name}"),
                )
            ]
        )
