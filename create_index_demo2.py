from elasticsearch import Elasticsearch, helpers
import ndjson
import sys

# Connect to Elasticsearch
es = Elasticsearch("http://localhost:9200")
INDEX_NAME = "legal_documents"
# UPDATE THIS PATH to where your actual file is located on your Linux machine
FILE_PATH = r"/home/akshay2/Downloads/parsed_all.ndjson" 

# Standard Mapping (No complex autocomplete fields, just standard analysis)
mapping = {
    "settings": {
        "analysis": {
            "analyzer": {
                "filename_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "word_delimiter_graph"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "filename": {
                "type": "text",
                "analyzer": "filename_analyzer",
                "fields": {
                    "raw": {"type": "keyword"}
                }
            },
            "year": {"type": "integer"},
            "bench": {"type": "text"},
            "text": {"type": "text"},
            "num_pages": {"type": "integer"},
            "embeddings": {"type": "dense_vector", "dims": 768}
        }
    },
}

# 1. CREATE THE INDEX
try:
    if es.indices.exists(index=INDEX_NAME):
        print(f"Index {INDEX_NAME} already exists.")
    else:
        es.indices.create(index=INDEX_NAME, body=mapping)
        print(f"Created index: {INDEX_NAME}")
except Exception as e:
    print(f"Error creating index: {e}")

# 2. GENERATOR FUNCTION (Streams data line-by-line)
def generate_actions():
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        # Use ndjson reader to handle parsing line by line
        reader = ndjson.reader(f)
        
        for i, value in enumerate(reader):
            # Print progress every 1000 docs so you know it's working
            if i % 1000 == 0:
                print(f" ... preparing document {i}", end='\r')

            yield {
                "_index": INDEX_NAME,
                "_id": i,
                "_source": {
                    "filename": value.get("filename"),
                    "year": int(value.get("year")) if value.get("year") else None,
                    "bench": value.get("bench"),
                    "text": value.get("text"),
                    "num_pages": value.get("num_pages"),
                },
            }
    print(f"\nFinished reading file.")

# 3. BULK INDEXING (The safe way)
print("Starting bulk index...")
try:
    success_count = 0
    # streaming_bulk handles the generator automatically
    for ok, info in helpers.streaming_bulk(es, generate_actions(), chunk_size=500):
        if ok:
            success_count += 1
        else:
            print(f"Failed to index a doc: {info}")
        
        if success_count % 1000 == 0:
             print(f" ... indexed {success_count} documents", end='\r')

    print(f"\nSuccessfully indexed {success_count} documents to {INDEX_NAME}")

except Exception as e:
    print(f"Error during indexing: {e}")