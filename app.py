from flask import Flask, render_template, request
from rag_layer import retrieve_documents, generate_answer ,extract_filters_from_query  # ✅ Import your functions
import markdown
from query_index import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_MAX_WORD_LIMIT,
    DEFAULT_MAX_DOCS_TO_PROCESS,
    DEFAULT_KEY_WORD_BOOST,
    DEFAULT_TOTAL_CHUNKS_TO_FETCH,
    DEFAULT_DROP_THRESHOLD,
    DEFAULT_MIN_SCORE_VARIANCE
)

app = Flask(__name__)

# Default settings dictionary to pass to templates
DEFAULTS = {
    "CHUNK_OVERLAP": DEFAULT_CHUNK_OVERLAP,
    "MAX_WORD_LIMIT": DEFAULT_MAX_WORD_LIMIT,
    "MAX_DOCS_TO_PROCESS": DEFAULT_MAX_DOCS_TO_PROCESS,
    "KEY_WORD_BOOST": DEFAULT_KEY_WORD_BOOST,
    "TOTAL_CHUNKS_TO_FETCH": DEFAULT_TOTAL_CHUNKS_TO_FETCH,
    "DROP_THRESHOLD": DEFAULT_DROP_THRESHOLD,
    "MIN_SCORE_VARIANCE": DEFAULT_MIN_SCORE_VARIANCE
}

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html", settings=DEFAULTS)


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

    # 3. Extract advanced parameters from request
    # Helper to safely convert types
    def get_arg(name, type_func):
        val = request.form.get(name)
        if val and val.strip():
            try:
                return type_func(val)
            except ValueError:
                return None
        return None

    search_kwargs = {}
    
    if val := get_arg("CHUNK_OVERLAP", int): search_kwargs["chunk_overlap"] = val
    if val := get_arg("MAX_WORD_LIMIT", int): search_kwargs["max_word_limit"] = val
    if val := get_arg("MAX_DOCS_TO_PROCESS", int): search_kwargs["max_docs"] = val
    if val := get_arg("KEY_WORD_BOOST", float): search_kwargs["keyword_boost"] = val
    if val := get_arg("TOTAL_CHUNKS_TO_FETCH", int): search_kwargs["total_chunks"] = val
    if val := get_arg("DROP_THRESHOLD", float): search_kwargs["drop_threshold"] = val
    if val := get_arg("MIN_SCORE_VARIANCE", float): search_kwargs["min_score_variance"] = val

    # Prepare settings to pass back to UI (so modal reflects current values)
    current_settings = DEFAULTS.copy()
    if "chunk_overlap" in search_kwargs: current_settings["CHUNK_OVERLAP"] = search_kwargs["chunk_overlap"]
    if "max_word_limit" in search_kwargs: current_settings["MAX_WORD_LIMIT"] = search_kwargs["max_word_limit"]
    if "max_docs" in search_kwargs: current_settings["MAX_DOCS_TO_PROCESS"] = search_kwargs["max_docs"]
    if "keyword_boost" in search_kwargs: current_settings["KEY_WORD_BOOST"] = search_kwargs["keyword_boost"]
    if "total_chunks" in search_kwargs: current_settings["TOTAL_CHUNKS_TO_FETCH"] = search_kwargs["total_chunks"]
    if "drop_threshold" in search_kwargs: current_settings["DROP_THRESHOLD"] = search_kwargs["drop_threshold"]
    if "min_score_variance" in search_kwargs: current_settings["MIN_SCORE_VARIANCE"] = search_kwargs["min_score_variance"]

    # Retrieve docs AND suggestion
    retrieved_docs, suggestion = retrieve_documents(query, year, bench, **search_kwargs)
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
                               suggestion = suggestion,
                               settings=current_settings)

    elif mode == "rag":
        raw_answer = generate_answer(query, retrieved_docs)
        answer_html = markdown.markdown(raw_answer)
        return render_template("results.html",
                               mode="rag",
                               query=query,
                               bench=bench,
                               answer=answer_html,
                               suggestion=suggestion,
                               settings=current_settings)

    return "Invalid selection"


if __name__ == "__main__":
    app.run(debug=True)
