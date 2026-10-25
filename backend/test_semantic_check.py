from app import retrieval


def test_semantic_retrieval():
    sources = [
        {
            "name": "customer_feedback.md",
            "content": {
                "chunks": [
                    {
                        "text": (
                            "Customers are unhappy because parcels arrive "
                            "several days after the promised delivery date."
                        ),
                        "embedding": retrieval._embed_query(
                            "Customers are unhappy because parcels arrive "
                            "several days after the promised delivery date."
                        ),
                    },
                    {
                        "text": "The supplier increased wholesale prices.",
                        "embedding": retrieval._embed_query("The supplier increased wholesale prices."),
                    },
                ]
            },
        }
    ]

    result = retrieval.search(
        sources,
        "why are customers upset about deliveries",
        limit=5,
    )

    print("Search method:", result["method"])
    print("Top result:", result["results"][0]["text"])

    assert result["method"] == "semantic"
    assert "parcels arrive" in result["results"][0]["text"]
