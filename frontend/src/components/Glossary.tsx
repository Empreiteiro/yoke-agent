"use client";

import { BookOpen, Layers, Search, Ruler, BarChart3, Target } from "lucide-react";

const sections = [
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
            className="bg-surface-100 rounded-2xl border border-surface-200/50 p-6"
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
