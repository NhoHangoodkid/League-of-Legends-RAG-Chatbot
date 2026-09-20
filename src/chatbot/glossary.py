"""
LoL Dynamic Terminology and Ability Resolver.
100% Automated from KnowledgeStore (MongoDB / Processors Data).
Zero hardcoded dictionaries.
"""

from chatbot.knowledge_store import get_knowledge_store


def get_ability_display_name(champion, key, english_name = None):
    """
    Format ability name dynamically. Resolves canonical English ability name directly
    from the KnowledgeStore champion abilities.
    """
    if english_name:
        return english_name.strip()

    store = get_knowledge_store()
    champ = store.get_champion(champion)
    if champ:
        abilities = champ.get("abilities", {})
        skill_data = abilities.get(key.upper())
        if skill_data and isinstance(skill_data, dict) and skill_data.get("name"):
            return skill_data["name"].strip()

    return key.upper()


def localize_term(term):
    """
    Resolve canonical game term (item, rune, or champion) dynamically from KnowledgeStore.
    """
    if not term:
        return ""
    clean = term.strip()
    store = get_knowledge_store()

    # Check Item
    item = store.get_item(clean)
    if item and item.get("name"):
        return item["name"]

    # Check Rune
    rune = store.get_rune(clean)
    if rune and rune.get("name"):
        return rune["name"]

    # Check Champion
    champ = store.get_champion(clean)
    if champ and champ.get("name"):
        return champ["name"]

    return clean


def localize_list(items):
    """Dynamically resolve and canonicalize a list of items/runes."""
    if not items:
        return []
    return [localize_term(it) for it in items]


# Dynamic backward-compatibility accessors
class DynamicGlossaryDict(dict):
    """Dynamic dict accessor backed by KnowledgeStore."""
    def __init__(self, entity_type):
        super().__init__()
        self.entity_type = entity_type

    def get(self, key, default = None):
        return localize_term(key) or default

    def __getitem__(self, key):
        return localize_term(key)


item_glossary = DynamicGlossaryDict("item")
rune_glossary = DynamicGlossaryDict("rune")
spell_glossary = DynamicGlossaryDict("spell")
champion_ability_glossary = {}
