"""
Knowledge Graph Schema for LoL Knowledge Bot.

Defines the ontology of node types, edge types, and their properties
for the Neo4j-backed Knowledge Graph.
"""

from enum import Enum


class NodeType(Enum):
    """Types of nodes in the Knowledge Graph."""
    CHAMPION = "Champion"
    ABILITY = "Ability"
    ITEM = "Item"
    RUNE = "Rune"
    ROLE = "Role"
    CC_TYPE = "CrowdControl"
    EFFECT = "Effect"
    PLAYSTYLE = "Playstyle"
    POWER_CURVE = "PowerCurve"
    WIN_CONDITION = "WinCondition"
    CHUNK = "Chunk"


class EdgeType(Enum):
    """Types of relationships in the Knowledge Graph."""
    HAS_ABILITY = "HAS_ABILITY"
    HAS_ROLE = "HAS_ROLE"
    HAS_CC = "HAS_CC"
    HAS_EFFECT = "HAS_EFFECT"
    HAS_PLAYSTYLE = "HAS_PLAYSTYLE"
    HAS_POWER_CURVE = "HAS_POWER_CURVE"
    HAS_WIN_CONDITION = "HAS_WIN_CONDITION"
    COUNTERS = "COUNTERS"
    SYNERGIZES_WITH = "SYNERGIZES_WITH"
    USES_ITEM = "USES_ITEM"
    USES_RUNE = "USES_RUNE"
    BUILDS_FROM = "BUILDS_FROM"
    BUILDS_INTO = "BUILDS_INTO"
    ABILITY_HAS_CC = "ABILITY_HAS_CC"
    ABILITY_HAS_EFFECT = "ABILITY_HAS_EFFECT"
    HAS_CHUNK = "HAS_CHUNK"


champion_properties = [
    "champion_id",
    "name",
    "title",
    "short_lore",
    "resource",
    "attack_type",
    "adaptive_type",
    "difficulty",
    "image",
    "stats_json",
]

ability_properties = [
    "ability_id",
    "champion_id",
    "key",
    "name",
    "description",
    "cooldown_json",
    "cost_json",
    "range_json",
    "maxrank",
]

item_properties = [
    "item_id",
    "name",
    "description",
    "plaintext",
    "cost_total",
    "cost_base",
    "cost_sell",
    "stats_json",
    "image",
]

rune_properties = [
    "rune_id",
    "name",
    "tree",
    "description",
    "long_description",
]


class GraphNode:
    """Represents a node to be inserted into the graph."""

    def __init__(self, node_id, node_type, properties = None):
        self.node_id = node_id
        self.node_type = node_type
        self.properties = properties or {}

    def __repr__(self):
        return f"GraphNode({self.node_id}, {self.node_type})"


class GraphEdge:
    """Represents an edge to be inserted into the graph."""

    def __init__(self, source_id, target_id, edge_type, properties = None):
        self.source_id = source_id
        self.target_id = target_id
        self.edge_type = edge_type
        self.properties = properties or {}

    def __repr__(self):
        return f"GraphEdge({self.source_id} -> {self.target_id}, {self.edge_type})"
