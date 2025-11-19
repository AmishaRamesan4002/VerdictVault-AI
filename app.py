from flask import Flask, render_template, request
from rag_layer import retrieve_documents, generate_answer

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/search", methods=["POST"])
def search():
    query = request.form.get("query")
    mode = request.form.get("mode")
    year = request.form.get("year") or None
    bench = request.form.get("bench") or None

    # Safely get filters
    year = request.form.get("year")
    bench = request.form.get("bench")

    # Fix for "None" string bug
    if not year or year == "None":
        year = None
    if not bench or bench == "None":
        bench = None

    # Retrieve docs AND suggestion
    retrieved_docs, suggestion = retrieve_documents(query, year, bench)

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
        answer = generate_answer(query, retrieved_docs)
        return render_template("results.html",
                               mode="rag",
                               query=query,
                               bench=bench,
                               answer=answer,
                               suggestion=suggestion)

    return "Invalid selection"


if __name__ == "__main__":
    app.run(debug=True)
