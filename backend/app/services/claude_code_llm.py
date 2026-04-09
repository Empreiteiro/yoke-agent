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

# Module-level token storage (outside the Pydantic model to avoid ModelPrivateAttr issues)
_claude_runtime_token: str | None = None


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

    # ── Token management & auth ─────────────────────────────────────────

    @classmethod
    def save_token(cls, token: str) -> None:
        """Save an OAuth token at runtime (persists for the process lifetime)
        and also write it to ~/.claude/.credentials.json for persistence across restarts."""
        global _claude_runtime_token
        _claude_runtime_token = token
        creds_path = Path.home() / ".claude" / ".credentials.json"
        creds_path.parent.mkdir(parents=True, exist_ok=True)
        # Merge with existing credentials if present
        existing = {}
        if creds_path.exists():
            try:
                existing = json.loads(creds_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        existing["oauthToken"] = token
        creds_path.write_text(json.dumps(existing, indent=2))
        logger.info("Claude Code OAuth token saved to %s", creds_path)

    @classmethod
    def get_status(cls) -> dict:
        """Check whether the Claude CLI is installed and authenticated."""
        result = {"installed": False, "binary_path": None, "authenticated": False, "error": None}
        try:
            binary = cls._find_claude_binary()
            result["installed"] = True
            result["binary_path"] = binary
        except FileNotFoundError as e:
            result["error"] = str(e)
            return result

        # Check if we have a token from any source
        has_token = bool(
            _claude_runtime_token
            or os.environ.get("RAG_CLAUDE_CODE_TOKEN")
            or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        )
        if not has_token:
            creds_path = Path.home() / ".claude" / ".credentials.json"
            if creds_path.exists():
                try:
                    creds = json.loads(creds_path.read_text())
                    has_token = bool(creds.get("oauthToken"))
                except (json.JSONDecodeError, OSError):
                    pass

        result["authenticated"] = has_token
        if not has_token:
            result["error"] = "No OAuth token found. Please authenticate via the UI or run 'claude login' in a terminal."
        return result

    @staticmethod
    def _get_cli_env() -> dict:
        """Build environment variables for the CLI subprocess."""
        env = {**os.environ}

        # 1. Runtime token saved via the UI (highest priority)
        if _claude_runtime_token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = _claude_runtime_token
            return env

        # 2. Explicit env var set by the user
        explicit_token = os.environ.get("RAG_CLAUDE_CODE_TOKEN")
        if explicit_token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = explicit_token
            return env

        # 3. Inherited from parent (e.g. Claude Desktop)
        if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            return env

        # 4. Credentials file
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
