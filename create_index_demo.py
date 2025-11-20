from elasticsearch import Elasticsearch, helpers
import ndjson
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 1. Initialize Embedding Model
# We use 'all-mpnet-base-v2' because it creates 768-dimensional vectors
# which matches your Elasticsearch mapping.
print("Loading embedding model...")
model = SentenceTransformer('all-mpnet-base-v2',device='cuda')

# 2. Initialize Text Splitter
# Chunk size of 1000 characters with 200 overlap is a standard starting point for RAG
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""]
)

es = Elasticsearch("http://localhost:9200")
INDEX_NAME = "legal_documents"
FILE_PATH = r"/home/akshay2/Downloads/parsed_all.ndjson"

# 3. Mapping (Slightly optimized for kNN)
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
                "fields": {"raw": {"type": "keyword"}}
            },
            "year": {"type": "integer"},
            "bench": {"type": "text"},
            "text": {"type": "text"}, # This will now hold the CHUNK text
            "num_pages": {"type": "integer"},
            "chunk_index": {"type": "integer"}, # Useful to order chunks later
            "parent_doc_id": {"type": "keyword"}, # Ref to original file
            "embeddings": {
                "type": "dense_vector", 
                "dims": 768,
                "index": True,      # Required for kNN search in newer ES
                "similarity": "cosine" # Good for text similarity
            }
        }
    },
}

# Delete index if exists to avoid conflicts during testing
# if es.indices.exists(index=INDEX_NAME):
#     es.indices.delete(index=INDEX_NAME)

# es.indices.create(index=INDEX_NAME, body=mapping)
# print(f"Created index: {INDEX_NAME}")

# Load data
with open(FILE_PATH, "r", encoding="utf-8") as f:
    data = ndjson.load(f)

print(f"Found {len(data)} source documents. Starting chunking and indexing...")

# Bulk index
actions = []
#24600
for i, value in enumerate(data):
    full_text = value.get("text", "")
    
    # Skip empty documents
    if not full_text:
        continue

    # A. Perform Chunking
    chunks = text_splitter.split_text(full_text)
    
    # Optimization: Encode all chunks for this document in one batch
    # (Much faster than encoding one by one inside the inner loop)
    if chunks:
        embeddings = model.encode(chunks,device='cuda')
    
    for chunk_idx, chunk_text in enumerate(chunks):
        doc = {
            "_index": INDEX_NAME,
            # Create a unique ID for the chunk (e.g., "0_1", "0_2")
            "_id": f"{i}_{chunk_idx}", 
            "_source": {
                # Metadata is repeated for every chunk
                "filename": value.get("filename"),
                "year": int(value.get("year")) if value.get("year") else None,
                "bench": value.get("bench"),
                "num_pages": value.get("num_pages"),
                "parent_doc_id": i,
                
                # The specific chunk data
                "text": chunk_text, 
                "chunk_index": chunk_idx,
                "embeddings": embeddings[chunk_idx].tolist() # Convert numpy array to list
            },
        }
        actions.append(doc)

    # Optional: Batch print progress
    if i % 10 == 0:
        print(f"Processed source document {i}/{len(data)}")

# Upload to Elasticsearch
print(f"Uploading {len(actions)} chunks to Elasticsearch...")
helpers.bulk(es, actions)
print(f"Successfully indexed {len(actions)} chunks to {INDEX_NAME}")