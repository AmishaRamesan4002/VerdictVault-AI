from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
import sys
import os
import json

# ---------------- CONFIGURATION ----------------
es = Elasticsearch("http://localhost:9200")
INDEX_NAME = "legal_documents"

# Default values (can be overridden via arguments)
DEFAULT_TOTAL_CHUNKS_TO_FETCH = 40
DEFAULT_KEY_WORD_BOOST = 0.3
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_MAX_WORD_LIMIT = 15000
DEFAULT_NEIGHBOR_WINDOW = 2
DEFAULT_MAX_DOCS_TO_PROCESS = 5
DEFAULT_DROP_THRESHOLD = 0.40
DEFAULT_MIN_SCORE_VARIANCE = 0.05

# This loads the file once when the server starts. Fast and efficient.
LINKS_FILE = "hyperlinks.json"
LINK_MAP = {}

try:
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, "r", encoding="utf-8") as f:
            LINK_MAP = json.load(f)
        print(f"Loaded {len(LINK_MAP)} hyperlinks.")
    else:
        print(f"Warning: {LINKS_FILE} not found. Links will not work.")
except Exception as e:
    print(f"Error loading links: {e}")

# RAG Configuration
try:
    # Load model once at startup
    print("Loading embedding model... (this may take a few seconds)")
    EMBEDDING_MODEL = SentenceTransformer('all-mpnet-base-v2')
except Exception as e:
    print(f"Error loading model: {e}. Make sure sentence-transformers is installed.")
    sys.exit(1)

# ---------------- HELPER FUNCTIONS ----------------

def clean_and_stitch_text(chunks, chunk_overlap=DEFAULT_CHUNK_OVERLAP):
    """Joins chunks and removes the overlapping characters."""
    if not chunks:
        return ""
    
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
                text_to_add = text[chunk_overlap:] if len(text) > chunk_overlap else text
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

def search_judgments(
    query_text=None, 
    year=None, 
    bench=None,
    total_chunks=DEFAULT_TOTAL_CHUNKS_TO_FETCH,
    keyword_boost=DEFAULT_KEY_WORD_BOOST,
    max_docs=DEFAULT_MAX_DOCS_TO_PROCESS,
    drop_threshold=DEFAULT_DROP_THRESHOLD,
    min_score_variance=DEFAULT_MIN_SCORE_VARIANCE,
    max_word_limit=DEFAULT_MAX_WORD_LIMIT,
    chunk_overlap=DEFAULT_CHUNK_OVERLAP,
    neighbor_window=DEFAULT_NEIGHBOR_WINDOW
):
    
    # 1. Build Filters
    filter_clauses = []
    if year: filter_clauses.append({"term": {"year": year}})
    if bench: filter_clauses.append({"match": {"bench": bench}})

    # 2. Perform Search
    suggest_text = None
    if query_text:
        query_vector = EMBEDDING_MODEL.encode(query_text).tolist()
        
        # Hybrid Query
        response = es.search(
            index=INDEX_NAME,
            size=total_chunks, 
            knn={
                "field": "embeddings",
                "query_vector": query_vector,
                "k": total_chunks,
                "num_candidates": 100,
                "filter": filter_clauses 
            },
            query={
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": query_text,
                            "fields": ["text", "bench", "filename"],
                            "boost": keyword_boost,
                            "fuzziness": "AUTO"
                        }
                    },
                    "filter": filter_clauses 
                }
            },
            suggest={
                "text": query_text,
                "simple_phrase": {
                    "phrase": {
                        "field": "text",
                        "size": 1,
                        "gram_size": 3,
                        "direct_generator": [{
                            "field": "text",
                            "suggest_mode": "always"
                        }],
                        "highlight": {
                            "pre_tag": "<em>",
                            "post_tag": "</em>"
                        }
                    }
                }
            },
            _source=["parent_doc_id", "chunk_index", "filename", "year", "bench", "_score"]
        )

        # Extract suggestion
        if response.get('suggest'):
            try:
                suggestions = response['suggest']['simple_phrase'][0]['options']
                if suggestions:
                    suggest_text = suggestions[0]['text']
            except (IndexError, KeyError):
                pass
    else:
        body = {"query": {"bool": {"filter": filter_clauses}}} if filter_clauses else {"query": {"match_all": {}}}
        response = es.search(index=INDEX_NAME, body=body, size=total_chunks)

    print(f"\n🔎 Query: '{query_text or ''}'")

    # 3. Group Chunks by Parent Document
    parent_docs = {}
    for hit in response["hits"]["hits"]:
        src = hit["_source"]
        p_id = src.get("parent_doc_id")
        if p_id is None: continue 
        
        if p_id not in parent_docs:
            parent_docs[p_id] = {
                "min_idx": src.get('chunk_index', 0), 
                "max_idx": src.get('chunk_index', 0),
                "score": hit['_score'],
                "metadata": src 
            }
        else:
            parent_docs[p_id]["min_idx"] = min(parent_docs[p_id]["min_idx"], src.get('chunk_index', 0))
            parent_docs[p_id]["max_idx"] = max(parent_docs[p_id]["max_idx"], src.get('chunk_index', 0))
            parent_docs[p_id]["score"] += hit['_score']

    # Sort all candidates by score
    sorted_parents = sorted(parent_docs.items(), key=lambda item: item[1]['score'], reverse=True)
    #print parent_docs file name and score for debugging
    print(f"   📄 Found {len(sorted_parents)} candidate documents."
          f" (Filtered by Year: {year}, Bench: {bench})"
          f"\n   Top Candidates:")
    for i, (p_id, info) in enumerate(sorted_parents):
        meta = info['metadata']
        print(f"   {i+1}. Score: {info['score']:.2f} | Year: {meta.get('year')} | Filename: {meta.get('filename')}")
    # ====================================================
    # 4. INTELLIGENT THRESHOLDING (The New Logic)
    # ====================================================
    final_parents_to_process = []
    
    if sorted_parents:
        # Always take the Top 1 result
        final_parents_to_process.append(sorted_parents[0])
        top_score = sorted_parents[0][1]['score']
        
        print(f"   📊 Top Doc Score: {top_score:.4f}")

        for i in range(len(sorted_parents) - 1):
            # Check if we already hit our hard limit
            if len(final_parents_to_process) >= max_docs:
                break

            prev_score = sorted_parents[i][1]['score']
            next_doc = sorted_parents[i+1]
            next_score = next_doc[1]['score']
            
            # Calculate relative drop percentage
            drop_pct = (prev_score - next_score) / prev_score if prev_score > 0 else 0
            
            # LOGIC 1: The "Elbow" Cutoff
            # If the score drops by more than 20% (DROP_THRESHOLD), assume relevance is lost.
            if drop_pct > drop_threshold:
                print(f"   ✂️  Cutoff: Doc {i+2} dropped by {drop_pct:.1%}. Stopping retrieval.")
                break
            
            # LOGIC 2: The "Flat & Low" Ambiguity Check
            # If we are at Doc 2, and it's basically identical to Doc 1 (tiny drop), 
            # but the overall scores are low, we might optionally stop to avoid noise.
            # (Here we just rely on the Elbow. If curve is flat, we take them until MAX limit).
            
            final_parents_to_process.append(next_doc)

    # ====================================================
    # 5. Process Final List
    # ====================================================
    results = []
    print(f"   📚 Processing {len(final_parents_to_process)} documents after thresholding...\n")

    for p_id, info in final_parents_to_process:
        meta = info['metadata']
        final_content = ""
        
        # Strategy A: Try Full Document
        all_chunks = get_chunks_from_es(p_id, strategy="all")
        
        if all_chunks:
            full_text = clean_and_stitch_text(all_chunks, chunk_overlap=chunk_overlap)
            word_count = len(full_text.split())
            if word_count <= max_word_limit:
                final_content = full_text
        
        # Strategy B: Fallback to Window
        if not final_content:
            start_fetch = info['min_idx'] - neighbor_window
            end_fetch = info['max_idx'] + neighbor_window
            window_chunks = get_chunks_from_es(p_id, strategy="window", start=start_fetch, end=end_fetch)
            final_content = clean_and_stitch_text(window_chunks, chunk_overlap=chunk_overlap)

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
            "bench": meta.get('bench'),
            "link": LINK_MAP.get(meta.get('filename'))
        })

    return results, suggest_text

# Examples of usage
if __name__ == "__main__":
    query_text = input("Enter query (or leave blank): ").strip() or None
    year_input = input("Enter year (or leave blank): ").strip()
    year = int(year_input) if year_input else None
    bench = input("Enter bench name (or leave blank): ").strip() or None

    results, suggestion = search_judgments(query_text=query_text, year=year, bench=bench)
    if suggestion:
        print(f"Did you mean: {suggestion}?")