# query_data.py
from elasticsearch import Elasticsearch
import sys

es = Elasticsearch("http://localhost:9200")
INDEX_NAME = "legal_documents"

def search_judgments(query_text=None, year=None, bench=None):
    must_clauses = []

    # Full-text or title search
    if query_text:
        must_clauses.append({
            "multi_match": {
                "query": query_text,
                "fields": ["filename", "text", "bench"],
                "fuzziness": "AUTO"
            }
        })

    # Filter by year (exact numeric match)
    if year:
        must_clauses.append({
            "term": {"year": year}
        })

    # Filter by bench (text match)
    if bench:
        must_clauses.append({
            "match": {"bench": bench}
        })

    # Build search body
    body = {"query": {"bool": {"must": must_clauses}}} if must_clauses else {"query": {"match_all": {}}}

    response = es.search(index=INDEX_NAME, body=body)

    print(f"\n Search results for query: '{query_text or ''}', Year: '{year or ''}', Bench: '{bench or ''}'")
    results=[]
    for hit in response["hits"]["hits"]:
        #get the text content from hit
        src = hit["_source"]
        content=src.get("text", "")
        print(f"Score: {hit['_score']:.2f} | Year: {src.get('year')} | Filename: {src.get('filename')}")
        if src.get("bench"):
            print(f"   Bench: {src.get('bench')}")
        print()
        results.append({"content": content,"score": hit['_score'],"year": src.get('year'), "filename": src.get('filename'), "bench": src.get('bench')})
    return results

# Examples of usage
if __name__ == "__main__":
    query_text = input("Enter query (or leave blank): ").strip() or None
    year_input = input("Enter year (or leave blank): ").strip()
    year = int(year_input) if year_input else None
    bench = input("Enter bench name (or leave blank): ").strip() or None

    search_judgments(query_text=query_text, year=year, bench=bench)