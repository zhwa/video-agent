"""
GraphFlow: A Parallel Graph Execution Framework for AI Agents

This module provides a state-based graph execution framework that enables
powerful parallel AI agent workflows with sophisticated routing and state management.
Includes built-in LLM utilities for OpenAI, Anthropic, and Ollama.
"""

__version__ = "1.0.0"
__author__ = "GraphFlow Contributors"
__license__ = "MIT"

import asyncio
import copy
import warnings
import time
from typing import Any, Dict, List, Callable, Union, Optional, TypeVar, Generic, get_type_hints
from dataclasses import dataclass

# Import the new execution engine
try:
    from engine import ParallelGraphExecutor, State as EngineState, GraphTopologyAnalyzer
    ENGINE_AVAILABLE = True
except ImportError as e1:
    try:
        from .engine import ParallelGraphExecutor, State as EngineState, GraphTopologyAnalyzer
        ENGINE_AVAILABLE = True
    except ImportError as e2:
        ENGINE_AVAILABLE = False
        # Fallback - we'll define minimal versions
        class ParallelGraphExecutor:
            def __init__(self, *args, **kwargs):
                raise ImportError(f"Parallel execution engine not available: {e1}, {e2}")
        class EngineState(dict):
            pass
        class GraphTopologyAnalyzer:
            def __init__(self, *args, **kwargs):
                raise ImportError(f"Graph topology analyzer not available: {e1}, {e2}")

# Import LLM utilities
try:
    from .llm_utils import (
        call_llm, configure_llm, ask_llm, chat_with_llm, 
        call_llm_async, get_llm_config
    )
    LLM_AVAILABLE = True
except ImportError:
    # Fallback if llm_utils not available - try absolute import
    try:
        from llm_utils import (
            call_llm, configure_llm, ask_llm, chat_with_llm, 
            call_llm_async, get_llm_config
        )
        LLM_AVAILABLE = True
    except ImportError:
        LLM_AVAILABLE = False
        def call_llm(*args, **kwargs):
            raise ImportError("LLM utilities not available. Ensure llm_utils.py is present.")
        def configure_llm(*args, **kwargs):
            raise ImportError("LLM utilities not available. Ensure llm_utils.py is present.")
        ask_llm = chat_with_llm = call_llm_async = get_llm_config = call_llm

StateT = TypeVar('StateT', bound=Dict[str, Any])
NodeT = TypeVar('NodeT')

# Special constants
START = "__start__"
END = "__end__"

# Core execution classes for GraphFlow
class BaseNode:
    def __init__(self): self.params,self.successors={},{}
    def set_params(self,params): self.params=params
    def next(self,node,action="default"):
        if action in self.successors: warnings.warn(f"Overwriting successor for action '{action}'")
        self.successors[action]=node; return node
    def prep(self,shared): pass
    def exec(self,prep_res): pass
    def post(self,shared,prep_res,exec_res): pass
    def _exec(self,prep_res): return self.exec(prep_res)
    def _run(self,shared): p=self.prep(shared); e=self._exec(p); return self.post(shared,p,e)
    def run(self,shared): 
        if self.successors: warnings.warn("Node won't run successors. Use Flow.")  
        return self._run(shared)
    def __rshift__(self,other): return self.next(other)
    def __sub__(self,action):
        if isinstance(action,str): return _ConditionalTransition(self,action)
        raise TypeError("Action must be a string")

class _ConditionalTransition:
    def __init__(self,src,action): self.src,self.action=src,action
    def __rshift__(self,tgt): return self.src.next(tgt,self.action)

class Node(BaseNode):
    def __init__(self,max_retries=1,wait=0): super().__init__(); self.max_retries,self.wait=max_retries,wait
    def exec_fallback(self,prep_res,exc): raise exc
    def _exec(self,prep_res):
        for self.cur_retry in range(self.max_retries):
            try: return self.exec(prep_res)
            except Exception as e:
                if self.cur_retry==self.max_retries-1: return self.exec_fallback(prep_res,e)
                if self.wait>0: time.sleep(self.wait)

class Flow(BaseNode):
    def __init__(self,start=None): super().__init__(); self.start_node=start
    def start(self,start): self.start_node=start; return start
    def get_next_node(self,curr,action):
        nxt=curr.successors.get(action or "default")
        if not nxt and curr.successors: warnings.warn(f"Flow ends: '{action}' not found in {list(curr.successors)}")
        return nxt
    def _orch(self,shared,params=None):
        curr,p,last_action =copy.copy(self.start_node),(params or {**self.params}),None
        while curr: curr.set_params(p); last_action=curr._run(shared); curr=copy.copy(self.get_next_node(curr,last_action))
        return last_action
    def _run(self,shared): p=self.prep(shared); o=self._orch(shared); return self.post(shared,p,o)
    def post(self,shared,prep_res,exec_res): return exec_res

class AsyncNode(Node):
    async def prep_async(self,shared): pass
    async def exec_async(self,prep_res): pass
    async def exec_fallback_async(self,prep_res,exc): raise exc
    async def post_async(self,shared,prep_res,exec_res): pass
    async def _exec(self,prep_res): 
        for self.cur_retry in range(self.max_retries):
            try: return await self.exec_async(prep_res)
            except Exception as e:
                if self.cur_retry==self.max_retries-1: return await self.exec_fallback_async(prep_res,e)
                if self.wait>0: await asyncio.sleep(self.wait)
    async def run_async(self,shared): 
        if self.successors: warnings.warn("Node won't run successors. Use AsyncFlow.")  
        return await self._run_async(shared)
    async def _run_async(self,shared): p=await self.prep_async(shared); e=await self._exec(p); return await self.post_async(shared,p,e)
    def _run(self,shared): raise RuntimeError("Use run_async.")

@dataclass
class Send:
    """Send a specific payload to a named node (for map-reduce workflows)."""
    node: str
    arg: Any

@dataclass
class Command:
    """Combine state updates with routing decisions."""
    update: Optional[Dict[str, Any]] = None
    goto: Optional[Union[str, List[str], Send, List[Send]]] = None
    resume: Optional[Dict[str, Any]] = None

class GraphNode(Node):
    """Enhanced Node with state management capabilities."""

    def __init__(self, func: Callable[[StateT], Any], name: str = None, **kwargs):
        super().__init__(**kwargs)
        self.func = func
        self.name = name or (func.__name__ if hasattr(func, '__name__') else 'node')

    def prep(self, shared: StateT) -> StateT:
        """Pass the entire state to the node function."""
        return shared

    def exec(self, state: StateT) -> Any:
        """Execute the node function with the state."""
        return self.func(state)

    def post(self, shared: StateT, prep_res: StateT, exec_res: Any) -> str:
        """Update shared state and determine next action."""
        if isinstance(exec_res, Command):
            # Handle Command objects
            if exec_res.update:
                self._update_state(shared, exec_res.update)

            if exec_res.goto:
                if isinstance(exec_res.goto, str):
                    return exec_res.goto
                elif isinstance(exec_res.goto, Send):
                    # Store Send object for the graph to handle
                    shared['__send__'] = exec_res.goto
                    return exec_res.goto.node
                elif isinstance(exec_res.goto, list):
                    # Multiple sends or nodes
                    shared['__sends__'] = exec_res.goto
                    return '__parallel__'

            return "default"

        elif isinstance(exec_res, dict):
            # Standard state update
            self._update_state(shared, exec_res)
            return "default"

        elif isinstance(exec_res, str):
            # Direct routing
            return exec_res

        else:
            # No state update, just continue
            return "default"

    def _update_state(self, shared: StateT, update: Dict[str, Any]):
        """Update the shared state with new values."""
        for key, value in update.items():
            if key in shared and isinstance(shared[key], list) and isinstance(value, list):
                # Append to lists by default
                shared[key].extend(value)
            else:
                # Replace other values
                shared[key] = value

class AsyncGraphNode(AsyncNode, GraphNode):
    """Async version of GraphNode."""

    def __init__(self, func: Callable[[StateT], Any], name: str = None, **kwargs):
        AsyncNode.__init__(self, **kwargs)
        self.func = func
        self.name = name or (func.__name__ if hasattr(func, '__name__') else 'async_node')

    async def prep_async(self, shared: StateT) -> StateT:
        return shared

    async def exec_async(self, state: StateT) -> Any:
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(state)
        else:
            return self.func(state)

    async def post_async(self, shared: StateT, prep_res: StateT, exec_res: Any) -> str:
        return super().post(shared, prep_res, exec_res)

class ConditionalEdge:
    """Represents a conditional edge that routes based on state."""

    def __init__(self, condition: Callable[[StateT], Union[str, List[str]]], 
                 path_map: Optional[Dict[Any, str]] = None):
        self.condition = condition
        self.path_map = path_map or {}

    def __call__(self, state: StateT) -> Union[str, List[str]]:
        result = self.condition(state)

        if self.path_map and result in self.path_map:
            return self.path_map[result]

        return result

class StateGraph(Generic[StateT]):
    """A state-based graph similar to LangGraph with parallel execution capabilities."""

    def __init__(self, state_schema: type = None, state_reducers: Dict[str, str] = None):
        self.state_schema = state_schema
        self.state_reducers = state_reducers or {}
        self.nodes: Dict[str, Union[GraphNode, AsyncGraphNode]] = {}
        self.edges: Dict[str, str] = {}
        self.conditional_edges: Dict[str, ConditionalEdge] = {}
        self.entry_point: Optional[str] = None
        self.compiled = False

        # Store type hints if available
        self.state_hints = {}
        if state_schema:
            try:
                self.state_hints = get_type_hints(state_schema)
            except:
                pass

    def add_node(self, name: str, func: Callable[[StateT], Any], **kwargs) -> 'StateGraph':
        """Add a node to the graph."""
        if self.compiled:
            warnings.warn("Adding node to already compiled graph")

        if asyncio.iscoroutinefunction(func):
            self.nodes[name] = AsyncGraphNode(func, name, **kwargs)
        else:
            self.nodes[name] = GraphNode(func, name, **kwargs)

        return self

    def add_edge(self, from_node: str, to_node: str) -> 'StateGraph':
        """Add a direct edge between nodes."""
        if self.compiled:
            warnings.warn("Adding edge to already compiled graph")

        self.edges[from_node] = to_node
        return self

    def add_conditional_edges(self, from_node: str, 
                            condition: Callable[[StateT], Union[str, List[str]]],
                            path_map: Optional[Dict[Any, str]] = None) -> 'StateGraph':
        """Add conditional routing from a node."""
        if self.compiled:
            warnings.warn("Adding conditional edge to already compiled graph")

        self.conditional_edges[from_node] = ConditionalEdge(condition, path_map)
        return self

    def set_entry_point(self, node_name: str) -> 'StateGraph':
        """Set the starting node for the graph."""
        self.entry_point = node_name
        return self

    def set_state_reducer(self, field_name: str, reducer_type: str) -> 'StateGraph':
        """Set a specific reducer for a state field."""
        self.state_reducers[field_name] = reducer_type
        return self

    def analyze_topology(self) -> 'GraphTopologyAnalyzer':
        """Get a topology analyzer for this graph."""
        if not ENGINE_AVAILABLE:
            raise ImportError("Graph topology analysis requires the engine module")
        return GraphTopologyAnalyzer(self)

    def compile(self, use_parallel_engine: bool = True) -> 'CompiledStateGraph':
        """Compile the graph into an executable form."""
        if not self.entry_point:
            raise ValueError("Must set an entry point before compiling")

        self.compiled = True
        return CompiledStateGraph(self, use_parallel_engine=use_parallel_engine)

class CompiledStateGraph:
    """A compiled, executable version of StateGraph."""

    def __init__(self, graph: StateGraph, use_parallel_engine: bool = True, max_concurrent: int = 10):
        self.graph = graph
        self.use_parallel_engine = use_parallel_engine and ENGINE_AVAILABLE
        self.max_concurrent = max_concurrent

        if self.use_parallel_engine:
            # Use the new parallel execution engine
            self.executor = ParallelGraphExecutor(graph, max_concurrent)
        else:
            # Fall back to the original linear execution
            self._build_flow()

    def _build_flow(self):
        """Build the linear execution graph (fallback mode)."""
        # Create a custom flow that handles state management
        self.flow = StateFlow(self.graph)

    def invoke(self, initial_state: StateT, field_reducers: Dict[str, str] = None) -> Any:
        """Execute the graph with the given initial state."""
        if self.use_parallel_engine:
            # Use parallel execution engine
            return self.executor.invoke(initial_state, field_reducers)
        else:
            # Use legacy linear execution
            return self.flow.run(initial_state)

    async def ainvoke(self, initial_state: StateT, field_reducers: Dict[str, str] = None) -> Any:
        """Async execute the graph with the given initial state."""
        if self.use_parallel_engine:
            # Use parallel execution engine
            return await self.executor.ainvoke(initial_state, field_reducers)
        else:
            # Use legacy execution
            if hasattr(self.flow, 'run_async'):
                return await self.flow.run_async(initial_state)
            else:
                return self.invoke(initial_state, field_reducers)

    def stream(self, initial_state: StateT, field_reducers: Dict[str, str] = None):
        """Stream intermediate results (generator)."""
        if self.use_parallel_engine:
            # For now, just yield the final result
            # TODO: Implement streaming support in parallel engine
            yield self.invoke(initial_state, field_reducers)
        else:
            # Legacy streaming
            yield self.invoke(initial_state, field_reducers)

    def get_execution_mode(self) -> str:
        """Get the current execution mode."""
        return "parallel" if self.use_parallel_engine else "linear"

    def analyze_graph(self):
        """Analyze the graph topology."""
        return self.graph.analyze_topology()

class StateFlow(Flow):
    """Custom Flow that handles StateGraph execution."""

    def __init__(self, graph: StateGraph):
        super().__init__()
        self.graph = graph
        self._setup_nodes()

    def _setup_nodes(self):
        """Setup linear execution nodes and connections."""
        # Set the start node
        if self.graph.entry_point:
            self.start_node = self.graph.nodes[self.graph.entry_point]

        # Connect nodes based on edges and conditional edges
        for node_name, node in self.graph.nodes.items():
            # Handle direct edges
            if node_name in self.graph.edges:
                target = self.graph.edges[node_name]
                if target != END:
                    node.next(self.graph.nodes[target])

            # Handle conditional edges
            if node_name in self.graph.conditional_edges:
                # We'll handle conditional routing in the custom orchestration
                pass

    def get_next_node(self, current_node_name: str, state: StateT) -> Optional[str]:
        """Determine the next node based on current state."""
        # Check for Send/Command routing first
        if '__send__' in state:
            send_obj = state.pop('__send__')
            return send_obj.node

        if '__sends__' in state:
            sends = state.pop('__sends__')
            # For simplicity, handle first send (could be enhanced for parallel)
            if sends and isinstance(sends[0], Send):
                return sends[0].node

        # Check conditional edges
        if current_node_name in self.graph.conditional_edges:
            condition = self.graph.conditional_edges[current_node_name]
            next_node = condition(state)

            if next_node == END:
                return None
            return next_node

        # Check direct edges
        if current_node_name in self.graph.edges:
            next_node = self.graph.edges[current_node_name]
            if next_node == END:
                return None
            return next_node

        return None

    def _orch(self, shared: StateT, params=None):
        """Custom orchestration that handles conditional routing."""
        current_node_name = self.graph.entry_point

        while current_node_name and current_node_name in self.graph.nodes:
            current_node = self.graph.nodes[current_node_name]

            # Execute the current node
            if params:
                current_node.set_params(params)

            action = current_node._run(shared)

            # Determine next node
            if action == END:
                break

            next_node_name = self.get_next_node(current_node_name, shared)

            if not next_node_name:
                break

            current_node_name = next_node_name

        return shared

# Convenience functions for building graphs
def create_graph(state_schema: type = None, state_reducers: Dict[str, str] = None) -> StateGraph:
    """Create a new StateGraph."""
    return StateGraph(state_schema, state_reducers)

def node(func: Callable[[StateT], Any]) -> Callable[[StateT], Any]:
    """Decorator to mark a function as a graph node."""
    func._is_graph_node = True
    return func

# State reducer helpers
def with_reducers(**reducers) -> Dict[str, str]:
    """Create a reducer configuration dictionary."""
    return reducers

def append_to(field: str) -> Dict[str, str]:
    """Create a reducer that appends to a list field."""
    return {field: 'append'}

def extend_list(field: str) -> Dict[str, str]:
    """Create a reducer that extends a list field."""
    return {field: 'extend'}

def merge_dict(field: str) -> Dict[str, str]:
    """Create a reducer that merges dictionary fields."""
    return {field: 'merge'}

def set_value(field: str) -> Dict[str, str]:
    """Create a reducer that sets/replaces a field value."""
    return {field: 'set'}

# Export main classes and functions
__all__ = [
    'StateGraph', 'CompiledStateGraph', 'GraphNode', 'AsyncGraphNode',
    'ConditionalEdge', 'Send', 'Command', 'START', 'END',
    'create_graph', 'node', 'with_reducers', 'append_to', 'extend_list', 'merge_dict', 'set_value',
    # Version and metadata
    '__version__', '__author__', '__license__',
    # New parallel execution classes
    'ParallelGraphExecutor', 'EngineState', 'GraphTopologyAnalyzer',
    # LLM utilities
    'call_llm', 'configure_llm', 'ask_llm', 'chat_with_llm', 
    'call_llm_async', 'get_llm_config'
]