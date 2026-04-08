from typing import Dict

from guardrail_ai.wdag.node import Node


class WDAG:
    """
    Weighted Directed Acyclic Graph (WDAG)
    Manages nodes, dependencies, and failure propagation.
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}

    # -----------------------------
    # Node Management
    # -----------------------------
    def add_node(self, node: Node) -> None:
        if node.name in self.nodes:
            raise ValueError(f"Node '{node.name}' already exists.")

        self.nodes[node.name] = node

    def get_node(self, name: str) -> Node:
        if name not in self.nodes:
            raise ValueError(f"Node '{name}' not found.")

        return self.nodes[name]

    # -----------------------------
    # Edge Management
    # -----------------------------
    def add_edge(self, source: str, target: str, weight: float = 1.0) -> None:
        if source not in self.nodes or target not in self.nodes:
           raise ValueError("Both nodes must exist before creating an edge.")

        self.nodes[source].add_downstream(self.nodes[target])

    # store weight
        if not hasattr(self, "weights"):
           self.weights = {}

        self.weights[(source, target)] = weight
    # -----------------------------
    # Failure Injection
    # -----------------------------
    def inject_failure(self, node_name: str, failure: Dict) -> None:
        """
        Inject a system failure into a node.
        This triggers downstream locking.
        """
        node = self.get_node(node_name)

        node.mark_failure(failure)

        # propagate impact
        self.propagate_impact(node)
        
        
    def _status_to_score(self, status: str) -> float:
        mapping = {
        "green": 1.0,
        "warning": 0.6,
        "critical": 0.0,
        "locked": 0.0,
        "grey": 0.5,
    }
        return mapping.get(status, 0.0)
    # -----------------------------
    # Failure Propagation
    # -----------------------------
    def propagate_impact(self, node: Node) -> None:

        for child in node.downstream:

            weight = self.weights.get((node.name, child.name), 1.0)

        # simple blast logic
            if node.status == "critical" and weight >= 0.5:
               child.update_status("critical")
            elif node.status == "warning" and weight >= 0.5:
               child.update_status("warning")

        # continue propagation
            self.propagate_impact(child)
    
    
    def reset(self) -> None:
        for node in self.nodes.values():
            node.reset()

    # -----------------------------
    # Graph State (for UI / API)
    # -----------------------------
    def to_dict(self) -> Dict:
        return {
            name: node.to_dict()
            for name, node in self.nodes.items()
        }