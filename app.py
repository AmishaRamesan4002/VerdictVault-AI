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

    # Retrieve docs based on query (you may also use year/bench later)
    retrieved_docs = retrieve_documents(query,year, bench)

    if mode == "docs":
        return render_template("results.html",
                               mode="docs",
                               query=query,
                               year=year,
                               bench=bench,
                               documents=retrieved_docs)

    elif mode == "rag":
        answer = generate_answer(query, retrieved_docs)
        return render_template("results.html",
                               mode="rag",
                               query=query,
                               year=year,
                               bench=bench,
                               answer=answer)

    return "Invalid selection"


if __name__ == "__main__":
    app.run(debug=True)
