import pickle
from elasticsearch import Elasticsearch, helpers

def export_index_to_pickle():
    # 1. Connect to Elasticsearch
    es = Elasticsearch("http://localhost:9200")
    INDEX_NAME = "legal_documents"
    OUTPUT_FILE = "legal_embeddings_dump.pkl"

    if not es.indices.exists(index=INDEX_NAME):
        print(f"Error: Index '{INDEX_NAME}' not found.")
        return

    print(f"Scanning index '{INDEX_NAME}' to retrieve embeddings...")

    # 2. Use helpers.scan()
    # This is efficient for large exports as it keeps a cursor open (scroll)
    # instead of trying to load everything at once.
    scan_gen = helpers.scan(
        es,
        index=INDEX_NAME,
        query={"query": {"match_all": {}}},
        preserve_order=True
    )

    all_docs = []

    try:
        for i, doc in enumerate(scan_gen):
            # doc['_source'] contains 'text', 'embeddings', 'filename', etc.
            source = doc["_source"]
            
            # Optional: Include the Elasticsearch ID if you need it later
            source["_es_id"] = doc["_id"]
            
            all_docs.append(source)

            if (i + 1) % 5000 == 0:
                print(f"  Fetched {i + 1} chunks...")

    except Exception as e:
        print(f"Error during export: {e}")

    print(f"Total documents retrieved: {len(all_docs)}")
    
    # 3. Save to Pickle
    print(f"Saving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "wb") as f:
        pickle.dump(all_docs, f)
    
    print("Export complete!")

if __name__ == "__main__":
    export_index_to_pickle()

# import pickle

# with open("legal_embeddings_dump.pkl", "rb") as f:
#     data = pickle.load(f)

# # Example: Access the first chunk's embedding
# print(data[0]['filename'])
# print(len(data[0]['embeddings'])) # Should be 768