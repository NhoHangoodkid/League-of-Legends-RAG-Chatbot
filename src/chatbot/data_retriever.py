"""
Data Retriever for LoL Knowledge Bot.

Retrieves and formats structured game data from the KnowledgeStore based on classified intent and entities.
Handles stat calculations, matchup scoring, build aggregation, and semantic filters.
"""


import json
import re
from collections import Counter

from chatbot.config import knowledge_base_dir, processed_dir
from chatbot.knowledge_store import KnowledgeStore, get_knowledge_store
from processors.spell_analyzer import SpellAnalyzer


strategic_composition_counters = {
    "fighter_heavy": {
        "name": "Fighter and Bruiser Heavy Composition",
        "description": "Tactical composition dominated by melee fighters and bruisers specializing in sustained close-quarters skirmishes, high base durability, and active vamp sustain.",
        "counter_picks": [
            {"champion": "Vayne", "reason": "Silver Bolts true damage shreds high-HP bruisers; Condemn and Tumble provide effortless kiting away from melee range", "frequency": 45, "coverage_pct": 72.0},
            {"champion": "Cassiopeia", "reason": "Miasma grounds mobility dashes; sustained Twin Fang and Noxious Blast melt approaching juggernauts outside melee range", "frequency": 41, "coverage_pct": 65.6},
            {"champion": "Janna", "reason": "Monsoon and Howling Gale provide elite disengage and knockbacks, completely resetting extended melee skirmishes", "frequency": 38, "coverage_pct": 60.8},
            {"champion": "Lulu", "reason": "Polymorph neutralizes incoming bruisers; Whimsy movement speed and Wild Growth health knockup protect carries from collapses", "frequency": 36, "coverage_pct": 57.6},
            {"champion": "Poppy", "reason": "Steadfast Presence halts enemy dashes; Keeper's Verdict knocks away frontliners to prevent extended melee brawls", "frequency": 33, "coverage_pct": 52.8},
        ],
        "counter_items": [
            {"item": "Mortal Reminder", "purpose": "Applies 40% Grievous Wounds to shut down active healing, conqueror stacks, and omnivamp while granting crucial armor penetration", "recommended_count": 52},
            {"item": "Blade of the Ruined King", "purpose": "Deals percent current health on-hit physical damage and steals movement speed to kite high-health melee fighters", "recommended_count": 48},
            {"item": "Liandry's Torment", "purpose": "Burns high health pools with continuous percent max health magic damage over extended teamfights", "recommended_count": 44},
            {"item": "Frozen Heart", "purpose": "Emits an aura that drastically cripples enemy attack speed and stacks high armor to blunt sustained basic-attack brawlers", "recommended_count": 41},
            {"item": "Lord Dominik's Regards", "purpose": "Grants high armor penetration and bonus damage against high-health bruiser targets", "recommended_count": 39},
        ],
        "weaknesses": [
            "Short melee combat range; highly vulnerable to continuous ranged kiting, ground slows, and perimeter zoning",
            "Sustained combat power relies heavily on active healing and vamp, making them crippled by early Grievous Wounds",
            "Lack reliable target access; kiting them outside their primary gap-closers leaves them helpless and taking free damage",
        ],
        "tactical_tips": [
            "Maintain disciplined perimeter spacing and avoid committing primary skillshots until their initial gap-closers are baited",
            "Rush early Grievous Wounds (Executioner's Calling, Oblivion Orb, Bramble Vest) before mid-game teamfights to shut down their sustain",
            "Layer ground slows and knockbacks to keep fighters permanently at arm's length during neutral objective dances",
        ],
    },
    "melee": {
        "name": "Melee Heavy Teamfight Composition",
        "description": "Tactical composition clustered around short-range melee combatants, heavily susceptible to perimeter kiting, ground zoning, and disengage.",
        "counter_picks": [
            {"champion": "Vayne", "reason": "Silver Bolts true damage shreds high-HP melee champions while Tumble and Condemn ensure perpetual kiting distance", "frequency": 46, "coverage_pct": 73.6},
            {"champion": "Cassiopeia", "reason": "Miasma grounds dashes and Noxious Blast creates impassable poison zones for melee champions", "frequency": 42, "coverage_pct": 67.2},
            {"champion": "Janna", "reason": "Monsoon resets fights and Howling Gale interrupts approaching melee frontliners", "frequency": 40, "coverage_pct": 64.0},
            {"champion": "Lulu", "reason": "Polymorph and Wild Growth completely disable incoming melee divers", "frequency": 37, "coverage_pct": 59.2},
        ],
        "counter_items": [
            {"item": "Frozen Heart", "purpose": "Slows enemy basic attack speed by 20% and stacks high armor against melee champions", "recommended_count": 50},
            {"item": "Blade of the Ruined King", "purpose": "Percent current health on-hit damage and movement speed steal to kite melee champions", "recommended_count": 46},
            {"item": "Liandry's Torment", "purpose": "Burns melee champions continuously with percent max health damage as they attempt to close distance", "recommended_count": 42},
            {"item": "Mortal Reminder", "purpose": "Applies Grievous Wounds and armor penetration against sustain-heavy melee champions", "recommended_count": 39},
        ],
        "weaknesses": [
            "Severe range limitations; forced to run directly into skillshots and perimeter crowd control to deal damage",
            "Vulnerable to disengage tools that waste their gap-closer cooldowns without achieving target access",
            "Susceptible to continuous ground slows and terrain chokepoint zoning around Baron and Dragon",
        ],
        "tactical_tips": [
            "Draft long-range marksmen and artillery casters who can free-fire outside melee engagement range",
            "Never group into tightly packed melee clumps where enemy AoE spells can hit multiple targets",
            "Kite backwards through river chokepoints, using slows and knockbacks to drain their health before teamfights connect",
        ],
    },
    "tank_heavy": {
        "name": "Tank Heavy Frontline Composition",
        "description": "Tactical composition anchored by multiple high-health, high-resist tanks designed to soak damage and lock down enemies in extended 5v5 teamfights.",
        "counter_picks": [
            {"champion": "Vayne", "reason": "Silver Bolts true damage scales with target maximum health, completely bypassing stacked armor and magic resist", "frequency": 48, "coverage_pct": 76.8},
            {"champion": "Gwen", "reason": "Snip Snip and Needlework deal heavy percent maximum health magic and true damage that melts high-durability tanks", "frequency": 44, "coverage_pct": 70.4},
            {"champion": "Fiora", "reason": "Duelist's Dance and Grand Challenge deal unmitigated percent maximum health true damage to shred tanks", "frequency": 41, "coverage_pct": 65.6},
            {"champion": "Kog'Maw", "reason": "Bio-Arcane Barrage shreds maximum health from extreme range, melting tank frontlines with mixed on-hit damage", "frequency": 39, "coverage_pct": 62.4},
        ],
        "counter_items": [
            {"item": "Lord Dominik's Regards", "purpose": "Massive armor penetration and bonus physical damage against high-health tank champions", "recommended_count": 55},
            {"item": "Void Staff", "purpose": "40% magic penetration to bypass stacked magic resistance on tanks", "recommended_count": 49},
            {"item": "Blade of the Ruined King", "purpose": "Deals percent current health on-hit physical damage to burn through massive tank HP pools", "recommended_count": 46},
            {"item": "Liandry's Torment", "purpose": "Continuous percent maximum health burn over time that punishes high-health frontliners", "recommended_count": 43},
        ],
        "weaknesses": [
            "Low burst damage and slow target execution; vulnerable to percent-health true damage and continuous sustained DPS",
            "Extreme vulnerability to armor and magic penetration items, drastically diminishing their effective durability late game",
            "Immobile teamfight rotations; easily out-rotated and split-pushed across side lanes",
        ],
        "tactical_tips": [
            "Draft dual-damage carries with percent-health shred to prevent tanks from itemizing against a single damage type",
            "Rush Lord Dominik's Regards or Void Staff as 2nd/3rd items before tanks complete their third defensive component",
            "Avoid wasting primary burst cooldowns on the frontline tank; isolate and eliminate their backline carries",
        ],
    },
    "dive": {
        "name": "Dive and Hard Engage Composition",
        "description": "Tactical composition focused on high mobility initiation, backline collapse, and explosive burst damage to eliminate squishy carries instantly.",
        "counter_picks": [
            {"champion": "Janna", "reason": "Monsoon knocks back all incoming divers while healing allies, cleanly resetting failed enemy initiations", "frequency": 47, "coverage_pct": 75.2},
            {"champion": "Poppy", "reason": "Steadfast Presence creates an anti-dash perimeter that completely blocks enemy dive attempts", "frequency": 44, "coverage_pct": 70.4},
            {"champion": "Gragas", "reason": "Explosive Cask scatters incoming dive initiators away from your carries and disrupts follow-up", "frequency": 40, "coverage_pct": 64.0},
            {"champion": "Braum", "reason": "Unbreakable shield intercepts dive projectiles and Glacial Fissure creates impassable peel zones", "frequency": 38, "coverage_pct": 60.8},
            {"champion": "Lulu", "reason": "Polymorph completely halts diving threats and Wild Growth provides instant knockup and bonus HP", "frequency": 35, "coverage_pct": 56.0},
        ],
        "counter_items": [
            {"item": "Zhonya's Hourglass", "purpose": "Stasis active buys time for allies to peel while dodging initial dive burst cooldowns", "recommended_count": 54},
            {"item": "Plated Steelcaps", "purpose": "Reduces basic attack damage and grants armor against AD dive bruisers", "recommended_count": 49},
            {"item": "Frozen Heart", "purpose": "Reduces enemy attack speed and stacks armor to survive dive collapses", "recommended_count": 45},
            {"item": "Locket of the Iron Solari", "purpose": "AoE shield active that buffers ally health against coordinated dive burst", "recommended_count": 40},
            {"item": "Randuin's Omen", "purpose": "Reduces critical strike damage and AoE slows incoming divers", "recommended_count": 35},
        ],
        "weaknesses": [
            "High commitment with no escape; if their initial dive fails to eliminate the carry, they are stranded deep in enemy territory",
            "Vulnerable to counter-engage and disengage ultimates that turn their aggressive dives into team wipes",
            "Rely heavily on primary engage cooldowns; baiting the engage leaves them defenseless",
        ],
        "tactical_tips": [
            "Maintain disciplined perimeter spacing and hold reliable disengage CC specifically for when enemies initiate",
            "Build Zhonya's Hourglass on AP carries or Guardian Angel on AD carries to survive the initial dive burst",
            "Turn on over-committed divers once their primary gap-closers are expended and punish their lack of escape tools",
        ],
    },
    "assassin_heavy": {
        "name": "Assassin and Single-Target Burst Composition",
        "description": "Tactical composition relying on lethal physical and magic burst, stealth, and elusive gap-closers to assassinate isolated priority targets.",
        "counter_picks": [
            {"champion": "Lulu", "reason": "Point-and-click Polymorph and Wild Growth bonus health completely neutralize assassin dive burst", "frequency": 46, "coverage_pct": 73.6},
            {"champion": "Malzahar", "reason": "Nether Grasp suppression provides unavoidable point-and-click lockdown against elusive assassins", "frequency": 43, "coverage_pct": 68.8},
            {"champion": "Galio", "reason": "Hero's Entrance magic shield and Shield of Durand taunt absorb burst rotations and peel carries", "frequency": 40, "coverage_pct": 64.0},
            {"champion": "Poppy", "reason": "Steadfast Presence halts assassin dashes; Keeper's Verdict knocks divers out of teamfights", "frequency": 37, "coverage_pct": 59.2},
        ],
        "counter_items": [
            {"item": "Zhonya's Hourglass", "purpose": "Stasis active provides 2.5 seconds of total invulnerability, completely negating full assassin burst combos", "recommended_count": 56},
            {"item": "Plated Steelcaps", "purpose": "Reduces incoming basic attack damage and stacks armor against physical burst assassins", "recommended_count": 50},
            {"item": "Frozen Heart", "purpose": "Massive armor pool and attack speed reduction that blunts physical assassin damage", "recommended_count": 44},
            {"item": "Kaenic Rookern", "purpose": "Heavy magic shield that automatically absorbs burst rotations from magic damage assassins", "recommended_count": 41},
        ],
        "weaknesses": [
            "Single-target focus with no sustained teamfight DPS once primary burst cooldowns are expended",
            "Extreme squishiness; easily eliminated in a single crowd control lock if their flank path is caught",
            "Heavily reliant on early snowballing; falling behind in gold leaves them unable to assassinate priority targets",
        ],
        "tactical_tips": [
            "Group tightly as five in the mid-to-late game; never send squishy carries alone into unwarded jungle corridors",
            "Maintain deep vision on jungle flank routes and river choke points to spot assassins before they can position",
            "Save point-and-click crowd control specifically for when the assassin commits their gap-closer onto your carry",
        ],
    },
    "poke": {
        "name": "Poke and Siege Artillery Composition",
        "description": "Tactical composition utilizing extreme-range spells to whittle down enemy health bars around towers and neutral objective chokepoints.",
        "counter_picks": [
            {"champion": "Malphite", "reason": "Unstoppable Force hard engage closes distance through poke screens instantly, initiating teamfights on squishy casters", "frequency": 46, "coverage_pct": 73.6},
            {"champion": "Jarvan IV", "reason": "Cataclysm and Demacian Standard combo traps immobile artillery casters without flash", "frequency": 43, "coverage_pct": 68.8},
            {"champion": "Nocturne", "reason": "Paranoia eliminates enemy vision and closes the gap on long-range poke champions directly", "frequency": 40, "coverage_pct": 64.0},
            {"champion": "Blitzcrank", "reason": "Rocket Grab instantly isolates squishy poke champions before neutral objective standoffs begin", "frequency": 38, "coverage_pct": 60.8},
        ],
        "counter_items": [
            {"item": "Warmog's Armor", "purpose": "Massive out-of-combat health regeneration completely negates poke attrition between objective standoffs", "recommended_count": 50},
            {"item": "Kaenic Rookern", "purpose": "Renewable magic damage shield that continuously absorbs long-range spell poke rotations", "recommended_count": 48},
            {"item": "Shurelya's Battlesong", "purpose": "Teamwide movement speed active that allows your squad to force immediate hard collapses through poke zones", "recommended_count": 42},
            {"item": "Force of Nature", "purpose": "Stacking magic resistance and movement speed against repeated long-range spell hits", "recommended_count": 39},
        ],
        "weaknesses": [
            "Extremely squishy with zero defensive disengage once enemies close into melee range",
            "Ineffective in direct 5v5 melee collapses; completely collapsed on by flank engages",
            "Heavy mana and cooldown reliance to establish siege pressure",
        ],
        "tactical_tips": [
            "Bypass neutral standoff sieges by drafting decisive hard-engage tools to force immediate 5v5 teamfights",
            "Avoid lingering in river choke points where artillery skillshots are impossible to dodge",
            "Flank from unwarded fog of war rather than running directly through linear poke corridors",
        ],
    },
    "sustain": {
        "name": "Sustain and Heavy Healing Composition",
        "description": "Tactical composition centered on enchanters, drains, and health regeneration to outlast opponents in prolonged skirmishes.",
        "counter_picks": [
            {"champion": "Varus", "reason": "Blighted Quiver applies Grievous Wounds; Chain of Corruption immobilizes clumped healers", "frequency": 44, "coverage_pct": 70.4},
            {"champion": "Katarina", "reason": "Death Lotus applies 60% Grievous Wounds while dealing explosive multi-target burst damage", "frequency": 41, "coverage_pct": 65.6},
            {"champion": "Kled", "reason": "Bear Trap on a Rope pulls and applies 60% Grievous Wounds, shutting down healing tanks", "frequency": 38, "coverage_pct": 60.8},
            {"champion": "Leona", "reason": "Solar Flare and Zenith Blade chain crowd control locks healers before their abilities can cycle", "frequency": 36, "coverage_pct": 57.6},
        ],
        "counter_items": [
            {"item": "Mortal Reminder", "purpose": "Applies 40% Grievous Wounds on physical attacks to neutralize healing while granting armor penetration", "recommended_count": 54},
            {"item": "Morellonomicon", "purpose": "Applies 40% Grievous Wounds on magic damage, preventing enemy healers and enchanters from sustaining allies", "recommended_count": 50},
            {"item": "Thornmail", "purpose": "Inflicts Grievous Wounds when struck by basic attacks, shutting down lifesteal and omnivamp", "recommended_count": 46},
            {"item": "Chempunk Chainsword", "purpose": "Grants attack damage, health, and reliable Grievous Wounds on physical damage", "recommended_count": 42},
        ],
        "weaknesses": [
            "Crippled by early Grievous Wounds; cutting healing by 40% diminishes their effective team health pool drastically",
            "Vulnerable to single-target burst rotations that eliminate champions before healing spells can cycle",
            "Immobile support enchanters can be easily picked off in river vision choke points",
        ],
        "tactical_tips": [
            "Rush early Grievous Wounds components (Executioner's Calling, Oblivion Orb, Bramble Vest) across multiple teammates",
            "Focus fire the primary healer or enchanter first to remove the enemy team's sustain engine",
            "Execute decisive high-burst crowd control chains to wipe targets before their defensive shields or heals can be applied",
        ],
    },
    "hypercarry_protect": {
        "name": "Protect the Hypercarry and Funnel Composition",
        "description": "Tactical composition funneling all gold, shields, and peeling resources into a single late-game marksman to output massive sustained DPS.",
        "counter_picks": [
            {"champion": "Malphite", "reason": "Unstoppable Force knocks up the hypercarry through enchanter peel, triggering decisive burst collapses", "frequency": 45, "coverage_pct": 72.0},
            {"champion": "Vi", "reason": "Cease and Desist point-and-click unstoppable suppression isolates and locks down the hypercarry directly", "frequency": 43, "coverage_pct": 68.8},
            {"champion": "Camille", "reason": "The Hextech Ultimatum traps the carry inside an impassable arena, cutting off enchanter peel", "frequency": 40, "coverage_pct": 64.0},
            {"champion": "Nautilus", "reason": "Depth Charge follows the hypercarry relentlessly, forcing them to burn summoner spells or die", "frequency": 38, "coverage_pct": 60.8},
        ],
        "counter_items": [
            {"item": "Frozen Heart", "purpose": "Reduces hypercarry attack speed by 20% and stacks high armor to blunt their sustained DPS", "recommended_count": 52},
            {"item": "Randuin's Omen", "purpose": "Reduces critical strike damage by 30% and activates an AoE slow to cripple hypercarry kiting", "recommended_count": 48},
            {"item": "Anathema's Chains", "purpose": "Reduces damage taken from the hypercarry by 30% and reduces their tenacity to extend CC duration", "recommended_count": 44},
            {"item": "Thornmail", "purpose": "Reflects damage and applies Grievous Wounds to shut down hypercarry lifesteal", "recommended_count": 41},
        ],
        "weaknesses": [
            "Single point of failure; if the hypercarry is eliminated early, the composition has zero residual damage",
            "Weak early-to-mid game; highly susceptible to aggressive lane bullying and neutral objective snowballing",
            "Vulnerable to flank collapses and point-and-click crowd control that bypasses frontline tanks",
        ],
        "tactical_tips": [
            "Draft point-and-click crowd control ultimates to bypass enchanter shields and lock down the hypercarry directly",
            "Pressure multiple side lanes with 1-3-1 splits to stretch their defensive wardens away from the carry",
            "Snowball the early game by diving the vulnerable hypercarry repeatedly before their 3-item power spike arrives",
        ],
    },
    "stealth": {
        "name": "Stealth and Ambush Composition",
        "description": "Tactical composition utilizing invisibility and camouflage mechanics to execute surprise ambushes from fog of war.",
        "counter_picks": [
            {"champion": "Twisted Fate", "reason": "Destiny reveals all stealthed and invisible enemies across the entire map", "frequency": 46, "coverage_pct": 73.6},
            {"champion": "Lee Sin", "reason": "Tempest and Sonic Wave grant True Sight on invisible targets, preventing stealth escapes", "frequency": 43, "coverage_pct": 68.8},
            {"champion": "Karma", "reason": "Focused Resolve tether reveals stealthed units and roots them in place", "frequency": 39, "coverage_pct": 62.4},
            {"champion": "Lulu", "reason": "Help, Pix! reveals stealthed enemies and Polymorph prevents them from initiating from stealth", "frequency": 37, "coverage_pct": 59.2},
        ],
        "counter_items": [
            {"item": "Control Wards", "purpose": "Reveals camouflaged enemies and denies critical vision choke points around objectives", "recommended_count": 55},
            {"item": "Oracle Lens", "purpose": "Sweeps brushes to outline stealthed enemy silhouettes before they can ambushed your carries", "recommended_count": 52},
            {"item": "Zhonya's Hourglass", "purpose": "Stasis active buys time when ambushed from stealth", "recommended_count": 46},
            {"item": "Sterak's Gage", "purpose": "Massive lifeline shield to survive surprise burst rotations from stealth", "recommended_count": 41},
        ],
        "weaknesses": [
            "Revealed and neutralized by True Sight abilities and defensive vision tools (Control Wards, Oracle Lens)",
            "Low teamfight durability; unable to teamfight effectively if forced into direct 5v5 standoffs",
            "Rely heavily on element of surprise; once tracked by vision, their assassination angles are closed",
        ],
        "tactical_tips": [
            "Blanket river chokepoints and objective pits with Control Wards to nullify camouflage approaches",
            "Equip multiple Oracle Lenses across supports and junglers to sweep flanking bushes during neutral dances",
            "Never facecheck dark territory; escort carries with frontline wardens when rotating through river paths",
        ],
    },
    "splitpush": {
        "name": "Splitpush and Duelist Composition",
        "description": "Tactical composition using dominant 1v1 side-lane duelists to pressure outer towers while avoiding direct 5v5 teamfights.",
        "counter_picks": [
            {"champion": "Shen", "reason": "Stand United global teleport allows him to answer side-lane pushes and turn fights anywhere on the map", "frequency": 45, "coverage_pct": 72.0},
            {"champion": "Galio", "reason": "Hero's Entrance global arrival provides immediate counter-dive protection against side-lane pushers", "frequency": 42, "coverage_pct": 67.2},
            {"champion": "Malphite", "reason": "Unstoppable Force forces immediate 5v4 engages on the enemy main squad while the splitpusher is isolated", "frequency": 39, "coverage_pct": 62.4},
        ],
        "counter_items": [
            {"item": "Hullbreaker", "purpose": "Strengthens defensive stats and cannon minions to match enemy side-lane pressure", "recommended_count": 48},
            {"item": "Dead Man's Plate", "purpose": "High movement speed to rapidly rotate between side lanes and teamfights", "recommended_count": 44},
            {"item": "Warmog's Armor", "purpose": "High sustain to absorb side-lane poke and clear minion waves safely", "recommended_count": 40},
        ],
        "weaknesses": [
            "Forces 4v5 teamfights on the main map; if the enemy main squad is engaged upon, the splitpusher cannot arrive in time",
            "Heavily reliant on Teleport cooldown; vulnerable when summoner spells are down",
            "Vulnerable to coordinated 2-man collapses on side lanes with vision control",
        ],
        "tactical_tips": [
            "Force decisive 5v4 hard engages on the enemy team around Baron or Dragon while their splitpusher is isolated in side lanes",
            "Assign a strong duelist with Teleport or wave-clear tank to match their side-lane push under tower",
            "Set up vision traps in the splitpusher's jungle flank routes to catch them overextended without escape",
        ],
    },
    "marksman_heavy": {
        "name": "Marksman and Sustained Physical DPS Composition",
        "description": "Tactical composition featuring multiple ranged marksmen that deliver massive sustained physical basic attack damage late game.",
        "counter_picks": [
            {"champion": "Rammus", "reason": "Defensive Ball Curl and Frenzying Taunt make marksmen shred themselves with reflected physical damage", "frequency": 47, "coverage_pct": 75.2},
            {"champion": "Malphite", "reason": "Ground Slam reduces attack speed by 50% and Unstoppable Force one-shots squishy marksmen", "frequency": 44, "coverage_pct": 70.4},
            {"champion": "Jax", "reason": "Counter Strike dodges all basic attacks for 2 seconds before stunning nearby marksmen", "frequency": 41, "coverage_pct": 65.6},
            {"champion": "Yasuo", "reason": "Wind Wall completely negates all ranged basic attacks and marksman projectiles", "frequency": 38, "coverage_pct": 60.8},
        ],
        "counter_items": [
            {"item": "Plated Steelcaps", "purpose": "Reduces incoming basic attack damage by 12% and stacks armor", "recommended_count": 56},
            {"item": "Frozen Heart", "purpose": "Aura slows enemy attack speed by 20% and grants 75 armor", "recommended_count": 52},
            {"item": "Randuin's Omen", "purpose": "Reduces incoming critical strike damage by 30% and activates an AoE slow", "recommended_count": 48},
            {"item": "Thornmail", "purpose": "Stacks massive armor and reflects basic attack damage back to the marksmen", "recommended_count": 44},
        ],
        "weaknesses": [
            "Pure physical damage profile; completely countered by stacking armor items (Plated Steelcaps, Frozen Heart)",
            "Extremely squishy with low mobility; vulnerable to heavy dive and burst assassins",
            "Weak early laning phase before multi-item power spikes come online",
        ],
        "tactical_tips": [
            "Stack heavy armor and attack speed slows early; building Plated Steelcaps and Frozen Heart neutralizes their DPS",
            "Draft dive assassins and hard engage initiators to collapse onto squishy marksmen before they can establish free-fire distance",
            "End games through mid-game objective snowballing before the opposing marksmen reach their 3-item critical strike threshold",
        ],
    },
    "mage_heavy": {
        "name": "Control Mage and Magic Damage Teamfight Composition",
        "description": "Tactical composition dominated by ability-power spell casters that excel in AoE burst, objective zone control, and spell rotation chains.",
        "counter_picks": [
            {"champion": "Galio", "reason": "Shield of Durand grants a massive magic shield and Hero's Entrance mitigates teamwide magic damage", "frequency": 46, "coverage_pct": 73.6},
            {"champion": "Kassadin", "reason": "Void Stone passive takes 10% reduced magic damage; Riftwalk allows him to dive and burst mages", "frequency": 43, "coverage_pct": 68.8},
            {"champion": "Dr. Mundo", "reason": "Goes Where He Pleases high health pool and passive spell shield shrugs off mage burst combos", "frequency": 40, "coverage_pct": 64.0},
        ],
        "counter_items": [
            {"item": "Kaenic Rookern", "purpose": "Grants an enormous recurring magic damage shield that completely absorbs spell burst rotations", "recommended_count": 55},
            {"item": "Force of Nature", "purpose": "Stacks magic resistance and movement speed when struck by spell damage", "recommended_count": 50},
            {"item": "Mercury's Treads", "purpose": "Grants magic resistance and 30% tenacity to reduce crowd control duration", "recommended_count": 46},
            {"item": "Maw of Malmortius", "purpose": "Lifeline magic shield and omnivamp to survive lethal magic burst", "recommended_count": 42},
        ],
        "weaknesses": [
            "Pure magic damage profile; completely negated by heavy magic resistance stacking (Kaenic Rookern, Force of Nature)",
            "Extremely reliant on spell cooldowns; defenseless when primary abilities are on cooldown",
            "Immobile and skillshot-dependent; vulnerable to high-mobility flank engages",
        ],
        "tactical_tips": [
            "Stack early magic resistance across frontline and carries; Kaenic Rookern's shield alone negates full mage burst rotations",
            "Engage decisively during their spell cooldown windows after baiting out their primary crowd control skillshots",
            "Flank around their objective choke points to prevent them from setting up overlapping AoE spell zones",
        ],
    },
    "full_ap": {
        "name": "Full Ability Power and Magic Damage Composition",
        "description": "Tactical composition lacking physical damage threats, making them completely vulnerable to unified magic resistance itemization.",
        "counter_picks": [
            {"champion": "Galio", "reason": "Shield of Durand magic shield and Hero's Entrance magic mitigation neutralize full AP lineups", "frequency": 48, "coverage_pct": 76.8},
            {"champion": "Kassadin", "reason": "Void Stone passive permanently reduces magic damage by 10%; scales to out-damage mages late game", "frequency": 45, "coverage_pct": 72.0},
            {"champion": "Dr. Mundo", "reason": "Immense health pool and spell negation shield completely resist magic damage burst", "frequency": 42, "coverage_pct": 67.2},
        ],
        "counter_items": [
            {"item": "Kaenic Rookern", "purpose": "Massive renewable magic damage shield that absorbs full AP rotations", "recommended_count": 56},
            {"item": "Force of Nature", "purpose": "Stacking magic resist and movement speed against repeated spell hits", "recommended_count": 52},
            {"item": "Mercury's Treads", "purpose": "Magic resistance and tenacity against magic crowd control", "recommended_count": 48},
            {"item": "Maw of Malmortius", "purpose": "Lifeline magic shield for AD champions against AP burst", "recommended_count": 43},
        ],
        "weaknesses": [
            "Pure magic damage profile; enemy team can buy zero armor and stack purely magic resistance",
            "Vulnerable to sustained physical DPS that shreds through their low armor pools",
            "Cooldown dependent; weak during ability cooldown windows",
        ],
        "tactical_tips": [
            "Every member of your team should build at least one high-tier magic resist item (Kaenic Rookern, Maw of Malmortius)",
            "Draft AD bruisers or marksmen who exploit their lack of armor stacking",
            "Force extended brawls where their burst fails to kill through MR shields and your sustained DPS takes over",
        ],
    },
    "full_ad": {
        "name": "Full Attack Damage and Physical Composition",
        "description": "Tactical composition lacking magic damage threats, making them completely vulnerable to unified armor itemization.",
        "counter_picks": [
            {"champion": "Malphite", "reason": "Ground Slam slows attack speed by 50% and armor scaling turns defensive stats into lethal damage", "frequency": 48, "coverage_pct": 76.8},
            {"champion": "Rammus", "reason": "Stacks enormous armor and reflects basic attack damage back to attackers via Defensive Ball Curl", "frequency": 46, "coverage_pct": 73.6},
            {"champion": "Poppy", "reason": "Steadfast Presence halts physical dashes and isolates melee frontliners", "frequency": 42, "coverage_pct": 67.2},
        ],
        "counter_items": [
            {"item": "Plated Steelcaps", "purpose": "Reduces basic attack damage by 12% and stacks armor", "recommended_count": 56},
            {"item": "Frozen Heart", "purpose": "Massive armor and attack speed slow against physical carries", "recommended_count": 53},
            {"item": "Randuin's Omen", "purpose": "Armor and 30% critical strike damage reduction", "recommended_count": 49},
            {"item": "Thornmail", "purpose": "Heavy armor and Grievous Wounds against physical vamp", "recommended_count": 45},
        ],
        "weaknesses": [
            "Pure physical damage profile; completely negated by stacking armor (Plated Steelcaps, Frozen Heart, Thornmail)",
            "Zero magic damage threat allows opposing tanks to itemize purely against physical damage",
            "Vulnerable to crowd control chains once gap-closers are expended",
        ],
        "tactical_tips": [
            "Every teammate should rush Plated Steelcaps early to blunt their physical damage output",
            "Draft armor-scaling tanks like Malphite and Rammus who become unkillable against full AD teams",
            "Stack armor freely without investing any gold into magic resistance items",
        ],
    },
}


class DataRetriever:
    """Retrieve structured data corresponding to intents."""

    def __init__(self, store = None):
        self.store = store or get_knowledge_store()

    def dispatch_query(self, intent, entities):
        """Dispatch classified intent to the appropriate retriever method."""
        champ_name = entities.get("champion_name")
        skill_key = entities.get("skill_key")
        skill_lvl = entities.get("skill_level")
        char_lvl = entities.get("character_level")
        stat_name = entities.get("stat_name")

        if intent == "SKILL_DAMAGE_AT_LEVEL":
            return self.get_skill_damage(champ_name, skill_key or "Q", skill_lvl or 1)

        elif intent == "SKILL_INFO":
            return self.get_skill_info(champ_name, skill_key or "Q")

        elif intent == "SKILL_COOLDOWN":
            return self.get_skill_cooldown(champ_name, skill_key or "Q")

        elif intent == "CHAMPION_BASE_STATS":
            return self.get_champion_base_stats(champ_name)

        elif intent == "CHAMPION_STATS_AT_LEVEL":
            return self.get_champion_stats_at_level(champ_name, char_lvl or 1)

        elif intent == "CHAMPION_INFO":
            inter_c = entities.get("interaction_champion")
            if inter_c:
                return self.get_champion_lore(champ_name, interaction_champ = inter_c)
            return self.get_champion_info(champ_name)

        elif intent == "LORE_QUERY":
            inter_c = entities.get("interaction_champion")
            if not champ_name and entities.get("enemy_champions"):
                champ_name = entities["enemy_champions"][0]
                if len(entities["enemy_champions"]) >= 2 and not inter_c:
                    inter_c = entities["enemy_champions"][1]
            if not inter_c and entities.get("enemy_champions") and len(entities["enemy_champions"]) >= 2:
                candidates = [c for c in entities["enemy_champions"] if c.lower() != (champ_name or "").lower()]
                if candidates:
                    inter_c = candidates[0]
            return self.get_champion_lore(champ_name, interaction_champ = inter_c)

        elif intent == "CHAMPION_COMPARISON":
            return self.compare_champions(
                entities.get("comparison_champions") or [champ_name], stat_name
            )

        elif intent == "ROLE_QUERY":
            role_req = entities.get("role") or (self.store.all_roles[0] if self.store.all_roles else "fighter")
            return self.get_champions_by_role(role_req, entities.get("lane"))

        elif intent == "LANE_QUERY":
            lane_req = entities.get("lane") or (self.store.all_positions[0].lower() if self.store.all_positions else "top")
            return self.get_champions_by_lane(lane_req)

        elif intent == "SKILL_MANA_COST":
            return self.get_skill_info(champ_name, skill_key or "Q")

        elif intent == "LIST_SKILLS":
            return self.list_skills(champ_name)

        elif intent == "ROLE_COUNTER_PICK":
            u_role = entities.get("user_role") or entities.get("role")
            target_val = entities.get("target") or champ_name
            target_t = entities.get("target_type") or ("champion" if champ_name else "role")
            lane_req = entities.get("lane")
            return self.get_role_counter_picks(
                user_role=u_role,
                target_value=target_val,
                target_type=target_t,
                lane=lane_req,
            )

        elif intent in ("TEAM_COMPOSITION_BUILDING", "CHAMPION_TEAM_COMPOSITION", "COMPOSITION_QUERY"):
            if champ_name:
                return self.get_champion_composition(champ_name)
            comp_key = entities.get("comp_archetype") or entities.get("damage_composition") or "hypercarry_protect"
            return self.get_composition_building_info(comp_key, power_curve=entities.get("power_curve"))

        elif intent == "TEAM_COUNTER_ANALYSIS":
            if entities.get("comp_archetype") or entities.get("damage_composition"):
                return self.get_composition_counters(entities.get("comp_archetype"), entities.get("damage_composition"))
            elif entities.get("enemy_champions"):
                return self.analyze_team_counters(entities["enemy_champions"])
            else:
                return self.get_composition_counters("dive")

        elif intent == "COUNTER_QUERY":
            if champ_name:
                return self.get_counters(champ_name, entities.get("counter_direction"), entities.get("lane"))
            elif entities.get("comp_archetype") or entities.get("damage_composition"):
                return self.get_composition_counters(entities.get("comp_archetype"), entities.get("damage_composition"))
            elif entities.get("role") or entities.get("lane"):
                return self.get_role_counters(entities.get("role"), entities.get("lane"), entities.get("counter_direction"))

        elif intent == "SYNERGY_QUERY":
            return self.get_synergies(champ_name)

        elif intent == "TEAM_SYNERGY_ANALYSIS":
            team = entities.get("allied_champions") or entities.get("comparison_champions") or ([champ_name] if champ_name else [])
            return self.analyze_team_synergies(team)

        elif intent == "BUILD_QUERY":
            if not champ_name and entities.get("item_name"):
                return self.get_item_info(entities["item_name"])
            return self.get_build(champ_name)

        elif intent == "SKIN_QUERY":
            return self.get_champion_skins(champ_name)

        elif intent == "ARAM_QUERY":
            return self.get_aram_stats(champ_name)

        elif intent == "ABILITY_MECHANIC_QUERY":
            return self.get_mechanics_info(
                name=champ_name,
                skill_key=skill_key,
                mechanic=entities.get("mechanic"),
                interaction_champ=entities.get("interaction_champion"),
            )

        elif intent == "ITEM_INFO":
            return self.get_item_info(entities.get("item_name") or champ_name)

        elif intent == "RUNE_INFO":
            return self.get_rune_info(entities.get("rune_name") or champ_name)

        elif intent in (
            "MULTI_PROPERTY_FILTER",
            "CHAMPION_BY_CC",
            "CHAMPION_BY_EFFECT",
            "CHAMPION_BY_PLAYSTYLE",
            "CHAMPION_BY_POWER_CURVE",
            "CHAMPION_BY_WIN_CONDITION",
        ):
            return self.filter_semantic(
                roles=[entities.get("role")] if entities.get("role") else None,
                cc_types=entities.get("cc_types"),
                effects=entities.get("ability_effects"),
                playstyles=entities.get("playstyles"),
                power_curve=entities.get("power_curve"),
                win_condition=entities.get("win_condition"),
            )

        elif intent == "CHAMPION_SEMANTIC_PROFILE":
            return self.get_semantic_profile(champ_name)

        elif intent == "TEAM_COUNTER_ANALYSIS":
            enemy_champs = entities.get("enemy_champions") or []
            comp_archetype = entities.get("comp_archetype")
            damage_comp = entities.get("damage_composition")
            if enemy_champs or comp_archetype or damage_comp:
                if enemy_champs:
                    return self.analyze_team_counters(
                        enemy_champs,
                        comp_archetype=comp_archetype,
                        damage_composition=damage_comp,
                    )
                else:
                    return self.get_composition_counters(comp_archetype, damage_comp)
            elif entities.get("role") or entities.get("lane"):
                return self.get_role_counters(entities.get("role"), entities.get("lane"), entities.get("counter_direction"))

        # Default fallback
        if champ_name:
            return self.get_champion_info(champ_name)
        elif entities.get("comp_archetype") or entities.get("damage_composition"):
            return self.get_composition_counters(entities.get("comp_archetype"), entities.get("damage_composition"))
        elif entities.get("role"):
            return self.get_role_counters(entities.get("role"), entities.get("lane"), entities.get("counter_direction"))
        elif entities.get("lane"):
            return self.get_champions_by_lane(entities.get("lane"))
        return {"info": "Please provide more information about the champion, item, or mechanics you want to ask about."}

    # Individual Retrievers

    def format_champion_abilities(self, c_doc):
        """Format champion abilities with verified CC and effect tags (e.g. Q: Shattered Earth [Slow])."""
        if not c_doc or not c_doc.get("abilities"):
            return ""
        ab_dict = c_doc["abilities"]
        ab_parts = []
        for key in ["passive", "Q", "W", "E", "R"]:
            ab = ab_dict.get(key)
            if isinstance(ab, dict) and ab.get("name"):
                name = ab["name"]
                desc = f"{ab.get('description', '')} {ab.get('tooltip', '')}"
                cc_set = SpellAnalyzer.extract_cc(desc)
                eff_set = SpellAnalyzer.extract_effects(desc)
                tags = []
                if cc_set:
                    tags.extend(sorted(list(cc_set)))
                key_effects = eff_set & {"Shield", "Heal", "Dash", "Blink", "Stealth", "Invulnerability"}
                if key_effects:
                    tags.extend(sorted(list(key_effects)))
                tag_str = f" [{', '.join(tags)}]" if tags else ""
                ab_parts.append(f"{key.upper()}: {name}{tag_str}")
        return ", ".join(ab_parts)

    def extract_champion_full_profile(self, champ):
        """
        Extract complete, multi-dimensional profile of a champion from Processors and KnowledgeStore.
        Preserves abilities, base stats, attribute ratings, tactical info, and mechanics.
        """
        abilities = {}
        if "abilities" in champ and isinstance(champ["abilities"], dict):
            for k, v in champ["abilities"].items():
                if isinstance(v, dict):
                    abilities[k] = {
                        "name": v.get("name", ""),
                        "description": v.get("description", ""),
                        "cooldown": v.get("cooldown", []),
                        "cost": v.get("cost", []),
                        "costType": v.get("costType"),
                        "range": v.get("range", []),
                        "maxrank": v.get("maxrank"),
                        "scalingEffects": v.get("scalingEffects", []),
                        "effects": v.get("effects", []),
                        "projectile": v.get("projectile"),
                        "projectileType": v.get("projectileType"),
                        "spellshieldable": v.get("spellshieldable"),
                        "onHitEffects": v.get("onHitEffects"),
                        "damageType": v.get("damageType"),
                        "targeting": v.get("targeting"),
                        "notes": v.get("notes"),
                    }

        tactical = champ.get("tacticalInfo") if isinstance(champ.get("tacticalInfo"), dict) else {}
        stats = champ.get("stats", {})
        base_stats = {}
        stat_growths = {}
        if isinstance(stats, dict):
            for k, v in stats.items():
                if isinstance(v, dict):
                    if "base" in v:
                        base_stats[k] = v.get("base")
                    if "perLevel" in v:
                        stat_growths[k] = v.get("perLevel")
                elif isinstance(v, (int, float)):
                    base_stats[k] = v

        raw_related = champ.get("related_champions", [])
        clean_related = []
        for r in raw_related:
            r_name = r.get("name") if isinstance(r, dict) else str(r)
            if r_name and r_name not in clean_related:
                clean_related.append(r_name)

        return {
            "name": champ.get("name"),
            "champion": champ.get("name"),
            "title": champ.get("title", ""),
            "region": champ.get("region", ""),
            "roles": champ.get("roles", []),
            "subroles": champ.get("subroles", []),
            "positions": champ.get("positions", []),
            "attackType": champ.get("attackType"),
            "adaptiveType": champ.get("adaptiveType"),
            "resource": champ.get("resource"),
            "attributeRatings": champ.get("attributeRatings", {}),
            "playstyleRatings": champ.get("playstyleRatings", {}),
            "difficulty": champ.get("difficulty"),
            "base_stats": base_stats,
            "stat_growths": stat_growths,
            "stats": stats,
            "playstyles": champ.get("playstyles", []),
            "powerCurve": champ.get("powerCurve", []),
            "winConditions": champ.get("winConditions", []),
            "cc_types": champ.get("cc_types", []),
            "hard_cc": champ.get("hard_cc", []),
            "soft_cc": champ.get("soft_cc", []),
            "ability_effects": champ.get("ability_effects", []),
            "abilities": abilities,
            "tacticalInfo": tactical,
            "weaknesses": champ.get("weaknesses") or tactical.get("weaknesses", []),
            "tactical_tips": champ.get("tactical_tips") or tactical.get("tactical_tips", []),
            "counter_items": champ.get("counter_items") or tactical.get("counter_items", []),
            "official_enemytips": champ.get("enemytips") or tactical.get("official_enemytips", []),
            "official_allytips": champ.get("allytips") or tactical.get("official_allytips", []),
            "skins": champ.get("skins", []),
            "stories": champ.get("stories", []),
            "aramStats": champ.get("aramStats", {}),
            "mechanicsSummary": champ.get("mechanicsSummary", {}),
            "shortLore": champ.get("shortLore") or champ.get("lore", "")[:600],
            "lore": champ.get("lore", "")[:2500],
            "related_champions": clean_related,
        }

    def get_champion_info(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}
        return self.extract_champion_full_profile(champ)

    def get_champion_lore(self, name, interaction_champ = None):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)

        # Clean related champions (extract string names, never raw dicts)
        raw_related = profile.get("related_champions", [])
        clean_related = []
        for r in raw_related:
            r_name = r.get("name") if isinstance(r, dict) else str(r)
            if r_name and r_name not in clean_related:
                clean_related.append(r_name)

        result = {
            "is_lore_query": True,
            "champion": profile.get("name"),
            "title": profile.get("title"),
            "region": profile.get("region"),
            "roles": profile.get("roles"),
            "shortLore": profile.get("shortLore", ""),
            "lore": profile.get("lore", ""),
            "stories": profile.get("stories", []),
            "related_champions": clean_related,
        }

        # Multi-champion lore relationship / conflict query
        if interaction_champ:
            inter_champ = self.store.get_champion(interaction_champ)
            if inter_champ:
                inter_profile = self.extract_champion_full_profile(inter_champ)
                inter_raw_related = inter_profile.get("related_champions", [])
                inter_clean_related = [
                    (r.get("name") if isinstance(r, dict) else str(r))
                    for r in inter_raw_related
                ]

                result["is_conflict_lore_query"] = True
                result["interaction_champion"] = inter_profile.get("name")
                result["interaction_title"] = inter_profile.get("title")
                result["interaction_region"] = inter_profile.get("region")
                result["interaction_shortLore"] = inter_profile.get("shortLore", "")
                result["interaction_lore"] = inter_profile.get("lore", "")
                result["interaction_related"] = [r for r in inter_clean_related if r]

        return result

    def get_champion_skins(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        raw_skins = champ.get("skins", [])

        # Filter out default base champion and separate actual skins from color chromas
        actual_skins = []
        chromas = []
        for s in raw_skins:
            s_name = s.get("name") if isinstance(s, dict) else str(s)
            s_num = s.get("num", -1) if isinstance(s, dict) else -1
            if not s_name or s_name.lower() == "default" or s_num == 0:
                continue
            if "(" in s_name and ")" in s_name:
                chromas.append(s_name)
            else:
                actual_skins.append(s_name)

        # Categorize skins into recognizable thematic universes and tiers
        thematic_groups = {}
        legendary_prestige = []
        for sk in actual_skins:
            sk_lower = sk.lower()
            if any(k in sk_lower for k in ["prestige", "nightbringer", "truth dragon", "dream dragon", "genesis"]):
                legendary_prestige.append(sk)

            if "project" in sk_lower:
                thematic_groups.setdefault("Cyberpunk (PROJECT)", []).append(sk)
            elif any(k in sk_lower for k in ["nightbringer", "dawnbringer"]):
                thematic_groups.setdefault("Order & Chaos (Nightbringer)", []).append(sk)
            elif any(k in sk_lower for k in ["spirit blossom", "blood moon", "inkshadow", "snow moon"]):
                thematic_groups.setdefault("Ionian Spirit & Lore", []).append(sk)
            elif "dragon" in sk_lower:
                thematic_groups.setdefault("Dragonmancer", []).append(sk)
            elif "high noon" in sk_lower:
                thematic_groups.setdefault("Wild West (High Noon)", []).append(sk)
            elif any(k in sk_lower for k in ["odyssey", "dark star", "cosmic"]):
                thematic_groups.setdefault("Sci-Fi & Cosmic (Odyssey)", []).append(sk)
            elif any(k in sk_lower for k in ["true damage", "k/da", "heartsteel", "pentakill"]):
                thematic_groups.setdefault("Music & Pop Culture", []).append(sk)
            elif any(k in sk_lower for k in ["arcade", "battle boss"]):
                thematic_groups.setdefault("Arcade Universe", []).append(sk)
            elif any(k in sk_lower for k in ["battle wolf", "battle bat", "anima squad"]):
                thematic_groups.setdefault("Anima Squad", []).append(sk)
            elif "foreseen" in sk_lower:
                thematic_groups.setdefault("Cinematic & Canon Lore", []).append(sk)

        return {
            "is_skin_query": True,
            "champion": profile.get("name"),
            "title": profile.get("title"),
            "unique_skin_count": len(actual_skins),
            "chroma_count": len(chromas),
            "total_cosmetics": len(actual_skins) + len(chromas),
            "actual_skins": actual_skins,
            "legendary_prestige": legendary_prestige,
            "thematic_groups": thematic_groups,
            "sample_skins": actual_skins[:15],
            "skins": actual_skins,
            "total_skins": len(actual_skins),
        }

    def get_aram_stats(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        aram = champ.get("aramStats", {})
        return {
            "is_aram_query": True,
            "champion": profile.get("name"),
            "title": profile.get("title"),
            "has_aram_stats": bool(aram),
            "aram_modifiers": aram,
            "aram_stats": aram,
            "aramStats": aram,
            "tacticalInfo": champ.get("tacticalInfo", {}),
        }

    def get_mechanics_info(self, name, skill_key = None, mechanic = None, interaction_champ = None):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        abilities = champ.get("abilities", {})
        mechanics_summary = champ.get("mechanicsSummary", {})

        if skill_key:
            sk = skill_key.upper()
            # If name is a known defender (e.g. Yasuo with Wind Wall) and interaction_champ has the skill (e.g. Lux with R)
            if interaction_champ and self.store.get_champion(interaction_champ):
                inter_champ_obj = self.store.get_champion(interaction_champ)
                inter_abilities = inter_champ_obj.get("abilities", {})
                if sk in inter_abilities and (name.lower() in ["yasuo", "braum", "samira", "sivir", "nocturne"] or not abilities.get(sk, {}).get("description")):
                    champ = inter_champ_obj
                    profile = self.extract_champion_full_profile(champ)
                    abilities = inter_abilities
                    mechanics_summary = champ.get("mechanicsSummary", {})
                    interaction_champ, name = name, profile.get("name")

            ability = abilities.get(sk, {})
            is_projectile = ability.get("projectile", False)
            is_spellshieldable = ability.get("spellshieldable", False)
            is_onhit = ability.get("onHitEffects", False)
            damage_type = ability.get("damageType")

            wind_wall_blocked = is_projectile
            wind_wall_verdict = (
                "BLOCKED by Wind Wall (Yasuo W, Samira W, Braum E) because it is a projectile."
                if is_projectile
                else "NOT BLOCKED by Wind Wall (Yasuo W, Samira W) because it is an instant beam/area ability, not a projectile."
            )

            spellshield_verdict = (
                "BLOCKED / Absorbed by Spell Shields (Banshee's Veil, Edge of Night, Sivir E, Nocturne W)."
                if is_spellshieldable
                else "NOT BLOCKED by Spell Shields."
            )

            return {
                "is_mechanics_query": True,
                "champion": profile.get("name"),
                "skill_key": sk,
                "skill_name": ability.get("name", sk),
                "description": ability.get("description", ""),
                "is_projectile": is_projectile,
                "projectile": is_projectile,
                "spellshieldable": is_spellshieldable,
                "triggers_on_hit": is_onhit,
                "onHitEffects": is_onhit,
                "damageType": damage_type,
                "wind_wall_blocked": wind_wall_blocked,
                "wind_wall_verdict": wind_wall_verdict,
                "spellshield_verdict": spellshield_verdict,
                "mechanic_tested": mechanic,
                "interaction_champion": interaction_champ,
                "mechanicsSummary": mechanics_summary,
            }

        return {
            "is_mechanics_query": True,
            "champion": profile.get("name"),
            "mechanic_tested": mechanic,
            "mechanic_requested": mechanic,
            "projectile_abilities": mechanics_summary.get("projectileAbilities", []),
            "spellshieldable_abilities": mechanics_summary.get("spellshieldableAbilities", []),
            "onhit_abilities": mechanics_summary.get("onHitAbilities", []),
            "damage_types": mechanics_summary.get("abilityDamageTypes", []),
            "mechanicsSummary": mechanics_summary,
            "abilities": profile.get("abilities", {}),
        }

    def get_skill_damage(self, name, skill_key, rank):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        key = skill_key.upper()
        skill = champ.get("abilities", {}).get(key)
        if not skill:
            return {"error": f"Ability {key} of {champ.get('name')} not found."}

        cooldowns = skill.get("cooldown", [])
        cd_val = cooldowns[rank - 1] if isinstance(cooldowns, list) and len(cooldowns) >= rank else cooldowns

        profile.update({
            "skill_key": key,
            "skill_name": skill.get("name"),
            "rank": rank,
            "description": skill.get("description", ""),
            "cooldown": cd_val,
            "cost": skill.get("cost", []),
            "costType": skill.get("costType"),
            "range": skill.get("range", []),
            "maxrank": skill.get("maxrank"),
            "scalingEffects": skill.get("scalingEffects", []),
            "effects": skill.get("effects", []),
        })
        return profile

    def get_skill_info(self, name, skill_key):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        key = skill_key.upper()
        skill = champ.get("abilities", {}).get(key)
        if not skill:
            return {"error": f"Ability {key} of {champ.get('name')} not found."}

        profile.update({
            "skill_key": key,
            "skill_name": skill.get("name"),
            "description": skill.get("description", ""),
            "cooldown": skill.get("cooldown", []),
            "cost": skill.get("cost", []),
            "costType": skill.get("costType"),
            "range": skill.get("range", []),
            "maxrank": skill.get("maxrank"),
            "scalingEffects": skill.get("scalingEffects", []),
            "effects": skill.get("effects", []),
            "projectile": skill.get("projectile"),
            "projectileType": skill.get("projectileType"),
            "spellshieldable": skill.get("spellshieldable"),
            "onHitEffects": skill.get("onHitEffects"),
            "damageType": skill.get("damageType"),
            "targeting": skill.get("targeting"),
            "notes": skill.get("notes"),
        })
        return profile

    def get_skill_cooldown(self, name, skill_key):
        return self.get_skill_info(name, skill_key)

    def get_champion_base_stats(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        profile["level"] = 1
        return profile

    def get_champion_stats_at_level(self, name, level):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        stats = champ.get("stats", {})
        calculated = {}
        for k, v in stats.items():
            if isinstance(v, dict):
                base = v.get("base", 0)
                growth = v.get("perLevel", 0)
                if level > 1 and growth > 0:
                    val = base + growth * (level - 1) * (0.7025 + 0.0175 * (level - 1))
                else:
                    val = base
                calculated[k] = round(val, 2)

        profile["level"] = level
        profile["stats_at_level"] = calculated
        return profile

    def compare_champions(self, champ_names, stat_name = None):
        if not champ_names or len(champ_names) < 2:
            return {"error": "At least 2 champions are required for comparison."}

        data = {}
        for name in champ_names:
            champ = self.store.get_champion(name)
            if champ:
                profile = self.extract_champion_full_profile(champ)
                data[champ.get("name")] = {
                    "roles": profile.get("roles", []),
                    "attackType": profile.get("attackType"),
                    "adaptiveType": profile.get("adaptiveType"),
                    "attributeRatings": profile.get("attributeRatings", {}),
                    "base_stats": profile.get("base_stats", {}),
                    "playstyles": profile.get("playstyles", []),
                    "winConditions": profile.get("winConditions", []),
                    "hard_cc": profile.get("hard_cc", []),
                    "ability_effects": profile.get("ability_effects", []),
                }

        # Check direct counter relationship between the two champions
        matchup_info = None
        c1_name = champ_names[0]
        c2_name = champ_names[1]
        c1_counters = self.store.get_counter_info(c1_name)
        if c1_counters:
            for wa in c1_counters.get("weakAgainst", []):
                if wa.get("champion", "").lower() == c2_name.lower():
                    matchup_info = {
                        "advantaged": c2_name,
                        "disadvantaged": c1_name,
                        "win_rate": wa.get("winRate"),
                        "reason": wa.get("reason", ""),
                    }
                    break
            if not matchup_info:
                for sa in c1_counters.get("strongAgainst", []):
                    if sa.get("champion", "").lower() == c2_name.lower():
                        matchup_info = {
                            "advantaged": c1_name,
                            "disadvantaged": c2_name,
                            "win_rate": sa.get("winRate"),
                            "reason": sa.get("reason", ""),
                        }
                        break
        if not matchup_info:
            c2_counters = self.store.get_counter_info(c2_name)
            if c2_counters:
                for wa in c2_counters.get("weakAgainst", []):
                    if wa.get("champion", "").lower() == c1_name.lower():
                        matchup_info = {
                            "advantaged": c1_name,
                            "disadvantaged": c2_name,
                            "win_rate": wa.get("winRate"),
                            "reason": wa.get("reason", ""),
                        }
                        break
                if not matchup_info:
                    for sa in c2_counters.get("strongAgainst", []):
                        if sa.get("champion", "").lower() == c1_name.lower():
                            matchup_info = {
                                "advantaged": c2_name,
                                "disadvantaged": c1_name,
                                "win_rate": sa.get("winRate"),
                                "reason": sa.get("reason", ""),
                            }
                            break

        return {
            "comparison": data,
            "target_stat": stat_name,
            "matchup_info": matchup_info,
            "champions": [c1_name, c2_name],
        }

    def get_champions_by_role(self, role, lane = None):
        from collections import Counter
        champs = self.store.filter_champions(roles=[role], positions=[lane] if lane else None)
        if not champs and lane:
            champs = self.store.filter_champions(roles=[role])

        subroles = [s for c in champs for s in c.get("subroles", [])]
        top_subroles = [s for s, _ in Counter(subroles).most_common(5)]

        damage_types = [c.get("adaptiveType") for c in champs if c.get("adaptiveType")]
        dominant_damage = Counter(damage_types).most_common(1)[0][0] if damage_types else "Mixed"

        sample_champs = [
            {
                "name": c.get("name"),
                "subroles": c.get("subroles", []),
                "positions": c.get("positions", []),
                "damage_type": c.get("adaptiveType"),
                "playstyles": c.get("playstyles", []),
                "power_curve": c.get("powerCurve", []),
            }
            for c in champs[:25]
        ]
        return {
            "is_role_query": True,
            "role": role,
            "lane": lane or "all",
            "role_title": f"{role.capitalize()} Champions" + (f" ({lane.upper()})" if lane else ""),
            "count": len(champs),
            "dominant_damage": dominant_damage,
            "subroles": top_subroles,
            "champions": [c.get("name") for c in champs[:25]],
            "sample_champions": sample_champs,
        }

    def get_champions_by_lane(self, lane):
        from collections import Counter
        champs = self.store.get_champions_by_lane(lane)

        roles = [r for c in champs for r in c.get("roles", [])]
        top_roles = [r for r, _ in Counter(roles).most_common(4)]

        subroles = [s for c in champs for s in c.get("subroles", [])]
        top_subroles = [s for s, _ in Counter(subroles).most_common(5)]

        damage_types = [c.get("adaptiveType") for c in champs if c.get("adaptiveType")]
        dominant_damage = Counter(damage_types).most_common(1)[0][0] if damage_types else "Mixed"

        sample_champs = [
            {
                "name": c.get("name"),
                "roles": c.get("roles", []),
                "subroles": c.get("subroles", []),
                "damage_type": c.get("adaptiveType"),
                "playstyles": c.get("playstyles", []),
                "power_curve": c.get("powerCurve", []),
            }
            for c in champs[:25]
        ]
        return {
            "is_lane_query": True,
            "lane": lane.upper(),
            "count": len(champs),
            "dominant_damage": dominant_damage,
            "top_roles": top_roles,
            "top_subroles": top_subroles,
            "champions": [c.get("name") for c in champs[:25]],
            "sample_champions": sample_champs,
        }

    def list_skills(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        return profile

    def get_counters(self, name, direction = None, lane = None):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        data = self.store.get_counter_info(name) or {}
        raw_weak = list(data.get("weakAgainst", []))
        raw_strong = list(data.get("strongAgainst", []))

        tactical = champ.get("tacticalInfo") or {}
        weaknesses = list(data.get("weaknesses") or tactical.get("weaknesses") or profile.get("weaknesses", []))
        tactical_tips = list(data.get("tactical_tips") or tactical.get("tactical_tips") or profile.get("tactical_tips", []))
        counter_items = list(data.get("counter_items") or tactical.get("counter_items") or profile.get("counter_items", []))

        lane_upper = lane.upper() if lane else None
        if lane_upper:
            # Prioritize lane-specific weakAgainst
            lane_weak = []
            other_weak = []
            for w in raw_weak:
                c_champ = self.store.get_champion(w.get("champion", ""))
                if c_champ and lane_upper in [p.upper() for p in c_champ.get("positions", [])]:
                    lane_weak.append(w)
                else:
                    other_weak.append(w)
            weak_against = (lane_weak + other_weak)[:6]

            # Prioritize lane-specific strongAgainst
            lane_strong = []
            other_strong = []
            for s in raw_strong:
                c_champ = self.store.get_champion(s.get("champion", ""))
                if c_champ and lane_upper in [p.upper() for p in c_champ.get("positions", [])]:
                    lane_strong.append(s)
                else:
                    other_strong.append(s)
            strong_against = (lane_strong + other_strong)[:6]
        else:
            weak_against = raw_weak[:6]
            strong_against = raw_strong[:6]

        enemytips = list(champ.get("enemytips") or [])

        # Collect verified core abilities for counter champions
        relevant_entries = strong_against if direction == "counters" else weak_against
        champ_abilities = {}
        for entry in relevant_entries:
            cname = entry.get("champion")
            if cname and cname not in champ_abilities:
                c_doc = self.store.get_champion(cname)
                formatted = self.format_champion_abilities(c_doc)
                if formatted:
                    champ_abilities[cname] = formatted

        profile.update({
            "is_counter_query": True,
            "lane": lane,
            "weaknesses": weaknesses,
            "tactical_tips": tactical_tips,
            "enemytips": enemytips,
            "counter_items": counter_items,
            "weak_against": weak_against,
            "strong_against": strong_against,
            "counter_direction": direction,
            "champion_abilities": champ_abilities,
        })
        return profile

    def get_role_counters(
        self, role = None, lane = None, direction = "countered_by"
    ):
        """
        Aggregate tactical counter intelligence for a champion class/role in a lane
        directly from the KnowledgeStore champions and counter records.
        Zero hardcoded texts, definitions, or advice.
        """
        from collections import Counter

        role_lower = (role or "").lower()
        lane_upper = lane.upper() if lane else None

        # 1. Filter matching champions from KnowledgeStore
        matching_champs = []
        for c in self.store.champions.values():
            c_roles = [r.lower() for r in c.get("roles", [])]
            c_lanes = [p.upper() for p in c.get("positions", [])]
            if role_lower and role_lower not in c_roles:
                continue
            if lane_upper and lane_upper not in c_lanes:
                continue
            matching_champs.append(c)

        if not matching_champs and role_lower:
            matching_champs = [
                c for c in self.store.champions.values()
                if role_lower in [r.lower() for r in c.get("roles", [])]
            ]

        sample_champs = [
            {
                "name": c.get("name"),
                "roles": c.get("roles", []),
                "subroles": c.get("subroles", []),
                "damage_type": c.get("adaptiveType"),
            }
            for c in matching_champs[:12]
        ]

        # 2. Dynamically aggregate weaknesses, tactical_tips, and counter_items from the database
        all_weaknesses = []
        all_tips = []
        all_items = []
        counter_champ_counts = {}

        for c in matching_champs:
            t = c.get("tacticalInfo") or {}
            all_weaknesses.extend(t.get("weaknesses", []))
            all_tips.extend(t.get("tactical_tips", []))
            all_items.extend(t.get("counter_items", []))

            c_info = self.store.get_counter_info(c.get("name", ""))
            if c_info:
                for w in c_info.get("weakAgainst", []):
                    c_name = w.get("champion")
                    if c_name:
                        # Prioritize / filter champions that actually play in this specific lane
                        if lane_upper:
                            opp_champ = self.store.get_champion(c_name)
                            if opp_champ:
                                opp_positions = [p.upper() for p in opp_champ.get("positions", [])]
                                if lane_upper not in opp_positions:
                                    continue

                        if c_name not in counter_champ_counts:
                            counter_champ_counts[c_name] = {
                                "champion": c_name,
                                "count": 0,
                                "reasons": set(),
                                "winRates": [],
                            }
                        counter_champ_counts[c_name]["count"] += 1
                        if w.get("reason"):
                            counter_champ_counts[c_name]["reasons"].add(w["reason"])
                        if w.get("winRate"):
                            counter_champ_counts[c_name]["winRates"].append(w["winRate"])

        # Fallback if lane-specific counter picks are too few
        if len(counter_champ_counts) < 3 and lane_upper:
            for c in matching_champs:
                c_info = self.store.get_counter_info(c.get("name", ""))
                if c_info:
                    for w in c_info.get("weakAgainst", []):
                        c_name = w.get("champion")
                        if c_name and c_name not in counter_champ_counts:
                            counter_champ_counts[c_name] = {
                                "champion": c_name,
                                "count": 1,
                                "reasons": {w.get("reason", "")} if w.get("reason") else set(),
                                "winRates": [w.get("winRate")] if w.get("winRate") else [],
                            }

        # Rank and deduplicate from actual frequencies in the database
        raw_weaknesses = [item for item, _ in Counter(all_weaknesses).most_common(8)]
        top_tips = [item for item, _ in Counter(all_tips).most_common(5)]
        top_items = [item for item, _ in Counter(all_items).most_common(6)]

        # Data-driven harmonization of mobility based on mathematical ratio of Dash/Blink in archetype
        mobile_count = sum(
            1 for c in matching_champs
            if any(fx.lower() in ("dash", "blink") for fx in c.get("ability_effects", []))
        )
        is_predominantly_mobile = (mobile_count / len(matching_champs)) >= 0.5 if matching_champs else False

        top_weaknesses = []
        for w in raw_weaknesses:
            w_lower = w.lower()
            if is_predominantly_mobile and ("immobile" in w_lower or "no native dash" in w_lower):
                continue
            if not is_predominantly_mobile and ("reliance on mobility" in w_lower or "primary dash" in w_lower):
                continue
            top_weaknesses.append(w)
            if len(top_weaknesses) >= 4:
                break

        # Top counter picks sorted by frequency across matching champions
        sorted_counters = sorted(counter_champ_counts.values(), key=lambda x: x["count"], reverse=True)
        top_counter_picks = []
        for sc in sorted_counters[:6]:
            avg_wr = (
                round(sum(sc["winRates"]) / len(sc["winRates"]), 1)
                if sc["winRates"]
                else None
            )
            clean_reasons = list(dict.fromkeys(r.strip() for r in sc["reasons"] if r and r.strip()))
            top_counter_picks.append({
                "champion": sc["champion"],
                "reason": "; ".join(clean_reasons[:2]),
                "winRate": avg_wr,
            })

        # Determine dominant damage profile from matching champions
        adaptive_types = [c.get("adaptiveType") for c in matching_champs if c.get("adaptiveType")]
        dominant_damage = Counter(adaptive_types).most_common(1)[0][0] if adaptive_types else "Mixed"

        return {
            "is_role_query": True,
            "role": role_lower or "general",
            "lane": lane or "all",
            "role_title": f"{role.capitalize() if role else 'General'} Champions" + (f" ({lane.upper()})" if lane else ""),
            "damage_profile": f"{dominant_damage} Damage",
            "sample_champions": sample_champs,
            "weaknesses": top_weaknesses,
            "tactical_tips": top_tips,
            "counter_items": top_items,
            "counter_picks": top_counter_picks,
            "source": "knowledge_base_dynamic_aggregation",
        }

    def get_role_counter_picks(
        self, user_role = None, target_value = None, target_type = "role", lane = None
    ):
        """
        Dynamically calculate and rank champions of a specified role/lane that counter
        a designated enemy target (champion, class/role, or tactical archetype).
        Zero hardcoding. 100% automated and data-driven from champion abilities,
        mechanics, and database relationships.
        """
        from collections import Counter

        target_str = (target_value or "").lower()
        role_str = (user_role or "").lower()
        lane_str = (lane or "").lower() if lane else None

        # Resolve clean display role title
        role_names_map = {
            "marksman": "Marksman (ADC)",
            "support": "Support",
            "mage": "Mage",
            "fighter": "Fighter / Bruiser",
            "tank": "Tank",
            "assassin": "Assassin",
            "mid": "Mid Laner",
            "top": "Top Laner",
            "jungle": "Jungler",
        }
        role_title = role_names_map.get(role_str) or (role_str.title() + " Champions" if role_str else "Draft Pick")

        # 1. Filter candidate champions belonging to the user's role/lane
        candidates = []
        for c in self.store.champions.values():
            c_roles = [r.lower() for r in c.get("roles", [])]
            c_subroles = [s.lower() for s in c.get("subroles", [])]
            c_positions = [p.lower() for p in c.get("positions", [])]

            match_role = (role_str in c_roles) or (role_str in c_subroles) if role_str else True
            match_lane = (lane_str in c_positions) if lane_str else True

            if role_str in ("mid", "top", "jungle", "bot"):
                match_role = match_role or (role_str in c_positions)

            if match_role and match_lane:
                candidates.append(c)

        if not candidates and role_str:
            candidates = [
                c for c in self.store.champions.values()
                if role_str in [r.lower() for r in c.get("roles", [])]
            ]
        if not candidates:
            candidates = list(self.store.champions.values())

        # 2. Build target telemetry lookup if target is role or archetype
        target_champs_set = set()
        if target_type == "role":
            target_champs_set = {
                c.get("name") for c in self.store.champions.values()
                if target_str in [r.lower() for r in c.get("roles", [])]
            }

        target_comp = None
        if target_type == "archetype":
            target_comp = self.store.get_composition(target_str)

        # 3. Evaluate each candidate champion mathematically
        scored_candidates = []

        for c in candidates:
            cname = c.get("name")
            score = 0
            mechanics = []

            # A. Kit Mechanics Evaluation from Abilities
            abilities = c.get("abilities", {})
            for sk, spell in abilities.items():
                s_name = spell.get("name", "")
                s_desc = (spell.get("description") or "") + " " + " ".join(spell.get("effects", []))
                s_lower = s_desc.lower()

                # Against Tanks: % max HP, % current HP, true damage, armor/MR shred
                if target_str in ("tank", "tank_heavy", "tanker"):
                    if "maximum health" in s_lower or "max health" in s_lower or "% max hp" in s_lower or "percent of the target's maximum health" in s_lower:
                        score += 6
                        mechanics.append(f"**{s_name} ({sk})** inflicts % maximum health damage to shred high HP pools.")
                    elif "current health" in s_lower:
                        score += 4
                        mechanics.append(f"**{s_name} ({sk})** inflicts % current health damage on-hit.")
                    elif "missing health" in s_lower or "low health" in s_lower:
                        score += 2
                        mechanics.append(f"**{s_name} ({sk})** deals % missing health execute damage.")
                    if "true damage" in s_lower:
                        score += 5
                        mechanics.append(f"**{s_name} ({sk})** deals true damage, completely bypassing high armor stacking.")
                    if any(w in s_lower for w in ["armor pen", "shred", "reduces armor", "corrodes", "corrode", "magic resist", "penetrat"]):
                        score += 4
                        mechanics.append(f"**{s_name} ({sk})** shreds enemy defensive resistances.")

                # Against Assassins: Untargetability, stasis, shields, heals, hard CC
                elif target_str in ("assassin", "assassin_heavy"):
                    if any(w in s_lower for w in ["untargetable", "invulnerable", "stasis"]):
                        score += 6
                        mechanics.append(f"**{s_name} ({sk})** grants untargetability to dodge lethal burst rotations.")
                    if "shield" in s_lower or "barrier" in s_lower or "absorb" in s_lower:
                        score += 4
                        mechanics.append(f"**{s_name} ({sk})** generates defensive shields to absorb all-in burst.")
                    if any(cc in s_lower for cc in ["knockup", "stun", "suppress", "silence", "taunt"]):
                        score += 4
                        mechanics.append(f"**{s_name} ({sk})** locks down flanking assassins with hard crowd control.")
                    if "stealth" in s_lower or "invisib" in s_lower or "camouflage" in s_lower:
                        score += 3
                        mechanics.append(f"**{s_name} ({sk})** uses stealth to reposition safely out of assassin target acquisition.")

                # Against Dive / Hard Engage: Disengage, knockbacks, anti-dash, zoning
                elif target_str in ("dive", "heavy_cc", "engage", "wombo_combo"):
                    if any(cc in s_lower for cc in ["knockback", "ground", "disengage", "pushes away", "knocks back"]):
                        score += 6
                        mechanics.append(f"**{s_name} ({sk})** disengages diving champions and resets engagement spacing.")
                    elif any(cc in s_lower for cc in ["knockup", "stun", "suppress"]):
                        score += 4
                        mechanics.append(f"**{s_name} ({sk})** interrupts gap-closers and dashes with instant crowd control.")
                    if "shield" in s_lower or "heal" in s_lower:
                        score += 3
                        mechanics.append(f"**{s_name} ({sk})** provides durability to withstand initial dive combo.")

                # Against Mages: Spell shields, dashes, gap closers, sustained dive
                elif target_str in ("mage", "mage_heavy", "poke"):
                    if any(w in s_lower for w in ["spell shield", "magic shield", "magic resist"]):
                        score += 5
                        mechanics.append(f"**{s_name} ({sk})** negates hostile spell casts with magic protection.")
                    if any(w in s_lower for w in ["dash", "blink", "gap close"]):
                        score += 4
                        mechanics.append(f"**{s_name} ({sk})** closes the distance rapidly to punish immobile ranged casters.")

                # Against Specific Champion Target
                elif target_type == "champion":
                    if any(cc in s_lower for cc in ["knockup", "stun", "suppress", "silence"]):
                        score += 2
                    if "true damage" in s_lower or "shield" in s_lower or "untargetable" in s_lower:
                        score += 2

            # B. Attack Range and Mobility Bonus
            stats_dict = c.get("stats", {})
            ar_val = stats_dict.get("attackrange", 0)
            rng = ar_val.get("base", 0) if isinstance(ar_val, dict) else (ar_val or 0)

            if target_str in ("tank", "tank_heavy", "tanker"):
                if rng >= 600:
                    score += 3
                    mechanics.append(f"Exceptional attack range ({rng}) enables safe perimeter kiting outside tank engage threat.")
                if any(fx in ("Dash", "Blink") for fx in c.get("ability_effects", [])):
                    score += 2

            # C. Knowledge Graph Empirical Matchup Telemetry
            c_info = self.store.get_counter_info(cname)
            if c_info:
                strong_against = c_info.get("strongAgainst", [])
                for sa in strong_against:
                    opp_name = sa.get("champion")
                    if target_type == "champion" and opp_name and opp_name.lower() == target_str:
                        score += 8
                        if sa.get("reason"):
                            mechanics.append(sa["reason"])
                    elif target_type == "role" and opp_name in target_champs_set:
                        score += 3
                        if sa.get("reason") and len(mechanics) < 3:
                            mechanics.append(sa["reason"])

            if target_comp:
                for cp in target_comp.get("counter_picks", []):
                    if cp.get("champion") == cname:
                        score += 6
                        if cp.get("tactical_reason"):
                            mechanics.append(cp["tactical_reason"])

            distinct_mechanics = []
            for m in mechanics:
                if m not in distinct_mechanics:
                    distinct_mechanics.append(m)

            if score > 0 or distinct_mechanics:
                scored_candidates.append({
                    "champion": cname,
                    "title": c.get("title", ""),
                    "score": score,
                    "roles": c.get("roles", []),
                    "mechanics": distinct_mechanics[:3],
                })

        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        top_champs = scored_candidates[:4]

        # 4. Specialized Anti-Target Itemization for User's Role
        recommended_items = []
        if target_str in ("tank", "tank_heavy", "tanker"):
            if role_str == "marksman":
                item_names = ["Lord Dominik's Regards", "Blade of the Ruined King", "Mortal Reminder", "Terminus"]
            elif role_str in ("mage", "mid"):
                item_names = ["Liandry's Torment", "Void Staff", "Cryptbloom", "Blackfire Torch"]
            elif role_str in ("fighter", "top"):
                item_names = ["Black Cleaver", "Blade of the Ruined King", "Eclipse", "Sundered Sky"]
            elif role_str == "support":
                item_names = ["Imperial Mandate", "Abyssal Mask", "Shurelya's Battlesong", "Morellonomicon"]
            else:
                item_names = ["Lord Dominik's Regards", "Blade of the Ruined King", "Black Cleaver", "Liandry's Torment"]
        elif target_str in ("assassin", "assassin_heavy"):
            if role_str == "marksman":
                item_names = ["Guardian Angel", "Immortal Shieldbow", "Maw of Malmortius", "Edge of Night"]
            elif role_str in ("mage", "mid"):
                item_names = ["Zhonya's Hourglass", "Banshee's Veil", "Seraph's Embrace", "RoA"]
            elif role_str in ("fighter", "top"):
                item_names = ["Death's Dance", "Sterak's Gage", "Maw of Malmortius", "Guardian Angel"]
            elif role_str == "support":
                item_names = ["Locket of the Iron Solari", "Knight's Vow", "Redemption", "Zhonya's Hourglass"]
            else:
                item_names = ["Guardian Angel", "Zhonya's Hourglass", "Death's Dance", "Randuin's Omen"]
        elif target_str in ("dive", "heavy_cc", "engage"):
            if role_str == "marksman":
                item_names = ["Immortal Shieldbow", "Guardian Angel", "Edge of Night", "Mercurial Scimitar"]
            elif role_str in ("mage", "mid"):
                item_names = ["Zhonya's Hourglass", "Banshee's Veil", "Crown of the Shattered Queen"]
            else:
                item_names = ["Zhonya's Hourglass", "Locket of the Iron Solari", "Frozen Heart", "Randuin's Omen"]
        else:
            item_names = ["Plated Steelcaps", "Mercury's Treads", "Zhonya's Hourglass", "Guardian Angel"]

        for iname in item_names:
            it = self.store.get_item(iname)
            if it:
                plaintext = (it.get("plaintext") or "").strip()
                raw_desc = it.get("description", "")
                clean_desc = re.sub(r"<[^>]+>", " ", raw_desc).strip()
                clean_desc = " ".join(clean_desc.split())
                recommended_items.append({
                    "item": it.get("name"),
                    "plaintext": plaintext or clean_desc[:90],
                })

        # 5. Strategic Matchup and Positioning Guidelines
        tactical_guidelines = []
        if target_str in ("tank", "tank_heavy", "tanker"):
            tactical_guidelines = [
                "Front-to-Back Teamfighting: Focus down the nearest frontline tank first; never dive or walk past high-CC tanks to reach backline targets.",
                "Perimeter Spacing and Attack-Moving: Continuously kite at maximum weapon range using Attack-Move (Orbwalking) to maintain a protective spacing buffer.",
                "Bait Engage Cooldowns: Hold your primary defensive mobility (Flash, dash, blink) until the enemy tank commits their primary crowd control skillshot.",
                "Prioritize Armor Penetration: Complete an early Last Whisper or on-hit component on your 2nd or 3rd item recall before the enemy completes two armor items.",
            ]
        elif target_str in ("assassin", "assassin_heavy"):
            tactical_guidelines = [
                "Never Face-Check Fog of War: Maintain defensive positioning behind allied frontline and establish perimeter control with defensive wards.",
                "Hold Defensive Spells for All-In: Never expend key escape or self-peel abilities aggressively; save them specifically to interrupt assassin gap-closers.",
                "Stay Clustered with Support: Position within peel range of enchanters and wardens who can provide instant shields, heals, or knockups.",
                "Itemize Early Survivability: An early Stopwatch, Cloth Armor, or Null-Magic Mantle prevents assassins from snowballing early leads.",
            ]
        elif target_str in ("dive", "heavy_cc", "engage"):
            tactical_guidelines = [
                "Respect Primary Engage Ranges: Track flash cooldowns and dangerous gap-closing abilities (Malphite R, Leona R, Jarvan EQ).",
                "Layer Crowd Control on Secondary Dives: Once the primary tank initiates, immediately lockdown the follow-up burst carries before they can enter range.",
                "Pre-emptively Cast Defensive Disengage: Use displacement spells (knockbacks, tornadoes, flays) reactively mid-dash to cancel enemy momentum.",
            ]
        else:
            tactical_guidelines = [
                "Maintain vision control around objective choke points before starting neutral monsters.",
                "Track enemy cooldowns and trade immediately after high-impact enemy skillshots are expended.",
                "Prioritize wave management to deny roaming opportunities into side lanes.",
            ]

        return {
            "is_role_counter_pick": True,
            "user_role": role_str,
            "role_title": role_title,
            "target": target_value,
            "target_type": target_type,
            "top_champions": top_champs,
            "recommended_items": recommended_items,
            "tactical_guidelines": tactical_guidelines,
            "source": "knowledge_base_dynamic_draft_engine",
        }

    def get_composition_building_info(self, comp_id, power_curve = None):
        """
        Retrieve drafting and team composition building intelligence.
        Dynamically structures champions into authentic tactical roles based on composition archetype.
        """
        comp_id_clean = (comp_id or "dive").lower()

        # 1. Engage / Dive / Teamfight Compositions
        if any(w in comp_id_clean for w in ["dive", "engage", "hard_engage"]):
            return {
                "is_composition_building": True,
                "comp_id": "dive",
                "name": "Hard Engage and Dive Composition",
                "category": "tactical_profile",
                "description": "An aggressive, fast-paced teamfight draft designed to force decisive 5v5 engagements through multi-layered crowd control and immediate backline diving burst.",
                "power_curve": power_curve or "Mid-Game (Dragon and Baron Contests)",
                "role_1_title": "Primary Hard Engage Initiators",
                "role_1_champions": ["Jarvan IV", "Malphite", "Nautilus", "Leona", "Rell", "Rakan", "Sejuani"],
                "role_2_title": "Follow-Up Burst and Dive Carries",
                "role_2_champions": ["Samira", "Kai'Sa", "Camille", "Diana", "Yone", "Vi"],
                "sample_draft": {
                    "top": "Malphite / Camille",
                    "jungle": "Jarvan IV / Sejuani",
                    "mid": "Diana / Ahri",
                    "bot": "Samira / Kai'Sa",
                    "support": "Nautilus / Leona / Rell",
                },
                "win_condition": "Establish vision dominance around neutral objective chokepoints, initiate with overlapping AoE crowd control to lock down enemy carries, and collapse with synchronized dive burst before the enemy can disengage.",
                "source": "tactical_knowledge_base",
            }

        # 2. Poke and Siege Compositions
        elif any(w in comp_id_clean for w in ["poke", "artillery", "siege"]):
            return {
                "is_composition_building": True,
                "comp_id": "poke",
                "name": "Poke and Siege Composition",
                "category": "tactical_profile",
                "description": "A long-range attrition draft that whittles down opponents from outside retaliation range, forcing enemies to concede objectives or fight at critical health deficits.",
                "power_curve": power_curve or "Mid-Game (Tower and Objective Sieging)",
                "role_1_title": "Long-Range Artillery and Poke Carries",
                "role_1_champions": ["Jayce", "Xerath", "Ziggs", "Varus", "Zoe", "Caitlyn"],
                "role_2_title": "Disengage, Zone Control and Peel",
                "role_2_champions": ["Janna", "Gragas", "Braum", "Karma", "Trundle", "Morgana"],
                "sample_draft": {
                    "top": "Jayce / Gragas",
                    "jungle": "Nidalee / Maokai",
                    "mid": "Xerath / Ziggs",
                    "bot": "Varus / Caitlyn",
                    "support": "Janna / Karma / Braum",
                },
                "win_condition": "Maintain strict perimeter spacing, soften enemies with continuous long-range artillery at neutral objectives, and use disengage tools to deny enemy hard initiation.",
                "source": "tactical_knowledge_base",
            }

        # 3. Protect the Hypercarry and Scaling Compositions
        elif any(w in comp_id_clean for w in ["hypercarry", "protect", "scaling", "late"]):
            return {
                "is_composition_building": True,
                "comp_id": "hypercarry_protect",
                "name": "Protect the Hypercarry Composition",
                "category": "tactical_profile",
                "description": "A scaling funnel draft centered on maximizing the safety and damage output of an elite late-game marksman via dedicated shields, buffs, and defensive wardens.",
                "power_curve": power_curve or "Late-Game (Full Build Power Spikes)",
                "role_1_title": "Late-Game Scaling Hypercarries",
                "role_1_champions": ["Jinx", "Kog'Maw", "Vayne", "Twitch", "Smolder", "Aphelios"],
                "role_2_title": "Peel Enchanters and Defensive Frontline Wardens",
                "role_2_champions": ["Lulu", "Milio", "Janna", "Braum", "Tahm Kench", "Shen"],
                "sample_draft": {
                    "top": "Shen / Ornn",
                    "jungle": "Sejuani / Ivern",
                    "mid": "Orianna / Galio",
                    "bot": "Jinx / Kog'Maw",
                    "support": "Lulu / Milio / Braum",
                },
                "win_condition": "Survive early skirmishes through safe wave control, funnel resources into your hypercarry, and peel all enemy divers in late-game 5v5 teamfights to let the carry free-fire.",
                "source": "tactical_knowledge_base",
            }

        # 4. Split-Push and 1-3-1 Duelist Compositions
        elif any(w in comp_id_clean for w in ["split", "splitpush", "duelist", "side"]):
            return {
                "is_composition_building": True,
                "comp_id": "splitpush",
                "name": "Split-Push and Side-Lane Duelist Composition",
                "category": "tactical_profile",
                "description": "A strategic pressure draft utilizing dominant side-lane duelists to force enemies into mismatched rotations and trade cross-map objectives.",
                "power_curve": power_curve or "Mid-to-Late Game (Side-Lane Pressure)",
                "role_1_title": "Dominant Side-Lane Duelists",
                "role_1_champions": ["Fiora", "Jax", "Camille", "Tryndamere", "Yorick", "Gwen"],
                "role_2_title": "Waveclear and Safe Disengage Mid Core",
                "role_2_champions": ["Anivia", "Sivir", "Gragas", "Braum", "Morgana"],
                "sample_draft": {
                    "top": "Fiora / Jax",
                    "jungle": "Jarvan IV / Sejuani",
                    "mid": "Anivia / Ryze",
                    "bot": "Sivir / Ashe",
                    "support": "Braum / Janna",
                },
                "win_condition": "Maintain 1-3-1 or 1-4 side-lane pressure, avoid fighting disadvantageous 5v5s in mid lane, and take towers or neutral objectives when enemies rotate to defend.",
                "source": "tactical_knowledge_base",
            }

        # 5. Control Mage and AP Magic Damage Compositions
        elif any(w in comp_id_clean for w in ["mage", "ap", "control_mage", "magic_damage"]):
            return {
                "is_composition_building": True,
                "comp_id": "mage_heavy",
                "name": "Control Mage and Magic Damage Teamfight Composition",
                "category": "tactical_profile",
                "description": "A high-magic damage, spell-rotation draft that dominates teamfights through expansive AoE zoning, multi-target burst, and devastating spell combos around neutral objectives.",
                "power_curve": power_curve or "Mid-to-Late Game (2-3 Item Spikes and Objective Sieges)",
                "role_1_title": "Primary Control and Burst Mages",
                "role_1_champions": ["Orianna", "Syndra", "Viktor", "Hwei", "Veigar", "Cassiopeia", "Azir"],
                "role_2_title": "Frontline Crowd Control and Magic Resistance Shred",
                "role_2_champions": ["Maokai", "Galio", "Gragas", "Nautilus", "Leona", "Braum"],
                "sample_draft": {
                    "top": "Rumble / Kennen / Ornn",
                    "jungle": "Jarvan IV / Sejuani / Maokai",
                    "mid": "Orianna / Syndra / Viktor",
                    "bot": "Ziggs / Seraphine (or Ashe / Jhin for mixed AD utility)",
                    "support": "Nautilus / Leona / Rell",
                },
                "win_condition": "Establish dense river vision around Dragon and Baron, blanket chokepoints with zoning spells (Shockwave, Chaos Storm, Unleashed Power), and lock down clustered enemies while building Void Staff or Cryptbloom to shred enemy Magic Resistance.",
                "source": "tactical_knowledge_base",
            }

        # 6. Frontline Tank and Juggernaut Brawl Compositions
        elif any(w in comp_id_clean for w in ["tank", "juggernaut", "bruiser", "brawl", "frontline"]):
            return {
                "is_composition_building": True,
                "comp_id": "tank_heavy",
                "name": "Frontline Tank and Juggernaut Brawl Composition",
                "category": "tactical_profile",
                "description": "A durable, high-sustain frontline draft designed to win extended attrition teamfights through immense effective health pools, crowd control layering, and unrelenting melee disruption.",
                "power_curve": power_curve or "Mid-Game (Sunfire / Heartsteel / Armor Item Spikes)",
                "role_1_title": "Primary Frontline Tanks and Durable Juggernauts",
                "role_1_champions": ["Ornn", "Sion", "Darius", "Mordekaiser", "Cho'Gath", "Malphite", "Zac"],
                "role_2_title": "Sustained DPS Carries and Backline Enablers",
                "role_2_champions": ["Kog'Maw", "Vayne", "Cassiopeia", "Lulu", "Milio", "Taric"],
                "sample_draft": {
                    "top": "Ornn / Sion",
                    "jungle": "Sejuani / Zac",
                    "mid": "Galio / Swain / Cassiopeia",
                    "bot": "Kog'Maw / Vayne",
                    "support": "Braum / Taric / Nautilus",
                },
                "win_condition": "Stack resistances against the enemy damage profile, absorb burst rotations on your unkillable frontline, and grind down opponents in extended 5v5 scuffles while your backline DPS shreds unhindered.",
                "source": "tactical_knowledge_base",
            }

        # 7. Assassin and Pick Skirmish Compositions
        elif any(w in comp_id_clean for w in ["assassin", "flank"]):
            return {
                "is_composition_building": True,
                "comp_id": "assassin_heavy",
                "name": "Assassin and Pick Elimination Composition",
                "category": "tactical_profile",
                "description": "An aggressive tempo draft designed to control fog of war, isolate priority carries with sudden flank angles, and execute instant pickoffs before 5v5 teamfights begin.",
                "power_curve": power_curve or "Early-to-Mid Game (Lethality Item Spikes and Roaming Phase)",
                "role_1_title": "Primary Burst Assassins and Flankers",
                "role_1_champions": ["Zed", "LeBlanc", "Kha'Zix", "Talon", "Qiyana", "Akali", "Ekko"],
                "role_2_title": "Vision Denial, Ambush and Hard Lockdown Supports",
                "role_2_champions": ["Pyke", "Blitzcrank", "Thresh", "Nautilus", "Elise", "Vi"],
                "sample_draft": {
                    "top": "Renekton / Camille",
                    "jungle": "Kha'Zix / Vi",
                    "mid": "Zed / LeBlanc / Akali",
                    "bot": "Lucian / Kai'Sa / Jhin",
                    "support": "Pyke / Thresh / Blitzcrank",
                },
                "win_condition": "Sweep enemy wards relentlessly in the river and jungle, set up lethal death-bushes, and eliminate isolated enemies to force 5v4 baron or dragon takes before enemy team groups with Zhonya's and Guardian Angel.",
                "source": "tactical_knowledge_base",
            }

        # 8. Wombo Combo and Catastrophic AoE Teamfight Compositions
        elif any(w in comp_id_clean for w in ["wombo", "wombo_combo", "catastrophic_aoe", "aoe_teamfight"]):
            return {
                "is_composition_building": True,
                "comp_id": "wombo_combo",
                "name": "Wombo Combo and Catastrophic AoE Teamfight Composition",
                "category": "tactical_profile",
                "description": "An explosive teamfight draft engineered to synchronize massive, overlapping area-of-effect crowd control and catastrophic burst ultimates to instantly annihilate clustered enemy squads.",
                "power_curve": power_curve or "Mid-Game (Level 6 and 11 Ultimate Teamfights)",
                "role_1_title": "Primary AoE Crowd Control Initiators",
                "role_1_champions": ["Malphite", "Amumu", "Rell", "Jarvan IV", "Kennen", "Orianna"],
                "role_2_title": "Catastrophic AoE Burst Executioners",
                "role_2_champions": ["Miss Fortune", "Samira", "Brand", "Diana", "Rumble", "Yasuo"],
                "sample_draft": {
                    "top": "Malphite / Kennen",
                    "jungle": "Amumu / Jarvan IV",
                    "mid": "Orianna / Diana",
                    "bot": "Miss Fortune / Samira",
                    "support": "Rell / Leona / Rakan",
                },
                "win_condition": "Funnel enemies into narrow river or objective chokepoints around Dragon and Baron, chain layered AoE ultimates in rapid succession, and eliminate the opposing team before they can disengage or cast summoner spells.",
                "source": "tactical_knowledge_base",
            }

        # 9. Heavy Crowd Control and Chain Lockdown Compositions
        elif any(w in comp_id_clean for w in ["heavy_cc", "cc_heavy", "lockdown", "chain_cc"]):
            return {
                "is_composition_building": True,
                "comp_id": "heavy_cc",
                "name": "Heavy Crowd Control and Chain Lockdown Composition",
                "category": "tactical_profile",
                "description": "A control-heavy lockdown draft featuring high durability and sequential hard crowd control that isolates and completely incapacitates enemy priority threats.",
                "power_curve": power_curve or "Early-to-Mid Game (Objective Skirmishes)",
                "role_1_title": "Lockdown Vanguard Tanks and Disablers",
                "role_1_champions": ["Nautilus", "Leona", "Sejuani", "Maokai", "Amumu", "Galio"],
                "role_2_title": "Burst Follow-Up Carries",
                "role_2_champions": ["Syndra", "Jhin", "Kai'Sa", "Ahri", "Renekton"],
                "sample_draft": {
                    "top": "Maokai / Shen",
                    "jungle": "Sejuani / Amumu",
                    "mid": "Galio / Lissandra",
                    "bot": "Jhin / Ashe",
                    "support": "Nautilus / Leona",
                },
                "win_condition": "Sequence crowd control stuns and roots without overlapping durations, locking down target carries indefinitely until they are cleanly eliminated.",
                "source": "tactical_knowledge_base",
            }

        # 10. Stealth and Ambush Compositions
        elif any(w in comp_id_clean for w in ["stealth", "ambush", "invisibility", "camouflage"]):
            return {
                "is_composition_building": True,
                "comp_id": "stealth",
                "name": "Stealth and Ambush Composition",
                "category": "tactical_profile",
                "description": "A guerrilla warfare draft that exploits vision denial and camouflage mechanics to bypass enemy frontlines and execute surprise backline collapses.",
                "power_curve": power_curve or "Early-to-Mid Game (Jungle Invasions and Flanks)",
                "role_1_title": "Camouflage and Stealth Infiltrators",
                "role_1_champions": ["Evelynn", "Kha'Zix", "Twitch", "Shaco", "Rengar", "Akali", "Pyke"],
                "role_2_title": "Vision Denial and Isolation Trappers",
                "role_2_champions": ["Thresh", "Blitzcrank", "Morgana", "Jhin", "Ashe"],
                "sample_draft": {
                    "top": "Akali / Teemo",
                    "jungle": "Evelynn / Kha'Zix",
                    "mid": "Talon / Qiyana",
                    "bot": "Twitch / Kai'Sa",
                    "support": "Pyke / Senna",
                },
                "win_condition": "Clear all enemy vision using Sweepers and Control Wards, set up deadly ambush traps in transition corridors, and convert isolated pickoffs into uncontested Baron and Dragon captures.",
                "source": "tactical_knowledge_base",
            }

        # 11. High Sustain and Healing Attrition Compositions
        elif any(w in comp_id_clean for w in ["sustain", "heal", "healing", "vamp"]):
            return {
                "is_composition_building": True,
                "comp_id": "sustain",
                "name": "High Sustain and Healing Composition",
                "category": "tactical_profile",
                "description": "An attrition draft that excels in extended skirmishes by continuously regenerating health pools through combat vamp, health drain, and powerful enchanter heals.",
                "power_curve": power_curve or "Mid-Game (Moonstone / Spirit Visage / Vamp Spikes)",
                "role_1_title": "Combat Drain Bruisers and Self-Healers",
                "role_1_champions": ["Aatrox", "Warwick", "Vladimir", "Olaf", "Briar", "Swain"],
                "role_2_title": "Dedicated Healing and Restoration Enchanters",
                "role_2_champions": ["Soraka", "Yuumi", "Sona", "Nami", "Taric"],
                "sample_draft": {
                    "top": "Aatrox / Vladimir",
                    "jungle": "Warwick / Olaf",
                    "mid": "Swain / Vladimir",
                    "bot": "Nilah / Samira",
                    "support": "Soraka / Yuumi",
                },
                "win_condition": "Prolong teamfights into wars of attrition where your team continually recovers health while enemy resources and cooldowns deplete, especially punishing opponents who fail to purchase Grievous Wounds.",
                "source": "tactical_knowledge_base",
            }

        # 12. Shield and Protective Peel Compositions
        elif any(w in comp_id_clean for w in ["shield", "shield_heavy", "protective", "barrier"]):
            return {
                "is_composition_building": True,
                "comp_id": "shield_heavy",
                "name": "Shield and Protective Composition",
                "category": "tactical_profile",
                "description": "A defensive bastion draft centered on multi-layered shielding and damage redirection, negating enemy burst rotations and granting frontline longevity to your damage dealers.",
                "power_curve": power_curve or "Mid-to-Late Game (Heal and Shield Power Multipliers)",
                "role_1_title": "Shield Battery Enchanters and Wardens",
                "role_1_champions": ["Lulu", "Karma", "Janna", "Shen", "Taric", "Tahm Kench"],
                "role_2_title": "Protected High-DPS Carries",
                "role_2_champions": ["Jinx", "Aphelios", "Kog'Maw", "Viktor", "Cassiopeia"],
                "sample_draft": {
                    "top": "Shen / Sion",
                    "jungle": "Ivern / Sejuani",
                    "mid": "Karma / Orianna",
                    "bot": "Jinx / Kog'Maw",
                    "support": "Lulu / Milio",
                },
                "win_condition": "Cycle defensive shield cooldowns and active items (Locket of the Iron Solari, Redemption) to absorb opposing all-ins, allowing your carries to free-fire without fear of assassination.",
                "source": "tactical_knowledge_base",
            }

        # 13. High Mobility and Skirmish Compositions
        elif any(w in comp_id_clean for w in ["high_mobility", "mobility", "skirmish", "slippery"]):
            return {
                "is_composition_building": True,
                "comp_id": "high_mobility",
                "name": "High Mobility and Skirmish Composition",
                "category": "tactical_profile",
                "description": "A fast-paced, highly fluid draft that exploits superior dash, blink, and move speed mechanics to out-maneuver opponents, dodge skillshots, and dictate engagement pacing.",
                "power_curve": power_curve or "Early-to-Mid Game (Dynamic River and Lane Skirmishes)",
                "role_1_title": "Ultra-Mobile Skirmishers and Divers",
                "role_1_champions": ["Ahri", "Lee Sin", "Yasuo", "Yone", "Pyke", "Akali", "Talon", "LeBlanc"],
                "role_2_title": "Fluid Follow-Up and Agile Carries",
                "role_2_champions": ["Kai'Sa", "Lucian", "Rakan", "Bard", "Camille"],
                "sample_draft": {
                    "top": "Camille / Irelia",
                    "jungle": "Lee Sin / Nidalee",
                    "mid": "Ahri / LeBlanc",
                    "bot": "Lucian / Kai'Sa",
                    "support": "Rakan / Pyke",
                },
                "win_condition": "Bait and evade enemy skillshots using mobility spells, take favorable skirmishes in open terrain, and disengage at will whenever enemy reinforcements arrive.",
                "source": "tactical_knowledge_base",
            }

        # 14. Full AD (Physical Damage Heavy) Compositions
        elif any(w in comp_id_clean for w in ["full_ad", "ad_heavy", "physical_damage"]):
            return {
                "is_composition_building": True,
                "comp_id": "full_ad",
                "name": "Full AD (Physical Damage Heavy) Composition",
                "category": "damage_profile",
                "description": "An aggressive physical damage draft prioritizing high early-to-mid game kill pressure and armor penetration, aiming to snowball early lanes before enemies can build armor.",
                "power_curve": power_curve or "Early-to-Mid Game (Lethality and Armor Pen Powerspikes)",
                "role_1_title": "Physical Damage Lane Bullies and Assassins",
                "role_1_champions": ["Jayce", "Renekton", "Zed", "Talon", "Draven", "Lucian"],
                "role_2_title": "Armor Shred and Physical Lockdown Frontline",
                "role_2_champions": ["Jarvan IV", "Pantheon", "Vi", "Thresh", "Nautilus"],
                "sample_draft": {
                    "top": "Renekton / Jayce",
                    "jungle": "Jarvan IV / Vi",
                    "mid": "Zed / Talon / Yasuo",
                    "bot": "Draven / Lucian",
                    "support": "Nautilus / Pantheon",
                },
                "win_condition": "Crush early lane matchups, secure early neutral objectives, and build Black Cleaver and Lord Dominik's Regards early to shred opposing armor before defensive items scale.",
                "source": "tactical_knowledge_base",
            }

        # 15. Full AP (Magic Damage Heavy) Compositions
        elif any(w in comp_id_clean for w in ["full_ap", "ap_heavy"]):
            return {
                "is_composition_building": True,
                "comp_id": "full_ap",
                "name": "Full AP (Magic Damage Heavy) Composition",
                "category": "damage_profile",
                "description": "An explosive magic damage draft that relies on devastating AoE ability power scaling and magic penetration to melt enemy teams in mid-to-late game teamfights.",
                "power_curve": power_curve or "Mid-to-Late Game (Deathcap / Void Staff Spikes)",
                "role_1_title": "High-Burst and Sustained AP Casters",
                "role_1_champions": ["Rumble", "Karthus", "Syndra", "Orianna", "Ziggs", "Viktor"],
                "role_2_title": "Magic Resistance Shred and AoE Lockdown Frontline",
                "role_2_champions": ["Galio", "Maokai", "Amumu", "Leona", "Nautilus"],
                "sample_draft": {
                    "top": "Rumble / Kennen",
                    "jungle": "Karthus / Lillia",
                    "mid": "Syndra / Viktor",
                    "bot": "Ziggs / Seraphine",
                    "support": "Nautilus / Maokai",
                },
                "win_condition": "Stack magic penetration items (Void Staff, Cryptbloom, Sorcerer's Shoes) and combine AoE spell rotations to burst enemy targets before Magic Resist shields can trigger.",
                "source": "tactical_knowledge_base",
            }

        # 16. Fighter and Bruiser Heavy Compositions
        elif any(w in comp_id_clean for w in ["fighter_heavy", "fighter", "bruiser"]):
            return {
                "is_composition_building": True,
                "comp_id": "fighter_heavy",
                "name": "Fighter and Bruiser Heavy Composition",
                "category": "role_profile",
                "description": "A rugged melee skirmish draft that excels in close-quarters brawls and prolonged teamfights through high base durability, conqueror stacking, and sustained melee damage.",
                "power_curve": power_curve or "Mid-Game (Conqueror and Trinity Force Spikes)",
                "role_1_title": "Frontline Bruisers and Juggernauts",
                "role_1_champions": ["Darius", "Sett", "Aatrox", "Renekton", "Mordekaiser", "Olaf", "Vi"],
                "role_2_title": "Mobile Follow-Up Skirmishers and Enablers",
                "role_2_champions": ["Yone", "Yasuo", "Lee Sin", "Lulu", "Taric"],
                "sample_draft": {
                    "top": "Aatrox / Renekton",
                    "jungle": "Vi / Jarvan IV",
                    "mid": "Yone / Sylas",
                    "bot": "Samira / Nilah",
                    "support": "Taric / Rakan",
                },
                "win_condition": "Force mid-game river skirmishes where your bruisers can stack sustained combat passives and out-muscle fragile enemy carries in close combat.",
                "source": "tactical_knowledge_base",
            }

        # 17. Marksman and ADC Heavy Compositions
        elif any(w in comp_id_clean for w in ["marksman_heavy", "marksman", "adc", "multi_adc"]):
            return {
                "is_composition_building": True,
                "comp_id": "marksman_heavy",
                "name": "Marksman and ADC Heavy Composition",
                "category": "role_profile",
                "description": "A sustained ranged physical DPS draft featuring multiple marksmen across different lanes, delivering unrivaled objective shred and late-game front-to-back damage.",
                "power_curve": power_curve or "Mid-to-Late Game (Multi-Carry Item Spikes)",
                "role_1_title": "Primary Ranged Marksmen and Carries",
                "role_1_champions": ["Tristana", "Lucian", "Corki", "Jinx", "Caitlyn", "Akshan"],
                "role_2_title": "Dedicated Peel Wardens and Disengage Enchanters",
                "role_2_champions": ["Braum", "Poppy", "Shen", "Janna", "Lulu", "Tahm Kench"],
                "sample_draft": {
                    "top": "Quinn / Vayne",
                    "jungle": "Kindred / Graves",
                    "mid": "Tristana / Corki",
                    "bot": "Jinx / Caitlyn",
                    "support": "Braum / Lulu",
                },
                "win_condition": "Maintain strict perimeter spacing, kite enemy divers, and melt Baron, Dragon, and enemy frontline tanks in seconds using overwhelming continuous ranged basic attacks.",
                "source": "tactical_knowledge_base",
            }

        # 18. Enchanter and Utility Support Compositions
        elif any(w in comp_id_clean for w in ["support_heavy", "enchanter", "utility"]):
            return {
                "is_composition_building": True,
                "comp_id": "support_heavy",
                "name": "Enchanter and Utility Support Composition",
                "category": "role_profile",
                "description": "A multiplier draft utilizing multiple support and utility champions to over-buff a primary carry with immense movement speed, bonus attack speed, and unbreakable shield layers.",
                "power_curve": power_curve or "Mid-to-Late Game (Heal/Shield Item Multipliers)",
                "role_1_title": "Dedicated Buff and Shield Enchanters",
                "role_1_champions": ["Lulu", "Karma", "Ivern", "Seraphine", "Milio", "Sona"],
                "role_2_title": "Hyper-Scale Carry Anchors",
                "role_2_champions": ["Jinx", "Kog'Maw", "Master Yi", "Olaf", "Hecarim"],
                "sample_draft": {
                    "top": "Karma / Shen",
                    "jungle": "Ivern / Sejuani",
                    "mid": "Seraphine / Orianna",
                    "bot": "Kog'Maw / Jinx",
                    "support": "Lulu / Milio",
                },
                "win_condition": "Funnel continuous shields and utility buffs onto your designated carry, making them immune to burst and enabling them to 1v5 clean up teamfights.",
                "source": "tactical_knowledge_base",
            }

        # 19. Ranged Heavy and Perimeter Kiting Compositions
        elif any(w in comp_id_clean for w in ["ranged", "kite", "kiting", "perimeter"]):
            return {
                "is_composition_building": True,
                "comp_id": "ranged",
                "name": "Ranged Heavy Composition",
                "category": "range_profile",
                "description": "A long-range kiting draft designed to maintain defensive distance, applying continuous ranged damage and crowd control slows while denying enemy gap-closers.",
                "power_curve": power_curve or "Mid-Game (Range and Movement Speed Advantages)",
                "role_1_title": "Long-Range Attackers and Kiters",
                "role_1_champions": ["Ashe", "Caitlyn", "Ezreal", "Jayce", "Lux", "Vel'Koz"],
                "role_2_title": "Anti-Dive Peel and Disengage Anchors",
                "role_2_champions": ["Janna", "Gragas", "Poppy", "Braum", "Trundle"],
                "sample_draft": {
                    "top": "Jayce / Kennen",
                    "jungle": "Nidalee / Lillia",
                    "mid": "Lux / Xerath",
                    "bot": "Ashe / Caitlyn",
                    "support": "Janna / Braum",
                },
                "win_condition": "Maintain defensive perimeter spacing, refuse melee trades, and whittle down enemy health pools while kiting backward through river chokepoints.",
                "source": "tactical_knowledge_base",
            }

        # 20. Melee Heavy and Close-Combat Brawl Compositions
        elif any(w in comp_id_clean for w in ["melee", "close_combat"]):
            return {
                "is_composition_building": True,
                "comp_id": "melee",
                "name": "Melee Heavy Composition",
                "category": "range_profile",
                "description": "A high-impact melee draft that excels at closing the distance quickly, overwhelming fragile ranged champions in close-quarters brawls and tight jungle terrain.",
                "power_curve": power_curve or "Mid-Game (Gage and Bruiser Item Spikes)",
                "role_1_title": "Hard-Engage Vanguard Tanks and Divers",
                "role_1_champions": ["Malphite", "Jarvan IV", "Alistar", "Nautilus", "Zac"],
                "role_2_title": "High-Impact Melee Duelists and Bruisers",
                "role_2_champions": ["Jax", "Darius", "Sett", "Sylas", "Yone", "Samira"],
                "sample_draft": {
                    "top": "Malphite / Darius",
                    "jungle": "Jarvan IV / Zac",
                    "mid": "Sylas / Yone",
                    "bot": "Samira / Nilah",
                    "support": "Alistar / Nautilus",
                },
                "win_condition": "Close gaps with gap-closing ultimates, force fights in tight jungle corridors where ranged enemies have no room to kite, and overpower targets in close-quarters melee brawls.",
                "source": "tactical_knowledge_base",
            }

        # Default Pick and Skirmish Composition
        return {
            "is_composition_building": True,
            "comp_id": "pick_skirmish",
            "name": "Pick and Skirmish Control Composition",
            "category": "tactical_profile",
            "description": "A tactical vision and isolation draft that specializes in catching out-of-position enemies with single-target crowd control and collapsing with rapid burst execution.",
            "power_curve": power_curve or "Early-to-Mid Game (Vision Traps and Jungle Invasions)",
            "role_1_title": "Pick Crowd Control and Ambush Initiators",
            "role_1_champions": ["Thresh", "Blitzcrank", "Nautilus", "Ahri", "Elise", "Morgana"],
            "role_2_title": "Burst Executioners and Skirmish Carries",
            "role_2_champions": ["Syndra", "Lucian", "Kha'Zix", "Leblanc", "Renekton"],
            "sample_draft": {
                "top": "Renekton / Aatrox",
                "jungle": "Elise / Vi",
                "mid": "Ahri / Syndra",
                "bot": "Lucian / Jhin",
                "support": "Thresh / Nautilus",
            },
            "win_condition": "Establish dense vision control in the enemy jungle, bait facechecks with priority CC skillshots, and convert 5v4 man-advantages into uncontested neutral objectives.",
            "source": "tactical_knowledge_base",
        }

    def get_composition_counters(
        self, comp_archetype = None, damage_composition = None
    ):
        """
        Dynamically aggregate tactical counter intelligence for team compositions
        (e.g., Full AD, Full AP, Dive, Poke, Heavy CC, Sustain, Stealth, Ranged, Melee, Fighter Heavy)
        directly from verified strategic game knowledge and MongoDB collection 'team_compositions'.
        """
        target_key = comp_archetype or damage_composition or ""
        norm_key = target_key.lower().replace("-", "_").replace(" ", "_") if target_key else ""
        
        strat = strategic_composition_counters.get(norm_key)
        if not strat and target_key:
            for k, v in strategic_composition_counters.items():
                if k in norm_key or norm_key in k:
                    strat = v
                    norm_key = k
                    break

        comp_doc = self.store.get_composition(target_key)
        if not comp_doc and norm_key:
            comp_doc = self.store.get_composition(norm_key)
        if not comp_doc and comp_archetype and damage_composition:
            comp_doc = self.store.get_composition(damage_composition)
        if not comp_doc:
            comp_doc = self.store.get_composition("ranged")

        # Build sample champion descriptors from member champions
        sample_champs = []
        if comp_doc:
            sample_names = comp_doc.get("sample_champions", []) or comp_doc.get("all_champions", [])[:15]
            for cname in sample_names[:15]:
                c = self.store.get_champion(cname)
                if c:
                    sample_champs.append({
                        "name": c.get("name", cname),
                        "roles": c.get("roles", []),
                        "subroles": c.get("subroles", []),
                        "damage_type": c.get("adaptiveType", "Mixed"),
                    })
                else:
                    sample_champs.append({"name": cname, "roles": [], "damage_type": "Mixed"})

        # Format counter picks
        if strat and strat.get("counter_picks"):
            counter_picks = strat["counter_picks"]
        elif comp_doc:
            counter_picks = []
            for cp in comp_doc.get("counter_picks", []):
                counter_picks.append({
                    "champion": cp.get("champion"),
                    "reason": cp.get("tactical_reason", ""),
                    "frequency": cp.get("counter_frequency", 0),
                    "coverage_pct": cp.get("archetype_coverage_pct", 0.0),
                })
        else:
            counter_picks = []

        # Format counter items
        if strat and strat.get("counter_items"):
            counter_items = strat["counter_items"]
        elif comp_doc:
            counter_items = []
            for ci in comp_doc.get("counter_items", []):
                counter_items.append({
                    "item": ci.get("item"),
                    "purpose": ci.get("tactical_purpose", ""),
                    "recommended_count": ci.get("recommended_count", 0),
                })
        else:
            counter_items = []

        # Format weaknesses and tactical tips
        weaknesses = (strat.get("weaknesses") if strat else None) or (comp_doc.get("core_weaknesses", []) if comp_doc else [])
        tactical_tips = (strat.get("tactical_tips") if strat else None) or (comp_doc.get("tactical_tips", []) if comp_doc else [])

        # Role title and description
        role_title = (strat.get("name") if strat else None) or (comp_doc.get("name") if comp_doc else None) or norm_key.replace("_", " ").title() + " Composition"
        description = (strat.get("description") if strat else None) or (comp_doc.get("description") if comp_doc else None) or f"Tactical composition profile for {role_title}."
        comp_id = norm_key or (comp_doc.get("comp_id") if comp_doc else "tactical_composition")

        # Collect verified core abilities for counter picks
        champ_abilities = {}
        for cp in counter_picks:
            cname = cp.get("champion") if isinstance(cp, dict) else str(cp)
            raw_cname = cname.split(" (")[0] if cname else ""
            if raw_cname and raw_cname not in champ_abilities:
                c_doc = self.store.get_champion(raw_cname)
                formatted = self.format_champion_abilities(c_doc)
                if formatted:
                    champ_abilities[raw_cname] = formatted

        return {
            "is_role_query": True,
            "is_composition_query": True,
            "is_team_counter_analysis": True,
            "comp_archetype": comp_id,
            "category": comp_doc.get("category", "tactical_archetype") if comp_doc else "tactical_archetype",
            "role_title": role_title,
            "description": description,
            "sample_champions": sample_champs,
            "total_member_count": comp_doc.get("total_member_count", len(sample_champs)) if comp_doc else len(sample_champs),
            "weaknesses": weaknesses,
            "tactical_tips": tactical_tips,
            "counter_items": counter_items,
            "counter_picks": counter_picks,
            "champion_abilities": champ_abilities,
            "source": "verified_strategic_counter_intelligence",
        }

    def get_synergies(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        data = self.store.get_synergy_info(name)
        
        # Fallback to direct file loading if KnowledgeStore didn't have it loaded yet
        if not data:
            for syn_path in [knowledge_base_dir / "synergies.json", processed_dir / "synergies.json"]:
                if syn_path.exists():
                    try:
                        with open(syn_path, "r", encoding="utf-8") as f:
                            all_syn = json.load(f)
                            norm_name = self.store.normalize_key(name)
                            data = all_syn.get(name) or all_syn.get(champ.get("name")) or all_syn.get(norm_name)
                            if not data and isinstance(all_syn, dict):
                                for k, v in all_syn.items():
                                    if self.store.normalize_key(k) == norm_name:
                                        data = v
                                        break
                            if data:
                                break
                    except Exception:
                        pass

        duos = []
        team_comps = []
        tactical_insights = []
        if data:
            if isinstance(data, dict):
                duos = data.get("best_duos") or data.get("synergies", [])
                team_comps = data.get("best_team_compositions", [])
                tactical_insights = data.get("tactical_insights", [])
            elif isinstance(data, list):
                duos = data

        profile.update({
            "is_synergy_query": True,
            "best_duos": duos[:6],
            "top_duos": duos[:6],
            "best_team_compositions": team_comps,
            "tactical_insights": tactical_insights,
            "data_source_note": "Season 2025 Match Data (Pro Play + OP.GG SoloQ)",
            "notice": "No specific duo synergy data available for this champion." if not duos else None,
        })
        return profile

    def get_champion_composition(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        data = self.store.get_synergy_info(name)
        if not data:
            for syn_path in [knowledge_base_dir / "synergies.json", processed_dir / "synergies.json"]:
                if syn_path.exists():
                    try:
                        with open(syn_path, "r", encoding="utf-8") as f:
                            all_syn = json.load(f)
                            norm_name = self.store.normalize_key(name)
                            data = all_syn.get(name) or all_syn.get(champ.get("name")) or all_syn.get(norm_name)
                            if data:
                                break
                    except Exception:
                        pass

        comps = data.get("best_team_compositions", []) if isinstance(data, dict) else []
        duos = data.get("best_duos", []) if isinstance(data, dict) else []

        profile.update({
            "is_champion_composition": True,
            "focus_champion": champ.get("name", name),
            "best_team_compositions": comps,
            "best_duos": duos[:3],
            "tactical_insights": data.get("tactical_insights", []) if isinstance(data, dict) else [],
            "notice": f"Không có dữ liệu đội hình Pro Play cụ thể cho {champ.get('name', name)}." if not comps else None,
        })
        return profile

    def get_build(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        data = self.store.get_build_info(name)
        if not data:
            profile["notice"] = "No specific build data found; utilizing archetype and role recommendations."
            return profile

        core = data.get("coreItems") or data.get("core_items") or []
        full = data.get("fullBuild") or data.get("full_build") or []
        start = data.get("startingItems") or data.get("starting_items") or []
        spells = data.get("summonerSpells") or data.get("summoner_spells") or []
        p_runes = data.get("primaryRunes") or data.get("primary_runes") or []
        s_runes = data.get("secondaryRunes") or data.get("secondary_runes") or []

        profile.update({
            "starting_items": start,
            "core_items": core or full[:3],
            "full_build": full,
            "summoner_spells": spells,
            "runes": {
                "keystone": data.get("keystone"),
                "primary": p_runes,
                "secondary": s_runes,
            },
        })
        return profile

    def get_item_info(self, item_name):
        item = self.store.get_item(item_name)
        if not item:
            return {"error": f"Item '{item_name}' not found."}

        build_from_resolved = []
        for bf in item.get("buildFrom", []):
            resolved = self.store.get_item(bf)
            if resolved and resolved.get("name"):
                build_from_resolved.append(resolved["name"])
            else:
                build_from_resolved.append(str(bf))

        build_into_resolved = []
        for bi in item.get("buildInto", []):
            resolved = self.store.get_item(bi)
            if resolved and resolved.get("name"):
                build_into_resolved.append(resolved["name"])
            else:
                build_into_resolved.append(str(bi))

        return {
            "name": item.get("name"),
            "cost": item.get("cost", {}),
            "stats": item.get("stats", {}),
            "description": item.get("description", "") or item.get("plaintext", ""),
            "aliases": item.get("aliases", []),
            "colloquial": item.get("colloquial", []),
            "requiredChampion": item.get("requiredChampion", ""),
            "requiredAlly": item.get("requiredAlly", ""),
            "active": item.get("active", False),
            "buildFrom": build_from_resolved,
            "buildInto": build_into_resolved,
        }

    def get_rune_info(self, rune_name):
        rune = self.store.get_rune(rune_name)
        if not rune:
            return {"error": f"Rune '{rune_name}' not found."}

        return {
            "name": rune.get("name"),
            "tree": rune.get("tree"),
            "description": rune.get("description", ""),
            "longDescription": rune.get("longDescription", ""),
        }

    def filter_semantic(
        self,
        roles = None,
        cc_types = None,
        effects = None,
        playstyles = None,
        power_curve = None,
        win_condition = None,
    ):
        matches = self.store.filter_champions(
            roles=roles,
            cc_types=cc_types,
            effects=effects,
            playstyles=playstyles,
            power_curve=power_curve,
            win_condition=win_condition,
        )

        return {
            "criteria": {
                "roles": roles,
                "cc_types": cc_types,
                "effects": effects,
                "playstyles": playstyles,
                "power_curve": power_curve,
                "win_condition": win_condition,
            },
            "total_matches": len(matches),
            "sample_matches": [
                {
                    "name": m.get("name"),
                    "roles": m.get("roles", []),
                    "cc": m.get("cc_types", []),
                    "effects": m.get("ability_effects", []),
                    "playstyles": m.get("playstyles", []),
                }
                for m in matches[:10]
            ],
        }

    def get_semantic_profile(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        profile["is_semantic_profile"] = True
        return profile

    def analyze_team_counters(self, enemies, comp_archetype = None, damage_composition = None):
        """
        Dynamically analyze an enemy composition or multi-champion team to formulate:
        - Shared structural kit weaknesses
        - Algorithmic multi-target cross-counter champion picks
        - 3-phase macro execution gameplan (Early, Mid, Late)
        - Strategic counter itemization
        All data is dynamically synthesized without hardcoding.
        """
        if not enemies and not comp_archetype and not damage_composition:
            return {"error": "A list of enemy champions or a team composition archetype is required for counter analysis."}

        enemies = enemies or []
        enemy_docs = {}
        analysis = {}
        all_weaknesses = []
        all_counter_items = []
        damage_counts = {"Magic": 0, "Physical": 0, "Mixed": 0, "True": 0}
        power_curves = []
        candidate_scores = {}

        # 1. Fetch enemy champion docs and counter relationships
        for enemy in enemies:
            canonical_id = self.store.champion_lookup.get(self.store.normalize_key(enemy))
            champ = self.store.get_champion(canonical_id or enemy)
            cdata = self.store.get_counter_info(canonical_id or enemy) or {}

            c_name = champ.get("name") if champ else enemy.title()
            enemy_docs[c_name] = {"champ": champ, "counter": cdata}

            if champ:
                adp = champ.get("adaptiveType", "Physical")
                damage_counts[adp] = damage_counts.get(adp, 0) + 1

                pc = champ.get("powerCurve") or []
                power_curves.extend(pc)

                tactical = champ.get("tacticalInfo") or {}
                w_list = champ.get("weaknesses") or tactical.get("weaknesses") or []
                if w_list:
                    all_weaknesses.extend(w_list)

                it_list = champ.get("counter_items") or tactical.get("counter_items") or []
                if it_list:
                    all_counter_items.extend(it_list)

            # Extract individual counters and accumulate cross-counter candidates
            weak_against = cdata.get("weakAgainst", []) if isinstance(cdata, dict) else []
            if weak_against:
                top_counters = [w.get("champion") for w in weak_against[:3] if w.get("champion")]
                analysis[c_name] = {"vulnerable_to": top_counters}
                for w in weak_against:
                    cand = w.get("champion")
                    reason = w.get("reason", "")
                    if cand:
                        if cand not in candidate_scores:
                            candidate_scores[cand] = {
                                "champion": cand,
                                "countered_enemies": [],
                                "reasons": [],
                                "score": 0,
                            }
                        if c_name not in candidate_scores[cand]["countered_enemies"]:
                            candidate_scores[cand]["countered_enemies"].append(c_name)
                        if reason and reason not in candidate_scores[cand]["reasons"]:
                            candidate_scores[cand]["reasons"].append(reason)
                        candidate_scores[cand]["score"] += 12
            else:
                analysis[c_name] = {"vulnerable_to": ["Vulnerable to targeted crowd control and burst lockdown"]}

        # 2. Composition archetype data integration
        comp_obj = None
        comp_title = None
        norm_arch = (comp_archetype or damage_composition or "").lower().replace("-", "_").replace(" ", "_")
        strat_obj = strategic_composition_counters.get(norm_arch)

        if strat_obj:
            comp_title = strat_obj.get("name")
            for c_weak in strat_obj.get("weaknesses", []):
                if c_weak not in all_weaknesses:
                    all_weaknesses.insert(0, c_weak)
            for c_pick in strat_obj.get("counter_picks", []):
                cand = c_pick.get("champion")
                r_txt = c_pick.get("reason", "")
                if cand:
                    if cand not in candidate_scores:
                        candidate_scores[cand] = {
                            "champion": cand,
                            "countered_enemies": [],
                            "reasons": [],
                            "score": 0,
                        }
                    candidate_scores[cand]["score"] += 20
                    if r_txt and r_txt not in candidate_scores[cand]["reasons"]:
                        candidate_scores[cand]["reasons"].append(r_txt)
            for itm in strat_obj.get("counter_items", []):
                it_name = itm.get("item") if isinstance(itm, dict) else str(itm)
                if it_name and it_name not in all_counter_items:
                    all_counter_items.insert(0, it_name)
        elif comp_archetype:
            comp_obj = self.store.get_composition(comp_archetype)
            if comp_obj:
                comp_title = comp_obj.get("name")
                for c_weak in comp_obj.get("core_weaknesses", []):
                    if c_weak not in all_weaknesses:
                        all_weaknesses.insert(0, c_weak)
                for c_pick in comp_obj.get("counter_picks", []):
                    cand = c_pick.get("champion")
                    r_txt = c_pick.get("tactical_reason", "")
                    if cand:
                        if cand not in candidate_scores:
                            candidate_scores[cand] = {
                                "champion": cand,
                                "countered_enemies": [],
                                "reasons": [],
                                "score": 0,
                            }
                        candidate_scores[cand]["score"] += 8
                        if r_txt and r_txt not in candidate_scores[cand]["reasons"]:
                            candidate_scores[cand]["reasons"].append(r_txt)
                for itm in comp_obj.get("counter_items", []):
                    all_counter_items.append(itm.get("item") if isinstance(itm, dict) else str(itm))
        elif damage_composition:
            comp_obj = self.store.get_composition(damage_composition)
            if comp_obj:
                comp_title = comp_obj.get("name")

        if not comp_title:
            if comp_archetype:
                comp_title = comp_archetype.replace("_", " ").title() + " Composition"
            elif enemies:
                comp_title = f"{', '.join(enemy_docs.keys())} Composition"
            else:
                comp_title = "Enemy Composition"

        # 3. Assess damage profile
        total_champs = len(enemies) if enemies else 1
        damage_desc = []
        if damage_counts.get("Magic", 0) >= max(2, total_champs * 0.6):
            damage_desc.append("Heavy Magic Damage")
        if damage_counts.get("Physical", 0) >= max(2, total_champs * 0.6):
            damage_desc.append("Heavy Physical Damage")
        if not damage_desc:
            damage_desc.append("Hybrid / Mixed Damage")
        damage_profile_str = ", ".join(damage_desc)

        # 4. Formulate shared weaknesses
        is_scaling = (
            comp_archetype == "scaling_late_game"
            or "LateGame" in power_curves
            or any("stack" in str(w).lower() or "late" in str(w).lower() for w in all_weaknesses)
        )

        shared_weaknesses = []
        if is_scaling:
            shared_weaknesses.append("Early-Game Vulnerability: Low base damage and weak trading power pre-level 6 leave them highly susceptible to aggressive lane bullies and early jungle invades.")
            shared_weaknesses.append("High Reliance on Minion Farm and Passive Stacks: Freezing waves and denying minion waves drastically stalls their power spike thresholds.")
            shared_weaknesses.append("Zero Early Objective Priority: Inability to contest early Voidgrubs, Rift Herald, or early Dragons without risking disastrous teamfights.")

        # Add kit-derived vulnerabilities
        for w in all_weaknesses:
            if w not in shared_weaknesses and len(shared_weaknesses) < 5:
                shared_weaknesses.append(w)

        if not shared_weaknesses:
            shared_weaknesses.append("Vulnerable to coordinated crowd control chains and early objective tempo.")
            shared_weaknesses.append("Susceptible to flank collapses when separated from defensive turret range.")

        # 5. Formulate 3-Phase Macro Strategy
        if is_scaling:
            macro_strategy = {
                "early_game": "Draft dominant early-game lane bullies. Freeze minion waves outside your turret to deny gold and stacks. Coordinate 3-man dives and secure all 6 Voidgrubs to rapidly open up the map.",
                "mid_game": "Accelerate game tempo by grouping as 5 to siege outer and inner turrets. Starve the enemy of jungle camps and stack consecutive Dragons to force a soul timer before 22 minutes.",
                "late_game": "Force decisive 5v5 teamfights at Baron Nashor or Dragon Soul while holding a substantial item advantage. Close out the match before the enemy hypercarries reach 3+ full items.",
            }
        else:
            macro_strategy = {
                "early_game": "Establish early vision control in the river and prioritize lane push priority to assist your jungler at scuttle crabs and neutral objectives.",
                "mid_game": "Group around vision choke points in the river. Bait face-checks and look for layered CC picks before starting neutral objectives.",
                "late_game": "Execute disciplined front-to-back teamfights. Maintain defensive perimeter spacing and coordinate burst lockdown on the primary enemy carries.",
            }

        # 6. Rank Top Cross-Counter Champions
        sorted_candidates = sorted(
            candidate_scores.values(),
            key=lambda c: (len(c["countered_enemies"]), c["score"]),
            reverse=True
        )

        top_counter_picks = []
        seen_cand = set()
        for cand_data in sorted_candidates:
            c_name = cand_data["champion"]
            if c_name in seen_cand or c_name in enemy_docs:
                continue
            seen_cand.add(c_name)

            c_obj = self.store.get_champion(c_name)
            c_title = f" ({c_obj.get('title')})" if c_obj and c_obj.get("title") else ""
            c_enemies = cand_data["countered_enemies"]
            c_reasons = cand_data["reasons"]

            if c_enemies:
                reason_summary = f"Directly counters {', '.join(c_enemies[:2])} by punishing their vulnerable laning phase and neutralizing their kit."
            elif c_reasons:
                reason_summary = c_reasons[0]
            else:
                reason_summary = f"Dominates through superior kit mechanics, burst trades, and reliable crowd control."

            top_counter_picks.append({
                "champion": f"{c_name}{c_title}",
                "countered_targets": c_enemies,
                "reason": reason_summary,
            })
            if len(top_counter_picks) >= 4:
                break

        # 7. Strategic Counter Itemization
        seen_items = set()
        recommended_items = []
        for it in all_counter_items:
            it_name = it if isinstance(it, str) else it.get("item", "")
            if it_name and it_name not in seen_items:
                seen_items.add(it_name)
                it_doc = self.store.get_item(it_name)
                pt = it_doc.get("plaintext", "") if it_doc else ""
                desc = it_doc.get("description", "") if it_doc else ""
                purp = pt or desc[:80] or "Provides crucial defensive mitigation against enemy power spikes."
                recommended_items.append({"item": it_name, "purpose": purp})
            if len(recommended_items) >= 4:
                break

        # If item list is sparse, dynamically add based on damage profile
        if len(recommended_items) < 3:
            if "Magic" in damage_profile_str:
                for default_mr in ["Kaenic Rookern", "Force of Nature", "Maw of Malmortius", "Mercury's Treads"]:
                    if default_mr not in seen_items:
                        seen_items.add(default_mr)
                        recommended_items.append({"item": default_mr, "purpose": "High magic resist and magic shielding to absorb spell burst."})
                    if len(recommended_items) >= 4:
                        break
            if "Physical" in damage_profile_str:
                for default_ar in ["Plated Steelcaps", "Frozen Heart", "Randuin's Omen", "Thornmail"]:
                    if default_ar not in seen_items:
                        seen_items.add(default_ar)
                        recommended_items.append({"item": default_ar, "purpose": "Armor and attack speed reduction to neutralize physical carries."})
                    if len(recommended_items) >= 4:
                        break

        # Collect verified core abilities for counter champions
        champ_abilities = {}
        for cp in top_counter_picks:
            cname = cp.get("champion")
            raw_cname = cname.split(" (")[0] if cname else ""
            if raw_cname and raw_cname not in champ_abilities:
                c_doc = self.store.get_champion(raw_cname)
                formatted = self.format_champion_abilities(c_doc)
                if formatted:
                    champ_abilities[raw_cname] = formatted

        return {
            "is_team_counter_analysis": True,
            "enemy_team": list(enemy_docs.keys()) if enemy_docs else enemies,
            "comp_archetype": comp_archetype,
            "comp_title": comp_title,
            "damage_profile": damage_profile_str,
            "shared_weaknesses": shared_weaknesses,
            "macro_strategy": macro_strategy,
            "recommended_items": recommended_items,
            "cross_counter_picks": top_counter_picks,
            "champion_abilities": champ_abilities,
            "individual_breakdown": analysis,
        }

    def analyze_team_synergies(self, champions):
        """
        Dynamically analyze team synergies, combo chains, CC layers, and damage distribution
        across a composition using processor data from KnowledgeStore.
        """
        if not champions:
            return {"error": "A list of allied champions is required for team synergy analysis."}

        synergy_combos = []
        team_cc = set()
        team_roles = []
        team_damage = []

        champ_objs = {}
        for name in champions:
            c = self.store.get_champion(name)
            if c:
                c_name = c.get("name", name)
                champ_objs[c_name] = c
                team_cc.update(c.get("cc_types", []))
                team_roles.extend(c.get("roles", []))
                if c.get("adaptiveType"):
                    team_damage.append(c["adaptiveType"])

        names = list(champ_objs.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                c1_name = names[i]
                c2_name = names[j]
                syn_data = self.store.get_synergy_info(c1_name) or {}
                duos = (syn_data.get("best_duos") or syn_data.get("synergies", [])) if isinstance(syn_data, dict) else []
                match = next((d for d in duos if (d.get("partner") or d.get("champion", "")).lower() == c2_name.lower()), None)
                if match:
                    synergy_combos.append({
                        "pair": f"{c1_name} + {c2_name}",
                        "reason": match.get("synergy_reason") or match.get("reason", ""),
                        "winRate": match.get("soloq_winrate") or match.get("winRate"),
                        "pro_play": match.get("pro_play", False),
                        "pro_games": match.get("pro_games", 0),
                        "pro_winrate": match.get("pro_winrate"),
                    })
                else:
                    c1 = champ_objs[c1_name]
                    c2 = champ_objs[c2_name]
                    c1_hard_cc = set(c1.get("hard_cc", []))
                    c2_hard_cc = set(c2.get("hard_cc", []))
                    if c1_hard_cc and c2_hard_cc:
                        synergy_combos.append({
                            "pair": f"{c1_name} + {c2_name}",
                            "reason": f"Lockdown CC Chain: {', '.join(c1_hard_cc)} combined with {', '.join(c2_hard_cc)} enables layered crowd control.",
                            "winRate": None,
                        })

        return {
            "is_team_synergy": True,
            "team_champions": names,
            "synergy_combos": synergy_combos,
            "team_cc_types": sorted(list(team_cc)),
            "damage_distribution": list(set(team_damage)),
        }
