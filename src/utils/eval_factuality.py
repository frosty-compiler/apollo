from eval.eval_coverage_quality import run_evaluation
from ..utils.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def run_eval_factuality(
    topic: str,
    article_path,
    article_references_path,
    draft_article_path,
    draft_article_references_path,
    results_dir,
):

    # Evaluate draft article
    result_draft = run_evaluation(
        topic=f"{topic}_draft",
        article_path=draft_article_path,
        references_path=draft_article_references_path,
        results_dir=results_dir,
        num_workers=7,
        batch_size=5,
        print_results=False,
    )
    logger.info(
        "Draft Factuality score: %.3f (%d/%d)",
        result_draft["factuality"],
        result_draft["verified_claims"],
        result_draft["total_claims"],
    )
    logger.info(
        "Draft Coverage score: %.3f",
        result_draft["section_specific_coverage"],
    )

    # Evaluate final article
    result_article = run_evaluation(
        topic=topic,
        article_path=article_path,
        references_path=article_references_path,
        results_dir=results_dir,
        num_workers=7,
        batch_size=5,
        print_results=False,
    )
    logger.info(
        "Article Factuality score: %.3f (%d/%d)",
        result_article["factuality"],
        result_article["verified_claims"],
        result_article["total_claims"],
    )
    logger.info(
        "Article Coverage score: %.3f",
        result_article["section_specific_coverage"],
    )
