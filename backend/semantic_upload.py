import sys
from pathlib import Path

from app.ingestion import parse_upload
from app.retrieval import search


def main():
    if len(sys.argv) < 3:
        print('Usage: python demo_semantic_upload.py "path/to/document.pdf" "your question"')
        return

    pdf_path = Path(sys.argv[1])
    query = " ".join(sys.argv[2:])

    if not pdf_path.is_file():
        print(f"File not found: {pdf_path}")
        return

    print("\n1. Reading PDF...")
    data = pdf_path.read_bytes()

    content, chunk_count = parse_upload(
        data,
        pdf_path.name,
        "document",
    )

    chunks = content["chunks"]
    embedded_count = sum(bool(chunk.get("embedding")) for chunk in chunks)

    print(f"   PDF: {pdf_path.name}")
    print(f"   Chunks extracted: {chunk_count}")
    print(f"   Chunks with embeddings: {embedded_count}")

    if not embedded_count:
        print("\nNo embeddings were generated.")
        print("Check that Ollama is running and bge-m3 is installed.")
        return

    print("\n2. Searching document...")
    print(f"   Question: {query}")

    source = {
        "name": pdf_path.name,
        "content": content,
    }

    result = search([source], query, limit=5)

    print(f"   Search method: {result['method']}")
    print("\n3. Retrieved evidence")

    for index, item in enumerate(result["results"], start=1):
        print(f"\n--- Result {index} ---")
        print(f"Similarity/score: {item['score']:.4f}")
        print(f"Page: {item['chunk'].get('page', 'Unknown')}")
        print(item["text"])

    if not result["results"]:
        print("No matching passages were found.")


if __name__ == "__main__":
    main()
