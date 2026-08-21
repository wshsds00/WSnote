import math


def recall_at_k(relevant: set, retrieved: list[str], k: int) -> float:
    if not relevant:
        return 0.0
    top = set(retrieved[:k])
    return len(top & relevant) / len(relevant)


def mrr_at_k(relevant: set, retrieved: list[str], k: int) -> float:
    for i, cid in enumerate(retrieved[:k], start=1):
        if cid in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(relevant: set, retrieved: list[str], k: int) -> float:
    dcg = sum(1.0 / math.log2(i + 1) for i, cid in enumerate(retrieved[:k], start=1) if cid in relevant)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return dcg / ideal if ideal > 0 else 0.0


def evaluate_query(relevant: set, retrieved: list[str], k_list: list[int]) -> dict:
    return {f"recall@{k}": recall_at_k(relevant, retrieved, k)
            for k in k_list} | {f"mrr@{k}": mrr_at_k(relevant, retrieved, k) for k in k_list} \
            | {f"ndcg@{k}": ndcg_at_k(relevant, retrieved, k) for k in k_list}
