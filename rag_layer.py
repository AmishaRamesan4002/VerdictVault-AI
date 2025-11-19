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
    # return search_judgments(query_text=query, year=None, bench=None)
    results, suggestion = search_judgments(query_text=query, year=year, bench=bench)
    return results, suggestion
    # print(f"Retrieving documents for query: '{query}'")
    # return [
    #     {"content": f"The main cause of World War I was a complex system of alliances, militarism, and imperialism."},
    #     {"content": f"Sample document 2: The assassination of Archduke Franz Ferdinand of Austria was the immediate trigger for the war."},
    #     {"content": f"Sample document 3: The war lasted from 1914 to 1918."},
    #     {"content": f"Irrelevant document 4: The capital of France is Paris."},
    # ]

# documents are the restrieved one
def generate_answer(query, documents, max_docs=5):
    # 1. Build Context with clear separators
    # We clearly label each document so the AI can cite them.
    context_pieces = []
    for i, doc in enumerate(documents[:max_docs]):
        # We include the Year and Filename in the context so the AI can use them in the answer
        meta_info = f"Source: {doc.get('filename', 'Unknown File')} ({doc.get('year', 'Unknown Year')})"
        content = doc.get('content', '')
        context_pieces.append(f"--- DOCUMENT {i+1} ---\n{meta_info}\nCONTENT:\n{content}\n")

    context = "\n".join(context_pieces)
    
    # 2. The Formatted Prompt
    prompt = f"""
    You are a highly skilled Legal Research Assistant. 
    Answer the user's query based STRICTLY on the provided documents.

    User Query: "{query}"

    Instructions for Formatting:
    1. Use clear headings with spacing.
    2. **For the Case Analysis section, you MUST use bullet points for each document.** 3. Do not output one large paragraph. Break it down.

    Structure your response exactly like this:
    
    **➤ Executive Summary**
    (2-3 sentences summarizing the answer.)

    **➤ Key Legal Principles**
    * (Principle 1)
    * (Principle 2)

    **➤ Case-by-Case Analysis**
    * **Case 1 ({documents[0].get('filename', 'Doc 1') if documents else 'Doc 1'}):** (Analyze this specific case here...)
    * **Case 2:** (Analyze the next case...)
    * **Case 3:** (Analyze the next case...)

    **➤ Conclusion**
    (Final verdict based on the texts.)

    --- RETRIEVED LEGAL DOCUMENTS ---
    {context}
    -----------------------------------
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"Error generating answer: {e}"
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
