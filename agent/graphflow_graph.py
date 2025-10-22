"""GraphFlow graph definition for video agent pipeline.

This module defines the state-based graph structure for the video generation
workflow. It supports both sequential and parallel execution modes.

Sequential Mode: Processes all chapters in one script_gen_node call
Parallel Mode: Dynamically creates one node per chapter and executes in parallel

The graph uses GraphFlow's StateGraph with reducers for automatic state merging
during parallel execution and conditional edges for branching logic.
"""

import logging
import os
from typing import Any, Dict, List

from .GraphFlow.graphflow import Command, StateGraph
from .graphflow_nodes import (
    compose_node,
    ingest_node,
    merge_node,
    script_gen_node,
    segment_node,
)

logger = logging.getLogger(__name__)


def create_video_agent_graph() -> Any:
    """Create the main video generation pipeline with GraphFlow.

    Detects parallelization mode from MAX_WORKERS and creates appropriate graph.

    This graph implements the core workflow:
    1. Ingest: Read and parse input document
    2. Segment: Extract chapters from document
    3. Script Gen: Generate LLM-based slide scripts (sequential or parallel)

    Plus optional branches:
    - Compose: Create video for each chapter
    - Merge: Merge all chapter videos into final output

    Returns:
        Compiled GraphFlow graph ready for execution
    """
    # Detect parallelization mode
    try:
        max_workers = int(os.getenv("MAX_WORKERS", "1"))
    except Exception:
        max_workers = 1

    if max_workers > 1:
        logger.info(f"Creating parallel graph with {max_workers} workers")
        return create_parallel_graph()
    else:
        logger.info("Creating sequential graph")
        return create_sequential_graph()


def create_sequential_graph() -> Any:
    """Create a sequential-only graph (one script_gen_node for all chapters).

    This is the baseline approach where all chapters are processed in a single node.

    Returns:
        Compiled GraphFlow graph in sequential mode
    """

    # Define state reducers for automatic field merging
    state_reducers = {
        "chapters": "extend",  # Collect all chapters
        "script_gen": "extend",  # Collect all scripts
        "videos": "extend",  # Collect all videos
        "composition_list": "extend",  # Collect composition results
        "metadata": "merge",  # Merge metadata dictionaries
        "processing_log": "extend",  # Collect all log entries
        "errors": "extend",  # Collect all errors
    }

    # Create the state graph
    graph = StateGraph(state_reducers=state_reducers)

    # Add core nodes
    graph.add_node("ingest", ingest_node)
    graph.add_node("segment", segment_node)
    graph.add_node("script_gen", script_gen_node)
    graph.add_node("compose", compose_node)
    graph.add_node("merge", merge_node)

    # Set entry point
    graph.set_entry_point("ingest")

    # Add sequential edges for main pipeline
    graph.add_edge("ingest", "segment")
    graph.add_edge("segment", "script_gen")

    # Conditional routing after script generation
    def route_after_script_gen(state: Dict[str, Any]) -> str | List[str]:
        """Route based on pipeline flags."""
        if state.get("full_pipeline") or state.get("compose"):
            logger.debug("Routing to compose node")
            return "compose"
        else:
            logger.debug("Pipeline ends after script generation")
            return "__end__"

    graph.add_conditional_edges("script_gen", route_after_script_gen)

    # Conditional routing after compose
    def route_after_compose(state: Dict[str, Any]) -> str | List[str]:
        """Route based on merge flag."""
        if state.get("merge"):
            logger.debug("Routing to merge node")
            return "merge"
        else:
            logger.debug("Pipeline ends after compose")
            return "__end__"

    graph.add_conditional_edges("compose", route_after_compose)

    # Compile and return
    compiled_graph = graph.compile()
    logger.debug("Sequential graph compiled successfully")

    return compiled_graph


def create_parallel_graph() -> Any:
    """Create a parallel execution graph.

    NOTE: Phase 2 enhancement - Currently uses sequential execution with
    parallel-ready infrastructure. Full fan-out/fan-in will be implemented
    in a future phase using GraphFlow's engine directly.

    For now, this returns the same graph as sequential, but with the
    infrastructure in place for parallelization.

    Returns:
        Compiled GraphFlow graph (currently sequential with parallel-ready state)
    """
    # For now, use sequential execution
    # Future enhancement: implement true fan-out/fan-in with engine support
    logger.info("Creating parallel-ready graph (currently sequential)")
    return create_sequential_graph()


def prepare_graph_input(
    input_path: str,
    run_id: str | None = None,
    google: Any = None,
    full_pipeline: bool = False,
    compose: bool = False,
    merge: bool = False,
) -> Dict[str, Any]:
    """Prepare initial state for graph execution.

    Args:
        input_path: Path to input document
        run_id: Optional run ID for checkpoint/artifact tracking
        google: Optional GoogleServices instance
        full_pipeline: Execute full pipeline (ingest -> merge)
        compose: Execute composition step
        merge: Execute merge step

    Returns:
        Initial state dictionary for graph.invoke()
    """
    import uuid

    if not run_id:
        run_id = str(uuid.uuid4())

    initial_state = {
        "input_path": input_path,
        "run_id": run_id,
        "full_pipeline": full_pipeline,
        "compose": compose,
        "merge": merge,
    }

    if google is not None:
        initial_state["google"] = google

    logger.debug(f"Prepared graph input for run {run_id}")

    return initial_state
