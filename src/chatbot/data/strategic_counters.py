"""
Strategic composition counter intelligence data.

Moved from data_retriever.py module-level dict to separate data file.
Contains verified counter picks, items, weaknesses, and tactical tips
for each team composition archetype.
"""

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
