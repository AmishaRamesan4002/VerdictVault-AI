from google import genai
from dotenv import load_dotenv
import os
from query_index import search_judgments
# --- Configuration and Client Setup ---
load_dotenv()

# The genai.configure() function is often not available or necessary 
# with the latest client. Instead, we directly initialize the Client.
# The Client will automatically look for the GOOGLE_API_KEY environment variable.

try:
    # ✅ Create the client: It automatically picks up the GOOGLE_API_KEY
    # from the environment if it's set via load_dotenv().
    client = genai.Client()
    print("Gemini client initialized successfully.")
except Exception as e:
    print(f"Error initializing Gemini client: {e}")
    print("Please ensure GOOGLE_API_KEY is correctly set in your .env file.")
    # Exit or handle error if the client can't be created

# Your retrieval function (written by teammate)
def retrieve_documents(query, year=None, bench=None):
    return search_judgments(query_text=query, year=None, bench=None)
    # print(f"Retrieving documents for query: '{query}'")
    # return [
    #     {"content": f"The main cause of World War I was a complex system of alliances, militarism, and imperialism."},
    #     {"content": f"Sample document 2: The assassination of Archduke Franz Ferdinand of Austria was the immediate trigger for the war."},
    #     {"content": f"Sample document 3: The war lasted from 1914 to 1918."},
    #     {"content": f"Irrelevant document 4: The capital of France is Paris."},
    # ]

# documents are the restrieved one
def generate_answer(query, documents, max_docs=3):

    # 1. Prepare context (combines documents into a single string)
    # Using enumerate and list slicing for clear context creation
    context = "\n\n".join(
        f"Document {i+1}:\n{doc['content']}"
        for i, doc in enumerate(documents[:max_docs])
    )
    
    # 2. Construct the RAG Prompt
    prompt = f"""
You are an expert Q&A assistant.
Answer the following Query using ONLY the information provided in the Documents section below.
Do not use any external knowledge.

Query:
{query}

Documents:
---
{context}
---
"""
#     If the answer cannot be found in the provided documents, you MUST respond with:
# "Not enough information in the provided documents."
    
    print("\n--- Generating Answer with Gemini ---")
    print(f"Prompt:\n{prompt}\n")
    # 3. Call the Gemini API
    # Using client.models.generate_content (the standard method)
    response = client.models.generate_content(
        model="gemini-2.5-flash",  # ✅ Recommended and fast model for RAG
        contents=prompt
    )

    return response.text.strip()

# --- Example Usage ---

# # 1. Define the user's question
# user_query = "What was the main cause and immediate trigger of World War I, and how long did it last?"

# # 2. Retrieve relevant documents
# retrieved_docs = retrieve_documents(user_query)

# # 3. Generate the final answer using RAG
# final_answer = generate_answer(
#     query=user_query, 
#     documents=retrieved_docs,
#     max_docs=3 # Only use the top 3 most relevant documents
# )

# # 4. Print the result
# print("\n" + "="*50)
# print(f"User Query: {user_query}")
# print("-" * 50)
# print(f"Generated RAG Answer:\n{final_answer}")
# print("="*50)