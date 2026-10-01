"""
Base Retriever class holding knowledge store reference and shared helpers.
"""

from chatbot.knowledge_store import KnowledgeStore, get_knowledge_store


class BaseRetriever:
    """Base class for all retriever components."""

    def __init__(self, store = None):
        self.store = store or get_knowledge_store()
