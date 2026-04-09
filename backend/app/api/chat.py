"""
AI Chat Assistant endpoint — streams responses via SSE using the default LLM provider.
"""
import json
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.chat import ChatRequest
from app.services.llm_factory import get_llm

logger = logging.getLogger(__name__)

router = APIRouter()

SYSTEM_PROMPT = """\
You are the AI assistant for the RAG Optimization Pipeline platform. \
This platform helps users systematically optimize Retrieval-Augmented Generation (RAG) \
pipelines through hyperparameter grid search and RAGAS evaluation.

Here is what users can do on this platform, step by step:

1. **Upload Documents** — Upload PDF, TXT, DOCX, MD, MDX, or CSV files as the knowledge base.
2. **Generate Dataset** — An LLM analyzes the documents and generates question-answer pairs for evaluation.
3. **Review & Approve** — Review, edit, add, or remove Q&A pairs. Import additional items from JSON.
4. **Grid Search Config** — Name the experiment and configure RAG hyperparameters: chunk sizes, overlap, \
embedding models, top-k values, search types, retrieval strategies (vector, HyDE, CRAG, Self-RAG, RAPTOR, \
multi-query, agentic, MMR, hybrid, CAG), and LLM models.
5. **Run Experiments** — Execute all grid search combinations with RAGAS evaluation metrics \
(faithfulness, answer relevance, context precision, context recall).
6. **Results & Report** — View rankings, compare configurations side-by-side, and analyze which settings \
performed best. Export results as CSV.

Additional platform features:
- **Collections** — Save and query the best vector store collections from completed experiments.
- **Providers** — Configure LLM providers: OpenAI, Anthropic, Google Gemini, Cohere, Ollama (local), \
Azure OpenAI, HuggingFace, Claude Code CLI, or custom OpenAI-compatible endpoints.
- **Vector Stores** — Configure vector store backends (ChromaDB, Qdrant, Pinecone, Weaviate, Milvus).
- **History** — View and manage past experiments.
- **Logs** — Monitor token usage and costs across all operations.
- **Concepts (Glossary)** — Learn about RAG concepts and evaluation metrics.

Help users understand how to use the platform, explain RAG concepts, suggest optimal configurations, \
and guide them through the pipeline. Be concise and actionable. Answer in the same language the user \
writes to you.\
"""


async def _stream_chat(db: Session, request: ChatRequest):
    """Async generator that yields SSE events."""
    try:
        llm = get_llm(
            db,
            provider_id=request.provider_id,
            model=request.model,
            temperature=0.3,
        )

        # Build LangChain message list
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        lc_messages = [SystemMessage(content=SYSTEM_PROMPT)]
        for msg in request.messages:
            if msg.role == "user":
                lc_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                lc_messages.append(AIMessage(content=msg.content))

        # Try streaming first, fall back to invoke
        try:
            async for chunk in llm.astream(lc_messages):
                text = chunk.content if hasattr(chunk, "content") else str(chunk)
                if text:
                    yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"
        except (NotImplementedError, AttributeError):
            # Provider doesn't support streaming — send full response at once
            response = await llm.ainvoke(lc_messages)
            text = response.content if hasattr(response, "content") else str(response)
            yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except ValueError as e:
        # No provider configured
        logger.warning("Chat: no provider configured — %s", e)
        msg = (
            "No LLM provider configured or active. "
            "Go to **Settings → Providers** and add a provider "
            "(OpenAI, Anthropic, Ollama, Claude Code CLI, etc.) before using the chat."
        )
        yield f"data: {json.dumps({'type': 'error', 'content': msg})}\n\n"

    except Exception as e:
        logger.exception("Chat stream error")
        error_str = str(e)
        # Provide user-friendly messages for common errors
        if "ConnectError" in error_str or "nodename nor servname" in error_str:
            msg = (
                "Could not connect to the LLM provider. "
                "Check that your provider's API key and base URL are correct "
                "in **Settings → Providers**, or try a different provider."
            )
        elif "APIConnectionError" in error_str:
            msg = (
                "Connection to the LLM API failed. "
                "Verify your internet connection and provider settings."
            )
        elif "AuthenticationError" in error_str or "401" in error_str:
            msg = (
                "Authentication failed. "
                "Check your API key in **Settings → Providers**."
            )
        else:
            msg = f"An error occurred: {error_str}"
        yield f"data: {json.dumps({'type': 'error', 'content': msg})}\n\n"


@router.post("/stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    """Stream chat responses as Server-Sent Events."""
    return StreamingResponse(
        _stream_chat(db, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
