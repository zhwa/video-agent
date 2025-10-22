"""
GraphFlow Parallel Execution Engine

This module provides the core parallel execution engine that transforms GraphFlow
from a linear executor into a true graph traversal system supporting:
- Parallel execution (fan-out/fan-in)
- Dependency-aware scheduling
- Declarative state management with reducers
- Async support for concurrent node execution
"""

import asyncio
from collections import defaultdict, deque
from copy import deepcopy
from typing import Dict, Any, List, Set, Callable, Optional
import logging

logger = logging.getLogger(__name__)

class State(dict):
    """A state object with reducer logic for field-wise merging."""

    def __init__(self, initial_data: Optional[Dict[str, Any]] = None, reducers: Optional[Dict[str, Callable]] = None):
        super().__init__(initial_data or {})
        self.reducers = reducers or {}
        self._last_command: Any = None  # For tracking Command routing
        self._set_default_reducers()

    def _set_default_reducers(self):
        """Set up default reducers for common patterns."""
        if 'append' not in self.reducers:
            self.reducers['append'] = self._append_reducer
        if 'extend' not in self.reducers:
            self.reducers['extend'] = self._extend_reducer
        if 'set' not in self.reducers:
            self.reducers['set'] = self._set_reducer
        if 'merge' not in self.reducers:
            self.reducers['merge'] = self._merge_reducer

    @staticmethod
    def _append_reducer(current: Any, new: Any) -> Any:
        """Append new item to list, or create list if needed."""
        if current is None:
            return [new] if not isinstance(new, list) else new
        if isinstance(current, list):
            if isinstance(new, list):
                return current + new
            else:
                return current + [new]
        return [current, new]

    @staticmethod
    def _extend_reducer(current: Any, new: Any) -> Any:
        """Extend list with new items."""
        if current is None:
            return new if isinstance(new, list) else [new]
        if isinstance(current, list) and isinstance(new, list):
            return current + new
        elif isinstance(current, list):
            return current + [new]
        else:
            return [current] + (new if isinstance(new, list) else [new])

    @staticmethod
    def _set_reducer(current: Any, new: Any) -> Any:
        """Replace current value with new value."""
        return new

    @staticmethod
    def _merge_reducer(current: Any, new: Any) -> Any:
        """Merge dictionaries or replace other types."""
        if isinstance(current, dict) and isinstance(new, dict):
            result = current.copy()
            result.update(new)
            return result
        return new

    def merge(self, update: Dict[str, Any], field_reducers: Optional[Dict[str, str]] = None) -> 'State':
        """
        Merge update into state using field-specific reducers.

        Args:
            update: Dictionary of updates to apply
            field_reducers: Optional mapping of field names to reducer names

        Returns:
            New State object with merged data
        """
        new_state = State(dict(self), self.reducers.copy())
        field_reducers = field_reducers or {}

        for key, value in update.items():
            # Determine which reducer to use
            reducer_name = field_reducers.get(key)

            if reducer_name and reducer_name in self.reducers:
                reducer = self.reducers[reducer_name]
            elif key.endswith('_list') or key.endswith('_history'):
                reducer = self.reducers['extend']
            elif key == 'results':  # Special case for results
                reducer = self.reducers['extend']
            elif isinstance(value, dict) and isinstance(self.get(key), dict):
                reducer = self.reducers['merge']
            else:
                reducer = self.reducers['set']

            old_value = self.get(key)
            new_value = reducer(old_value, value)
            new_state[key] = new_value

        return new_state

    def copy(self) -> 'State':
        """Create a deep copy of the state."""
        new_state = State(deepcopy(dict(self)), self.reducers.copy())
        new_state._last_command = self._last_command
        return new_state

class NodeExecution:
    """Represents a node execution with its state and metadata."""

    def __init__(self, node_name: str, state: 'State', predecessors: Optional[Set[str]] = None):
        self.node_name = node_name
        self.state = state
        self.predecessors = predecessors or set()
        self.task: Optional[asyncio.Task] = None
        self.completed = False
        self.result: Any = None
        self.error: Optional[Exception] = None

class ParallelGraphExecutor:
    """
    Core execution engine that supports parallel node execution with dependency management.

    This replaces the linear while loop with a true graph traversal algorithm that can:
    - Execute multiple nodes in parallel when their dependencies are met
    - Handle fan-out (one node -> multiple successors) 
    - Handle fan-in (multiple nodes -> one successor with join semantics)
    - Manage state updates from concurrent executions
    """

    def __init__(self, graph, max_concurrent: int = 10):
        self.graph = graph
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Build graph topology for efficient traversal
        self._build_topology()

    def _build_topology(self):
        """Build internal data structures for graph traversal."""
        self.successors: Dict[str, List[str]] = defaultdict(list)
        self.predecessors: Dict[str, List[str]] = defaultdict(list)

        # Process direct edges
        for from_node, to_node in self.graph.edges.items():
            if to_node != "__end__":
                self.successors[from_node].append(to_node)
                self.predecessors[to_node].append(from_node)

        # Process conditional edges (we'll determine successors at runtime)
        # For now, just mark that these nodes have conditional outgoing edges
        self.conditional_nodes = set(self.graph.conditional_edges.keys())

    def get_successors(self, node_name: str, state: State) -> List[str]:
        """Get successor nodes for a given node and state."""
        successors = []
        # Check for Command-based routing in state
        if hasattr(state, '_last_command') and state._last_command:
            command = state._last_command
            if hasattr(command, 'goto') and command.goto:
                if isinstance(command.goto, str):
                    if command.goto != "__end__":
                        successors.append(command.goto)
                elif isinstance(command.goto, list):
                    # Only add string node names, skip Send objects
                    for g in command.goto:
                        if isinstance(g, str) and g != "__end__":
                            successors.append(g)
                        # If Send, skip (or handle as needed)
                # Clear the command after processing
                state._last_command = None
                return successors

        # Check direct edges
        direct_successors = self.successors.get(node_name, [])
        successors.extend(direct_successors)

        # Check conditional edges
        if node_name in self.graph.conditional_edges:
            condition = self.graph.conditional_edges[node_name]
            result = condition(state)

            if isinstance(result, str):
                if result != "__end__":
                    successors.append(result)
            elif isinstance(result, list):
                successors.extend([r for r in result if r != "__end__"])

        return list(set(successors))  # Remove duplicates

    def get_entry_nodes(self) -> List[str]:
        """Get nodes that have no predecessors (entry points)."""
        if self.graph.entry_point:
            return [self.graph.entry_point]

        # Find nodes with no incoming edges
        all_nodes = set(self.graph.nodes.keys())
        nodes_with_predecessors = set()

        for preds in self.predecessors.values():
            nodes_with_predecessors.update(preds)

        entry_nodes = all_nodes - nodes_with_predecessors
        return list(entry_nodes)

    def are_dependencies_met(self, node_name: str, completed_nodes: Set[str]) -> bool:
        """Check if all predecessors of a node have completed."""
        required_predecessors = set(self.predecessors.get(node_name, []))

        # If no explicit predecessors but it's a target of multiple command routes,
        # we need to track this differently. For now, let's be conservative.
        if not required_predecessors and node_name in self.graph.nodes:
            # Check if this node is targeted by commands from multiple nodes
            # This is a simple heuristic - in a full implementation, we'd track
            # command routing dependencies more explicitly
            return True

        return required_predecessors.issubset(completed_nodes)

    async def execute_node(self, execution: NodeExecution) -> NodeExecution:
        """Execute a single node asynchronously."""
        async with self.semaphore:
            try:
                node = self.graph.nodes[execution.node_name]

                # Execute the node directly, bypassing the post() method which is for linear execution
                if hasattr(node, 'exec_async') and callable(getattr(node, 'exec_async')):
                    # Async node
                    result = await node.exec_async(execution.state)
                elif hasattr(node, 'func') and asyncio.iscoroutinefunction(node.func):
                    # Async function wrapped in GraphNode
                    result = await node.func(execution.state)
                elif hasattr(node, 'func'):
                    # Sync function wrapped in GraphNode
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, node.func, execution.state)
                elif hasattr(node, 'exec'):
                    # Sync node - run in thread pool to avoid blocking
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, node.exec, execution.state)
                else:
                    raise ValueError(f"Node {execution.node_name} has no executable method")

                execution.result = result
                execution.completed = True

                logger.debug(f"Node {execution.node_name} completed successfully")

            except Exception as e:
                execution.error = e
                execution.completed = True
                logger.error(f"Node {execution.node_name} failed: {e}")

        return execution

    async def ainvoke(self, initial_state: Dict[str, Any], 
                     field_reducers: Optional[Dict[str, str]] = None) -> State:
        """
        Execute the graph asynchronously with parallel node execution.

        Args:
            initial_state: Initial state dictionary
            field_reducers: Optional mapping of field names to reducer names

        Returns:
            Final state after graph execution
        """
        # Initialize state
        state = State(initial_state, self.graph.state_reducers if hasattr(self.graph, 'state_reducers') else {})
        field_reducers = field_reducers or {}

        # Track execution
        completed_nodes: Set[str] = set()
        active_executions: Dict[str, NodeExecution] = {}
        pending_tasks: Set[asyncio.Task] = set()
        # NEW: Track output states for each node (for fan-in merging)
        node_outputs: Dict[str, List[State]] = defaultdict(list)
        # NEW: Track output results for each node (for fan-in merging)
        node_results: Dict[str, List[Any]] = defaultdict(list)

        # Start with entry nodes
        entry_nodes = self.get_entry_nodes()
        if not entry_nodes:
            raise ValueError("No entry nodes found in graph")

        # Initialize the execution queue
        ready_nodes = deque()
        for node_name in entry_nodes:
            if node_name in self.graph.nodes:
                ready_nodes.append(NodeExecution(node_name, state.copy()))

        while ready_nodes or pending_tasks:
            # Start all ready nodes
            while ready_nodes and len(pending_tasks) < self.max_concurrent:
                execution = ready_nodes.popleft()
                # Skip if already completed or active
                if execution.node_name in completed_nodes or execution.node_name in active_executions:
                    continue
                # For fan-in: if node has multiple predecessors, merge their *results* into the state
                preds = self.predecessors.get(execution.node_name, [])
                if len(preds) > 1:
                    merged_state = state.copy()
                    pred_results = [node_results[p][-1] for p in preds if node_results[p]]
                    # Collect all keys from all predecessor results
                    all_keys = set()
                    for pred_result in pred_results:
                        if isinstance(pred_result, dict):
                            all_keys.update(pred_result.keys())
                    # For each key, merge values from all predecessor results
                    for key in all_keys:
                        # Special handling for 'results' to avoid double merging
                        if key == 'results':
                            # Only merge the raw results from predecessors, not from the global state
                            values = [pr.get(key) for pr in pred_results if isinstance(pr, dict) and pr.get(key) is not None]
                            merged_value = []
                            for v in values:
                                if isinstance(v, list):
                                    merged_value.extend(v)
                                else:
                                    merged_value.append(v)
                            merged_state[key] = merged_value
                            continue
                        values = [pr.get(key) for pr in pred_results if isinstance(pr, dict) and pr.get(key) is not None]
                        if not values:
                            continue  # No valid values to merge
                        reducer_name = field_reducers.get(key)
                        if reducer_name and reducer_name in merged_state.reducers:
                            reducer = merged_state.reducers[reducer_name]
                        elif key.endswith('_list') or key.endswith('_history'):
                            reducer = merged_state.reducers['extend']
                        elif any(isinstance(v, dict) for v in values) and isinstance(merged_state.get(key), dict):
                            reducer = merged_state.reducers['merge']
                        else:
                            reducer = merged_state.reducers['set']
                        merged_value = merged_state.get(key)
                        for v in values:
                            merged_value = reducer(merged_value, v)
                        merged_state[key] = merged_value
                    execution.state = merged_state
                # Create and start task
                task = asyncio.create_task(self.execute_node(execution))
                pending_tasks.add(task)
                active_executions[execution.node_name] = execution
                logger.debug(f"Started execution of node: {execution.node_name}")

            # Wait for at least one task to complete
            if pending_tasks:
                done, pending_tasks = await asyncio.wait(
                    pending_tasks, return_when=asyncio.FIRST_COMPLETED
                )

                # Process completed tasks
                for task in done:
                    execution = await task
                    node_name = execution.node_name

                    # Remove from active executions
                    if node_name in active_executions:
                        del active_executions[node_name]

                    if execution.error:
                        # Handle error (for now, just log and continue)
                        logger.error(f"Node {node_name} failed: {execution.error}")
                        completed_nodes.add(node_name)
                        continue

                    # Mark as completed
                    completed_nodes.add(node_name)
                    # NEW: Save the output state and result for this node
                    node_outputs[node_name].append(execution.state.copy())
                    node_results[node_name].append(execution.result)

                    # Update global state based on node result and get routing command
                    routing_command = None
                    if execution.result:
                        # Check if it's a Command before merging
                        try:
                            from .graphflow import Command
                        except ImportError:
                            from graphflow import Command

                        if isinstance(execution.result, Command):
                            routing_command = execution.result

                        state = self._merge_node_result(state, execution.result, field_reducers)

                    # Find newly ready successor nodes using the routing command
                    if routing_command and routing_command.goto:
                        # Use Command routing
                        if isinstance(routing_command.goto, str):
                            successors = [routing_command.goto] if routing_command.goto != "__end__" else []
                        elif isinstance(routing_command.goto, list):
                            # Only add string node names, skip Send objects
                            successors = [g for g in routing_command.goto if isinstance(g, str) and g != "__end__"]
                        else:
                            successors = []
                    else:
                        # Use graph topology
                        successors = self.get_successors(node_name, state)
                    for successor in successors:
                        if (successor not in completed_nodes and 
                            successor not in active_executions and
                            self.are_dependencies_met(successor, completed_nodes)):
                            ready_nodes.append(NodeExecution(successor, state.copy(), {node_name}))
                            logger.debug(f"Node {successor} is now ready to execute")
                    # --- Ensure fan-in/finalization node is always executed ---
                    # If this node is a predecessor to a fan-in node, and all its predecessors are done, enqueue the fan-in node
                    for fanin_node, preds in self.predecessors.items():
                        if len(preds) > 1 and fanin_node not in completed_nodes and fanin_node not in active_executions:
                            if set(preds).issubset(completed_nodes):
                                ready_nodes.append(NodeExecution(fanin_node, state.copy(), set(preds)))
                                logger.debug(f"Fan-in node {fanin_node} is now ready to execute (forced)")
                    # --- Ensure any successor node whose dependencies are met is always executed ---
                    for possible_node in self.successors:
                        if (possible_node not in completed_nodes and
                            possible_node not in active_executions and
                            self.are_dependencies_met(possible_node, completed_nodes)):
                            ready_nodes.append(NodeExecution(possible_node, state.copy(), set(self.predecessors.get(possible_node, []))))
                            logger.debug(f"Node {possible_node} is now ready to execute (forced, all deps met)")

        logger.info(f"Graph execution completed. Processed {len(completed_nodes)} nodes.")
        # Merge the output of the last executed node(s) into the final state
        # Find terminal nodes (nodes with no outgoing edges)
        terminal_nodes = [n for n in completed_nodes if not self.successors.get(n)]
        # Merge the output of all terminal nodes into the final state using reducer logic
        terminal_nodes = [n for n in completed_nodes if not self.successors.get(n)]
        terminal_results = [node_results[n][-1] for n in terminal_nodes if node_results[n]]
        for result in terminal_results:
            state = self._merge_node_result(state, result, field_reducers)
        return state

    def _merge_node_result(self, state: State, result: Any, field_reducers: Dict[str, str]) -> State:
        """Merge node execution result into the global state."""
        # Import here to avoid circular import
        try:
            from .graphflow import Command
        except ImportError:
            from graphflow import Command
        if isinstance(result, Command):
            # Store the command for routing decisions
            state._last_command = result
            if result.update:
                state = state.merge(result.update, field_reducers)
        elif isinstance(result, dict):
            state = state.merge(result, field_reducers)
        # For other result types, we don't update state

        return state

    def invoke(self, initial_state: Dict[str, Any], 
              field_reducers: Optional[Dict[str, str]] = None) -> State:
        """Synchronous wrapper for graph execution."""
        return asyncio.run(self.ainvoke(initial_state, field_reducers))

class GraphTopologyAnalyzer:
    """Utility class for analyzing graph structure and detecting issues."""

    def __init__(self, graph):
        self.graph = graph

    def detect_cycles(self) -> List[List[str]]:
        """Detect cycles in the graph using DFS."""
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node: str, path: List[str]):
            if node in rec_stack:
                # Found cycle
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)

            # Get successors (simplified - doesn't handle conditional edges perfectly)
            successors = []
            if node in self.graph.edges:
                successors.append(self.graph.edges[node])

            for successor in successors:
                if successor != "__end__":
                    dfs(successor, path + [node])

            rec_stack.remove(node)

        for node in self.graph.nodes:
            if node not in visited:
                dfs(node, [])

        return cycles

    def find_unreachable_nodes(self) -> List[str]:
        """Find nodes that cannot be reached from entry points."""
        if not self.graph.entry_point:
            return []

        reachable = set()

        def dfs(node: str):
            if node in reachable or node == "__end__":
                return

            reachable.add(node)

            # Direct edges
            if node in self.graph.edges:
                dfs(self.graph.edges[node])

            # Note: This is simplified and doesn't perfectly handle conditional edges

        dfs(self.graph.entry_point)

        all_nodes = set(self.graph.nodes.keys())
        return list(all_nodes - reachable)