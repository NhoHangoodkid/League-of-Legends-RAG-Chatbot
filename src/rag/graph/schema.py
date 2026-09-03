"""
Knowledge Graph Schema for LoL Knowledge Bot.

Defines the ontology of node types, edge types, and their properties
for the Neo4j-backed Knowledge Graph.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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


class EdgeType(Enum):
    """Types of relationships in the Knowledge Graph."""

    # Champion → Ability
    HAS_ABILITY = "HAS_ABILITY"

    # Champion → Role/Tags
    HAS_ROLE = "HAS_ROLE"

    # Champion → CC/Effect (aggregated from abilities)
    HAS_CC = "HAS_CC"
    HAS_EFFECT = "HAS_EFFECT"

    # Champion → Strategic metadata
    HAS_PLAYSTYLE = "HAS_PLAYSTYLE"
    HAS_POWER_CURVE = "HAS_POWER_CURVE"
    HAS_WIN_CONDITION = "HAS_WIN_CONDITION"

    # Champion ↔ Champion (matchup relationships)
    COUNTERS = "COUNTERS"
    SYNERGIZES_WITH = "SYNERGIZES_WITH"

    # Champion → Item/Rune (build relationships)
    USES_ITEM = "USES_ITEM"
    USES_RUNE = "USES_RUNE"

    # Item → Item (build path)
    BUILDS_FROM = "BUILDS_FROM"
    BUILDS_INTO = "BUILDS_INTO"

    # Ability → CC/Effect (per-ability granularity)
    ABILITY_HAS_CC = "ABILITY_HAS_CC"
    ABILITY_HAS_EFFECT = "ABILITY_HAS_EFFECT"


#-----------------------------------------------------------------------------
# Node property schemas — define what data each node type carries
#-----------------------------------------------------------------------------

CHAMPION_PROPERTIES = [
    "champion_id",   # Canonical ID (e.g. "Aatrox")
    "name",          # Display name
    "title",         # Title (e.g. "the Darkin Blade")
    "short_lore",    # Short lore blurb
    "resource",      # Resource type (Mana, Energy, etc.)
    "attack_type",   # Melee / Ranged
    "adaptive_type", # Physical / Magic
    "difficulty",    # Difficulty rating (1-10)
    "image",         # Image filename
    # Stats stored as JSON string for Neo4j compatibility
    "stats_json",    # Full stats dict as JSON
]

ABILITY_PROPERTIES = [
    "ability_id",    # e.g. "Aatrox_Q"
    "champion_id",   # Parent champion
    "key",           # Q / W / E / R / passive
    "name",          # Ability name
    "description",   # Cleaned description text
    "cooldown_json", # Cooldown values as JSON
    "cost_json",     # Cost values as JSON
    "range_json",    # Range values as JSON
    "maxrank",       # Max rank (usually 5, R=3)
]

ITEM_PROPERTIES = [
    "item_id",       # Numeric ID as string
    "name",          # Item name
    "description",   # Description text
    "plaintext",     # Short description
    "cost_total",    # Total gold cost
    "cost_base",     # Base/combine cost
    "cost_sell",     # Sell value
    "stats_json",    # Stats dict as JSON
    "image",         # Image filename
]

RUNE_PROPERTIES = [
    "rune_id",       # Rune ID
    "name",          # Rune name
    "tree",          # Rune tree (Precision, Domination, etc.)
    "description",   # Short description
    "long_description",  # Full description
]


@dataclass
class GraphNode:
    """Represents a node to be inserted into the graph."""

    node_id: str
    node_type: NodeType
    properties: Dict[str, Any] = field(default_factory = dict)


@dataclass
class GraphEdge:
    """Represents an edge to be inserted into the graph."""

    source_id: str
    target_id: str
    edge_type: EdgeType
    properties: Dict[str, Any] = field(default_factory = dict)
