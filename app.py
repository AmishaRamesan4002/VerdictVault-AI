from flask import Flask, render_template, request
from rag_layer import retrieve_documents, generate_answer   # ✅ Import your functions

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/search", methods=["POST"])
def search():
    query = request.form.get("query")
    mode = request.form.get("mode")  # "docs" or "rag"

    retrieved_docs = retrieve_documents(query)

    # Case 1: Return list of retrieved documents
    if mode == "docs":
        return render_template("results.html",
                               mode="docs",
                               query=query,
                               documents=retrieved_docs)

    # Case 2: Generate short answer using RAG
    elif mode == "rag":
        answer = generate_answer(query, retrieved_docs)
        return render_template("results.html",
                               mode="rag",
                               query=query,
                               answer=answer)

    else:
        return "Invalid selection"


if __name__ == "__main__":
    app.run(debug=True)
