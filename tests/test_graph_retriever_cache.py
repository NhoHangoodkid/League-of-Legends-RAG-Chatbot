from rag.retriever.graph_retriever import GraphRetriever


class FakeGraphStore:
    def __init__(self, results=None):
        self.calls = 0
        self.results = [{"id": "Aatrox"}] if results is None else results
        self.queries = []

    def run_cypher(self, query, **params):
        self.calls += 1
        self.queries.append((query, params))
        return self.results


def test_repeated_champion_name_lookup_uses_cache():
    store = FakeGraphStore()
    retriever = GraphRetriever(store)

    assert retriever.find_champion_id("Aatrox") == "Aatrox"
    assert retriever.find_champion_id("aatrox") == "Aatrox"
    assert store.calls == 1


def test_missing_champion_lookup_is_cached():
    store = FakeGraphStore(results=[])
    retriever = GraphRetriever(store)

    assert retriever.find_champion_id("not-a-champion") is None
    assert retriever.find_champion_id("NOT-A-CHAMPION") is None
    assert store.calls == 2
