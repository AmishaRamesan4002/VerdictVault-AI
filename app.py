from flask import Flask, render_template, request
from rag_layer import retrieve_documents, generate_answer ,extract_filters_from_query  # ✅ Import your functions
import markdown

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/search", methods=["POST"])
def search():
    query = request.form.get("query")
    mode = request.form.get("mode")
    filter_source = request.form.get("filter_source", "auto") # Get the selection

    # 1. Initialize filters
    year = None
    bench = None
    
    # 2. Handle filter source logic
    if filter_source == "manual":
        # Option 1: Manual Input (Use what the user typed in the separate fields)
        year = request.form.get("year")
        bench = request.form.get("bench")

        # Clean up empty strings or "None" strings to actual None
        if not year or year.lower() == "none":
            year = None
        if not bench or bench.lower() == "none":
            bench = None
            
    elif filter_source == "auto":
        # Option 2: Automatic Extraction (Extract from the main query using Gemini)
        # We use the new function here to extract year/bench from the query text.
        print(f"Filter source is 'auto'. Attempting to extract filters from query: '{query}'")
        year, bench = extract_filters_from_query(query)

        
    # Retrieve docs AND suggestion
    retrieved_docs, suggestion = retrieve_documents(query, year, bench)
    # print(retrieved_docs)
    # print(suggestion)

    # retrieved_docs = retrieve_documents(query)

    # Don't suggest the same thing the user typed
    if suggestion and suggestion.lower() == query.lower():
        suggestion = None

    if mode == "docs":
        return render_template("results.html",
                               mode="docs",
                               query=query,
                               bench = bench,
                               documents=retrieved_docs,
                               suggestion = suggestion)

    elif mode == "rag":
        raw_answer = generate_answer(query, retrieved_docs)
        answer_html = markdown.markdown(raw_answer)
        return render_template("results.html",
                               mode="rag",
                               query=query,
                               bench=bench,
                               answer=answer_html,
                               suggestion=suggestion)

    return "Invalid selection"


if __name__ == "__main__":
    app.run(debug=True)
