# query_data.py
from elasticsearch import Elasticsearch
import sys,os,json

es = Elasticsearch("http://localhost:9200")
INDEX_NAME = "legal_documents"

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

def search_judgments(query_text=None, year=None, bench=None):
    must_clauses = []

    # 1. Build the Search Query
    if query_text:
        must_clauses.append({
            "multi_match": {
                "query": query_text,
                "fields": ["filename", "text", "bench"],
                "fuzziness": "AUTO"
            }
        })

    if year:
        must_clauses.append({"term": {"year": year}})

    if bench:
        must_clauses.append({"match": {"bench": bench}})

    # 2. Construct the Body with 'Suggest'
    body = {
        "query": {"bool": {"must": must_clauses}} if must_clauses else {"query": {"match_all": {}}},
        # This part asks Elasticsearch for corrections
        "suggest": {
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
        }
    }

    response = es.search(index=INDEX_NAME, body=body)

    # 3. Extract the "Did you mean?" Suggestion
    suggest_text = None
    if response.get('suggest'):
        try:
            suggestions = response['suggest']['simple_phrase'][0]['options']
            if suggestions:
                suggest_text = suggestions[0]['text']
        except (IndexError, KeyError):
            pass

    # 4. Format Results
    results = []
    for hit in response["hits"]["hits"]:
        src = hit["_source"]
        filename = src.get('filename')

        pdf_link = LINK_MAP.get(filename)

        results.append({
            "content": src.get("text", ""),
            "score": hit['_score'],
            "year": src.get('year'),
            "filename": filename,
            "bench": src.get('bench'),
            "link": pdf_link
        })
    
    # Return results AND the suggestion
    return results, suggest_text

# Examples of usage
if __name__ == "__main__":
    query_text = input("Enter query (or leave blank): ").strip() or None
    year_input = input("Enter year (or leave blank): ").strip()
    year = int(year_input) if year_input else None
    bench = input("Enter bench name (or leave blank): ").strip() or None

    search_judgments(query_text=query_text, year=year, bench=bench)