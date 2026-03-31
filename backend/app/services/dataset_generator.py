"""LLM-powered evaluation dataset generation from documents."""

import json
import random
import math
from typing import List, Dict, Optional

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

from app.services.llm_factory import get_llm, _resolve_provider
from app.services.token_tracker import log_llm_response


SYSTEM_PROMPT = """You are an expert at creating evaluation questions for testing information retrieval systems.

Your task is to generate realistic question-answer pairs based on the provided text. Follow these rules strictly:

1. Write questions as a real person would naturally ask them — conversational, direct, and without referencing "the text", "the document", "the passage", "the author mentions", etc.
2. Questions should sound like someone who NEEDS the information but hasn't read the source material.
3. Vary question types: factual (who, what, when, where), causal (why, how), comparative, and analytical.
4. Vary difficulty: mix simple factual recall with questions that require connecting multiple pieces of information.
5. Answers must be grounded in the provided text — do not invent facts.
6. Each answer should be concise but complete (1-3 sentences).

BAD examples (do NOT generate questions like these):
- "What does the author say about X?" (references the document)
- "According to the text, what is Y?" (references the text)
- "What is mentioned in chapter 3?" (references structure)

GOOD examples:
- "What are the main causes of X?"
- "How does Y work?"
- "Who was responsible for Z and why?"
- "What is the relationship between A and B?"

Return a JSON array where each object has:
- "question": the natural question
- "ground_truth": the correct answer based on the text
- "context": the exact passage(s) from the text that support the answer"""

USER_PROMPT_TEMPLATE = """Generate {num_questions} diverse question-answer pairs from the following content.
{language_instruction}
Content:
{content}

Return ONLY a valid JSON array. Each object must have "question", "ground_truth", and "context" fields."""

# Target ~5 questions per batch to keep quality high
QUESTIONS_PER_BATCH = 5
# Maximum characters per batch sent to LLM
BATCH_CHAR_LIMIT = 6000


def _estimate_questions_for_content(total_chars: int) -> int:
    """Estimate a reasonable number of questions based on content size."""
    # Roughly 1 question per 1500 chars of content, minimum 5, max 100
    estimated = max(5, total_chars // 1500)
    return min(estimated, 100)


def _split_into_batches(documents: List[Document], max_chars: int = BATCH_CHAR_LIMIT) -> List[str]:
    """Split documents into batches suitable for LLM processing."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chars,
        chunk_overlap=200,
        length_function=len,
        separators=["\n\n\n", "\n\n", "\n", ". ", " "],
    )

    # Combine all document content
    full_text = "\n\n---\n\n".join(doc.page_content for doc in documents)
    chunks = splitter.split_text(full_text)
    return chunks


def _select_pages(documents: List[Document], max_pages: int, randomize: bool = True) -> List[Document]:
    """Select a subset of document pages for processing.

    Args:
        documents: All document pages/chunks from the loader
        max_pages: Maximum number of pages to process
        randomize: If True, select random pages; if False, take first N pages
    """
    if len(documents) <= max_pages:
        return documents

    if randomize:
        return random.sample(documents, max_pages)
    else:
        return documents[:max_pages]


async def generate_qa_pairs(
    documents: List[Document],
    db: Session,
    num_questions: Optional[int] = None,
    provider_id: Optional[int] = None,
    model: Optional[str] = None,
    reading_mode: str = "full",
    max_pages: Optional[int] = None,
    language: str = "auto",
) -> tuple[List[Dict[str, str]], List[Dict]]:
    """Generate Q&A evaluation pairs from documents using an LLM.

    Args:
        documents: Source documents to generate questions from
        db: Database session
        num_questions: Number of questions to generate (None = auto-calculate)
        provider_id: Optional LLM provider ID
        model: Optional model name
        reading_mode: "full" to read all pages, "partial" to read a subset
        max_pages: When reading_mode="partial", max pages to read (random selection)
    """
    provider = _resolve_provider(db, provider_id, capability="llm")
    # Ollama models often ignore JSON format instructions — use native JSON mode to enforce it
    ollama_format = "json" if provider.provider_type == "ollama" else None
    llm = get_llm(db, provider_id=provider_id, model=model, temperature=0.3, format=ollama_format)

    # Apply page selection
    sampled_pages_info: List[Dict] = []
    if reading_mode == "partial" and max_pages and max_pages > 0:
        docs_to_process = _select_pages(documents, max_pages, randomize=True)
        for doc in docs_to_process:
            sampled_pages_info.append({
                "source": doc.metadata.get("source", ""),
                "page": doc.metadata.get("page", None),
                "preview": doc.page_content[:300],
            })
    else:
        docs_to_process = documents

    # Split content into processable batches
    batches = _split_into_batches(docs_to_process)

    if not batches:
        return []

    # Auto-calculate question count if not specified
    total_chars = sum(len(b) for b in batches)
    if num_questions is None:
        num_questions = _estimate_questions_for_content(total_chars)

    # Distribute questions across batches
    questions_per_batch = max(2, math.ceil(num_questions / len(batches)))
    remaining_questions = num_questions

    # Build language instruction
    if language and language != "auto":
        language_instruction = f"\nIMPORTANT: Write ALL questions and answers in {language}.\n"
    else:
        language_instruction = "\nWrite questions and answers in the same language as the content.\n"

    all_pairs = []
    for batch_content in batches:
        if remaining_questions <= 0:
            break

        batch_q_count = min(questions_per_batch, remaining_questions)

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=USER_PROMPT_TEMPLATE.format(
                    num_questions=batch_q_count,
                    language_instruction=language_instruction,
                    content=batch_content,
                )
            ),
        ]

        try:
            response = await llm.ainvoke(messages)

            # Log token usage
            try:
                log_llm_response(
                    db=db,
                    response=response,
                    operation="dataset_generation",
                    provider_name=provider.name,
                    model_name=model or provider.default_llm_model or "unknown",
                    metadata={
                        "batch": len(all_pairs) // questions_per_batch + 1,
                        "questions_requested": batch_q_count,
                    },
                )
            except Exception:
                pass

            pairs = _parse_llm_response(response.content)
            all_pairs.extend(pairs)
            remaining_questions -= len(pairs)

        except Exception as e:
            # Log error but continue with other batches
            import logging
            logging.getLogger(__name__).warning(f"Batch generation failed: {e}")
            continue

    return all_pairs, sampled_pages_info


def _parse_llm_response(content: str) -> List[Dict[str, str]]:
    """Parse JSON Q&A pairs from LLM response, handling markdown code blocks."""
    import re
    content = content.strip()

    # Strip markdown code fences (anywhere in the string, not just at start)
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if fence_match:
        content = fence_match.group(1).strip()
    else:
        # Fallback: strip leading ``` if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

    try:
        pairs = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            pairs = json.loads(content[start:end])
        else:
            raise ValueError(f"Failed to parse LLM response as JSON. Response: {content[:200]!r}")

    # If model returned a dict wrapping the array (e.g. {"questions": [...]}), unwrap it
    if isinstance(pairs, dict):
        # Find the first list value
        list_value = next((v for v in pairs.values() if isinstance(v, list)), None)
        if list_value is not None:
            pairs = list_value
        else:
            # Single Q&A object — wrap it
            pairs = [pairs]

    if not isinstance(pairs, list):
        raise ValueError(f"Expected JSON array, got {type(pairs).__name__}")

    # Filter out any non-dict items (e.g. Ollama returning strings instead of objects)
    valid_pairs = [p for p in pairs if isinstance(p, dict)]
    if not valid_pairs and pairs:
        raise ValueError(f"JSON array contained no objects (got {type(pairs[0]).__name__})")

    return valid_pairs
