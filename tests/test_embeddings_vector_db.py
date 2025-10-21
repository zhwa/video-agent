from agent.adapters import get_embeddings_adapter, get_vector_db_adapter

def test_dummy_embeddings_and_vector_db():
    emb = get_embeddings_adapter()
    vecdb = get_vector_db_adapter()
    texts = ["Hello world", "Another sentence"]
    vectors = emb.embed_texts(texts)
    assert len(vectors) == 2
    vecdb.upsert("t1", vectors[0], metadata={"text": "Hello world"})
    vecdb.upsert("t2", vectors[1], metadata={"text": "Another sentence"})
    res = vecdb.query(vectors[0], top_k=2)
    assert len(res) == 2
    # Best match should be t1 at top
    assert res[0][0] == "t1"