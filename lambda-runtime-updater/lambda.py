import boto3
from packaging.version import Version, InvalidVersion
import argparse
from typing import Optional, List, Dict, Any, Tuple
import logging
import colorlog
from concurrent.futures import ThreadPoolExecutor, as_completed


lambda_client = boto3.client("lambda")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update outdated Lambda Python runtimes.")
    parser.add_argument(
        "--python_version", "-a",
        required=True,
        help="Target Python runtime (e.g. python3.12)",
    )
    args = parser.parse_args()
    _validate_runtime(args.python_version)
    return args


def _validate_runtime(runtime: str) -> None:
    """Raise early with a clear message if the runtime string is malformed."""
    if not runtime.startswith("python"):
        raise ValueError(f"Runtime must start with 'python', got: {runtime!r}")
    version_str = runtime.split("python", 1)[-1]
    try:
        Version(version_str)
    except InvalidVersion:
        raise ValueError(f"Invalid Python version in runtime string: {runtime!r}")


# ── Pagination fix ────────────────────────────────────────────────────────────

def list_lambda_functions() -> List[Dict[str, Any]]:
    """
    Return ALL Lambda functions in the account, handling AWS pagination.

    boto3's list_functions() returns at most 50 functions per call.
    Without pagination the remaining functions are silently dropped.
    """
    functions: List[Dict[str, Any]] = []
    paginator = lambda_client.get_paginator("list_functions")
    for page in paginator.paginate():
        functions.extend(page.get("Functions", []))
    return functions


# ── Runtime filtering ─────────────────────────────────────────────────────────

def get_python_name_runtime(lambda_json_list: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """
    Extract (name, runtime) pairs for Python-only Lambda functions.

    Non-Python runtimes (nodejs, java, …) are skipped so that
    compare_runtime never receives an incompatible string.
    """
    result = []
    for item in lambda_json_list:
        name = item.get("FunctionName", "")
        runtime = item.get("Runtime", "")
        if name and runtime.startswith("python"):
            result.append((name, runtime))
    return result


# ── Version comparison ────────────────────────────────────────────────────────

def compare_runtime(runtime: str, target_runtime: str) -> bool:
    """Return True when *runtime* is older than *target_runtime*."""
    return (
        Version(runtime.split("python", 1)[-1])
        < Version(target_runtime.split("python", 1)[-1])
    )


# ── Concurrent update ─────────────────────────────────────────────────────────

def update_runtime(function_name: str, old_runtime: str, new_runtime: str) -> bool:
    """
    Update one Lambda function's runtime.
    Returns True on success.

    The original version swallowed exceptions silently;
    we now log the
    full error message so failures are visible.
    """
    logging.info("Updating %s  %s → %s", function_name, old_runtime, new_runtime)
    try:
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Runtime=new_runtime,
        )
        return True
    except Exception as exc:
        logging.error("Failed to update %s: %s", function_name, exc)
        return False


def update_runtimes_concurrently(
    targets: List[Tuple[str, str]],
    new_runtime: str,
    max_workers: int = 10,
) -> None:
    """
    Update multiple Lambda functions in parallel using a thread pool.

    Sequential updates are slow at scale; concurrent I/O-bound calls
    finish in roughly the time of a single update.
    """
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_name = {
            pool.submit(update_runtime, name, old_rt, new_runtime): name
            for name, old_rt in targets
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                success = future.result()
                if success:
                    logging.info("Successfully updated %s", name)
            except Exception as exc:
                logging.error("Unexpected error for %s: %s", name, exc)


# ── Logging setup ─────────────────────────────────────────────────────────────

def apply_logs() -> None:
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
            log_colors={
                "DEBUG":    "cyan",
                "INFO":     "green",
                "WARNING":  "yellow",
                "ERROR":    "red",
                "CRITICAL": "bold_red",
            },
        )
    )
    logger = colorlog.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ── Entry point ───────────────────────────────────────────────────────────────

def run(target_runtime: str) -> None:
    apply_logs()

    all_functions = list_lambda_functions()
    python_functions = get_python_name_runtime(all_functions)

    targets = [
        (name, runtime)
        for name, runtime in python_functions
        if compare_runtime(runtime, target_runtime)
    ]

    if not targets:
        logging.info("No functions with a runtime older than %s", target_runtime)
        return

    logging.info(
        "Found %d function(s) to update to %s", len(targets), target_runtime
    )
    update_runtimes_concurrently(targets, target_runtime)


if __name__ == "__main__":
    args = parse_arguments()
    run(args.python_version)