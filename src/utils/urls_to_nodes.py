import os
import json
import logging
import argparse
import time
from collections import defaultdict, Counter
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("url_mapping.log"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def add_urls_to_graph_generator_files(base_path, topic_path, stats_file=None):
    """
    Add URLs to nodes in GraphGenerator JSON files based on gather_info.json.

    Args:
        base_path (str): Base path to the SciWiki-100 directory
        topic_path (str): Path to the specific topic directory
        stats_file (str, optional): Path to save statistics

    Returns:
        dict: Statistics about the URL addition process
    """
    topic_name = os.path.basename(topic_path)
    domain_name = os.path.basename(os.path.dirname(topic_path))
    topic_id = os.path.basename(os.path.dirname(os.path.dirname(topic_path)))

    logger.info(f"Processing {domain_name}/{topic_id}/{topic_name}")

    gather_info_path = os.path.join(topic_path, "gather_info.json")

    if not os.path.exists(gather_info_path):
        logger.error(f"Error: gather_info.json not found at {gather_info_path}")
        return None

    try:
        with open(gather_info_path, "r") as f:
            gather_info = json.load(f)
    except Exception as e:
        logger.error(f"Error loading gather_info.json: {str(e)}")
        return None

    url_map = {}
    queries_by_depth = gather_info.get("queries_by_depth", {})

    for depth, queries in queries_by_depth.items():
        url_map[depth] = []
        for query in queries:
            for result in query.get("search_results", []):
                url_map[depth].append(result.get("url", ""))

    graph_generator_path = os.path.join(topic_path, "kg", "GraphGenerator")

    if not os.path.exists(graph_generator_path):
        logger.error(
            f"Error: GraphGenerator directory not found at {graph_generator_path}"
        )
        return None

    stats = {
        "topic": topic_name,
        "domain": domain_name,
        "topic_id": topic_id,
        "depths_processed": 0,
        "total_files_processed": 0,
        "total_nodes_updated": 0,
        "urls_by_depth": {},
        "errors": [],
    }

    for depth_str in url_map:
        depth_dir = os.path.join(graph_generator_path, f"depth_{depth_str}")
        if not os.path.exists(depth_dir):
            logger.warning(f"Warning: depth_{depth_str} directory not found")
            continue

        depth_stats = {"files_processed": 0, "nodes_updated": 0, "urls_assigned": []}

        for version_dir in os.listdir(depth_dir):
            if not os.path.isdir(os.path.join(depth_dir, version_dir)):
                continue

            version_path = os.path.join(depth_dir, version_dir)

            snippet_files = [
                f
                for f in os.listdir(version_path)
                if f.startswith(f"gen_kg_prompt_{version_dir}_snippet_")
                and f.endswith(".json")
                and not "_group" in f
            ]

            snippet_files.sort(key=lambda x: int(x.split("_")[-1].split(".")[0]))

            if len(snippet_files) > len(url_map[depth_str]):
                logger.warning(
                    f"Warning: More snippet files ({len(snippet_files)}) than URLs ({len(url_map[depth_str])}) for depth {depth_str}"
                )

            for i, snippet_file in enumerate(snippet_files):
                if i >= len(url_map[depth_str]):
                    logger.warning(f"Warning: No URL available for {snippet_file}")
                    continue

                snippet_path = os.path.join(version_path, snippet_file)
                url_value = url_map[depth_str][i]

                try:
                    with open(snippet_path, "r") as f:
                        snippet_data = json.load(f)

                    node_count = 0
                    for node in snippet_data.get("nodes", []):
                        node["url"] = url_value
                        node_count += 1

                    with open(snippet_path, "w") as f:
                        json.dump(snippet_data, f, indent=2)

                    depth_stats["files_processed"] += 1
                    depth_stats["nodes_updated"] += node_count
                    depth_stats["urls_assigned"].append(url_value)

                    logger.debug(
                        f"Updated {snippet_file} with URL: {url_value} ({node_count} nodes)"
                    )
                except Exception as e:
                    error_msg = f"Error processing {snippet_path}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

        stats["depths_processed"] += 1
        stats["total_files_processed"] += depth_stats["files_processed"]
        stats["total_nodes_updated"] += depth_stats["nodes_updated"]
        stats["urls_by_depth"][depth_str] = depth_stats

    logger.info(f"URL addition to GraphGenerator files completed for {topic_name}")
    logger.info(
        f"Processed {stats['total_files_processed']} files across {stats['depths_processed']} depths"
    )
    logger.info(f"Updated {stats['total_nodes_updated']} nodes total")

    if stats_file:
        try:
            with open(stats_file, "w") as f:
                json.dump(stats, f, indent=2)
            logger.info(f"Statistics saved to {stats_file}")
        except Exception as e:
            logger.error(f"Error saving statistics to {stats_file}: {str(e)}")

    return stats


def add_urls_to_state_files(topic_path, stats_file=None):
    """
    Add URLs to nodes in State kg_depth_N.json files by matching nodes from
    the corresponding GraphGenerator snippet files from all depths up to and including N.

    Args:
        topic_path (str): Path to the specific topic directory
        stats_file (str, optional): Path to save statistics

    Returns:
        dict: Statistics about the URL addition process
    """
    topic_name = os.path.basename(topic_path)
    domain_name = os.path.basename(os.path.dirname(topic_path))
    topic_id = os.path.basename(os.path.dirname(os.path.dirname(topic_path)))

    logger.info(f"Processing state files for {domain_name}/{topic_id}/{topic_name}")

    kg_path = os.path.join(topic_path, "kg")
    graph_generator_path = os.path.join(kg_path, "GraphGenerator")
    states_path = os.path.join(kg_path, "States")

    if not os.path.exists(graph_generator_path):
        logger.error(
            f"Error: GraphGenerator directory not found at {graph_generator_path}"
        )
        return None

    if not os.path.exists(states_path):
        logger.error(f"Error: States directory not found at {states_path}")
        return None

    depth_dirs = [d for d in os.listdir(graph_generator_path) if d.startswith("depth_")]
    depth_dirs.sort(key=lambda x: int(x.split("_")[1]))

    stats = {
        "topic": topic_name,
        "domain": domain_name,
        "topic_id": topic_id,
        "state_files_processed": 0,
        "total_nodes_matched": 0,
        "state_stats_by_depth": {},
        "errors": [],
    }

    all_snippet_nodes = {}  # {depth: {node_key: url}}

    logger.info("Collecting nodes from all snippet files...")
    for depth_dir in depth_dirs:
        depth_num = int(depth_dir.split("_")[1])
        all_snippet_nodes[depth_num] = {}

        depth_path = os.path.join(graph_generator_path, depth_dir)
        version_dirs = [
            d
            for d in os.listdir(depth_path)
            if os.path.isdir(os.path.join(depth_path, d))
        ]

        for version_dir in version_dirs:
            version_path = os.path.join(depth_path, version_dir)
            snippet_files = [
                f
                for f in os.listdir(version_path)
                if f.startswith(f"gen_kg_prompt_{version_dir}_snippet_")
                and f.endswith(".json")
                and not "_group" in f
            ]

            for snippet_file in snippet_files:
                snippet_path = os.path.join(version_path, snippet_file)

                try:
                    with open(snippet_path, "r") as f:
                        snippet_data = json.load(f)
                except Exception as e:
                    error_msg = f"Error loading snippet file {snippet_path}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)
                    continue

                for snippet_node in snippet_data.get("nodes", []):
                    if "url" not in snippet_node:
                        continue

                    exact_key = (
                        snippet_node.get("id", ""),
                        snippet_node.get("label", ""),
                        snippet_node.get("description", ""),
                    )
                    id_key = snippet_node.get("id", "")

                    all_snippet_nodes[depth_num][exact_key] = snippet_node["url"]

    logger.info("Processing state files...")
    for depth_dir in depth_dirs:
        depth_num = int(depth_dir.split("_")[1])
        state_file = os.path.join(states_path, f"kg_depth_{depth_num}.json")

        if not os.path.exists(state_file):
            logger.warning(f"Warning: State file {state_file} not found")
            continue

        try:
            with open(state_file, "r") as f:
                state_data = json.load(f)
        except Exception as e:
            error_msg = f"Error loading state file {state_file}: {str(e)}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            continue

        depth_stats = {
            "total_nodes": len(state_data.get("nodes", [])),
            "nodes_with_url_before": 0,
            "nodes_with_url_after": 0,
            "matched_nodes": 0,
            "unmatched_nodes": 0,
            "url_distribution": {},
        }

        for node in state_data.get("nodes", []):
            if "url" in node:
                depth_stats["nodes_with_url_before"] += 1

        for node in state_data.get("nodes", []):

            exact_key = (
                node.get("id", ""),
                node.get("label", ""),
                node.get("description", ""),
            )
            id_key = node.get("id", "")
            matched = False

            for d in range(depth_num + 1):

                if exact_key in all_snippet_nodes[d]:
                    node["url"] = all_snippet_nodes[d][exact_key]
                    depth_stats["matched_nodes"] += 1

                    if node["url"] in depth_stats["url_distribution"]:
                        depth_stats["url_distribution"][node["url"]] += 1
                    else:
                        depth_stats["url_distribution"][node["url"]] = 1

                    matched = True
                    break

            if not matched:
                depth_stats["unmatched_nodes"] += 1

        for node in state_data.get("nodes", []):
            if "url" in node:
                depth_stats["nodes_with_url_after"] += 1

        try:
            with open(state_file, "w") as f:
                json.dump(state_data, f, indent=2)
            logger.info(f"Updated state file {state_file}")
        except Exception as e:
            error_msg = f"Error saving state file {state_file}: {str(e)}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)

        stats["state_files_processed"] += 1
        stats["total_nodes_matched"] += depth_stats["matched_nodes"]
        stats["state_stats_by_depth"][depth_num] = depth_stats

        logger.info(f"Statistics for {state_file}:")
        logger.info(f"  Total nodes: {depth_stats['total_nodes']}")
        logger.info(f"  Nodes with URL before: {depth_stats['nodes_with_url_before']}")
        logger.info(f"  Nodes with URL after: {depth_stats['nodes_with_url_after']}")
        logger.info(f"  Matched nodes: {depth_stats['matched_nodes']}")
        logger.info(f"  Unmatched nodes: {depth_stats['unmatched_nodes']}")
        logger.info(
            f"  URL coverage: {depth_stats['nodes_with_url_after'] / depth_stats['total_nodes'] * 100:.2f}%"
        )

    logger.info(f"URL addition to state files completed for {topic_name}")
    logger.info(f"Processed {stats['state_files_processed']} state files")
    logger.info(f"Matched {stats['total_nodes_matched']} nodes total")

    if stats_file:
        try:
            with open(stats_file, "w") as f:
                json.dump(stats, f, indent=2)
            logger.info(f"Statistics saved to {stats_file}")
        except Exception as e:
            logger.error(f"Error saving statistics to {stats_file}: {str(e)}")

    return stats


def remove_urls_from_graph_generator_files(topic_path):
    """
    Remove URLs from nodes in GraphGenerator JSON files.

    Args:
        topic_path (str): Path to the specific topic directory
    """
    topic_name = os.path.basename(topic_path)
    domain_name = os.path.basename(os.path.dirname(topic_path))
    topic_id = os.path.basename(os.path.dirname(os.path.dirname(topic_path)))

    logger.info(
        f"Removing URLs from GraphGenerator files for {domain_name}/{topic_id}/{topic_name}"
    )

    graph_generator_path = os.path.join(topic_path, "kg", "GraphGenerator")

    if not os.path.exists(graph_generator_path):
        logger.error(
            f"Error: GraphGenerator directory not found at {graph_generator_path}"
        )
        return

    files_processed = 0
    nodes_modified = 0

    for depth_dir in os.listdir(graph_generator_path):
        if not depth_dir.startswith("depth_"):
            continue

        depth_path = os.path.join(graph_generator_path, depth_dir)
        if not os.path.isdir(depth_path):
            continue

        for version_dir in os.listdir(depth_path):
            version_path = os.path.join(depth_path, version_dir)
            if not os.path.isdir(version_path):
                continue

            for file_name in os.listdir(version_path):
                if not file_name.endswith(".json") or "_group" in file_name:
                    continue

                file_path = os.path.join(version_path, file_name)

                try:
                    with open(file_path, "r") as f:
                        file_data = json.load(f)

                    modified = False
                    file_nodes_modified = 0

                    for node in file_data.get("nodes", []):
                        if "url" in node:
                            del node["url"]
                            modified = True
                            file_nodes_modified += 1

                    if modified:
                        with open(file_path, "w") as f:
                            json.dump(file_data, f, indent=2)

                        files_processed += 1
                        nodes_modified += file_nodes_modified
                        logger.debug(
                            f"Removed URLs from {file_path} ({file_nodes_modified} nodes)"
                        )
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {str(e)}")

    logger.info(f"URL removal from GraphGenerator files completed for {topic_name}")
    logger.info(
        f"Processed {files_processed} files and removed URLs from {nodes_modified} nodes"
    )


def remove_urls_from_state_files(topic_path):
    """
    Remove URLs from nodes in State kg_depth_N.json files.

    Args:
        topic_path (str): Path to the specific topic directory
    """
    topic_name = os.path.basename(topic_path)
    domain_name = os.path.basename(os.path.dirname(topic_path))
    topic_id = os.path.basename(os.path.dirname(os.path.dirname(topic_path)))

    logger.info(
        f"Removing URLs from state files for {domain_name}/{topic_id}/{topic_name}"
    )

    states_path = os.path.join(topic_path, "kg", "States")

    if not os.path.exists(states_path):
        logger.error(f"Error: States directory not found at {states_path}")
        return

    files_processed = 0
    nodes_modified = 0

    for file_name in os.listdir(states_path):
        if not file_name.startswith("kg_depth_") or not file_name.endswith(".json"):
            continue

        file_path = os.path.join(states_path, file_name)

        try:
            with open(file_path, "r") as f:
                file_data = json.load(f)

            modified = False
            file_nodes_modified = 0

            for node in file_data.get("nodes", []):
                if "url" in node:
                    del node["url"]
                    modified = True
                    file_nodes_modified += 1

            if modified:
                with open(file_path, "w") as f:
                    json.dump(file_data, f, indent=2)

                files_processed += 1
                nodes_modified += file_nodes_modified
                logger.info(
                    f"Removed URLs from {file_path} ({file_nodes_modified} nodes)"
                )
        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}")

    logger.info(f"URL removal from state files completed for {topic_name}")
    logger.info(
        f"Processed {files_processed} files and removed URLs from {nodes_modified} nodes"
    )


def generate_url_coverage_report(topic_path, output_file=None):
    """
    Generate a report on URL coverage in State files.

    Args:
        topic_path (str): Path to the specific topic directory
        output_file (str, optional): Path to save the report

    Returns:
        dict: Report data
    """
    topic_name = os.path.basename(topic_path)
    domain_name = os.path.basename(os.path.dirname(topic_path))
    topic_id = os.path.basename(os.path.dirname(os.path.dirname(topic_path)))

    logger.info(
        f"Generating URL coverage report for {domain_name}/{topic_id}/{topic_name}"
    )

    states_path = os.path.join(topic_path, "kg", "States")

    if not os.path.exists(states_path):
        logger.error(f"Error: States directory not found at {states_path}")
        return None

    report = {
        "topic": topic_name,
        "domain": domain_name,
        "topic_id": topic_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "coverage_by_depth": {},
        "overall": {
            "total_nodes": 0,
            "nodes_with_url": 0,
            "coverage_percentage": 0,
            "unique_urls": set(),
        },
    }

    for file_name in sorted(
        os.listdir(states_path),
        key=lambda x: (
            int(x.split("_")[2].split(".")[0]) if x.startswith("kg_depth_") else 0
        ),
    ):
        if not file_name.startswith("kg_depth_") or not file_name.endswith(".json"):
            continue

        file_path = os.path.join(states_path, file_name)
        depth = file_name.split("_")[2].split(".")[0]

        try:
            with open(file_path, "r") as f:
                file_data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading state file {file_path}: {str(e)}")
            continue

        total_nodes = len(file_data.get("nodes", []))
        nodes_with_url = sum(1 for node in file_data.get("nodes", []) if "url" in node)
        urls = [node.get("url") for node in file_data.get("nodes", []) if "url" in node]
        unique_urls = set(urls)

        coverage_percentage = (
            round(nodes_with_url / total_nodes * 100, 2) if total_nodes > 0 else 0
        )

        report["coverage_by_depth"][depth] = {
            "total_nodes": total_nodes,
            "nodes_with_url": nodes_with_url,
            "coverage_percentage": coverage_percentage,
            "unique_urls_count": len(unique_urls),
            "unique_urls": list(unique_urls),
        }

        report["overall"]["total_nodes"] += total_nodes
        report["overall"]["nodes_with_url"] += nodes_with_url
        report["overall"]["unique_urls"].update(unique_urls)

    if report["overall"]["total_nodes"] > 0:
        report["overall"]["coverage_percentage"] = round(
            report["overall"]["nodes_with_url"]
            / report["overall"]["total_nodes"]
            * 100,
            2,
        )

    report["overall"]["unique_urls"] = list(report["overall"]["unique_urls"])
    report["overall"]["unique_urls_count"] = len(report["overall"]["unique_urls"])

    logger.info("\nURL Coverage Report by Depth:")
    logger.info("-" * 80)
    logger.info(
        f"{'Depth':<10}{'Total Nodes':<15}{'Nodes w/ URL':<15}{'Coverage %':<15}{'Unique URLs':<15}"
    )
    logger.info("-" * 80)

    for depth, stats in report["coverage_by_depth"].items():
        logger.info(
            f"{depth:<10}{stats['total_nodes']:<15}{stats['nodes_with_url']:<15}"
            f"{stats['coverage_percentage']:<15.2f}{stats['unique_urls_count']:<15}"
        )

    logger.info("-" * 80)
    logger.info(
        f"Overall: {report['overall']['nodes_with_url']}/{report['overall']['total_nodes']} nodes "
        f"({report['overall']['coverage_percentage']}%)"
    )
    logger.info(f"Total Unique URLs: {report['overall']['unique_urls_count']}")

    if output_file:
        try:
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report saved to {output_file}")
        except Exception as e:
            logger.error(f"Error saving report to {output_file}: {str(e)}")

    return report


def process_all_topics(
    base_path,
    operation,
    output_dir=None,
    domain_filter=None,
    topic_id_filter=None,
    topic_filter=None,
):
    """
    Process all topics in the SciWiki-100 directory structure.

    Args:
        base_path (str): Base path to the SciWiki-100 directory
        operation (str): Operation to perform (add/remove/report)
        output_dir (str, optional): Directory to save output files
        domain_filter (str, optional): Only process topics in this domain
        topic_id_filter (str, optional): Only process topics with this ID
        topic_filter (str, optional): Only process topics with this name
    """
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    domains = [
        d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))
    ]

    if domain_filter:
        domains = [d for d in domains if d == domain_filter]

    total_topics_processed = 0

    for domain in domains:
        domain_path = os.path.join(base_path, domain)

        topic_ids = [
            d
            for d in os.listdir(domain_path)
            if os.path.isdir(os.path.join(domain_path, d))
        ]

        if topic_id_filter:
            topic_ids = [d for d in topic_ids if d == topic_id_filter]

        for topic_id in topic_ids:
            topic_id_path = os.path.join(domain_path, topic_id)

            topics = [
                d
                for d in os.listdir(topic_id_path)
                if os.path.isdir(os.path.join(topic_id_path, d))
            ]

            if topic_filter:
                topics = [d for d in topics if d == topic_filter]

            for topic in topics:
                topic_path = os.path.join(topic_id_path, topic)

                if not os.path.exists(os.path.join(topic_path, "kg")):
                    logger.warning(
                        f"Skipping {domain}/{topic_id}/{topic} - no kg directory"
                    )
                    continue

                logger.info(f"Processing {domain}/{topic_id}/{topic}")

                if operation == "add":

                    if output_dir:
                        gen_stats_file = os.path.join(
                            output_dir,
                            f"{domain}_{topic_id}_{topic}_generator_stats.json",
                        )
                        state_stats_file = os.path.join(
                            output_dir, f"{domain}_{topic_id}_{topic}_state_stats.json"
                        )
                        report_file = os.path.join(
                            output_dir, f"{domain}_{topic_id}_{topic}_report.json"
                        )
                    else:
                        gen_stats_file = None
                        state_stats_file = None
                        report_file = None

                    # Step 1: Add URLs to GraphGenerator files
                    add_urls_to_graph_generator_files(
                        base_path, topic_path, gen_stats_file
                    )

                    # Step 2: Add URLs to State files
                    add_urls_to_state_files(topic_path, state_stats_file)

                    # Step 3: Generate report
                    generate_url_coverage_report(topic_path, report_file)

                elif operation == "remove":
                    # Step 1: Remove URLs from GraphGenerator files
                    remove_urls_from_graph_generator_files(topic_path)

                    # Step 2: Remove URLs from State files
                    remove_urls_from_state_files(topic_path)

                elif operation == "report":
                    if output_dir:
                        report_file = os.path.join(
                            output_dir, f"{domain}_{topic_id}_{topic}_report.json"
                        )
                    else:
                        report_file = None

                    # Generate report
                    generate_url_coverage_report(topic_path, report_file)

                total_topics_processed += 1

    logger.info(f"Processing complete. Processed {total_topics_processed} topics.")


def main():
    parser = argparse.ArgumentParser(description="URL Mapping Tool for SciWiki-100")

    parser.add_argument(
        "--base_path",
        type=str,
        default="../output/apollo/gen_articles/SciWiki-100",
        help="Base path to the SciWiki-100 directory",
    )

    parser.add_argument(
        "--operation",
        type=str,
        # required=True,
        default="add",
        choices=["add", "remove", "report"],
        help="Operation to perform (add, remove, or report URLs)",
    )

    parser.add_argument(
        "--output_dir",
        type=str,
        default="../output/apollo/gen_articles/SciWiki-100/_reports/all_domains_2",
        help="Directory to save output files (optional)",
    )

    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Only process topics in this domain (optional)",
    )

    parser.add_argument(
        "--topic_id",
        type=str,
        default=None,
        help="Only process topics with this ID (optional)",
    )

    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Only process topics with this name (optional)",
    )

    parser.add_argument(
        "--single_topic_path",
        type=str,
        default=None,
        help="Process a single topic at this path (overrides other filters)",
    )

    args = parser.parse_args()

    if args.output_dir and not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    if args.output_dir:
        log_file = os.path.join(args.output_dir, "url_mapping.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(file_handler)

    if args.single_topic_path:
        topic_path = args.single_topic_path

        if not os.path.exists(topic_path):
            logger.error(f"Error: Topic path not found at {topic_path}")
            return

        if not os.path.exists(os.path.join(topic_path, "kg")):
            logger.error(f"Error: No kg directory found at {topic_path}")
            return

        if args.operation == "add":
            if args.output_dir:
                topic_name = os.path.basename(topic_path)
                domain_name = os.path.basename(
                    os.path.dirname(os.path.dirname(topic_path))
                )
                topic_id = os.path.basename(os.path.dirname(topic_path))

                gen_stats_file = os.path.join(
                    args.output_dir,
                    f"{domain_name}_{topic_id}_{topic_name}_generator_stats.json",
                )
                state_stats_file = os.path.join(
                    args.output_dir,
                    f"{domain_name}_{topic_id}_{topic_name}_state_stats.json",
                )
                report_file = os.path.join(
                    args.output_dir,
                    f"{domain_name}_{topic_id}_{topic_name}_report.json",
                )
            else:
                gen_stats_file = None
                state_stats_file = None
                report_file = None

            # Step 1: Add URLs to GraphGenerator files
            add_urls_to_graph_generator_files(
                os.path.dirname(os.path.dirname(os.path.dirname(topic_path))),
                topic_path,
                gen_stats_file,
            )

            # Step 2: Add URLs to State files
            add_urls_to_state_files(topic_path, state_stats_file)

            # Step 3: Generate report
            generate_url_coverage_report(topic_path, report_file)

        elif args.operation == "remove":
            # Step 1: Remove URLs from GraphGenerator files
            remove_urls_from_graph_generator_files(topic_path)

            # Step 2: Remove URLs from State files
            remove_urls_from_state_files(topic_path)

        elif args.operation == "report":
            if args.output_dir:
                topic_name = os.path.basename(topic_path)
                domain_name = os.path.basename(
                    os.path.dirname(os.path.dirname(topic_path))
                )
                topic_id = os.path.basename(os.path.dirname(topic_path))

                report_file = os.path.join(
                    args.output_dir,
                    f"{domain_name}_{topic_id}_{topic_name}_report.json",
                )
            else:
                report_file = None

            generate_url_coverage_report(topic_path, report_file)

    else:
        process_all_topics(
            args.base_path,
            args.operation,
            args.output_dir,
            args.domain,
            args.topic_id,
            args.topic,
        )


if __name__ == "__main__":
    main()
