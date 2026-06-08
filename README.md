# VerdictVault-AI

## Hybrid Legal Retrieval and Retrieval-Augmented Generation System for Indian Supreme Court Judgments

VerdictVault AI is a legal information retrieval and Retrieval-Augmented Generation (RAG) platform built on Indian Supreme Court judgments.

The system supports two modes of interaction:

### 1. Legal Document Retrieval
Users can search for relevant judgments and directly access the original verdict documents through stored case links.

### 2. AI-Powered Legal Research
Users can ask natural language legal questions and receive structured answers generated through Retrieval-Augmented Generation (RAG), grounded in retrieved court judgments.

This dual-mode design allows VerdictVault AI to function both as a legal search engine and as an AI-assisted legal research platform.

---

## Features

- Hybrid legal retrieval using semantic and keyword search
- Direct access to original court verdicts through case links
- AI-powered legal question answering using RAG
- Automatic extraction of filters such as year and bench
- Metadata-aware search over Supreme Court judgments
- Elasticsearch-based indexing and retrieval pipeline
- Interactive web interface for legal research
---

## User Workflows

### Workflow 1: Case Retrieval

```text
User Query
      ↓
Hybrid Retrieval
      ↓
Relevant Judgments
      ↓
Direct Case Links

Output:
Original Court Documents
```

Users can retrieve the most relevant judgments and open the original verdict documents directly.

---

### Workflow 2: AI-Powered Legal Research

```text
User Query
      ↓
Hybrid Retrieval
      ↓
Context Reconstruction
      ↓
Gemini RAG Layer
      ↓
Structured Legal Answer

Output:
Executive Summary
Key Legal Principles
Case Analysis
Conclusion
```

Users can ask legal questions in natural language and receive grounded answers generated from retrieved judgments.

---

## System Architecture

```text
Supreme Court PDFs
        │
        ▼
PDF Parsing & Cleaning
        │
        ▼
Metadata Extraction
        │
        ▼
Text Chunking
        │
        ▼
Embedding Generation
        │
        ▼
Elasticsearch Indexing
        │
        ▼
Hybrid Retrieval
(Dense + Keyword Search)
        │
        ▼
Context Reconstruction
        │
        ├──────────────► Direct Case Links
        │
        ▼
Gemini RAG Layer
        │
        ▼
Legal Analysis & Summaries
```

---

## Dataset

The system is built on a large collection of Indian Supreme Court judgments.

### Extracted Metadata

- Judgment Text
- Filename
- Year
- Bench Information
- Number of Pages

The preprocessing pipeline automatically extracts and structures metadata during PDF parsing.

---

## Document Processing Pipeline

### PDF Parsing

Judgments are parsed using PyPDF2.

The pipeline:

- Extracts text from PDF pages
- Removes Indian Kanoon watermark text
- Extracts bench information
- Detects judgment year
- Handles extraction failures gracefully

### Parallel Processing

To process large collections efficiently:

- Multi-process PDF parsing
- Incremental saving
- Year-wise partitioning
- NDJSON generation

---

## Chunking Strategy

Large judgments are split into overlapping chunks before indexing.

```text
Chunk Size    : 1000 characters
Chunk Overlap : 200 characters
```

Chunking is implemented using:

```python
RecursiveCharacterTextSplitter
```

This improves retrieval quality while preserving context.

---

## Embedding Generation

Semantic embeddings are generated using:

```text
all-mpnet-base-v2
```

Embedding dimension:

```text
768
```

Each chunk is transformed into a dense vector representation before indexing.

---

## Elasticsearch Index

Each indexed chunk stores:

```text
filename
year
bench
parent_doc_id
chunk_index
text
embedding
```

This enables both semantic retrieval and metadata-based filtering.

---

## Hybrid Retrieval Engine

VerdictVault AI combines semantic search and keyword search.

### Semantic Search

Uses:

- Sentence Transformers
- Dense Vector Embeddings
- Elasticsearch kNN Search

to retrieve conceptually relevant judgments.

### Keyword Search

Uses:

- Multi-match queries
- Fuzzy matching
- Metadata filtering

to improve retrieval precision.

### Hybrid Search

Final retrieval combines:

```text
Dense Retrieval
+
Keyword Retrieval
+
Metadata Filtering
```

This approach improves recall while maintaining relevance.

---

## Intelligent Retrieval Strategies

### Dynamic Relevance Thresholding

Instead of always returning a fixed number of documents, VerdictVault AI analyzes score drops between results and dynamically decides how many judgments should be included.

This reduces irrelevant retrievals and improves answer quality.

### Context Reconstruction

Retrieved chunks are stitched together using neighboring chunks while removing duplicated overlap regions.

This reconstructs coherent legal passages before they are passed to the RAG layer.

---

## Query Understanding

Gemini is used to automatically extract filters from natural language queries.

### Example

Query:

```text
Privacy judgments by Justice B.K. Mukherjea in 1952
```

Extracted Filters:

```json
{
  "year": "1952",
  "bench": "B.K. Mukherjea"
}
```

These filters are automatically applied during retrieval.

---

## Retrieval-Augmented Generation (RAG)

Retrieved judgments are supplied to Gemini 2.5 Flash for answer generation.

The generated responses follow a structured format:

### Executive Summary

Brief overview of the legal issue.

### Key Legal Principles

Important legal doctrines and interpretations.

### Case-by-Case Analysis

Discussion of each retrieved judgment.

### Conclusion

Final synthesized answer grounded in retrieved documents.

---

## Technologies Used

- Python
- Flask
- Elasticsearch
- Sentence Transformers
- LangChain Text Splitters
- Gemini API
- PyPDF2
- NumPy
- NDJSON

---

## Key Concepts Demonstrated

### Information Retrieval

- Elasticsearch
- Ranking Systems
- Search Pipelines

### Semantic Search

- Dense Embeddings
- Vector Similarity Search
- kNN Retrieval

### Hybrid Retrieval

- Dense Retrieval
- Keyword Retrieval
- Metadata Filtering

### Retrieval-Augmented Generation

- Context Construction
- Grounded Generation
- Legal Question Answering

### Data Engineering

- Large-Scale PDF Processing
- Metadata Extraction
- Parallel Processing Pipelines

---

please download the parsed_all.ndjson file from the below google drive link

https://drive.google.com/file/d/1pYw5oIvGBhdda_6RNDLlHw69J6pVsogm/view?usp=sharing

add your API key in .env file

The project demonstrates how modern retrieval systems and large language models can be combined to build a practical legal search and AI-assisted research platform.