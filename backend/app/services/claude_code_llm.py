"""
LangChain-compatible ChatModel that wraps the Claude Code CLI binary as a subprocess.

Usage:
    llm = ChatClaudeCode()
    response = await llm.ainvoke([HumanMessage(content="Hello")])
"""
import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, AsyncIterator, Iterator, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

logger = logging.getLogger(__name__)


class ChatClaudeCode(BaseChatModel):
    """Chat model that invokes the Claude CLI binary as a subprocess."""

    model_name: str = "claude-code"
    temperature: float = 0.0  # kept for interface compatibility

    @property
    def _llm_type(self) -> str:
        return "claude-code-cli"

    @property
    def _identifying_params(self) -> dict:
        return {"model_name": self.model_name}

    # ── Binary discovery ──────────────────────────────────────────────

    @staticmethod
    def _find_claude_binary() -> str:
        """Locate the claude CLI binary."""
        # 1. Check PATH
        found = shutil.which("claude")
        if found:
            return found

        # 2. macOS Claude Desktop bundle
        support_dir = Path.home() / "Library" / "Application Support" / "Claude" / "claude-code"
        if support_dir.exists():
            for version_dir in sorted(support_dir.iterdir(), reverse=True):
                candidate = version_dir / "claude.app" / "Contents" / "MacOS" / "claude"
                if candidate.exists():
                    return str(candidate)

        # 3. Common install paths
        for path in ["/usr/local/bin/claude", "/opt/homebrew/bin/claude"]:
            if Path(path).exists():
                return path

        raise FileNotFoundError(
            "Claude CLI binary not found. Install Claude Code CLI or ensure 'claude' is in your PATH."
        )

    # ── Auth environment ──────────────────────────────────────────────

    @staticmethod
    def _get_cli_env() -> dict:
        """Build environment variables for the CLI subprocess.

        The Claude CLI authenticates via an OAuth token. It looks for the token
        in this order:
        1. CLAUDE_CODE_OAUTH_TOKEN env var (inherited from parent or set explicitly)
        2. Its own stored credentials from `claude login`

        When launched from Claude Desktop, the parent process sets
        CLAUDE_CODE_OAUTH_TOKEN — we inherit it. When launched from a standalone
        terminal, the user must run `claude login` first.
        """
        env = {**os.environ}

        # If an explicit token is set via RAG_CLAUDE_CODE_TOKEN, use that
        explicit_token = os.environ.get("RAG_CLAUDE_CODE_TOKEN")
        if explicit_token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = explicit_token
            return env

        # Otherwise inherit CLAUDE_CODE_OAUTH_TOKEN from parent if available
        # (e.g. when backend is launched from Claude Desktop or a session that has it)
        if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            return env

        # Try to read from the credentials file created by `claude login`
        creds_path = Path.home() / ".claude" / ".credentials.json"
        if creds_path.exists():
            try:
                creds = json.loads(creds_path.read_text())
                if isinstance(creds, dict) and creds.get("oauthToken"):
                    env["CLAUDE_CODE_OAUTH_TOKEN"] = creds["oauthToken"]
            except (json.JSONDecodeError, KeyError):
                pass

        return env

    # ── Message conversion ────────────────────────────────────────────

    @staticmethod
    def _messages_to_prompt(messages: List[BaseMessage]) -> str:
        """Convert LangChain messages into a single prompt string for the CLI."""
        parts = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                parts.append(f"System: {msg.content}")
            elif isinstance(msg, HumanMessage):
                parts.append(f"Human: {msg.content}")
            elif isinstance(msg, AIMessage):
                parts.append(f"Assistant: {msg.content}")
            else:
                parts.append(str(msg.content))
        return "\n\n".join(parts)

    # ── Sync generation (required by BaseChatModel) ───────────────────

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Synchronous generation — runs the async version in a new event loop."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an async context — create a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    asyncio.run, self._agenerate(messages, stop=stop)
                ).result()
            return result
        else:
            return asyncio.run(self._agenerate(messages, stop=stop))

    # ── Async generation ──────────────────────────────────────────────

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Invoke claude CLI and return the complete text response."""
        binary = self._find_claude_binary()
        prompt = self._messages_to_prompt(messages)
        env = self._get_cli_env()

        proc = await asyncio.create_subprocess_exec(
            binary, "-p", prompt, "--output-format", "text",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_text = stderr.decode().strip() if stderr else ""
            out_text = stdout.decode().strip() if stdout else ""
            # The CLI sometimes writes errors to stdout
            error_msg = err_text or out_text or f"CLI exited with code {proc.returncode}"
            if "Not logged in" in error_msg or "login" in error_msg.lower():
                raise RuntimeError(
                    "Claude CLI is not authenticated. Please run 'claude login' in your terminal first."
                )
            raise RuntimeError(f"Claude CLI error: {error_msg}")

        text = stdout.decode().strip()
        message = AIMessage(content=text)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    # ── Async streaming ───────────────────────────────────────────────

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """Stream tokens from claude CLI using --output-format stream-json."""
        binary = self._find_claude_binary()
        prompt = self._messages_to_prompt(messages)
        env = self._get_cli_env()

        proc = await asyncio.create_subprocess_exec(
            binary, "-p", prompt, "--output-format", "stream-json", "--verbose",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        buffer = ""
        while True:
            chunk = await proc.stdout.read(4096)
            if not chunk:
                break
            buffer += chunk.decode()

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                text = self._extract_text_from_stream(data)
                if text:
                    chunk_msg = ChatGenerationChunk(
                        message=AIMessageChunk(content=text)
                    )
                    if run_manager:
                        await run_manager.on_llm_new_token(text)
                    yield chunk_msg

        await proc.wait()
        if proc.returncode and proc.returncode != 0:
            stderr_bytes = await proc.stderr.read() if proc.stderr else b""
            err_text = stderr_bytes.decode().strip()
            if "Not logged in" in err_text or "login" in err_text.lower() or "Not logged in" in buffer:
                raise RuntimeError(
                    "Claude CLI is not authenticated. Please run 'claude login' in your terminal, "
                    "or start the backend from within Claude Desktop so it inherits the auth token."
                )

    @staticmethod
    def _extract_text_from_stream(data: dict) -> str:
        """Extract text content from a stream-json event."""
        msg_type = data.get("type", "")

        # assistant message with content blocks
        if msg_type == "assistant":
            content = data.get("message", {}).get("content", [])
            texts = [block.get("text", "") for block in content if block.get("type") == "text"]
            return "".join(texts)

        # incremental content delta
        if msg_type == "content_block_delta":
            delta = data.get("delta", {})
            return delta.get("text", "")

        # final result
        if msg_type == "result":
            return data.get("result", "")

        return ""
