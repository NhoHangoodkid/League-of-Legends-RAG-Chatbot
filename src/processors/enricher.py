"""
Champion Enricher.

Adds strategic metadata to champion data:
- Playstyles (Burst, Poke, Sustained, Utility, etc.)
- Power curves (EarlyGame, MidGame, LateGame)
- Win conditions (Teamfight, Splitpush, Pick, Siege)


(CHAMPION_PLAYSTYLES, POWER_CURVES, WIN_CONDITIONS dictionaries)
"""

import json
from pathlib import Path


try:
    from .utils import PROCESSED_DIR, load_json, save_json, log
except ImportError:
    try:
        from processors.utils import PROCESSED_DIR, load_json, save_json, log
    except ImportError:
        from utils import PROCESSED_DIR, load_json, save_json, log



CHAMPION_PLAYSTYLES = {
    # Assassins
    "Akali": ["Burst", "Mobility", "Assassin"],
    "Akshan": ["Burst", "Mobility", "Marksman"],
    "Diana": ["Burst", "Dive", "Assassin"],
    "Ekko": ["Burst", "Mobility", "Assassin"],
    "Evelynn": ["Burst", "Assassin", "Stealth"],
    "Fizz": ["Burst", "Mobility", "Assassin"],
    "Kassadin": ["Burst", "Scaling", "Assassin"],
    "Katarina": ["Burst", "Reset", "Assassin"],
    "Kayn": ["Burst", "Mobility", "Assassin"],
    "Khazix": ["Burst", "Assassin", "Stealth"],
    "Leblanc": ["Burst", "Mobility", "Assassin"],
    "Naafiri": ["Burst", "Assassin"],
    "Nocturne": ["Burst", "Dive", "Assassin"],
    "Pyke": ["Burst", "Assassin", "Support"],
    "Qiyana": ["Burst", "Assassin"],
    "Rengar": ["Burst", "Assassin", "Stealth"],
    "Shaco": ["Burst", "Assassin", "Stealth"],
    "Talon": ["Burst", "Mobility", "Assassin"],
    "Zed": ["Burst", "Assassin"],
    # Mages
    "Ahri": ["Burst", "Mobility", "Mage"],
    "Anivia": ["Control", "Zone", "Mage"],
    "Annie": ["Burst", "Engage", "Mage"],
    "AurelionSol": ["Sustained", "Scaling", "Mage"],
    "Aurora": ["Burst", "Control", "Mage"],
    "Azir": ["Sustained", "Scaling", "Zone", "Mage"],
    "Brand": ["Burst", "AOE", "Mage"],
    "Cassiopeia": ["Sustained", "DPS", "Mage"],
    "Hwei": ["Poke", "Control", "Mage"],
    "Karma": ["Poke", "Utility", "Mage"],
    "Karthus": ["Sustained", "Scaling", "Mage"],
    "Lissandra": ["Burst", "Engage", "Control", "Mage"],
    "Lux": ["Burst", "Poke", "Mage"],
    "Malzahar": ["Sustained", "Control", "Mage"],
    "Mel": ["Burst", "Poke", "Mage"],
    "Neeko": ["Burst", "Engage", "Mage"],
    "Orianna": ["Control", "Utility", "Mage"],
    "Ryze": ["Sustained", "Scaling", "Mage"],
    "Syndra": ["Burst", "Mage"],
    "Taliyah": ["Burst", "Zone", "Mage"],
    "TwistedFate": ["Utility", "Roam", "Mage"],
    "Veigar": ["Burst", "Scaling", "Mage"],
    "Velkoz": ["Poke", "Burst", "Mage"],
    "Vex": ["Burst", "Engage", "Mage"],
    "Viktor": ["Burst", "Zone", "Mage"],
    "Vladimir": ["Sustained", "Scaling", "Mage"],
    "Xerath": ["Poke", "Artillery", "Mage"],
    "Ziggs": ["Poke", "Siege", "Mage"],
    "Zoe": ["Burst", "Poke", "Mage"],
    "Zyra": ["Zone", "Control", "Mage"],
    # Fighters/Bruisers
    "Aatrox": ["Sustained", "Drain", "Fighter"],
    "Ambessa": ["Burst", "Dive", "Fighter"],
    "Belveth": ["Sustained", "Scaling", "Fighter"],
    "Briar": ["Sustained", "Dive", "Fighter"],
    "Camille": ["Burst", "Dive", "Fighter"],
    "Darius": ["Sustained", "Juggernaut", "Fighter"],
    "Fiora": ["Splitpush", "Duelist", "Fighter"],
    "Gangplank": ["Burst", "Scaling", "Fighter"],
    "Garen": ["Sustained", "Juggernaut", "Fighter"],
    "Gnar": ["Sustained", "Engage", "Fighter"],
    "Graves": ["Burst", "Mobility", "Fighter"],
    "Gwen": ["Sustained", "Scaling", "Fighter"],
    "Hecarim": ["Burst", "Dive", "Fighter"],
    "Illaoi": ["Sustained", "Juggernaut", "Fighter"],
    "Irelia": ["Sustained", "Dive", "Fighter"],
    "Jax": ["Sustained", "Scaling", "Splitpush", "Fighter"],
    "Jayce": ["Poke", "Burst", "Fighter"],
    "Kled": ["Dive", "Engage", "Fighter"],
    "LeeSin": ["Burst", "Mobility", "Fighter"],
    "Mordekaiser": ["Sustained", "Juggernaut", "Fighter"],
    "Nasus": ["Sustained", "Scaling", "Splitpush", "Fighter"],
    "Olaf": ["Sustained", "Dive", "Fighter"],
    "Pantheon": ["Burst", "Dive", "Fighter"],
    "Quinn": ["Burst", "Roam", "Fighter"],
    "RekSai": ["Burst", "Dive", "Fighter"],
    "Renekton": ["Burst", "Dive", "Fighter"],
    "Riven": ["Burst", "Mobility", "Fighter"],
    "Sett": ["Sustained", "Engage", "Fighter"],
    "Trundle": ["Sustained", "Juggernaut", "Fighter"],
    "Tryndamere": ["Sustained", "Splitpush", "Fighter"],
    "Udyr": ["Sustained", "Dive", "Fighter"],
    "Urgot": ["Sustained", "Juggernaut", "Fighter"],
    "Vi": ["Burst", "Dive", "Fighter"],
    "Volibear": ["Sustained", "Dive", "Fighter"],
    "Warwick": ["Sustained", "Dive", "Fighter"],
    "MonkeyKing": ["Burst", "Engage", "Fighter"],  # Wukong
    "XinZhao": ["Sustained", "Dive", "Fighter"],
    "Yasuo": ["Sustained", "Scaling", "Fighter"],
    "Yone": ["Sustained", "Scaling", "Fighter"],
    "Yorick": ["Sustained", "Splitpush", "Fighter"],
    # Tanks
    "Alistar": ["Engage", "Peel", "Tank"],
    "Amumu": ["Engage", "AOE", "Tank"],
    "Braum": ["Peel", "Utility", "Tank"],
    "Chogath": ["Sustained", "Scaling", "Tank"],
    "DrMundo": ["Sustained", "Juggernaut", "Tank"],
    "Galio": ["Engage", "Utility", "Tank"],
    "Gragas": ["Burst", "Engage", "Tank"],
    "JarvanIV": ["Engage", "Dive", "Tank"],
    "KSante": ["Engage", "Peel", "Tank"],
    "Leona": ["Engage", "Lockdown", "Tank"],
    "Malphite": ["Engage", "AOE", "Tank"],
    "Maokai": ["Engage", "Peel", "Tank"],
    "Nautilus": ["Engage", "Lockdown", "Tank"],
    "Nunu": ["Engage", "Objective", "Tank"],
    "Ornn": ["Engage", "Utility", "Tank"],
    "Poppy": ["Peel", "Engage", "Tank"],
    "Rammus": ["Engage", "Dive", "Tank"],
    "Rell": ["Engage", "Lockdown", "Tank"],
    "Sejuani": ["Engage", "AOE", "Tank"],
    "Shen": ["Utility", "Splitpush", "Tank"],
    "Singed": ["Sustained", "Proxy", "Tank"],
    "Sion": ["Engage", "Scaling", "Tank"],
    "Skarner": ["Engage", "Pick", "Tank"],
    "TahmKench": ["Peel", "Utility", "Tank"],
    "Taric": ["Peel", "Utility", "Tank"],
    "Thresh": ["Engage", "Peel", "Utility", "Tank"],
    "Zac": ["Engage", "Dive", "Tank"],
    # Marksmen
    "Aphelios": ["Sustained", "Scaling", "Marksman"],
    "Ashe": ["Utility", "Engage", "Marksman"],
    "Caitlyn": ["Poke", "Siege", "Marksman"],
    "Corki": ["Burst", "Poke", "Marksman"],
    "Draven": ["Burst", "Snowball", "Marksman"],
    "Ezreal": ["Poke", "Burst", "Marksman"],
    "Jhin": ["Burst", "Utility", "Marksman"],
    "Jinx": ["Sustained", "Scaling", "Marksman"],
    "Kaisa": ["Burst", "Scaling", "Marksman"],
    "Kalista": ["Sustained", "Utility", "Marksman"],
    "Kindred": ["Sustained", "Scaling", "Marksman"],
    "KogMaw": ["Sustained", "Scaling", "Marksman"],
    "Lucian": ["Burst", "Lane", "Marksman"],
    "MissFortune": ["Burst", "AOE", "Marksman"],
    "Nilah": ["Sustained", "Scaling", "Marksman"],
    "Samira": ["Burst", "Reset", "Marksman"],
    "Senna": ["Poke", "Utility", "Scaling", "Marksman"],
    "Sivir": ["Sustained", "Utility", "Marksman"],
    "Smolder": ["Poke", "Scaling", "Marksman"],
    "Tristana": ["Burst", "Scaling", "Marksman"],
    "Twitch": ["Burst", "Stealth", "Marksman"],
    "Varus": ["Poke", "Burst", "Marksman"],
    "Vayne": ["Sustained", "Scaling", "Duelist", "Marksman"],
    "Xayah": ["Burst", "Utility", "Marksman"],
    "Zeri": ["Sustained", "Mobility", "Marksman"],
    # Supports
    "Bard": ["Utility", "Roam", "Support"],
    "Blitzcrank": ["Pick", "Engage", "Support"],
    "Janna": ["Peel", "Disengage", "Support"],
    "Lulu": ["Peel", "Utility", "Support"],
    "Milio": ["Peel", "Utility", "Support"],
    "Morgana": ["Peel", "Pick", "Support"],
    "Nami": ["Poke", "Utility", "Support"],
    "Rakan": ["Engage", "Mobility", "Support"],
    "Renata": ["Utility", "Peel", "Support"],
    "Seraphine": ["Utility", "Poke", "Support"],
    "Sona": ["Utility", "Sustained", "Support"],
    "Soraka": ["Sustained", "Heal", "Support"],
    "Yuumi": ["Sustained", "Utility", "Support"],
    "Zilean": ["Utility", "Poke", "Support"],
    # Others
    "Elise": ["Burst", "Dive", "Mage"],
    "Fiddlesticks": ["Burst", "Engage", "Mage"],
    "Heimerdinger": ["Zone", "Siege", "Mage"],
    "Ivern": ["Utility", "Support", "Mage"],
    "Kayle": ["Sustained", "Scaling", "Mage"],
    "Kennen": ["Burst", "Engage", "Mage"],
    "Lillia": ["Sustained", "Kite", "Mage"],
    "MasterYi": ["Sustained", "Reset", "Assassin"],
    "Nidalee": ["Poke", "Burst", "Mage"],
    "Rumble": ["Sustained", "Zone", "Mage"],
    "Shyvana": ["Sustained", "Dive", "Fighter"],
    "Swain": ["Sustained", "Drain", "Mage"],
    "Sylas": ["Burst", "Sustained", "Mage"],
    "Teemo": ["Poke", "Zone", "Mage"],
    "Viego": ["Sustained", "Reset", "Assassin"],
    # New / recently added champions
    "Locke": ["Utility", "Support"],
    "Yunara": ["Sustained", "Mage"],
    "Zaahen": ["Sustained", "Fighter"],
}

POWER_CURVES = {
    "EarlyGame": [
        "Draven", "Renekton", "Pantheon", "LeeSin", "Elise", "Olaf",
        "Darius", "Lucian", "Caitlyn", "Jayce", "Karma", "Rakan",
        "RekSai", "XinZhao", "Blitzcrank", "Thresh", "Leona",
        "Nautilus", "Alistar", "Volibear", "Warwick", "Nidalee",
        "Rengar", "Kled", "Pyke", "Sett", "Talon",
    ],
    "MidGame": [
        "Ahri", "Fizz", "Katarina", "Talon", "Zed", "Qiyana",
        "Syndra", "Orianna", "Viktor", "Corki", "Ezreal", "MissFortune",
        "Jhin", "Kaisa", "Hecarim", "Khazix", "Rengar", "Graves",
        "Kindred", "Irelia", "Camille", "Fiora", "Riven", "Aatrox",
        "Mordekaiser", "Sett", "Gnar", "Rumble", "Gragas",
        "Akali", "Diana", "Ekko", "Nocturne", "LeeSin", "Vi",
        "Lissandra", "Neeko", "Vex", "Brand", "Shaco",
        "Lillia", "Sylas", "Kennen", "Belveth", "Briar",
        "Samira", "Xayah", "Lucian", "Kalista", "Tristana",
        "Ambessa", "Quinn", "Gangplank",
    ],
    "LateGame": [
        "Kassadin", "Kayle", "Veigar", "Vladimir", "Ryze", "Azir",
        "Cassiopeia", "Karthus", "AurelionSol", "Jinx", "Vayne",
        "KogMaw", "Twitch", "Aphelios", "Tristana", "Sivir",
        "Jax", "Nasus", "Gangplank", "Ornn", "Chogath", "Sion",
        "Senna", "Smolder", "Nilah", "Zeri", "Yasuo", "Yone", "Gwen",
        "MasterYi", "Viego", "Kayn",
    ],
}

WIN_CONDITIONS = {
    "Teamfight": [
        "Amumu", "Malphite", "Orianna", "Seraphine", "MissFortune",
        "MonkeyKing", "Kennen", "Diana", "Zyra", "Brand", "Fiddlesticks",
        "JarvanIV", "Sejuani", "Galio", "Neeko", "Rell", "Leona",
        "Karthus", "Vex", "Annie", "Lissandra", "Qiyana", "Rakan",
        "Gnar", "Hecarim", "Braum", "Alistar",
        "Aatrox", "Sett", "Vladimir", "Swain",
    ],
    "Splitpush": [
        "Fiora", "Jax", "Tryndamere", "Yorick", "Nasus", "Camille",
        "Shen", "Gwen", "Trundle", "Udyr", "Illaoi", "Sion",
        "Kayle",
    ],
    "Pick": [
        "Blitzcrank", "Thresh", "Pyke", "Zoe", "Ahri", "Evelynn",
        "Rengar", "Khazix", "Nocturne", "Ashe", "Morgana", "Lux",
        "Leblanc", "Talon", "Zed", "Shaco", "Ekko",
    ],
    "Siege": [
        "Ziggs", "Xerath", "Velkoz", "Caitlyn", "Jayce", "Heimerdinger",
        "Varus", "Ezreal", "Corki", "Zeri", "Hwei",
    ],
    "Objective": [
        "Nunu", "Shyvana", "MasterYi", "Kindred", "Karthus",
        "Chogath", "Kalista",
    ],
    "Skirmish": [
        "Irelia", "Riven", "Yasuo", "Yone", "Sylas", "Akali",
        "Fizz", "Katarina", "LeeSin", "Viego",
        "Graves", "Olaf", "XinZhao", "Vi",
        "Draven", "Lucian", "Kaisa", "Samira",
    ],
}


class Enricher:
    """Add strategic metadata (playstyles, power curves, win conditions) to champions."""

    def enrich(self):
        """
        Read processed champion data and add strategic metadata.
        Updates src/processors/processed/champions.json in-place.
        """
        print("[Enricher] Loading champion data...")
        champions = self.load_champions()

        if not champions:
            print("[Enricher] ERROR: No champion data found!")
            return {}

        print(f"[Enricher] Enriching {len(champions)} champions...")

        enriched_count = 0
        fallback_count = 0
        for champ_id, champ in champions.items():
            playstyles = CHAMPION_PLAYSTYLES.get(champ_id, [])

            power_curve = []
            for curve, champs in POWER_CURVES.items():
                if champ_id in champs:
                    power_curve.append(curve)

            win_conditions = []
            for condition, champs in WIN_CONDITIONS.items():
                if champ_id in champs:
                    win_conditions.append(condition)

            # Fallback inference when no curated data exists
            if not playstyles:
                playstyles = self._infer_playstyles(champ)
                fallback_count += 1

            if not power_curve:
                power_curve = self._infer_power_curve(champ)

            if not win_conditions:
                win_conditions = self._infer_win_conditions(champ, playstyles)

            champ["playstyles"] = playstyles
            champ["powerCurve"] = power_curve
            champ["winConditions"] = win_conditions

            if playstyles or power_curve or win_conditions:
                enriched_count += 1

        # Save updated data
        self.save_champions(champions)
        print(f"[Enricher] Enriched {enriched_count}/{len(champions)} champions with strategic data")
        if fallback_count:
            print(f"[Enricher] {fallback_count} champions used fallback inference for playstyles")
        return champions

    @staticmethod
    def _infer_playstyles(champ):
        """
        Rule-based fallback: infer playstyles from roles, tacticalInfo, and playstyleRatings.
        Used when a champion is not in the curated CHAMPION_PLAYSTYLES dictionary.
        """
        inferred = []
        roles = champ.get("roles", [])
        tactical = champ.get("tacticalInfo", {})
        ratings = champ.get("playstyleRatings", {})

        # Map roles to playstyle archetypes
        role_map = {
            "assassin": "Assassin", "mage": "Mage", "fighter": "Fighter",
            "tank": "Tank", "marksman": "Marksman", "support": "Support",
        }
        for role in roles:
            tag = role_map.get(role.lower(), "")
            if tag:
                inferred.append(tag)

        # Use CDragon playstyle ratings to infer combat style
        damage = ratings.get("damage", 0)
        durability = ratings.get("durability", 0)
        mobility_r = ratings.get("mobility", 0)
        cc_r = ratings.get("crowdControl", 0)

        if damage >= 3 and durability <= 1:
            inferred.insert(0, "Burst")
        elif damage >= 2 and durability >= 2:
            inferred.insert(0, "Sustained")

        if mobility_r >= 3:
            inferred.append("Mobility")
        if cc_r >= 3:
            inferred.append("Control")

        return inferred if inferred else ["Flexible"]

    @staticmethod
    def _infer_power_curve(champ):
        """
        Infer power curve from stats scaling and champion attributes.
        Champions with high base stats and low scaling → EarlyGame.
        Champions with low base and high scaling → LateGame.
        Default → MidGame.
        """
        stats = champ.get("stats", {})
        roles = [r.lower() for r in champ.get("roles", [])]
        resource = champ.get("resource", "").upper()

        # Heuristics based on stat growth
        ad_growth = 0
        hp_growth = 0
        if "attackdamage" in stats:
            ad_growth = stats["attackdamage"].get("perLevel", 0)
        if "hp" in stats:
            hp_growth = stats["hp"].get("perLevel", 0)

        # High growth stats → late game
        if ad_growth >= 4.0 or hp_growth >= 110:
            return ["LateGame"]

        # Assassins and early-game fighters
        if "assassin" in roles and ad_growth < 3.5:
            return ["MidGame"]

        # Tanks generally scale into mid-late
        if "tank" in roles:
            return ["MidGame", "LateGame"]

        # Supports peak mid
        if "support" in roles:
            return ["MidGame"]

        # Marksmen generally scale late
        if "marksman" in roles:
            return ["MidGame", "LateGame"]

        return ["MidGame"]

    @staticmethod
    def _infer_win_conditions(champ, playstyles):
        """Infer win conditions from roles and playstyles."""
        conditions = []
        playstyle_set = set(p.lower() for p in playstyles)
        roles = [r.lower() for r in champ.get("roles", [])]

        if "engage" in playstyle_set or "aoe" in playstyle_set:
            conditions.append("Teamfight")
        if "splitpush" in playstyle_set or "duelist" in playstyle_set:
            conditions.append("Splitpush")
        if "assassin" in playstyle_set or "pick" in playstyle_set or "stealth" in playstyle_set:
            conditions.append("Pick")
        if "siege" in playstyle_set or "artillery" in playstyle_set or "poke" in playstyle_set:
            conditions.append("Siege")

        # Fallback: role-based
        if not conditions:
            if "tank" in roles:
                conditions.append("Teamfight")
            elif "marksman" in roles:
                conditions.append("Teamfight")
            elif "fighter" in roles:
                conditions.append("Skirmish")
            elif "mage" in roles:
                conditions.append("Teamfight")
            elif "support" in roles:
                conditions.append("Teamfight")
            else:
                conditions.append("Teamfight")

        return conditions

    @staticmethod
    def load_champions():
        """Load processed champion data."""
        return load_json(PROCESSED_DIR / "champions.json")

    @staticmethod
    def save_champions(data):
        """Save updated champion data."""
        return save_json(data, PROCESSED_DIR / "champions.json")