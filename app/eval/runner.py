import json
from pathlib import Path

from app.eval.metrics import recall_at_k, mrr_at_k, ndcg_at_k


def _key_match(chunk_id: str, keys: list[str]) -> bool:
    return any(chunk_id == k or chunk_id.startswith(k + "##") for k in keys)


def _relevant_chunk_ids(searcher, keys: list[str]) -> set[str]:
    """从全量索引匹配 golden key（`笔记名##小节标题`），而非只限被检索到的块。"""
    return {c.chunk_id for c in searcher.db.all_chunks() if _key_match(c.chunk_id, keys)}


def run_eval(searcher_factory, golden_path, configs, k_list=(5, 10)) -> list[dict]:
    """golden: {"queries":[{"q":..,"relevant_chunk_keys":[..]}]}。
    searcher_factory(config) -> 具备 search(q,k) 与 db.all_chunks() 的对象。"""
    golden = json.loads(Path(golden_path).read_text(encoding="utf-8"))
    total = len(golden["queries"])
    keys = [f"recall@{k}" for k in k_list] + [f"mrr@{k}" for k in k_list] + [f"ndcg@{k}" for k in k_list]
    results = []
    for cfg in configs:
        searcher = searcher_factory(cfg)
        agg = {key: 0.0 for key in keys}
        for q in golden["queries"]:
            hits = searcher.search(q["q"], k=max(k_list))
            retrieved = [h.chunk_id for h in hits]
            relevant = _relevant_chunk_ids(searcher, q["relevant_chunk_keys"])
            for k in k_list:
                agg[f"recall@{k}"] += recall_at_k(relevant, retrieved, k)
                agg[f"mrr@{k}"] += mrr_at_k(relevant, retrieved, k)
                agg[f"ndcg@{k}"] += ndcg_at_k(relevant, retrieved, k)
        agg = {key: round(v / total, 4) for key, v in agg.items()}
        results.append({"config": cfg, "metrics": agg})
    return results


def build_report(results: list[dict]) -> str:
    lines = ["# WSnote 检索质量评测报告", ""]
    if not results:
        lines.append("（空）")
        return "\n".join(lines)
    metric_keys = list(results[0]["metrics"].keys())
    header = "| 配置 | " + " | ".join(metric_keys) + " |"
    sep = "|" + "---|" * (len(metric_keys) + 1)
    lines.append(header); lines.append(sep)
    for r in results:
        cfg = "&".join(f"{k}={v}" for k, v in r["config"].items())
        vals = " | ".join(str(r["metrics"][mk]) for mk in metric_keys)
        lines.append(f"| {cfg} | {vals} |")
    return "\n".join(lines)
