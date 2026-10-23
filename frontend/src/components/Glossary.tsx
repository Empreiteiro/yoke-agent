"use client";

import { BookOpen, Layers, Search, Ruler, BarChart3, Target, Brain, Sparkles, ShieldCheck } from "lucide-react";

const sections = [
  {
    title: "About Yoke — Poka-Yoke for AI",
    icon: ShieldCheck,
    items: [
      {
        term: "Poka-Yoke (ポカヨケ)",
        description:
          "Japanese term coined by Shigeo Shingo at Toyota, literally meaning \"mistake-proofing\" (poka = inadvertent error, yokeru = to avoid). It describes any mechanism in a manufacturing process that prevents a human operator from making mistakes — the classic example being a socket shaped so the plug only fits one way. A Poka-Yoke doesn't detect errors after they happen; it stops them from being possible in the first place.",
      },
      {
        term: "Why \"Yoke Agent\"",
        description:
          "Yoke Agent applies the Poka-Yoke philosophy to AI systems. Shipping a RAG pipeline or agent means choosing dozens of hyperparameters — chunk size, embedding model, Top-K, temperature, prompts, tool schemas, scenarios — and every bad choice silently degrades quality in production. Instead of hoping you picked well, Yoke Agent lets you grid-search every combination, evaluate them with reproducible metrics (RAGAS for RAG, G-Eval rubrics for agents), and promote only the configuration that objectively wins. The platform is the mistake-proofing jig for your AI: it makes it hard to ship a worse configuration than the one you measured.",
      },
      {
        term: "AI Quality Studio",
        description:
          "The product positioning: Yoke Agent is an AI Quality Studio with two complementary workbenches. The RAG workbench optimizes retrieval pipelines through dataset generation, hyperparameter grid search, and RAGAS evaluation. The Agent workbench stress-tests LLM agents against scenario libraries (tool use, decision paths, response quality, guardrails) and scores their behavior with an LLM-as-judge. Both flows end the same way — with a ranked leaderboard and an LLM-generated improvement report — so you always know which configuration to ship and why.",
      },
    ],
  },
  {
    title: "RAG Hyperparameters",
    icon: Layers,
    items: [
      {
        term: "Chunk Size",
        description:
          "The number of characters (or tokens) each text fragment contains after splitting the source document. Smaller chunks improve retrieval precision for specific questions, while larger chunks preserve more surrounding context. Typical values range from 256 to 2048.",
      },
      {
        term: "Chunk Overlap",
        description:
          "The percentage of each chunk that overlaps with the next one. Overlap prevents important information from being cut at chunk boundaries. For example, 20% overlap on a 1000-character chunk means the last 200 characters of one chunk appear at the start of the next.",
      },
      {
        term: "Embedding Model",
        description:
          "The neural network that converts text into dense numerical vectors (embeddings). Different models produce vectors of different sizes (dimensions) and capture semantic meaning with varying quality. Popular choices include OpenAI's text-embedding-3-small (1536d) and text-embedding-3-large (3072d).",
      },
      {
        term: "Embedding Dimensions",
        description:
          "The size of the output vector produced by the embedding model. Some models (like OpenAI's text-embedding-3 family) support reducing dimensions at query time to save storage and speed up search, with a trade-off in semantic accuracy. Lower dimensions = faster but less precise.",
      },
      {
        term: "Top-K",
        description:
          "The number of most similar document chunks retrieved for each query. A higher K provides more context to the LLM but may introduce noise from less relevant chunks. A lower K is more focused but risks missing important information spread across multiple chunks.",
      },
      {
        term: "Search Type",
        description:
          "The algorithm used to find relevant chunks. 'Vector' performs pure semantic similarity search. 'MMR' (Maximum Marginal Relevance) balances relevance with diversity to avoid redundant results. 'Hybrid' combines vector search with keyword matching (BM25) for broader coverage.",
      },
      {
        term: "Distance Metric",
        description:
          "The mathematical function used to measure how similar two embedding vectors are. 'Cosine' measures the angle between vectors (most common, works well with normalized embeddings). 'L2' (Euclidean) measures straight-line distance. 'IP' (Inner Product) is similar to cosine but without normalization.",
      },
    ],
  },
  {
    title: "Chunking Strategies",
    icon: Search,
    items: [
      {
        term: "Recursive Character",
        description:
          "Splits text using a hierarchy of separators (paragraphs, line breaks, sentences, words). Tries the largest separator first, then falls back to smaller ones. This is the most common strategy and works well for general-purpose text.",
      },
      {
        term: "Token-based",
        description:
          "Splits text by counting tokens (subword units used by LLMs) rather than characters. Ensures each chunk fits exactly within a model's context window. More precise than character-based splitting for LLM consumption.",
      },
      {
        term: "Semantic Chunking",
        description:
          "Uses an embedding model to group semantically similar sentences together. Instead of splitting at fixed sizes, it creates chunks that represent coherent topics. Better for documents where topics don't follow a regular structure.",
      },
    ],
  },
  {
    title: "Advanced Retrieval Strategies",
    icon: Sparkles,
    items: [
      {
        term: "Multi-Query RAG",
        description:
          "Instead of searching with the original question only, an LLM generates N alternative formulations (e.g., 3-5 paraphrases) and retrieves documents for each one. All results are merged using Reciprocal Rank Fusion (RRF) to produce a single ranked list. This overcomes vocabulary mismatch between the question and the source documents, significantly improving recall. Cost impact: one extra LLM call per question for query generation. Reference: LangChain MultiQueryRetriever, RAG Fusion paper (arXiv:2402.03367).",
      },
      {
        term: "Agentic RAG",
        description:
          "An LLM agent dynamically decides the retrieval strategy per question instead of following a fixed retrieve-then-generate pipeline. The agent has access to tools: retrieve (semantic search), retrieve_mmr (diverse search), decompose_question (break complex questions into sub-questions), reformulate_query (rewrite queries for better retrieval), and evaluate_relevance (check if retrieved docs are useful). The agent loops until it has enough context or reaches the max steps limit. Multi-hop questions show significant improvement with this approach. Cost impact: multiple LLM calls per question (one per agent step). Reference: LangGraph Agentic RAG tutorial, Adaptive RAG paper (arXiv:2403.14403).",
      },
      {
        term: "HyDE (Hypothetical Document Embeddings)",
        description:
          "Instead of embedding the question directly, HyDE first generates a hypothetical answer via LLM, then embeds that hypothesis for similarity search. The hypothesis is semantically closer to actual document passages than the short question, dramatically improving retrieval recall for complex queries. Adds one LLM call per question. Reference: HyDE paper (arXiv:2212.10496).",
      },
      {
        term: "Corrective RAG (CRAG)",
        description:
          "After retrieving documents, an LLM grades their relevance to the question. If documents are irrelevant, the query is reformulated and retrieval is retried (up to a configurable max). This self-correcting loop ensures the generation step receives high-quality context. Key parameters: relevance threshold (0-1) and max retries. Reference: CRAG paper (arXiv:2401.15884).",
      },
      {
        term: "Self-RAG",
        description:
          "The LLM decides whether retrieval is even needed for each question. For factual queries it retrieves and validates context; for general knowledge it can answer directly. After retrieval, it grades document relevance and may switch to MMR search for diversity. This adaptive approach avoids unnecessary retrieval while ensuring quality for complex questions. Reference: Self-RAG paper (arXiv:2310.11511).",
      },
      {
        term: "RAPTOR",
        description:
          "Recursive Abstractive Processing for Tree-Organized Retrieval. Builds a hierarchical tree of summaries: original chunks at the bottom, clustered summaries at each level above. Retrieval can search all levels (collapsed), traverse from top down (tree traversal), or target specific levels. Excellent for documents with thematic structure. Reference: RAPTOR paper (arXiv:2401.18059).",
      },
      {
        term: "CAG (Cache-Augmented Generation)",
        description:
          "Loads the entire document into the LLM context window instead of chunking, embedding, and retrieving. Serves as a baseline comparison: if CAG outperforms RAG, the retrieval configuration needs improvement. If RAG matches CAG at lower cost, the pipeline is well-tuned. Expensive per question but eliminates all retrieval errors. Reference: CAG paper (arXiv:2404.12457).",
      },
      {
        term: "Reciprocal Rank Fusion (RRF)",
        description:
          "A simple and effective algorithm for merging multiple ranked result lists into a single ranking. For each document, the RRF score is calculated as the sum of 1/(k + rank) across all lists where it appears, where k is a constant (typically 60). Documents are then sorted by their fused score. RRF is used by Multi-Query RAG to combine results from different query formulations without requiring score normalization across retrieval runs.",
      },
    ],
  },
  {
    title: "RAGAS Evaluation Metrics",
    icon: BarChart3,
    items: [
      {
        term: "Faithfulness",
        description:
          "Measures whether the generated answer is factually consistent with the retrieved context. A high faithfulness score means the LLM did not hallucinate or add information not present in the provided chunks. This is computed by breaking the answer into individual claims and verifying each against the context.",
      },
      {
        term: "Answer Relevancy",
        description:
          "Evaluates how relevant the generated answer is to the original question. An answer can be factually correct but not address what was asked. This metric generates hypothetical questions from the answer and measures their similarity to the original question. Higher scores indicate the answer directly addresses the query.",
      },
      {
        term: "Context Precision",
        description:
          "Measures the signal-to-noise ratio in the retrieved chunks. A high precision means most of the retrieved context was actually useful for answering the question. Low precision indicates the retrieval returned many irrelevant chunks alongside the relevant ones.",
      },
      {
        term: "Context Recall",
        description:
          "Evaluates whether all the information needed to answer the question was successfully retrieved. It compares the retrieved context against the ground truth answer to check if key facts are present. Low recall means important information was missed during retrieval.",
      },
    ],
  },
  {
    title: "Optional Metrics",
    icon: Target,
    items: [
      {
        term: "Answer Similarity",
        description:
          "Measures the semantic similarity between the generated answer and the ground truth (expected answer). Uses embedding-based comparison to capture meaning rather than exact wording. Useful when there are multiple valid ways to phrase a correct answer.",
      },
      {
        term: "Answer Correctness",
        description:
          "A composite metric that combines factual correctness (does the answer contain the right facts?) with semantic similarity. It decomposes both the generated and ground truth answers into individual statements and checks for overlap. Provides a more complete picture than similarity alone.",
      },
    ],
  },
  {
    title: "Interpreting Results",
    icon: Ruler,
    items: [
      {
        term: "Overall Score",
        description:
          "The average of the four core metrics (Faithfulness, Answer Relevancy, Context Precision, Context Recall). Provides a single number to compare configurations. Scores above 80% are generally strong; below 60% indicates significant room for improvement.",
      },
      {
        term: "What to optimize first",
        description:
          "If Context Recall is low, your chunks are too small or Top-K is too low — the system can't find the right information. If Context Precision is low, try smaller chunks or a better embedding model. If Faithfulness is low, the LLM is hallucinating — provide more focused context. If Relevancy is low, the LLM isn't answering the actual question.",
      },
    ],
  },
];

export default function Glossary() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-primary">Concepts & Glossary</h2>
        <p className="text-sm text-t-secondary mt-1">
          Understand the hyperparameters and evaluation metrics used in RAG optimization
        </p>
      </div>

      {sections.map((section) => {
        const SectionIcon = section.icon;
        return (
          <div
            key={section.title}
            className="bg-surface-100 rounded-2xl border border-themed p-6"
          >
            <div className="flex items-center gap-3 mb-5">
              <div className="w-9 h-9 rounded-xl bg-accent/10 flex items-center justify-center">
                <SectionIcon className="w-4.5 h-4.5 text-accent" />
              </div>
              <h3 className="text-lg font-semibold text-primary">{section.title}</h3>
            </div>

            <div className="space-y-4">
              {section.items.map((item) => (
                <div key={item.term} className="pl-4 border-l-2 border-accent/20">
                  <h4 className="text-sm font-semibold text-primary mb-1">{item.term}</h4>
                  <p className="text-sm text-t-secondary leading-relaxed">{item.description}</p>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
