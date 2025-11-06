from elasticsearch import Elasticsearch, helpers
import ndjson

es = Elasticsearch("http://localhost:9200")
INDEX_NAME = "legal_documents"

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

es.indices.create(index=INDEX_NAME, body=mapping)
print(f"Created index: {INDEX_NAME}")

# Load data
with open(r"D:\DS_PhD\IR\Project\parsed_all.ndjson", "r", encoding="utf-8") as f:
    data = ndjson.load(f)

# Bulk index
actions = []
for i, value in enumerate(data):
    doc = {
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
    actions.append(doc)

helpers.bulk(es, actions)
print(f" Indexed {len(actions)} documents to {INDEX_NAME}")

