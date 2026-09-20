"""
Champion Synergy and Pro Team Composition Processor.

Synthesizes empirical match statistics with grounded ability mechanics:
1. Absolute Pair Synergies: Combines SoloQ and Pro Play into authoritative, unified
   synergy metrics (Absolute Win Rate, sample size, grounded skill mechanics).
   Zero distinction between pro and rank.
2. Champion-Centric Pro Team Compositions: Mines 20,082 complete 5-man pro play lineups
   (Oracle's Elixir 2025 matches) to generate empirical 5-man team compositions centered
   around each champion (Top, Jungle, Mid, Bot, Support) with role synergies and win conditions.

Outputs:
- src/processors/processed/synergies.json and src/data/knowledge_base/synergies.json
- src/processors/processed/team_compositions.json and src/data/knowledge_base/team_compositions.json
"""

import csv
import json
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import time
from collections import Counter, defaultdict
from pathlib import Path

# Ensure src is in sys.path
src_dir = Path(__file__).resolve().parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

try:
    import pandas as pd
    pandas_available = True
except ImportError:
    pandas_available = False

from processors.utils import (
    BLITZ_raw_dir,
    OPGG_SYNERGY_raw_dir,
    ORACLES_ELIXIR_raw_dir,
    processed_dir,
    project_root,
    load_json,
    log,
    save_json,
)

tag = "SynergyProcessor"
kb_dir = src_dir / "data" / "knowledge_base"


class SynergyProcessor:
    """
    Synthesizes pro match history, SoloQ win rates, and ability mechanics
    into absolute pair relationships and champion-centric 5-man team compositions.
    """

    def __init__(self, processed_dir = None, kb_dir = None):
        self.processed_dir = processed_dir or processed_dir
        self.kb_dir = kb_dir or kb_dir
        self.raw_oe_dir = ORACLES_ELIXIR_raw_dir
        self.raw_opgg_dir = OPGG_SYNERGY_raw_dir
        self.raw_blitz_dir = BLITZ_raw_dir

    def load_champions_kb(self):
        """Load merged champions dictionary for mechanics verification."""
        candidates = [
            self.processed_dir / "champions.json",
            self.kb_dir / "champions.json",
            src_dir / "collectors" / "raw" / "meraki" / "champions.json",
        ]
        for p in candidates:
            if p.exists():
                data = load_json(p)
                if data and isinstance(data, dict):
                    return data
        return {}

    def load_pro_play_data(self):
        """
        Parse 2025 Oracle's Elixir CSV into:
        1. pro_duos: dict (c1, c2) -> {'games': N, 'wins': W}
        2. pro_teams: list of {'lineup': {top, jng, mid, bot, sup}, 'win': 1/0}
        """
        csv_path = self.raw_oe_dir / "2025_LoL_esports_match_data.csv"
        if not csv_path.exists():
            matches = list(self.raw_oe_dir.glob("*_match_data.csv"))
            if matches:
                csv_path = matches[0]
            else:
                log(tag, f"Warning: No match CSV found in {self.raw_oe_dir}")
                return {}, []

        log(tag, f"Parsing professional match data from {csv_path.name}...")
        pro_duos = defaultdict(lambda: {"games": 0, "wins": 0})
        pro_teams = []

        if pandas_available:
            df = pd.read_csv(csv_path, low_memory=False)
            player_df = df[df["position"].isin(["top", "jng", "mid", "bot", "sup"])].copy().dropna(subset=["champion"])

            for (gameid, side), group in player_df.groupby(["gameid", "side"]):
                pos_map = dict(zip(group["position"], group["champion"]))
                result = group["result"].iloc[0]
                is_win = 1 if result in [1, "1", True, "True", "Blue", "Red"] else 0

                # 5-man team
                if len(pos_map) == 5:
                    pro_teams.append({
                        "lineup": {
                            "top": pos_map["top"],
                            "jungle": pos_map["jng"],
                            "mid": pos_map["mid"],
                            "bot": pos_map["bot"],
                            "support": pos_map["sup"]
                        },
                        "win": is_win
                    })

                # Pairs
                for p1, p2 in [("bot", "sup"), ("mid", "jng"), ("top", "jng"), ("mid", "sup")]:
                    if p1 in pos_map and p2 in pos_map:
                        c1, c2 = pos_map[p1], pos_map[p2]
                        if c1 and c2:
                            pro_duos[(c1, c2)]["games"] += 1
                            pro_duos[(c1, c2)]["wins"] += is_win
                            pro_duos[(c2, c1)]["games"] += 1
                            pro_duos[(c2, c1)]["wins"] += is_win
        else:
            with open(csv_path, "r", encoding = "utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                games = defaultdict(dict)
                game_results = {}
                for row in reader:
                    pos = row.get("position")
                    if pos in ("top", "jng", "mid", "bot", "sup"):
                        gid = (row.get("gameid"), row.get("side"))
                        games[gid][pos] = row.get("champion")
                        if gid not in game_results:
                            res = row.get("result")
                            game_results[gid] = 1 if res in ("1", 1, "True") else 0

                for gid, pos_map in games.items():
                    is_win = game_results.get(gid, 0)
                    if len(pos_map) == 5:
                        pro_teams.append({
                            "lineup": {
                                "top": pos_map.get("top"),
                                "jungle": pos_map.get("jng"),
                                "mid": pos_map.get("mid"),
                                "bot": pos_map.get("bot"),
                                "support": pos_map.get("sup")
                            },
                            "win": is_win
                        })

                    for p1, p2 in [("bot", "sup"), ("mid", "jng"), ("top", "jng"), ("mid", "sup")]:
                        if p1 in pos_map and p2 in pos_map:
                            c1, c2 = pos_map[p1], pos_map[p2]
                            if c1 and c2:
                                pro_duos[(c1, c2)]["games"] += 1
                                pro_duos[(c1, c2)]["wins"] += is_win
                                pro_duos[(c2, c1)]["games"] += 1
                                pro_duos[(c2, c1)]["wins"] += is_win

        log(tag, f"Extracted {len(pro_teams)} complete 5-man pro teams and {len(pro_duos)} pro pair stats")
        return pro_duos, pro_teams

    def load_soloq_duos(self):
        """Load OP.GG MCP SoloQ duo synergy dataset."""
        syn_file = self.raw_opgg_dir / "champion_synergies.json"
        if not syn_file.exists():
            return {}
        return load_json(syn_file) or {}

    def load_tactical_tips(self):
        """Load Blitz.gg tactical tips (insights, strengths, weaknesses)."""
        tips_file = self.raw_blitz_dir / "champion_tactical_tips.json"
        if not tips_file.exists():
            return {}
        tips_data = load_json(tips_file) or []
        tips_by_id = {}
        for item in tips_data:
            cid = item.get("championId")
            if cid:
                tips_by_id[cid] = item.get("tips", {})
        return tips_by_id

    @staticmethod
    def generate_mechanics_reason(champ_a, champ_b, a_name, b_name):
        """
        Cross-reference ability mechanics to generate a concrete, grounded gameplay explanation.
        """
        a_cc = set(champ_a.get("hard_cc", []) if isinstance(champ_a, dict) else [])
        b_cc = set(champ_b.get("hard_cc", []) if isinstance(champ_b, dict) else [])
        a_roles = set(r.lower() for r in champ_a.get("roles", [])) if isinstance(champ_a, dict) else set()
        b_roles = set(r.lower() for r in champ_b.get("roles", [])) if isinstance(champ_b, dict) else set()
        b_subroles = set(champ_b.get("subroles", [])) if isinstance(champ_b, dict) else set()

        # 1. Jinx + Enchanters (Lulu, Milio, Janna, Yuumi, Soraka)
        if (a_name == "Jinx" and b_name in ("Lulu", "Milio", "Janna", "Yuumi", "Soraka")) or (b_name == "Jinx" and a_name in ("Lulu", "Milio", "Janna", "Yuumi", "Soraka")):
            enc = b_name if a_name == "Jinx" else a_name
            if enc == "Lulu":
                return (
                    "ENCHANTER_HYPERCARRY_PEEL",
                    "Lulu is Jinx's premier hypercarry enchanter: Whimsy (W) grants massive Attack Speed and Movement Speed to accelerate Get Excited! passive resets, Help, Pix! (E) attaches bonus on-hit magic damage to Fishbones AoE rockets, and Wild Growth (R) provides anti-dive knockup peel and bonus health."
                )
            elif enc == "Milio":
                return (
                    "RANGE_STEROID_AND_PEEL",
                    "Cozy Campfire (W) extends Jinx's Fishbones attack range to over 800 while granting on-hit healing; Ultra Mega Fire Kick (Q) knocks back diving assassins, and Breath of Life (R) cleanses hard crowd control to prevent Jinx from getting locked down."
                )
            return (
                "ENCHANTER_HYPERCARRY_PEEL",
                f"Defensive shields, heals, and speed steroids from {enc} protect immobile hypercarry Jinx against dive threats, enabling safe long-range Fishbones rocket DPS and reliable Get Excited! passive resets in teamfights."
            )

        # 2. Jinx + Hook / Catcher Supports (Thresh, Blitzcrank, Nautilus, Pyke)
        if (a_name == "Jinx" and b_name in ("Thresh", "Blitzcrank", "Nautilus", "Pyke", "Leona", "Alistar")) or (b_name == "Jinx" and a_name in ("Thresh", "Blitzcrank", "Nautilus", "Pyke", "Leona", "Alistar")):
            sup = b_name if a_name == "Jinx" else a_name
            if sup == "Thresh":
                return (
                    "HOOK_TRAP_CHAIN",
                    "Classic hook-to-trap CC layering: When Thresh lands Death Sentence (Q) or Flay (E), Jinx immediately casts Flame Chompers! (E) beneath the immobilized target for a guaranteed 1.5s root chain, followed by Zap! (W) slow and Fishbones rocket barrage. Dark Passage (W) lantern provides vital safety for the immobile hypercarry."
                )
            elif sup == "Blitzcrank":
                return (
                    "HOOK_TRAP_CHAIN",
                    "Guaranteed hook-to-trap kill combo: Blitzcrank's Rocket Grab (Q) pulls the target directly into Jinx's pre-placed Flame Chompers! (E) for an inescapable chain root, Power Fist (E) knockup, and lethal Zap! execution."
                )
            elif sup == "Nautilus":
                return (
                    "ENGAGE_BURST_LOCKDOWN",
                    "Point-and-click crowd control lockdown: Nautilus initiates with Dredge Line (Q) and Staggering Blow passive root into Depth Charge (R) knockup, allowing Jinx to safely place Flame Chompers! (E) and free-fire rockets from maximum range."
                )
            elif sup == "Leona":
                return (
                    "ENGAGE_BURST_LOCKDOWN",
                    "Solar Flare (R) and Zenith Blade (E) hard lockdown locks enemies in place, letting Jinx chain Flame Chompers! (E) roots and proc Leona's Sunlight passive with rapid Fishbones rocket AoE."
                )
            return (
                "HOOK_TRAP_CHAIN",
                f"Displacement hooks and crowd control from {sup} allow Jinx to layer Flame Chompers! (E) underneath immobilized targets for guaranteed follow-up root, Zap! (W) slow, and lethal burst damage."
            )

        # 3. Jinx + Braum
        if (a_name == "Jinx" and b_name == "Braum") or (a_name == "Braum" and b_name == "Jinx"):
            return (
                "WARDEN_PEEL_AND_STACK",
                "Defensive shield wall and long-range stun stacking: Braum's Unbreakable (E) intercepts enemy skillshots and dive threats, while Jinx easily stacks and triggers Braum's Concussive Blows passive stun from 700+ attack range with Fishbones rockets."
            )

        # 4. Ashe + Braum iconic passive stack
        if (a_name == "Ashe" and b_name == "Braum") or (a_name == "Braum" and b_name == "Ashe"):
            return (
                "PASSIVE_STACK_BURST_CC",
                "Ashe's Frost Shot passive slow makes landing Braum's Winter's Bite (Q) effortless; Ranger's Focus (Q) rapid attack speed procs all 4 stacks of Braum's Concussive Blows stun in under 1 second."
            )

        # 5. Ashe + Seraphine: Slow converts to Root
        if (a_name == "Ashe" and b_name == "Seraphine") or (a_name == "Seraphine" and b_name == "Ashe"):
            return (
                "POKE_SLOW_TO_ROOT",
                "Ashe's constant Frost Shot basic attack slow automatically converts Seraphine's Beat Drop (E) from a slow into an instant root without needing double-cast echo."
            )

        # 6. Lucian + Milio/Nami: Double passive procs
        if (a_name == "Lucian" and b_name in ("Milio", "Nami")) or (b_name == "Lucian" and a_name in ("Milio", "Nami")):
            sup = b_name if a_name == "Lucian" else a_name
            return (
                "ON_HIT_BUFF_BURST",
                f"Buffs from {sup} (Tidecaller's Blessing / Fired Up!) activate Lucian's Vigilance passive, adding bonus magic damage to Lightslinger double-taps for explosive lane trade burst."
            )

        # 7. Caitlyn + Hard CC (Morgana, Lux, Swain)
        if (a_name == "Caitlyn" and b_name in ("Morgana", "Lux", "Swain")) or (b_name == "Caitlyn" and a_name in ("Morgana", "Lux", "Swain")):
            sup = b_name if a_name == "Caitlyn" else a_name
            return (
                "TRAP_CHAIN_HEADSHOT",
                f"Long-duration bindings from {sup} guarantee Yordle Snap Trap (W) placement under the immobilized target, chaining roots into guaranteed critical Headshots and Piltover Peacemaker (Q) burst."
            )

        # 8. Knockup for Yasuo / Yone
        if b_name in ("Yasuo", "Yone") and ("Knockup" in a_cc or "Airborne" in a_cc or a_name in ("Malphite", "Gragas", "Diana", "Alistar", "Rakan", "Zac")):
            return (
                "AIRBORNE_ENGAGE",
                f"{a_name}'s wide-area airborne knockup creates the perfect trigger for {b_name} to activate Last Breath / Fate Sealed, blinking into the backline and holding multiple priority carries immobilized."
            )

        # 9. Hypercarry Marksman + Enchanter (Kog'Maw, Twitch, Vayne, Aphelios)
        if "marksman" in a_roles and ("ENCHANTER" in b_subroles or b_name in ("Lulu", "Yuumi", "Janna", "Milio", "Soraka")):
            return (
                "PEEL_HYPERCARRY",
                f"Shields, heals, and movement/attack speed steroids from {b_name} safeguard {a_name} through vulnerable scaling phases, enabling safe positioning and unmatched sustained DPS."
            )

        # 10. Hard Engage Vanguard + Burst Carry
        if ("VANGUARD" in b_subroles or b_name in ("Nautilus", "Leona", "Rell", "Alistar", "Thresh")) and a_name in ("Kai'Sa", "Samira", "Draven", "Tristana", "Kalista"):
            return (
                "ENGAGE_BURST_LOCKDOWN",
                f"Hard crowd control and gap closing from {b_name} immobilizes targets, allowing {a_name} to dive in and unload lethal burst damage before enemies can react."
            )

        # 11. CC Chain Burst
        if bool(a_cc) and bool(b_cc):
            cc_str = ", ".join(list(a_cc | b_cc)[:2])
            return (
                "CC_CHAIN_BURST",
                f"Dual crowd control ({cc_str}) creates an inescapable chain lockdown sequence, ensuring successful lane ganks and skirmish pickoffs around neutral objectives."
            )

        return (
            "TACTICAL_SYNERGY",
            f"{a_name} and {b_name} complement each other's combat spacing, balancing physical/magic damage profiles and providing reliable peeling or engagement utility."
        )

    @staticmethod
    def classify_lineup_archetype(lineup, champs_kb):
        """Classify a 5-man lineup into one of 5 canonical strategic archetypes."""
        names = [lineup.get(pos, "") for pos in ["top", "jungle", "mid", "bot", "support"]]
        dive_champs = {"Vi", "Yone", "Ambessa", "Rakan", "Kai'Sa", "Leona", "Camille", "Jarvan IV", "Nocturne", "Akali", "Diana", "Xin Zhao"}
        wombo_champs = {"Rumble", "Sejuani", "Orianna", "Yone", "Braum", "Kennen", "Amumu", "Miss Fortune", "Rakan", "Gnar", "Azir"}
        poke_champs = {"Jayce", "Varus", "Corki", "Ziggs", "Xerath", "Lux", "Nidalee", "Zoe", "Hwei"}
        hypercarries = {"Jinx", "Aphelios", "Kog'Maw", "Ashe", "Zeri", "Vayne", "Sivir"}

        names_set = set(names)
        if len(names_set & wombo_champs) >= 2:
            return "wombocombo", "Wombo Combo and AOE Teamfight"
        if len(names_set & dive_champs) >= 2:
            return "dive", "Dive and Hard Engage"
        if len(names_set & poke_champs) >= 2:
            return "poke", "Poke and Siege Artillery"
        if len(names_set & hypercarries) >= 1:
            return "protect_carry", "Protect the Hypercarry (Front-to-Back)"
        return "pick_skirmish", "Pick and Skirmish Control"

    @staticmethod
    def generate_teammate_synergies(focus_name, lineup, champs_kb):
        """Generate role-by-role mechanics breakdown dynamically based on champion kits."""
        synergies = {}
        focus_data = champs_kb.get(focus_name, {}) if isinstance(champs_kb, dict) else {}

        for pos, teammate in lineup.items():
            if teammate == focus_name:
                continue

            mate_data = champs_kb.get(teammate, {}) if isinstance(champs_kb, dict) else {}
            pos_title = pos.capitalize()
            mate_roles = set(r.lower() for r in mate_data.get("roles", []))
            mate_subroles = set(s.lower() for s in mate_data.get("subroles", []))
            mate_hard_cc = mate_data.get("hard_cc", [])
            mate_cc = mate_data.get("cc_types", [])
            mate_effects = set(mate_data.get("ability_effects", []))
            mate_adaptive = mate_data.get("adaptiveType", "")

            # 1. Knockup / Airborne synergy for Yasuo / Yone
            if focus_name in ("Yasuo", "Yone") and any(c in ("Knockup", "Airborne") for c in mate_cc):
                if pos in ("top", "jungle") and ("tank" in mate_roles or "vanguard" in mate_subroles):
                    synergies[pos] = f"{teammate} ({pos_title}): Heavy airborne initiation and crowd control lockdown provides the ideal trigger for {focus_name}'s ultimate collapse."
                elif pos == "support" and "enchanter" in mate_subroles:
                    synergies[pos] = f"{teammate} ({pos_title}): Grants protective shields and speed buffs alongside clutch airborne knockup peel to enable {focus_name}'s ultimate in teamfights."
                else:
                    synergies[pos] = f"{teammate} ({pos_title}): Reliable airborne knockup provides the primary activation trigger for {focus_name}'s ultimate engagement."
            # 2. Defensive Warden / Peel Tank
            elif "warden" in mate_subroles or ("tank" in mate_roles and pos in ("support", "top") and mate_hard_cc):
                cc_str = f" via {', '.join(mate_hard_cc[:2])}" if mate_hard_cc else ""
                synergies[pos] = f"{teammate} ({pos_title}): Anchors the frontline, absorbing opposing burst and providing peel lockdown{cc_str} to safeguard {focus_name}."
            # 3. Vanguard / Hard Engage Tank
            elif "vanguard" in mate_subroles or ("tank" in mate_roles and ("Knockup" in mate_hard_cc or "Stun" in mate_hard_cc)):
                cc_str = f" ({', '.join(mate_hard_cc[:2])})" if mate_hard_cc else ""
                synergies[pos] = f"{teammate} ({pos_title}): Serves as primary fight initiator, collapsing with hard crowd control{cc_str} to create decisive engagement windows for {focus_name}."
            # 4. Enchanter / Defensive Utility
            elif "enchanter" in mate_subroles or (mate_effects & {"Heal", "Shield"} and "support" in mate_roles):
                synergies[pos] = f"{teammate} ({pos_title}): Grants protective shielding, health restoration, and combat buffs to extend {focus_name}'s survivability and trading uptime."
            # 5. Diver / Flanker / Assassin
            elif "diver" in mate_subroles or "assassin" in mate_roles:
                synergies[pos] = f"{teammate} ({pos_title}): Applies intense backline flank threat, forcing enemy carries to scatter and dividing defensive attention away from {focus_name}."
            # 6. Poke and Artillery
            elif "artillery" in mate_subroles or ("AOE" in mate_effects and mate_data.get("attackType") == "RANGED" and pos in ("mid", "bot")):
                synergies[pos] = f"{teammate} ({pos_title}): Softens opposing formations with long-range poke harassment, depleting enemy health bars before {focus_name} initiates."
            # 7. Marksman / Sustained Carry
            elif "marksman" in mate_roles:
                synergies[pos] = f"{teammate} ({pos_title}): Supplies continuous ranged sustained DPS, forcing opponents to respect backline damage while {focus_name} controls space."
            # 8. Dynamic General Complement
            else:
                cc_desc = f"with {mate_hard_cc[0]} lockdown" if mate_hard_cc else "with versatile skirmish utility"
                dmg_desc = "magic damage" if "MAGIC" in mate_adaptive else ("physical damage" if "PHYSICAL" in mate_adaptive else "consistent damage")
                synergies[pos] = f"{teammate} ({pos_title}): Supplies complementary {dmg_desc} and crowd control {cc_desc} to round out teamfight execution alongside {focus_name}."

        return synergies

    @staticmethod
    def generate_win_condition(focus_name, lineup, archetype_key):
        """Generate concrete win condition for the 5-man team composition in English."""
        top, jng, mid, bot, sup = lineup.get("top", ""), lineup.get("jungle", ""), lineup.get("mid", ""), lineup.get("bot", ""), lineup.get("support", "")
        if archetype_key == "wombocombo":
            return f"Chain area-of-effect crowd control ultimates from {jng} and {sup} around neutral objectives (Dragon/Baron) to lock down enemy squads while {mid} and {top} deliver devastating follow-up burst damage."
        elif archetype_key == "dive":
            return f"Execute coordinated multi-angle flanks with {jng} and {top} to eliminate priority backline carries before enemy frontlines can establish defensive spacing."
        elif archetype_key == "protect_carry":
            return f"Anchor a durable frontline with {top} and {jng} while {sup} provides dedicated peel, creating space for {bot} to safely output unrivaled late-game sustained damage."
        elif archetype_key == "poke":
            return f"Leverage long-range siege abilities from {mid} and {bot} to deplete enemy health bars before major objectives, securing towers and Dragons without committing to chaotic melee brawls."
        else:
            return f"Establish river vision dominance, isolate overextended enemies with pick CC, and convert man-advantage skirmishes into secure neutral objectives."

    def extract_champion_pro_team_compositions(self, champ_name, champ_teams, champs_kb, top_n = 3):
        """
        Extract top 5-man pro team compositions centered around focus champion.
        """
        c_teams = champ_teams.get(champ_name, [])
        if not c_teams:
            return []

        lineup_counts = Counter()
        lineup_wins = Counter()
        for t in c_teams:
            l = t["lineup"]
            key = (l["top"], l["jungle"], l["mid"], l["bot"], l["support"])
            lineup_counts[key] += 1
            lineup_wins[key] += t["win"]

        comps = []
        for rank, (key, count) in enumerate(lineup_counts.most_common(top_n), start=1):
            wins = lineup_wins[key]
            wr = round((wins / count) * 100, 1)
            lineup_dict = {
                "top": key[0],
                "jungle": key[1],
                "mid": key[2],
                "bot": key[3],
                "support": key[4]
            }
            arch_key, arch_name = self.classify_lineup_archetype(lineup_dict, champs_kb)
            synergies = self.generate_teammate_synergies(champ_name, lineup_dict, champs_kb)
            win_cond = self.generate_win_condition(champ_name, lineup_dict, arch_key)

            top_partner_str = f"{key[0]} - {key[1]} - {key[2]} - {key[3]} - {key[4]}"
            comp_obj = {
                "comp_id": f"pro_comp_{champ_name.lower()}_{rank}",
                "focus_champion": champ_name,
                "comp_name": f"Đội hình {arch_name.split(' (')[0]} ({top_partner_str})",
                "archetype": arch_key,
                "archetype_name": arch_name,
                "lineup": lineup_dict,
                "games_played": count,
                "win_rate": wr,
                "teammate_synergies": synergies,
                "win_condition": win_cond,
            }
            comps.append(comp_obj)
        return comps

    def process(self, champions = None, save_to_disk = True):
        """
        Synthesize pro matches, SoloQ stats, and mechanics into absolute pairs
        and champion-centric pro team compositions.
        """
        start_time = time.time()
        log(tag, "Starting Champion Absolute Synergy and Pro Team Composition Processing...")

        champs_kb = champions or self.load_champions_kb()
        pro_duos, pro_teams = self.load_pro_play_data()
        soloq_data = self.load_soloq_duos()
        blitz_tips = self.load_tactical_tips()

        # Build champion lookup index
        champ_by_name = {}
        for cid, cdata in champs_kb.items():
            name = cdata.get("name", cid)
            champ_by_name[name.lower()] = (cid, cdata)
            champ_by_name[cid.lower()] = (cid, cdata)

        # Index 5-man pro teams by champion
        champ_pro_teams = defaultdict(list)
        for t in pro_teams:
            for pos, ch in t["lineup"].items():
                if ch:
                    champ_pro_teams[ch].append(t)

        synergy_documents = {}
        team_comp_documents = {}

        # 1. Process SoloQ and Pro pair data into unified Absolute Pairs
        for key, record in soloq_data.items():
            champ_name = record.get("champion")
            if not champ_name:
                continue

            my_pos = record.get("my_position", "all").upper()
            synergies_raw = record.get("synergies", [])
            cid, cdata = champ_by_name.get(champ_name.lower(), (champ_name, {}))

            if champ_name not in synergy_documents:
                c_id_num = cdata.get("id") or cdata.get("key")
                tips = blitz_tips.get(int(c_id_num) if c_id_num and str(c_id_num).isdigit() else -1, {})
                insights = tips.get("insights", [])

                synergy_documents[champ_name] = {
                    "champion": champ_name,
                    "champion_id": cid,
                    "role": my_pos,
                    "tactical_insights": insights[:3] if insights else [],
                    "best_duos": [],
                    "best_team_compositions": [],
                }

            for partner_entry in synergies_raw:
                partner_name = partner_entry.get("partner")
                if not partner_name:
                    continue

                soloq_games = partner_entry.get("games", 0)
                soloq_wr = partner_entry.get("win_rate", 0.0)
                soloq_wins = round(soloq_wr * soloq_games)

                pro_match = pro_duos.get((champ_name, partner_name))
                pro_games = pro_match["games"] if pro_match else 0
                pro_wins = pro_match["wins"] if pro_match else 0

                # Unified Absolute Win Rate with Bayesian smoothing
                total_games = soloq_games + pro_games
                total_wins = soloq_wins + pro_wins
                # Smooth with prior of 50% over C=20 games
                abs_wr = round(((total_wins + 10) / (total_games + 20)) * 100, 1)

                _, pdata = champ_by_name.get(partner_name.lower(), (partner_name, {}))
                tag, reason = self.generate_mechanics_reason(cdata, pdata, champ_name, partner_name)

                duo_obj = {
                    "partner": partner_name,
                    "role": partner_entry.get("position", "SUPPORT").upper(),
                    "win_rate": abs_wr,
                    "sample_games": total_games,
                    "synergy_tag": tag,
                    "synergy_reason": reason,
                    "score_rank": partner_entry.get("rank", 99),
                }
                synergy_documents[champ_name]["best_duos"].append(duo_obj)

        # 2. Enrich with high-frequency pro duos that might not be in SoloQ sample
        for (c1, c2), pro_stats in pro_duos.items():
            if pro_stats["games"] >= 15:
                if c1 in synergy_documents:
                    existing_partners = {d["partner"] for d in synergy_documents[c1]["best_duos"]}
                    if c2 not in existing_partners:
                        _, cdata = champ_by_name.get(c1.lower(), (c1, {}))
                        _, pdata = champ_by_name.get(c2.lower(), (c2, {}))
                        tag, reason = self.generate_mechanics_reason(cdata, pdata, c1, c2)
                        abs_wr = round(((pro_stats["wins"] + 10) / (pro_stats["games"] + 20)) * 100, 1)
                        synergy_documents[c1]["best_duos"].append({
                            "partner": c2,
                            "role": "PARTNER",
                            "win_rate": abs_wr,
                            "sample_games": pro_stats["games"],
                            "synergy_tag": tag,
                            "synergy_reason": reason,
                        })

        # 3. Add top champions from pro matches that might not be in soloq_data yet (e.g. Yone)
        for champ_name in list(champ_pro_teams.keys()):
            if champ_name not in synergy_documents and len(champ_pro_teams[champ_name]) >= 20:
                cid, cdata = champ_by_name.get(champ_name.lower(), (champ_name, {}))
                c_id_num = cdata.get("id") or cdata.get("key")
                tips = blitz_tips.get(int(c_id_num) if c_id_num and str(c_id_num).isdigit() else -1, {})
                insights = tips.get("insights", [])

                # Find top pro partners for this champion
                top_partners = []
                for (p1, p2), stats in pro_duos.items():
                    if p1 == champ_name and stats["games"] >= 10:
                        abs_wr = round(((stats["wins"] + 10) / (stats["games"] + 20)) * 100, 1)
                        _, pdata = champ_by_name.get(p2.lower(), (p2, {}))
                        tag, reason = self.generate_mechanics_reason(cdata, pdata, champ_name, p2)
                        top_partners.append({
                            "partner": p2,
                            "role": "PARTNER",
                            "win_rate": abs_wr,
                            "sample_games": stats["games"],
                            "synergy_tag": tag,
                            "synergy_reason": reason,
                        })

                top_partners.sort(key=lambda x: (x["win_rate"], x["sample_games"]), reverse=True)
                synergy_documents[champ_name] = {
                    "champion": champ_name,
                    "champion_id": cid,
                    "role": "MID",
                    "tactical_insights": insights[:3] if insights else [],
                    "best_duos": top_partners[:5],
                    "best_team_compositions": [],
                }

        # 4. Extract Champion-Centric Pro Team Compositions
        log(tag, "Extracting champion-centric 5-man pro team compositions...")
        for champ_name, doc in synergy_documents.items():
            # Sort best duos: prioritize official synergy score rank, then sample volume and win rate
            doc["best_duos"].sort(
                key=lambda x: (
                    x.get("score_rank", 99),
                    -x.get("sample_games", 0),
                    -x.get("win_rate", 0),
                )
            )
            doc["best_duos"] = doc["best_duos"][:6]

            # Extract pro 5-man team compositions
            comps = self.extract_champion_pro_team_compositions(champ_name, champ_pro_teams, champs_kb, top_n=3)
            doc["best_team_compositions"] = comps

            # Also index into team_comp_documents
            for c in comps:
                team_comp_documents[c["comp_id"]] = c

        # Save to disk
        if save_to_disk:
            self.processed_dir.mkdir(parents=True, exist_ok=True)
            self.kb_dir.mkdir(parents=True, exist_ok=True)

            # Synergies
            save_json(synergy_documents, self.processed_dir / "synergies.json")
            save_json(synergy_documents, self.kb_dir / "synergies.json")

            # Team Compositions
            existing_comps = load_json(self.processed_dir / "team_compositions.json") or {}
            combined_comps = {**existing_comps, **team_comp_documents}
            save_json(combined_comps, self.processed_dir / "team_compositions.json")
            save_json(combined_comps, self.kb_dir / "team_compositions.json")

            log(tag, f"Saved {len(synergy_documents)} champion synergy profiles and {len(combined_comps)} team compositions")

        elapsed = time.time() - start_time
        log(tag, f"Completed processing in {elapsed:.2f}s! Champions with absolute duos and pro comps: {len(synergy_documents)}")
        return synergy_documents


if __name__ == "__main__":
    sp = SynergyProcessor()
    res = sp.process()
    print("\nSAMPLE YONE PROFILE")
    yone = res.get("Yone", {})
    print("Champion:", yone.get("champion"))
    print("Best Duos:")
    for d in yone.get("best_duos", [])[:3]:
        print(f"  * {d['partner']} ({d['role']}): {d['win_rate']}% WR ({d['sample_games']} games)")
        print(f"    Reason: {d['synergy_reason'][:90]}...")
    print("Best Team Compositions:")
    for c in yone.get("best_team_compositions", []):
        print(f"  * {c['comp_name']} [{c['win_rate']}% WR, {c['games_played']} games]")
        print(f"    Lineup: {c['lineup']}")
        print(f"    Win Condition: {c['win_condition']}")
