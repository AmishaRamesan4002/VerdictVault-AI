# query_data.py
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
import sys

# ---------------- CONFIGURATION ----------------
es = Elasticsearch("http://localhost:9200")
INDEX_NAME = "legal_documents"

# RAG Configuration
try:
    # Load model once at startup
    print("Loading embedding model... (this may take a few seconds)")
    EMBEDDING_MODEL = SentenceTransformer('all-mpnet-base-v2')
except Exception as e:
    print(f"Error loading model: {e}. Make sure sentence-transformers is installed.")
    sys.exit(1)

CHUNK_OVERLAP = 200       # Must match your indexing config
MAX_WORD_LIMIT = 15000    # Limit for fetching full document
NEIGHBOR_WINDOW = 2       # Fallback: chunks before/after to fetch if doc is too big
MAX_DOCS_TO_PROCESS = 3   # Top N documents to return

# ---------------- HELPER FUNCTIONS ----------------

def clean_and_stitch_text(chunks):
    """Joins chunks and removes the overlapping characters."""
    if not chunks: return ""
    
    full_text = ""
    last_index = -1
    
    for hit in chunks:
        src = hit['_source']
        current_index = src['chunk_index']
        text = src['text']
        
        if last_index == -1:
            full_text += text
        else:
            if current_index == last_index + 1:
                # Remove overlap
                text_to_add = text[CHUNK_OVERLAP:] if len(text) > CHUNK_OVERLAP else text
                full_text += text_to_add
            else:
                # Gap handling
                full_text += "\n\n[...Gap...]\n\n" + text
        last_index = current_index
    return full_text

def get_chunks_from_es(parent_id, strategy="all", start=0, end=0):
    """Fetches chunks based on strategy (all vs window)."""
    must_clauses = [{"term": {"parent_doc_id": parent_id}}]
    
    if strategy == "window":
        must_clauses.append({
            "range": {
                "chunk_index": {
                    "gte": max(0, start),
                    "lte": end
                }
            }
        })

    # Optimized to check size first if getting all
    if strategy == "all":
        count_res = es.count(index=INDEX_NAME, query={"bool": {"must": must_clauses}})
        if count_res['count'] > 85: # Approx 16k words threshold
            return None

    response = es.search(
        index=INDEX_NAME,
        size=1000, # Max chunks to retrieve
        query={"bool": {"must": must_clauses}},
        sort=[{"chunk_index": {"order": "asc"}}],
        _source=["chunk_index", "text"]
    )
    return response['hits']['hits']

# ---------------- MAIN SEARCH FUNCTION ----------------

def search_judgments(query_text=None, year=None, bench=None):
    # 1. Build Filters (Shared by both Vector and Keyword search)
    filter_clauses = []
    if year:
        filter_clauses.append({"term": {"year": year}})
    if bench:
        filter_clauses.append({"match": {"bench": bench}})

    # 2. Perform Search (Hybrid if text exists, Filter-only if not)
    if query_text:
        query_vector = EMBEDDING_MODEL.encode(query_text).tolist()
        
        # Hybrid Query: kNN + Keyword Match
        response = es.search(
            index=INDEX_NAME,
            size=20, # Get enough seed chunks to group
            knn={
                "field": "embeddings",
                "query_vector": query_vector,
                "k": 20,
                "num_candidates": 100,
                "filter": filter_clauses # Apply filters to vector search
            },
            query={
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": query_text,
                            "fields": ["text", "bench", "filename"],
                            "boost": 0.3
                        }
                    },
                    "filter": filter_clauses # Apply filters to keyword search
                }
            },
            _source=["parent_doc_id", "chunk_index", "filename", "year", "bench", "_score"]
        )
    else:
        # Metadata only search (No vector)
        body = {"query": {"bool": {"filter": filter_clauses}}} if filter_clauses else {"query": {"match_all": {}}}
        response = es.search(index=INDEX_NAME, body=body, size=20)

    print(f"\n Search results for query: '{query_text or ''}', Year: '{year or ''}', Bench: '{bench or ''}'")

    # 3. Group Chunks by Parent Document
    parent_docs = {}
    for hit in response["hits"]["hits"]:
        src = hit["_source"]
        p_id = src.get("parent_doc_id")
        if p_id is None: continue # Skip if old data format
        
        if p_id not in parent_docs:
            parent_docs[p_id] = {
                "min_idx": src.get('chunk_index', 0), 
                "max_idx": src.get('chunk_index', 0),
                "score": hit['_score'],
                "metadata": src # Store full metadata
            }
        else:
            # Expand range and accumulate score
            parent_docs[p_id]["min_idx"] = min(parent_docs[p_id]["min_idx"], src.get('chunk_index', 0))
            parent_docs[p_id]["max_idx"] = max(parent_docs[p_id]["max_idx"], src.get('chunk_index', 0))
            parent_docs[p_id]["score"] += hit['_score']

    # 4. Process Top Results (Stitch & Deduplicate)
    results = []
    
    # Sort by score and take top N
    sorted_parents = sorted(parent_docs.items(), key=lambda item: item[1]['score'], reverse=True)[:MAX_DOCS_TO_PROCESS]

    for p_id, info in sorted_parents:
        meta = info['metadata']
        final_content = ""
        
        # Strategy A: Try Full Document
        all_chunks = get_chunks_from_es(p_id, strategy="all")
        
        if all_chunks:
            full_text = clean_and_stitch_text(all_chunks)
            word_count = len(full_text.split())
            if word_count <= MAX_WORD_LIMIT:
                final_content = full_text
        
        # Strategy B: Fallback to Window
        if not final_content:
            start_fetch = info['min_idx'] - NEIGHBOR_WINDOW
            end_fetch = info['max_idx'] + NEIGHBOR_WINDOW
            window_chunks = get_chunks_from_es(p_id, strategy="window", start=start_fetch, end=end_fetch)
            final_content = clean_and_stitch_text(window_chunks)

        # Print summary
        print(f"Score: {info['score']:.2f} | Year: {meta.get('year')} | Filename: {meta.get('filename')}")
        if meta.get("bench"):
            print(f"   Bench: {meta.get('bench')}")
        print(f"   > Retrieved Content Length: {len(final_content)} chars")
        print()

        results.append({
            "content": final_content,
            "score": info['score'],
            "year": meta.get('year'),
            "filename": meta.get('filename'),
            "bench": meta.get('bench')
        })

    return results

# Examples of usage
if __name__ == "__main__":
    query_text = input("Enter query (or leave blank): ").strip() or None
    year_input = input("Enter year (or leave blank): ").strip()
    year = int(year_input) if year_input else None
    bench = input("Enter bench name (or leave blank): ").strip() or None

    search_judgments(query_text=query_text, year=year, bench=bench)
    