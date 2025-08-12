import logging
import tiktoken
import json
from src.utils import load_json

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def inspect_outline_token_limit(final_kg, max_tokens=125000, model_name="gpt-4o-mini"):
    """Reduce KG size to fit within context window limits."""
    logger.info(
        f"Initial KG: {len(final_kg.get('nodes', []))} nodes, {len(final_kg.get('edges', []))} edges, "
        f"{len(final_kg.get('questions', []))} questions, {len(final_kg.get('keywords', []))} keywords"
    )

    filtered_kg = {
        "nodes": final_kg.get("nodes", []),
        "edges": final_kg.get("edges", []),
        "questions": final_kg.get("questions", []),
        "keywords": final_kg.get("keywords", []),
    }

    try:
        encoding = tiktoken.encoding_for_model(model_name)
        kg_json = json.dumps(filtered_kg)
        token_count = len(encoding.encode(kg_json))

        # Print initial token count
        logger.info(
            f"Initial token count before any filtering: {token_count}/{max_tokens} tokens"
        )

        if token_count <= max_tokens:
            logger.info(
                f"Knowledge graph fits: {token_count}/{max_tokens} tokens. Sending to OutlineGenAgent."
            )
            return filtered_kg

        reduction_steps = [0.3, 0.5, 0.7, 1.0]
        for step in reduction_steps:
            questions_to_keep = int(len(filtered_kg["questions"]) * (1 - step))
            keywords_to_keep = int(len(filtered_kg["keywords"]) * (1 - step))

            temp_kg = {
                "nodes": filtered_kg["nodes"],
                "edges": filtered_kg["edges"],
                "questions": filtered_kg["questions"][:questions_to_keep],
                "keywords": filtered_kg["keywords"][:keywords_to_keep],
            }
            kg_json = json.dumps(temp_kg)
            token_count = len(encoding.encode(kg_json))

            if token_count <= max_tokens:
                logger.info(
                    f"Reduced graph fits after {int(step*100)}% reduction: {token_count}/{max_tokens} tokens "
                )
                return temp_kg
            else:
                logger.info(
                    f"Still too large after {int(step*100)}% reduction: {token_count}/{max_tokens} tokens"
                )

        logger.warning(
            "Knowledge graph may still exceed token limit even after removing all questions and keywords"
        )
        return {
            "nodes": filtered_kg["nodes"],
            "edges": filtered_kg["edges"],
            "questions": [],
            "keywords": [],
        }

    except Exception as e:
        logger.error(f"Error estimating tokens: {e}, returning filtered graph")
        return filtered_kg


if __name__ == "__main__":

    final_kg = load_json(
        "../output/apollo/gen_articles_test/SciWiki-100/Med_Dentistry/0/Ovarian_cyst_250508-074143/kg/States/kg_depth_4.json"
    )
    filtered_kg = inspect_outline_token_limit(final_kg)

    # Print a summary of what happened
    print("\nSUMMARY:")
    print(f"Original nodes: {len(final_kg.get('nodes', []))}")
    print(f"Original edges: {len(final_kg.get('edges', []))}")
    print(f"Original questions: {len(final_kg.get('questions', []))}")
    print(f"Original keywords: {len(final_kg.get('keywords', []))}")
    print(f"Filtered nodes: {len(filtered_kg.get('nodes', []))}")
    print(f"Filtered edges: {len(filtered_kg.get('edges', []))}")
    print(f"Filtered questions: {len(filtered_kg.get('questions', []))}")
    print(f"Filtered keywords: {len(filtered_kg.get('keywords', []))}")

    """
    __main__ : ERROR : Error generating outline: litellm.ContextWindowExceededError: litellm.BadRequestError: AzureException ContextWindowExceededError - Error code: 400 - {'error': {'message': "This model's maximum context length is 128000 tokens. However, you requested 129182 tokens (113182 in the messages, 16000 in the completion). Please reduce the length of the messages or completion.", 'type': 'invalid_request_error', 'param': 'messages', 'code': 'context_length_exceeded'}}
    """
