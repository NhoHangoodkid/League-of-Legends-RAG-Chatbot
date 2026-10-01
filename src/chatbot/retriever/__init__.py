"""
Retriever package for LoL Knowledge Bot.

Provides modular retrievers for champion profiles, skills, lanes, counters,
compositions, synergies, and items unified under the DataRetriever facade.
"""

from chatbot.retriever.data_retriever import DataRetriever
from chatbot.retriever.base import BaseRetriever
from chatbot.data.strategic_counters import strategic_composition_counters

__all__ = [
    "DataRetriever",
    "BaseRetriever",
    "strategic_composition_counters",
]
