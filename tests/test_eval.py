import json
from app.eval.metrics import recall_at_k, mrr_at_k, ndcg_at_k, evaluate_query


def test_metrics():
    rel = {"c1", "c3"}
    retrieved = ["c1", "c2", "c3", "c4"]
    assert recall_at_k(rel, retrieved, 5) == 1.0
    assert recall_at_k(rel, retrieved, 1) == 0.5
    assert mrr_at_k(rel, retrieved, 5) == 1.0
    assert mrr_at_k(rel, ["c2", "c3"], 5) == 0.5
    ndcg = ndcg_at_k(rel, ["c1", "c2", "c3"], 5)
    assert 0.5 < ndcg <= 1.0
    m = evaluate_query(rel, retrieved, [5])
    assert m["recall@5"] == 1.0


def test_run_eval_report_markdown():
    from app.eval.runner import build_report
    report = build_report([{"config": {"chunk_size": 512}, "metrics": {"recall@5": 0.9}}])
    assert "0.9" in report and report.startswith("#")


def test_golden_file_format():
    g = json.loads('{"queries":[{"q":"JVM 内存","relevant_chunk_keys":["n1##内存"]}]}')
    assert g["queries"][0]["relevant_chunk_keys"][0] == "n1##内存"


def test_run_eval_end_to_end(tmp_path):
    import json as _json
    from app.eval.runner import run_eval, build_report
    from app.ingest.chunker import Chunk
    from app.retrieval.hybrid import RetrievalHit

    golden = tmp_path / "golden.json"
    golden.write_text(_json.dumps({"queries": [
        {"q": "JVM", "relevant_chunk_keys": ["n1##内存"]}
    ]}, ensure_ascii=False), encoding="utf-8")

    class FakeDB:
        def all_chunks(self):
            return [Chunk("n1##内存##0", "n1", "内存", "JVM 内存 堆", 0)]

    class FakeSearcher:
        db = FakeDB()
        def search(self, q, k=10):
            return [RetrievalHit("n1##内存##0", "n1", "内存", "JVM 内存 堆", 1.0)]

    results = run_eval(lambda cfg: FakeSearcher(), str(golden),
                       [{"chunk_size": 512}], k_list=(5,))
    assert results[0]["metrics"]["recall@5"] == 1.0
    assert results[0]["metrics"]["mrr@5"] == 1.0
    report = build_report(results)
    assert "recall@5" in report


def test_run_eval_recall_penalizes_missing_relevant(tmp_path):
    """相关块未被检索到时 recall 应正确下降（分母是全部相关块，不只是命中的）。"""
    import json as _json
    from app.eval.runner import run_eval
    from app.ingest.chunker import Chunk
    from app.retrieval.hybrid import RetrievalHit

    golden = tmp_path / "golden.json"
    golden.write_text(_json.dumps({"queries": [
        {"q": "JVM", "relevant_chunk_keys": ["n1##内存", "n1##GC"]}
    ]}, ensure_ascii=False), encoding="utf-8")

    class FakeDB:
        def all_chunks(self):
            return [Chunk("n1##内存##0", "n1", "内存", "堆", 0),
                    Chunk("n1##GC##0", "n1", "GC", "垃圾回收", 0)]

    class FakeSearcher:
        db = FakeDB()
        def search(self, q, k=10):
            return [RetrievalHit("n1##内存##0", "n1", "内存", "堆", 1.0)]  # GC 未命中

    results = run_eval(lambda cfg: FakeSearcher(), str(golden),
                       [{"chunk_size": 512}], k_list=(5,))
    assert results[0]["metrics"]["recall@5"] == 0.5
    assert results[0]["metrics"]["mrr@5"] == 1.0
