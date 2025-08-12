
import os
import json
import numpy as np
from tqdm import tqdm

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


RUNS_EVAL = {
    "o_rag": [
        "manual_run_2025-05-03_00-12-10",
        "manual_run_2025-05-03_00-22-45",
        "manual_run_2025-05-03_00-33-20",
        "manual_run_2025-05-03_00-44-05",
        "manual_run_2025-05-03_00-55-30",
    ],
    "storm": [
        "manual_run_2025-05-04_00-37-55_p2_c5_42",
        "manual_run_2025-05-04_00-57-35_p2_c5_42",
        "manual_run_2025-05-04_00-57-51_p2_c5_42",
        "manual_run_2025-05-04_10-20-34_p2_c5_42",
        "manual_run_2025-05-04_10-20-37_p2_c5_42",
    ],
    "omnithink": [
        "manual_run_2025-05-04_00-05-12",
        "manual_run_2025-05-04_00-10-25",
        "manual_run_2025-05-04_00-20-05",
        "manual_run_2025-05-04_00-24-45",
        "manual_run_2025-05-04_00-24-47",
    ],
    "apollo": [
        "0",
        "1",
        "2",
        "3",
        "4",
    ],
}


def is_allowed_run(path, pipeline):
    for run_id in RUNS_EVAL.get(pipeline, []):
        if run_id in path:
            return True
    return False

def get_snippets(data, pipeline):

    all_snippets = []

    if pipeline == "omnithink":
        for info in data["info"]:
            all_snippets.append(info["snippets"])
        for child in data["children"]:
            all_snippets = all_snippets + get_snippets(
                data["children"][child], pipeline
            )

    elif pipeline == "storm":
        for perspective in data:
            for turn in perspective.get("dlg_turns", []):
                for result in turn.get("search_results", []):
                    snippets = result.get("snippets", [])
                    if snippets:
                        all_snippets.append(snippets)

    elif pipeline == "apollo":
        for depth in data.get("queries_by_depth", {}):
            queries = data["queries_by_depth"][depth]
            for query in queries:
                for result in query.get("search_results", []):
                    snippets = result.get("snippets", [])
                    if snippets:
                        all_snippets.append(snippets)

    return all_snippets

def calculate_snippet_similarities(snippets, model, show_progress_bar=False):
    # model = SentenceTransformer(model_path)

    snippets = [" ".join(snippet) for snippet in snippets]
    snippet_embeddings = model.encode(snippets, show_progress_bar=show_progress_bar)

    similarity_matrix = cosine_similarity(snippet_embeddings)
    upper_triangle_indices = np.triu_indices_from(similarity_matrix, k=1)
    similarities = similarity_matrix[upper_triangle_indices]
    mean_similarity = np.mean(similarities)

    return mean_similarity, similarities

def eval_info_diversity_per_depth(
    base_dir: str,
    max_depth: int,
    embedding_model: str = "Snowflake/snowflake-arctic-embed-m-v2.0",
    pipeline: str = "apollo",
    show_progress_bar: bool = True,
) -> dict:
    model = SentenceTransformer(embedding_model, trust_remote_code=True)

    all_diversity = []
    depth_snippets = [[] for _ in range(max_depth)]

    json_paths = []
    for root, _, files in os.walk(base_dir):
        if not is_allowed_run(root, pipeline):
            continue
        if pipeline == "apollo" and "gather_info.json" in files:
            json_paths.append(os.path.join(root, "gather_info.json"))

    print(f"{len(json_paths)} json files found.")
    for fullpath in tqdm(
        json_paths, desc="Processing JSONs", disable=show_progress_bar
    ):
        try:
            data = json.load(open(fullpath))
        except (IOError, json.JSONDecodeError):
            continue

        snippets_all = get_snippets(data, pipeline)
        if len(snippets_all) > 1:
            mean_sim, _ = calculate_snippet_similarities(snippets_all, model)
            all_diversity.append(1.0 - mean_sim)

        for depth in range(max_depth):
            for qry in data.get("queries_by_depth", {}).get(str(depth), []):
                for res in qry.get("search_results", []):
                    if s := res.get("snippets"):
                        depth_snippets[depth].append(s)

    avg_div = float(np.mean(all_diversity)) if all_diversity else 0.0

    per_depth = []
    for snippets_at_d in depth_snippets:
        if len(snippets_at_d) > 1:
            mean_sim, _ = calculate_snippet_similarities(snippets_at_d, model)
            per_depth.append(1.0 - mean_sim)
        else:
            per_depth.append(0.0)
    try:
        import torch, gc

        del model
        torch.cuda.empty_cache()
        gc.collect()
    except ImportError:
        pass

    return {
        "pipeline": pipeline,
        "model": embedding_model,
        "average_diversity": avg_div,
        "per_depth_diversity": per_depth,
    }
