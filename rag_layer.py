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
def retrieve_documents(query, year=None, bench=None, **kwargs):
    # return search_judgments(query_text=query, year=None, bench=None)
    results, suggestion = search_judgments(query_text=query, year=year, bench=bench, **kwargs)
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



# --- NEW FUNCTION FOR FILTER EXTRACTION ---

def extract_filters_from_query(query):
    """
    Uses the Gemini model to extract Year and Bench from a user query.
    Returns the extracted year (str or None) and bench (str or None).
    """
    extraction_prompt = f"""
    Analyze the following user query and extract the most likely **Year** (a four-digit number) 
    and **Bench/Court Name** (e.g., 'Court No. 5', 'Division Bench', 'Full Bench'). 
    If a filter is not present or ambiguous, return 'None' for that field.

    User Query: "{query}"

    Output the results as a single JSON object.

    Example 1:
    Query: "landmark judgment on defamation in 2022 by the bench People Hiralal J. Kania, Saiyid Fazal Ali, Mehr Chand Mahajan"
    Output: {{"year": "2022", "bench": "Hiralal J. Kania, Saiyid Fazal Ali, Mehr Chand Mahajan"}}

    Example 2:
    Query: "State of Maharashtra by bench People B.K. Mukherjea"
    Output: {{"year": "None", "bench": "B.K. Mukherjea"}}

    Example 3:
    Query: "right to privacy bench Saiyid Fazal Ali, Mehr Chand Mahajan in 2000"
    Output: {{"year": "2000", "bench": "Saiyid Fazal Ali, Mehr Chand Mahajan"}}

    Example 4:
    Query: "State of Bombay"
    Output: {{"year": "None", "bench": "None"}}

    OUTPUT JSON:
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=extraction_prompt,
            config={"response_mime_type": "application/json"} # Ensure JSON output
        )
        
        # Parse the JSON output
        import json
        
        # Clean the text to ensure valid JSON (sometimes models add markdown formatting)
        clean_text = response.text.strip().lstrip('```json').rstrip('```').strip()
        
        filter_data = json.loads(clean_text)
        
        # Use .get() and clean up 'None' string to actual None
        year = filter_data.get("year")
        bench = filter_data.get("bench")

        return (
            year if year and year.lower() != 'none' else None, 
            bench if bench and bench.lower() != 'none' else None
        )

    except Exception as e:
        print(f"Error during filter extraction: {e}")
        # Return None, None on error to gracefully fall back to unfiltered search
        return None, None
