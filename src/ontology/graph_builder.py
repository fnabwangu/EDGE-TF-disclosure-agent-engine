"""graph_builder.py
Builds a NetworkX graph linking ETF -> security -> function
"""
import networkx as nx

def build_graph():
    G = nx.DiGraph()
    G.add_node("ETF-EX-001", type="etf")
    G.add_node("SEC-ABC", type="security")
    G.add_edge("ETF-EX-001", "SEC-ABC", weight=1.0)
    return G
"""## Semantic Knowledge Graph Builder (`src/ontology/graph_builder.py`)

The `graph_builder.py` module constructs and traverses a directed semantic knowledge graph of regulatory statutes, portfolio entities, corporate relationships, qualitative theses, and risk gates within the **EDGE-TF-disclosure-agent-engine**. It establishes verifiable relationship topologies (e.g., `ISSUED_BY`, `SUBJECT_TO_RULE`, `HEDGED_BY`, `SUPPORTS_THEMATIC_CLUSTER`, `FALSIFIED_BY`) to support statutory compliance checks, parent-subsidiary concentration rollups, and causal risk tracking.

---

### Key Capabilities

* **`Directed Entity-Relationship Graph`**: Models nodes (`EntityNode`: tickers, statutory rules, themes, theses, operators) and directional typed edges (`RelationshipEdge`).
* **`Statutory Lineage & Parent Entity Rollups`**: Traverses corporate hierarchies and issuer networks to identify hidden concentration exposures for IRC Subchapter M (5/50 rule) and 1940 Act compliance.
* **`Hypothesis & Derivatives Graph Binding`**: Directly links short options overlays and falsification triggers to underlying equity nodes and thematic clusters.
* **`Graph Export & Path Traversal`**: Provides adjacency exports, neighborhood queries, and path validation algorithms for pre-trade audit trails and compliance dashboards.

# src/ontology/graph_builder.py"""
"""
EDGE-TF Disclosure Agent Engine - Semantic Knowledge Graph Builder.

Constructs, links, and traverses a directed ontological graph connecting
issuers, regulatory rules, thematic mandates, hypotheses, and derivative overlays.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from src.ontology import (
    AssetClassification,
    LiquidityBucket,
    RegulatoryFramework,
    ThematicMandateCluster,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class NodeType(str, Enum):
    ASSET = "ASSET"
    ISSUER = "ISSUER"
    REGULATORY_RULE = "REGULATORY_RULE"
    THEMATIC_CLUSTER = "THEMATIC_CLUSTER"
    INVESTMENT_THESIS = "INVESTMENT_THESIS"
    DERIVATIVE_OVERLAY = "DERIVATIVE_OVERLAY"
    FIDUCIARY_OPERATOR = "FIDUCIARY_OPERATOR"


class EdgeType(str, Enum):
    ISSUED_BY = "ISSUED_BY"
    PARENT_OF = "PARENT_OF"
    SUBJECT_TO_RULE = "SUBJECT_TO_RULE"
    BELONGS_TO_CLUSTER = "BELONGS_TO_CLUSTER"
    HEDGED_BY = "HEDGED_BY"
    BACKED_BY_UNDERLYING = "BACKED_BY_UNDERLYING"
    TARGETS_ASSET = "TARGETS_ASSET"
    AUTHORED_BY = "AUTHORED_BY"
    INVALIDATED_BY = "INVALIDATED_BY"


@dataclass
class EntityNode:
    node_id: str
    node_type: NodeType
    label: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "label": self.label,
            "attributes": self.attributes,
            "created_at_utc": self.created_at_utc,
        }


@dataclass
class RelationshipEdge:
    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "weight": self.weight,
            "properties": self.properties,
            "created_at_utc": self.created_at_utc,
        }


class SemanticGraphBuilder:
    """
    Constructs and manages the directed semantic network mapping assets,
    corporate structures, statutory boundaries, and options overlays.
    """

    def __init__(self):
        self.nodes: Dict[str, EntityNode] = {}
        self.edges: Dict[str, RelationshipEdge] = {}
        self._adjacency_out: Dict[str, List[str]] = {}
        self._adjacency_in: Dict[str, List[str]] = {}
        
        self._bootstrap_regulatory_nodes()
        self._bootstrap_thematic_clusters()

    def _generate_edge_id(self, source_id: str, target_id: str, edge_type: EdgeType) -> str:
        raw_key = f"{source_id}->{edge_type.value}->{target_id}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]

    def _bootstrap_regulatory_nodes(self):
        """Initializes canonical regulatory rule nodes in the graph."""
        for framework in RegulatoryFramework:
            node_id = f"RULE_{framework.name}"
            self.add_node(
                node_id=node_id,
                node_type=NodeType.REGULATORY_RULE,
                label=framework.value,
                attributes={"statutory_body": "SEC_OR_IRS", "framework_name": framework.name}
            )

    def _bootstrap_thematic_clusters(self):
        """Initializes mandate thematic cluster nodes."""
        for cluster in ThematicMandateCluster:
            node_id = f"THEME_{cluster.name}"
            self.add_node(
                node_id=node_id,
                node_type=NodeType.THEMATIC_CLUSTER,
                label=cluster.value,
                attributes={"is_names_rule_eligible": cluster != ThematicMandateCluster.UNCLASSIFIED_NON_MANDATE}
            )

    def add_node(
        self,
        node_id: str,
        node_type: NodeType,
        label: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> EntityNode:
        """Adds an entity node to the graph if it does not already exist."""
        clean_id = node_id.upper()
        if clean_id in self.nodes:
            # Update attributes if existing
            if attributes:
                self.nodes[clean_id].attributes.update(attributes)
            return self.nodes[clean_id]

        node = EntityNode(
            node_id=clean_id,
            node_type=node_type,
            label=label,
            attributes=attributes or {}
        )
        self.nodes[clean_id] = node
        self._adjacency_out[clean_id] = []
        self._adjacency_in[clean_id] = []
        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        properties: Optional[Dict[str, Any]] = None
    ) -> RelationshipEdge:
        """Connects two nodes with a typed directional edge."""
        s_id = source_id.upper()
        t_id = target_id.upper()

        if s_id not in self.nodes:
            raise KeyError(f"Source node {s_id} does not exist in graph.")
        if t_id not in self.nodes:
            raise KeyError(f"Target node {t_id} does not exist in graph.")

        edge_id = self._generate_edge_id(s_id, t_id, edge_type)
        if edge_id in self.edges:
            return self.edges[edge_id]

        edge = RelationshipEdge(
            edge_id=edge_id,
            source_id=s_id,
            target_id=t_id,
            edge_type=edge_type,
            weight=weight,
            properties=properties or {}
        )
        self.edges[edge_id] = edge
        self._adjacency_out[s_id].append(edge_id)
        self._adjacency_in[t_id].append(edge_id)
        return edge

    def link_asset_constituent(
        self,
        ticker: str,
        issuer_name: str,
        asset_class: AssetClassification,
        thematic_cluster: ThematicMandateCluster,
        liquidity_bucket: LiquidityBucket,
        parent_company_id: Optional[str] = None
    ):
        """
        Convenience builder linking an equity asset to its issuer, thematic cluster,
        and applicable statutory regulatory rules.
        """
        asset_id = f"ASSET_{ticker.upper()}"
        issuer_id = f"ISSUER_{ticker.upper()}"

        # 1. Create Nodes
        self.add_node(
            node_id=asset_id,
            node_type=NodeType.ASSET,
            label=ticker.upper(),
            attributes={
                "asset_class": asset_class.value,
                "liquidity_bucket": liquidity_bucket.value,
            }
        )
        self.add_node(
            node_id=issuer_id,
            node_type=NodeType.ISSUER,
            label=issuer_name,
            attributes={"primary_ticker": ticker.upper()}
        )

        # 2. Asset -> Issuer
        self.add_edge(asset_id, issuer_id, EdgeType.ISSUED_BY)

        # 3. Parent Issuer hierarchy linkage (for Subchapter M rollup)
        if parent_company_id:
            parent_id = f"ISSUER_{parent_company_id.upper()}"
            self.add_node(
                node_id=parent_id,
                node_type=NodeType.ISSUER,
                label=parent_company_id.upper()
            )
            self.add_edge(parent_id, issuer_id, EdgeType.PARENT_OF)

        # 4. Asset -> Thematic Cluster
        cluster_node_id = f"THEME_{thematic_cluster.name}"
        if cluster_node_id in self.nodes:
            self.add_edge(asset_id, cluster_node_id, EdgeType.BELONGS_TO_CLUSTER)

        # 5. Asset -> Statutory Rules
        self.add_edge(asset_id, f"RULE_{RegulatoryFramework.IRC_SUBCHAPTER_M.name}", EdgeType.SUBJECT_TO_RULE)
        self.add_edge(asset_id, f"RULE_{RegulatoryFramework.SEC_RULE_22E4.name}", EdgeType.SUBJECT_TO_RULE)
        self.add_edge(asset_id, f"RULE_{RegulatoryFramework.SEC_RULE_35D1.name}", EdgeType.SUBJECT_TO_RULE)

    def link_options_overlay(
        self,
        contract_symbol: str,
        underlying_ticker: str,
        asset_class: AssetClassification,
        strike_price: float,
        expiration_date: str
    ):
        """Links covered calls or short LEAP puts to underlying equity nodes and Rule 18f-4."""
        overlay_id = f"OPT_{contract_symbol.upper()}"
        underlying_id = f"ASSET_{underlying_ticker.upper()}"

        # 1. Overlay Node
        self.add_node(
            node_id=overlay_id,
            node_type=NodeType.DERIVATIVE_OVERLAY,
            label=contract_symbol.upper(),
            attributes={
                "asset_class": asset_class.value,
                "strike_price": strike_price,
                "expiration_date": expiration_date,
                "underlying_ticker": underlying_ticker.upper()
            }
        )

        # 2. Link to Underlying Asset
        if underlying_id in self.nodes:
            edge_type = EdgeType.BACKED_BY_UNDERLYING if asset_class == AssetClassification.DERIVATIVE_COVERED_CALL else EdgeType.TARGETS_ASSET
            self.add_edge(overlay_id, underlying_id, edge_type)

        # 3. Link to Rule 18f-4 Derivatives Risk Governance
        self.add_edge(overlay_id, f"RULE_{RegulatoryFramework.SEC_RULE_18F4.name}", EdgeType.SUBJECT_TO_RULE)

    def get_issuer_group_members(self, issuer_id: str) -> List[str]:
        """
        Traverses parent-subsidiary relationships to find all entities belonging
        to the same corporate group for concentration aggregation.
        """
        clean_issuer = issuer_id.upper()
        visited = set()
        queue = [clean_issuer]

        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)

            # Traverse outgoing PARENT_OF edges
            for edge_id in self._adjacency_out.get(curr, []):
                edge = self.edges[edge_id]
                if edge.edge_type == EdgeType.PARENT_OF:
                    queue.append(edge.target_id)

            # Traverse incoming PARENT_OF edges (climb up to parent)
            for edge_id in self._adjacency_in.get(curr, []):
                edge = self.edges[edge_id]
                if edge.edge_type == EdgeType.PARENT_OF:
                    queue.append(edge.source_id)

        return sorted(list(visited))

    def export_graph_json(self) -> Dict[str, Any]:
        """Serializes complete knowledge graph for audit logging and visualization."""
        return {
            "graph_summary": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "exported_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges.values()],
        }


__all__ = [
    "NodeType",
    "EdgeType",
    "EntityNode",
    "RelationshipEdge",
    "SemanticGraphBuilder",
]
