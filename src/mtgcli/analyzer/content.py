"""Content layer: trigger families, scaling, and tribal detection.

These are the three content signals the new analyzer was missing (surfaced by the Pantlaza
calibration run): what EVENT a trigger fires on, what a value SCALES with, and what creature
TYPE a card cares about. Trigger-family and for-each/number-of scaling reuse the existing
oracle_hooks extractors (one definition, no duplication); this layer wraps them into traced
Signals and adds the two gaps oracle_hooks didn't cover: power/toughness scaling and tribal.
"""
import re
from typing import List

from mtgcli.analyzer.model import (
    CardProfile, Signal, Trace, EvidenceKind, Confidence, Polarity,
)
from mtgcli.deckbuilder.oracle_hooks import extract_trigger_events, extract_scaling

# Common Commander creature types (curated, DB-free). Enough to catch tribal payoffs/lords;
# the golden set will flag any gaps to add here.
_CREATURE_TYPES = {
    "dinosaur", "elf", "goblin", "zombie", "vampire", "angel", "dragon", "human", "wizard",
    "warrior", "soldier", "beast", "cat", "merfolk", "sliver", "spirit", "knight", "cleric",
    "rogue", "snake", "hydra", "wolf", "elemental", "demon", "giant", "bird", "insect", "faerie",
    "pirate", "ninja", "samurai", "rat", "squirrel", "dwarf", "elephant", "wurm", "dog", "horror",
    "shaman", "druid", "monk", "assassin", "berserker", "phoenix", "sphinx", "hippo", "ooze",
    "spider", "treefolk", "fungus", "saproling", "myr", "golem", "construct", "thopter", "dinosaurs",
    "kavu", "minotaur", "orc", "kithkin", "kor", "rebel", "ally", "werewolf", "cephalid", "frog",
    "fish", "crab", "wall", "plant", "fox", "rabbit", "bear", "boar", "ox", "goat", "bat", "devil",
    "imp", "gremlin", "gnome", "homunculus", "leviathan", "kraken", "octopus", "serpent", "whale",
    # batch #20: Gallia's Satyrs and Reaper King's Scarecrows were invisible — the
    # whitelist was missing a swath of real types. All entries are genuine creature
    # types (no oracle-noun collisions like "token"/"card").
    "satyr", "scarecrow", "skeleton", "centaur", "cyclops", "dryad", "unicorn", "pegasus",
    "griffin", "drake", "lizard", "illusion", "eldrazi", "phyrexian", "aetherborn", "vedalken",
    "viashino", "salamander", "otter", "mouse", "raccoon", "badger", "monkey", "ape",
    "crocodile", "turtle", "wraith", "specter", "shade", "nightmare", "archon", "praetor",
    "basilisk", "cockatrice", "gargoyle", "chimera", "manticore", "naga", "gorgon", "harpy",
    "siren", "nymph", "pilot", "artificer", "scout", "archer", "barbarian", "mystic", "pilgrim",
}

# tribal references: "another Dinosaur", "other Dinosaurs", "Dinosaur creatures", "Dinosaurs you control"
_TRIBAL_PATTERNS = [
    # "(?:nontoken\s+)?" — qualifier may sit between the article and the type (batch-16
    # Miirym: "another NONTOKEN Dragon you control"; measured: elf/zombie/vampire/dragon/
    # human/spirit variants exist). The negation guard below still sees "non-" prefixes
    # because "nontoken" is skipped, not captured.
    r"\b(?:another|other|each other|each)\s+(?:nontoken\s+)?([A-Za-z]+?)s?\s+(?:you control|creature)",
    r"\b([A-Za-z]+?)s?\s+creatures?\s+you control",
    r"\b([A-Za-z]+?)\s+creatures\b",
    r"\bother\s+([A-Za-z]+?)s\b",
    # singular trigger form: "whenever a Ninja you control ..." (Yuriko-style);
    # lowercase-safe: the _CREATURE_TYPES whitelist filters non-type words (creature, card...)
    r"\ba\s+(?:nontoken\s+)?([a-z]+)\s+you control\b",
    # library/hand references: "Dinosaur creature cards" (Gishath-style)
    r"\b([a-z]+)\s+creature cards?\b",
    # mass attack phrasing: "attack with one or more Zombies" (Varina-style)
    r"\bone or more ([a-z]+?)s\b",
    # tribal cost reduction / cast payoffs: "Hydra spells you cast cost {4} less" (Gargos-style)
    r"\b([a-z]+)\s+spells?\s+you\s+cast\b",
    # or-conjunction type pairs: "a Wolf or Werewolf you control" (Tovolar-style, batch #19).
    # Two single-group patterns so each half hits the whitelist check independently.
    r"\ba\s+([a-z]+)\s+or\s+[a-z]+\s+you control\b",
    r"\ba\s+[a-z]+\s+or\s+([a-z]+)\s+you control\b",
    # tribal tutor form: "search your library for a Sliver card" (Sliver Overlord, batch #19);
    # non-type words (land, aura...) are filtered by the whitelist.
    r"search your library for an? ([a-z]+) card\b",
    # anthem with explicit 'creatures': "Other Scarecrow creatures you control get +1/+1"
    # (Reaper King, batch #20) — the plain "other Xs" pattern needs the trailing s.
    r"\bother\s+([a-z]+)\s+creatures\b",
    # "another <Type> you control" trigger form (Reaper King's enters trigger, batch #20).
    r"\banother\s+(?:nontoken\s+)?([a-z]+)\s+you control\b",
    # plural pair-anthem: "Skeletons and Zombies you control get +1/+1" (Gisa, batch #22;
    # 29 measured pairs). Two single-group patterns, one per half.
    r"\b([a-z]+)s and [a-z]+s you control\b",
    r"\b[a-z]+s and ([a-z]+)s you control\b",
]

# power/toughness scaling that extract_scaling misses
_PT_SCALING = [
    (r"(?:x is|equal to)\s+(?:that creature's|its|their)\s+(power|toughness)", "creature_{}"),
    (r"(?:x is|equal to)\s+(?:the|its)\s+(power|toughness)", "creature_{}"),
    (r"deals damage equal to (?:its|that creature's) (power|toughness)", "creature_{}"),
]


def detect_trigger_families(text: str, profile: CardProfile, card_name: str = None) -> None:
    """Emit a signal per trigger event family (reuses oracle_hooks.extract_trigger_events)."""
    low = (text or "").lower()
    _board_attack = ("you control attack", "creatures you control attack", "you control deals combat damage",
                     "whenever you attack", "one or more creatures", "attacking creature",
                     "creatures attack",
                     # batch #23 Neyali gap: token armies attack too
                     "tokens you control attack")
    for family in extract_trigger_events(text or ""):
        # Direction check FIRST (batch #22 Isperia CW): "whenever a creature attacks YOU"
        # is an INCOMING attack — a pillowfort/deterrent trigger, never your own attack
        # theme. Measured: 19 cards, all defense (Isperia, Marchesa's Decree, Revenge of
        # Ravens). Own-board forms ("whenever you attack") are unaffected via _board_attack.
        if (family == "attacks_or_combat"
                and re.search(r"attacks you\b", low)
                and not any(p in low for p in _board_attack)):
            profile.add_signal(Signal(
                id="INCOMING_ATTACK_TRIGGER",
                label="Triggers when opponents attack YOU (defense, not an attack theme)",
                kind=EvidenceKind.RULE_RELATION,
                confidence=Confidence.STRONG,
                timing="triggered",
                trace=Trace(rule_id="content.trigger.incoming_attack.v1", rule_version="1.0",
                            matched_text=family, span=None,
                            note="Opponents attacking you is a pillowfort payoff, not your combat plan."),
            ))
            continue
        # Scope check for the attack family: "whenever <CARDNAME> attacks" is the commander's
        # own engine event (Korvold sacrifices when HE attacks), not an attack-triggers THEME
        # (Isshin/Toski reward the whole board attacking). Self-only -> weaker separate signal.
        if family == "attacks_or_combat" and not any(p in low for p in _board_attack):
            # Batch #19 CW class: the self-scope forms must also cover the SABOTEUR
            # trigger ("Whenever <name> deals combat damage to a player, <value>") —
            # Nine-Fingers Keene (digs Gates) and Yidris (grants cascade) are engine
            # events exactly like Zur, not attack themes. Board forms ("you control
            # deals combat damage") are already excluded by _board_attack above.
            self_subjects = ["this creature attacks", "whenever this creature attacks",
                             "this creature deals combat damage to a player"]
            if card_name:
                short = card_name.split(",")[0].strip().lower()
                self_subjects += [f"{short} attacks", f"{short} enters or attacks",
                                  f"{short} deals combat damage to a player"]
                # no-comma legends are referenced by their FIRST name in oracle text
                # ("Zur the Enchanter" -> "Whenever Zur attacks"); skip articles.
                first = card_name.split()[0].strip().lower()
                if first not in ("the", "a", "an") and len(first) > 2:
                    self_subjects += [f"{first} attacks", f"{first} enters or attacks",
                                      f"{first} deals combat damage to a player"]
            # A self-attack trigger whose EFFECT feeds combat (puts creatures attacking, untaps
            # CREATURES, grants extra combat) is still an attack THEME (Kaalia, Godo); a
            # non-combat effect (tutoring, sacrificing) is an engine event (Zur, Korvold).
            # Batch #19: the untap exemption is DIRECTIONAL — "untap each snow permanent"
            # (Jorn) is mana/value, not combat (measured: 101 creature-untaps vs 94 other).
            # CREATURE deployment in the effect (Lathril's Elf tokens, Gishath's
            # Dinosaurs onto the battlefield) still feeds the combat plan — the engine
            # ruling applies only to NONCREATURE value (Keene's Gates, Yidris' cascade,
            # Jorn's snow untaps, Zur's enchantments).
            _combat_effect = ("attacking", "untap it", "untap them", "untap those",
                              "untap all creatures", "untap each creature",
                              "untap target creature", "untap that creature",
                              "untap all attacking", "extra combat", "combat phase",
                              "gains haste", "creature token")
            trigger_line = next((l for l in low.split("\n")
                                 if any(s in l for s in self_subjects)), "")
            # "creature card" counts as deployment only when it reaches the BATTLEFIELD
            # (Gishath). Batch #20 Otrimi CW: "return target creature card ... to your
            # hand" is card advantage — an engine event, not combat.
            _deploys_creature_card = ("creature card" in trigger_line
                                      and ("onto the battlefield" in trigger_line
                                           or "to the battlefield" in trigger_line))
            if (any(s in low for s in self_subjects)
                    and not any(k in trigger_line for k in _combat_effect)
                    and not _deploys_creature_card):
                profile.add_signal(Signal(
                    id="SELF_ATTACK_TRIGGER",
                    label="Triggers when THIS creature attacks (own engine, not a theme)",
                    kind=EvidenceKind.RULE_RELATION,
                    confidence=Confidence.STRONG,
                    timing="triggered",
                    trace=Trace(rule_id="content.trigger.self_attack.v1", rule_version="1.0",
                                matched_text=family, span=None,
                                note="Only the card's own attack triggers it — an engine event, not an attack-triggers theme."),
                ))
                continue
        profile.add_signal(Signal(
            id=f"TRIGGER_{family.upper()}",
            label=f"Triggers on: {family}",
            kind=EvidenceKind.RULE_RELATION,
            confidence=Confidence.STRONG,
            timing="triggered",
            trace=Trace(rule_id=f"content.trigger.{family}.v1", rule_version="1.0",
                        matched_text=family, span=None,
                        note=f"Ability triggers on the '{family}' event family."),
        ))


def detect_scaling(text: str, profile: CardProfile) -> None:
    """Emit SCALES_WITH signals: reuse oracle_hooks for-each/number-of, plus power/toughness."""
    if not text:
        return
    for ref in extract_scaling(text):
        profile.add_signal(Signal(
            id="SCALES_WITH",
            label=f"Scales with: {ref}",
            kind=EvidenceKind.RULE_RELATION,
            confidence=Confidence.LIKELY,
            trace=Trace(rule_id="content.scaling.count.v1", rule_version="1.0",
                        matched_text=ref, span=None,
                        note=f"Effect scales with the count/quantity of '{ref}'."),
        ))
    low = text.lower()
    for pattern, ref_fmt in _PT_SCALING:
        for m in re.finditer(pattern, low):
            axis = m.group(1)
            profile.add_signal(Signal(
                id="SCALES_WITH",
                label=f"Scales with: {ref_fmt.format(axis)}",
                kind=EvidenceKind.RULE_RELATION,
                confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.scaling.pt.v1", rule_version="1.0",
                            matched_text=m.group(0), span=m.span(),
                            note=f"Value scales with a creature's {axis} (rewards high-{axis} creatures)."),
            ))


def detect_tribal(text: str, profile: CardProfile) -> None:
    """Emit TRIBAL_<TYPE> signals for referenced creature types (generalizes scope to subtypes)."""
    if not text:
        return
    low = text.lower()
    seen = set()
    for pattern in _TRIBAL_PATTERNS:
        for m in re.finditer(pattern, low):
            word = m.group(1).rstrip("s")
            # Negation guard: "non-Human creatures you control" must NOT read as Human tribal
            # (Mikaeus HATES humans). Check the character(s) immediately before the match.
            pre = low[max(0, m.start(1) - 4):m.start(1)]
            if pre.endswith("non-") or pre.endswith("non "):
                continue
            if word in _CREATURE_TYPES and word not in seen:
                seen.add(word)
                profile.add_signal(Signal(
                    id=f"TRIBAL_{word.upper()}",
                    label=f"Tribal: cares about {word.capitalize()}s",
                    kind=EvidenceKind.RULE_RELATION,
                    confidence=Confidence.LIKELY,
                    trace=Trace(rule_id="content.tribal.v1", rule_version="1.0",
                                matched_text=m.group(0), span=m.span(),
                                note=f"References the {word.capitalize()} creature type (tribal synergy)."),
                ))
                profile.add_tag(f"{word.capitalize()} Tribal", profile.signals[-1].trace)


def detect_keywords(text: str, profile: CardProfile, type_line: str = "") -> None:
    """Detect a few archetype-defining keywords/types the tag vocab doesn't cleanly surface:
    evoke (self-sacrifice value / ETB fuel) and Vehicle/crew (Vehicles archetype)."""
    low = (text or "").lower()
    tline = (type_line or "").lower()

    if re.search(r"\bevoke\b", low):
        profile.add_signal(Signal(
            id="EVOKE", label="Evoke (alternative sac cost)", kind=EvidenceKind.RULE_RELATION,
            confidence=Confidence.EXACT,
            trace=Trace(rule_id="content.evoke.v1", rule_version="1.0",
                        matched_text="evoke", span=None,
                        note="Evoke: can be cast for a cost then sacrificed — ETB fuel / self-sacrifice value."),
        ))
        profile.add_tag("Evoke", profile.signals[-1].trace)

    if "vehicle" in tline or re.search(r"\bcrew \d+", low):
        profile.add_signal(Signal(
            id="VEHICLE", label="Vehicle / crew", kind=EvidenceKind.RULE_RELATION,
            confidence=Confidence.EXACT,
            trace=Trace(rule_id="content.vehicle.v1", rule_version="1.0",
                        matched_text="vehicle" if "vehicle" in tline else "crew",
                        span=None, note="Vehicle (needs crew) — Vehicles archetype."),
        ))
        profile.add_tag("Vehicles", profile.signals[-1].trace)

    # Tax / stax: effects that make spells cost more (e.g. Saga chapters, prison pieces).
    # Direction matters (batch-13 GAAIV finding): a GENERAL tax ("spells your opponents
    # cast cost {1} more" — GAAIV, Thalia) is a prison plan and defines Stax. A tax
    # CONDITIONAL ON TARGETING ("spells that target a Merfolk you control cost {2} more" —
    # the Kopala/Charix/Esior class) is a protection effect, not stax; giving it a Stax
    # high band would be the Erebos CW class (one hate line != a prison plan). Measured
    # over all commanders: 5 general taxers vs 6 targeting/protection taxers (incl.
    # Hinata's per-target tax, whose real plan is spellslinger).
    for _tax_line in low.split("\n"):
        if not (re.search(r"cost (?:\{\d+\}|\d+|one|two|three) (?:or more )?more to cast", _tax_line)
                or re.search(r"spells? cost .* more", _tax_line)):
            continue
        if "target" in _tax_line:
            profile.add_signal(Signal(
                id="TARGETED_TAX", label="Targeting tax (protection)",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                polarity=Polarity.RESTRICTIVE,
                trace=Trace(rule_id="content.tax.v2", rule_version="2.0",
                            matched_text=_tax_line.strip()[:80], span=None,
                            note="Tax conditional on targeting — protects your permanents; not a prison plan."),
            ))
            profile.add_tag("Protection", profile.signals[-1].trace)
        else:
            profile.add_signal(Signal(
                id="TAX_COST_INCREASE", label="Tax (spells cost more)",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                polarity=Polarity.RESTRICTIVE,
                trace=Trace(rule_id="content.tax.v2", rule_version="2.0",
                            matched_text=_tax_line.strip()[:80], span=None,
                            note="Increases opponents' (or all) casting costs — a tax/stax effect."),
            ))
            profile.add_tag("Stax", profile.signals[-1].trace)
        break  # one tax signal is enough

    # Legendary-matters: oracle references legendary permanents/spells as a synergy payoff
    # (not just the card being legendary itself, which lives in the type line).
    _legendary_patterns = [
        r"legendary creatures? you control",
        r"legendary permanents? you control",
        r"another legendary",
        r"each legendary",
        r"number of legendary",
        r"cast a legendary",
        r"legendary (?:creature )?spell",
        r"target legendary",
    ]
    for pat in _legendary_patterns:
        m = re.search(pat, low)
        if m:
            profile.add_signal(Signal(
                id="LEGENDARY_MATTERS", label="Legendary matters",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.legendary.v1", rule_version="1.0",
                            matched_text=m.group(0), span=m.span(),
                            note="References legendary permanents/spells as a synergy payoff."),
            ))
            profile.add_tag("Legendary Matters", profile.signals[-1].trace)
            break

    # Monarch: granting/claiming the crown is a politics plan (batch-14 Queen Marchesa
    # finding — 'you become the monarch' read nothing while her deterrent token read Go
    # Wide). Measured: ~60 cards / 13 commanders, all monarch-politics builds (Queen
    # Marchesa, Jared Carthalion, Aragorn King of Gondor).
    m = re.search(r"becomes? the monarch", low)
    if m:
        profile.add_signal(Signal(
            id="MONARCH", label="Monarch (crown politics)",
            kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
            trace=Trace(rule_id="content.monarch.v1", rule_version="1.0",
                        matched_text=m.group(0), span=m.span(),
                        note="Becoming/granting the monarch — politics + recurring card advantage."),
        ))
        profile.add_tag("Monarch", profile.signals[-1].trace)


# Clause-level repeat markers: a recurring trigger, a scheduled trigger, or an activated
# ability (cost ":" effect). Planeswalker loyalty: only PLUS/0 activations count as repeat
# markers — they fire every turn indefinitely. A MINUS ability consumes loyalty (self-
# limiting; a big minus is once-per-game), so its token creation is a finisher, not an
# engine — the batch-13 CW was Lord Windgrace's −11 (six Cats) reading Go Wide: high.
# Measured against the DB: 53 plus/0 loyalty token-makers keep firing, 81 minus stop.
_REPEAT_MARKERS = ("whenever", "at the beginning of")
_ACTIVATED_RE = re.compile(r"(?:\}\s*:|^(?:\+\d+|0)\s*:|\btap\b[^:]*:)", re.IGNORECASE | re.MULTILINE)
# Tokens handed to OPPONENTS are a downside/political effect, not your engine.
# "target opponent creates" (batch #18 CW: Phelddagrif's Hippo gifts read Go Wide) —
# measured 23, all opponent-gifts (Hunted cycle, Clackbridge Troll, Forbidden Orchard).
# "target player creates" deliberately NOT added: usually self-targeted modal support
# (Dark Salvation creates YOUR Zombies).
_OPPONENT_TOKEN_RE = re.compile(r"(?:that player|each opponent|an opponent|target opponent|defending player)\s+creates", re.IGNORECASE)


def detect_repeatable_token_making(text: str, profile: CardProfile) -> None:
    """Emit REPEATABLE_TOKEN_MAKER only when BOTH conditions hold in the SAME clause:
    a repeatability marker (recurring/scheduled trigger or activated ability) AND token
    creation. This is the conjunction the substring tag vocabulary cannot express — it
    over-matched cards like Gonti (combat-damage trigger, no tokens) and under-matched
    others. Clause = one oracle line/sentence."""
    if not text:
        return
    # Clause = one oracle LINE. Each ability is one line in oracle text; sentences within a
    # line belong to the same ability (e.g. "{T}: Draw a card. Create a token." is ONE
    # activated ability), so splitting by sentence would break the conjunction.
    # Modal BULLETS (batch #23 Caesar gap) belong to their header ability: "Whenever you
    # attack ... choose two —" + "• Create two 1/1 ... tokens" is ONE ability, so bullet
    # lines are merged into the preceding header line before the conjunction check.
    raw_lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    clauses = []
    for ln in raw_lines:
        if ln.startswith("•") and clauses:
            clauses[-1] = clauses[-1] + " " + ln
        else:
            clauses.append(ln)

    for clause in clauses:
        low = clause.lower()
        creates_token = "create" in low and "token" in low
        if not creates_token:
            continue
        if _OPPONENT_TOKEN_RE.search(low):
            continue  # gives the token to an opponent — not your engine
        # Ephemeral tokens (encore/embalm-haste style): the SAME clause sacrifices or exiles
        # them at the next end step — a temporary strike force, not a standing army.
        if ("at the beginning of the next end step" in low and ("sacrifice" in low or "exile" in low))            or "exile those tokens" in low:
            continue
        # Deterrent / catch-up tokens (batch-14 Queen Marchesa CW): creation CONDITIONED on
        # an opponent-state ("if an opponent is the monarch / controls more lands than you",
        # "if you have less life") is insurance or a punishment rider, not an army plan.
        # Measured: 15 cards, all parity/catch-up effects (Beza, Linvala, Sunset Revelry).
        if re.search(r"if an opponent|unless an opponent|if you have (?:less|fewer)|if you control fewer", low):
            continue
        repeatable = any(m in low for m in _REPEAT_MARKERS) or bool(_ACTIVATED_RE.search(clause))
        if not repeatable:
            continue
        # Classify WHAT is created: value tokens (Treasure/Clue/Food/...) are ramp/resources,
        # not an army — repeatably making them must NOT read as Go Wide (a Treasure commander
        # is a value engine, not a token-swarm deck).
        _value_kinds = ("treasure", "clue", "food", "blood", "gold", "powerstone", "map",
                        "junk", "incubator")
        makes_value = any(f"{k} token" in low for k in _value_kinds)
        makes_creature = "creature token" in low
        # Utility bodies (0/X: Eggs, Walls) are sacrifice fodder / blockers, not an army.
        # EXCEPT the counter-body class (batch #15 Zaxara gap): a 0/0 token that gets
        # +1/+1 counters in the same clause is a real (often huge) body, not fodder —
        # measured 30 cards, all genuine (the Fractal cycle, Zaxara's Hydras, Gimbal's
        # Gremlins); the 184 true-fodder makers (Eggs, Walls) don't put counters on it.
        import re as _re
        gets_counters = _re.search(r"\+1/\+1 counters? on (?:it|them|each)", low)
        if makes_creature and _re.search(r"create[^.]*?\b0/\d", low) and not gets_counters:
            profile.add_signal(Signal(
                id="UTILITY_TOKEN_MAKER", label="Repeatable utility-token production (0/X fodder)",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.repeatable_tokens.v3", rule_version="3.0",
                            matched_text=clause[:80], span=None,
                            note="0/X tokens are fodder/blockers, not go-wide pressure."),
            ))
            profile.add_tag("Utility Tokens", profile.signals[-1].trace)
            return
        # Noncreature, non-value tokens (Aura "Mask", Equipment, Shard...) are neither an army
        # nor a resource engine — they must not reach the Go Wide branch by default.
        import re as _re2
        has_pt_token = bool(_re2.search(r"\d+/\d+[^.]*token", low))
        if not makes_creature and not makes_value and not has_pt_token:
            continue
        if makes_value and not makes_creature:
            profile.add_signal(Signal(
                id="REPEATABLE_VALUE_TOKENS",
                label="Repeatable value-token production (Treasure/Clue/Food/...)",
                kind=EvidenceKind.RULE_RELATION,
                confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.repeatable_tokens.v2", rule_version="2.0",
                            matched_text=clause[:80], span=None,
                            note="Recurring noncreature value tokens: resource engine, not go-wide."),
            ))
            profile.add_tag("Value Tokens", profile.signals[-1].trace)
        else:
            profile.add_signal(Signal(
                id="REPEATABLE_TOKEN_MAKER",
                label="Repeatable token production",
                kind=EvidenceKind.RULE_RELATION,
                confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.repeatable_tokens.v1", rule_version="1.0",
                            matched_text=clause[:80], span=None,
                            note="Recurring trigger or activated ability that creates tokens in the same clause."),
            ))
            profile.add_tag("Repeatable Tokens", profile.signals[-1].trace)
        return  # one signal is enough


_GY_COPY_IT_RE = re.compile(r"\bcopy (it|them|that card)\b")
_GY_KEYWORD_RE = re.compile(r"\bembalm\b|\beternalize\b")


def detect_graveyard_clone(text: str, profile: CardProfile) -> None:
    """GRAVEYARD_CLONE: copying/recasting cards OUT of a graveyard (batch-16 Feldon/
    Mimeoplasm finding). The class is a CONJUNCTION the substring vocabulary cannot
    express safely — 'copy of' alone catches library/battlefield clones, 'from a
    graveyard' alone is the over-broad phrase graveyard_recast deliberately avoids.
    Matching runs on RULES text (reminder text stripped — the batch-14 lesson: Volo's
    '(A copy of a creature spell becomes a token.)' reminder next to a NEGATIVE graveyard
    condition read a false Graveyard Value high). Two compensations, both measured:
    embalm/eternalize keywords ARE graveyard clones by rule (their copy semantics live
    only in reminder text), and the directional 'from ... graveyard ... copy it/them/that
    card' recast form (Kaervek/Nashi/Shiko class). Re-measured against the DB: 112 cards,
    all genuine graveyard value; 7 reminder-text false positives dropped (Volo, Joo Dee,
    Deepfathom Echo...), 20 genuine recasters gained (Mizzix's Mastery, Wildfire Devils...)."""
    if not text:
        return
    for line in text.split("\n"):
        low = re.sub(r"\([^)]*\)", "", line.lower())
        is_keyword_clone = bool(_GY_KEYWORD_RE.search(low))
        is_rules_clone = "graveyard" in low and (
            "copy of" in low or "copies of" in low or _GY_COPY_IT_RE.search(low))
        if is_keyword_clone or is_rules_clone:
            profile.add_signal(Signal(
                id="GRAVEYARD_CLONE", label="Clones/recasts cards from a graveyard",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.graveyard_clone.v1", rule_version="1.0",
                            matched_text=low.strip()[:80], span=None,
                            note="Graveyard + copy in one ability line — graveyard-fueled value engine."),
            ))
            profile.add_tag("Graveyard Clone", profile.signals[-1].trace)
            return


# Trigger doublers: cards that make OTHER triggered abilities trigger additional times
# (Isshin, Panharmonicon, Yarok). The doubler's CONDITION tells us which archetype it feeds:
# doubling attack triggers defines an attack-triggers deck; doubling ETB triggers feeds ETB value.
_DOUBLER_RE = re.compile(r"triggers? an additional time|causes a triggered ability", re.IGNORECASE)


def detect_trigger_doubler(text: str, profile: CardProfile) -> None:
    if not text:
        return
    for line in text.split("\n"):
        low = line.lower()
        m = _DOUBLER_RE.search(low)
        if not m:
            continue
        profile.add_signal(Signal(
            id="TRIGGER_DOUBLER", label="Doubles triggered abilities",
            kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
            trace=Trace(rule_id="content.trigger_doubler.v1", rule_version="1.0",
                        matched_text=m.group(0), span=None,
                        note="Makes triggered abilities trigger additional times (trigger doubler)."),
        ))
        # Context: WHICH triggers does it double? Same line tells us.
        if "attack" in low:
            profile.add_signal(Signal(
                id="DOUBLES_ATTACK_TRIGGERS", label="Doubles attack triggers",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.trigger_doubler.attack.v1", rule_version="1.0",
                            matched_text=line.strip()[:80], span=None,
                            note="Doubler conditioned on attacking — defines an attack-triggers deck."),
            ))
        if "dying" in low or "dies" in low:
            profile.add_signal(Signal(
                id="DOUBLES_DEATH_TRIGGERS", label="Doubles death triggers",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.trigger_doubler.death.v1", rule_version="1.0",
                            matched_text=line.strip()[:80], span=None,
                            note="Doubler conditioned on dying — defines an aristocrats deck."),
            ))
        if "enter" in low:
            profile.add_signal(Signal(
                id="DOUBLES_ETB_TRIGGERS", label="Doubles enter-the-battlefield triggers",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.trigger_doubler.etb.v1", rule_version="1.0",
                            matched_text=line.strip()[:80], span=None,
                            note="Doubler conditioned on entering — feeds ETB value/blink."),
            ))
        return


# Modal toolbox: a card whose structure IS the signal — 4+ separate activated abilities
# (a menu of modes, e.g. Kenrith, Cromat). Any single mode's archetype evidence is an OPTION
# the deck can lean into, not the card's theme; the agent should align the chosen mode with
# the user's requested direction.
_ACTIVATED_LINE_RE = re.compile(r"^\{[^}]+\}[^:]*:", re.MULTILINE)


def detect_modal_structure(text: str, profile: CardProfile) -> None:
    if not text:
        return
    n = len(_ACTIVATED_LINE_RE.findall(text))
    if n >= 4:
        profile.add_signal(Signal(
            id="MODAL_TOOLBOX", label=f"Modal toolbox ({n} activated abilities)",
            kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
            trace=Trace(rule_id="content.modal_toolbox.v1", rule_version="1.0",
                        matched_text=f"{n} activated-ability lines", span=None,
                        note="4+ separate activated abilities: a menu of modes, not one theme."),
        ))
        profile.add_tag("Toolbox", profile.signals[-1].trace)


# Sacrifice outlets: "Sacrifice a/an/another <thing>:" as an ACTIVATION COST. The sacrificed
# type varies (creature, Goblin, artifact, ...), so this is a regex rule, not vocabulary.
_SAC_OUTLET_RE = re.compile(r"sacrifice (?:a|an|another|any number of|two|three)?\s*[\w' ]{1,25}?\s*:",
                            re.IGNORECASE)


def detect_sac_outlet(text: str, profile: CardProfile) -> None:
    if not text:
        return
    m = _SAC_OUTLET_RE.search(text)
    if m:
        profile.add_signal(Signal(
            id="SAC_OUTLET", label="Sacrifice outlet (sac as a cost)",
            kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
            trace=Trace(rule_id="content.sac_outlet.v1", rule_version="1.0",
                        matched_text=m.group(0)[:60], span=m.span(),
                        note="Sacrificing as an activation cost — repeatable aristocrats enabler."),
        ))
        profile.add_tag("Sacrifice Outlet", profile.signals[-1].trace)


# Lost-life payoff: cards that REWARD opponents having lost life this turn (Sygg, Bloodchief
# Ascension, the spectacle cycle). The threshold variant ("lost 3 or more life this turn") makes
# this a variable-number class the substring vocabulary cannot enumerate (the SAC_OUTLET lesson);
# the naked "or more life this turn" phrase measured dirty (catches lifeGAIN payoffs — Angelic
# Accord class). Measured against the DB: 40 cards, all genuine lost-life payoffs; the
# player-scoped forms only ("you've lost life" self-payoffs deliberately excluded).
_LOST_LIFE_PAYOFF_RE = re.compile(
    r"(an opponent|a player|each opponent|each player) lost (\d+ or more )?life this turn",
    re.IGNORECASE)


def detect_lost_life_payoff(text: str, profile: CardProfile) -> None:
    if not text:
        return
    m = _LOST_LIFE_PAYOFF_RE.search(text)
    if m:
        profile.add_signal(Signal(
            id="LOST_LIFE_PAYOFF", label="Rewards opponents' life loss",
            kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
            trace=Trace(rule_id="content.lost_life_payoff.v1", rule_version="1.0",
                        matched_text=m.group(0)[:60], span=m.span(),
                        note="Payoff conditioned on an opponent having lost life this turn — a lifeloss-matters plan."),
        ))
        profile.add_tag("Lost-Life Payoff", profile.signals[-1].trace)


# Theft-by-exile: exiling cards from an OPPONENT'S zone and letting YOU play/cast them
# (Elder Brain, Gonti-class impulse theft, Stolen Strategy). A conjunction with two
# direction traps the substring vocabulary cannot express: the exiled zone must be an
# opponent's (not your own impulse draw — Colfenor's Plans class), and the player given
# access must be YOU (not the owner — Elkin Lair/Lightstall giveaway class, killed by
# requiring 'you may play/cast'; 'you own' excluded for the Triple Triad self-play form).
# Order-free within the line: Gonti's zone comes BEFORE the exile verb ('top four cards
# of target opponent's library, exile one of them'). Reminder text stripped (Kaervek's
# crime reminder says 'their graveyards' while he recasts his OWN). Measured against
# the DB: 97 cards, all genuine you-play-theirs theft.
_THEFT_EXILE_ZONE_RE = re.compile(
    r"that player's hand|opponent's hand|that player's library|opponent's library"
    r"|their library|their hand|opponent's graveyard|their graveyards?"
    r"|each player's library|each player's hand")
_THEFT_EXILE_PLAY_RE = re.compile(r"\byou may (play|cast)\b")
_THEFT_TOPDECK_ZONE_RE = re.compile(
    r"top cards? of (their|that player's|each player's|target opponent's"
    r"|an opponent's|each opponent's) librar(y|ies)")


def detect_theft_exile(text: str, profile: CardProfile) -> None:
    if not text:
        return
    for line in text.split("\n"):
        low = re.sub(r"\([^)]*\)", "", line.lower())
        if ("exile" in low and _THEFT_EXILE_ZONE_RE.search(low)
                and _THEFT_EXILE_PLAY_RE.search(low) and "you own" not in low):
            profile.add_signal(Signal(
                id="THEFT_EXILE", label="Plays opponents' cards via exile",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.theft_exile.v1", rule_version="1.0",
                            matched_text=low.strip()[:60], span=None,
                            note="Exiles from an opponent's zone and YOU may play/cast it — impulse theft."),
            ))
            profile.add_tag("Theft (exile)", profile.signals[-1].trace)
            return
    # Top-of-library form (the Xanathar class, batch #17 gap): "you may play the top
    # card of their library" grants YOU access to an opponent's topdeck with no exile
    # involved. Same-line conjunction: opponent-zone top card + "you may play/cast".
    # Measured against the DB: 37 cards, all genuine you-play-theirs (Xanathar, Gonti
    # Canny Acquisitor, Grenzo Havoc Raiser, Ragavan, Etali, Daxos of Meletis...).
    for line in text.split("\n"):
        low = re.sub(r"\([^)]*\)", "", line.lower())
        if (_THEFT_TOPDECK_ZONE_RE.search(low)
                and _THEFT_EXILE_PLAY_RE.search(low) and "you own" not in low):
            profile.add_signal(Signal(
                id="THEFT_TOPDECK", label="Plays opponents' topdeck",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.theft_topdeck.v1", rule_version="1.0",
                            matched_text=low.strip()[:60], span=None,
                            note="Grants YOU play/cast access to an opponent's top card — topdeck theft."),
            ))
            profile.add_tag("Theft (topdeck)", profile.signals[-1].trace)
            break
    # Multi-line form (the Nightveil Specter class): the exile trigger sits on one line
    # ("deals combat damage ... that player exiles the top card of their library") and
    # the play permission on another ("You may play cards exiled with ~"). Card-level
    # conjunction: an opponent-zone exile line AND an 'exiled with' play-permission line.
    # This replaces the theft tag's naked "exiled with" phrase, which measured dirty
    # (191 cards: ~76 own-card impulse like Colfenor's Plans, ~77 O-Ring removal).
    # Measured against the DB: 12 cards, all genuine you-play-theirs (Nightveil Specter,
    # Jeleva, Kheru Mind-Eater, Muse Vessel, Court of Locthwain, Valki//Tibalt...).
    whole = re.sub(r"\([^)]*\)", "", text.lower())
    if "you own" in whole:
        return
    lines = whole.split("\n")
    has_opp_exile = any(
        "exile" in l and _THEFT_EXILE_ZONE_RE.search(l) for l in lines)
    has_play_exiled_with = any(
        "exiled with" in l
        and (_THEFT_EXILE_PLAY_RE.search(l) or "play lands and cast spells" in l
             or "may be cast" in l)
        for l in lines)
    if has_opp_exile and has_play_exiled_with:
        profile.add_signal(Signal(
            id="THEFT_EXILE", label="Plays opponents' cards via exile",
            kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
            trace=Trace(rule_id="content.theft_exile.v2", rule_version="1.0",
                        matched_text="exiled with (multi-line)", span=None,
                        note="Exiles from an opponent's zone on one line, plays the exiled cards on another — the Nightveil Specter class."),
        ))
        profile.add_tag("Theft (exile)", profile.signals[-1].trace)


# Conditional cast-rider (batch #22, the Raggadragga+Hallar class — 23 measured): a
# "whenever you cast a spell, IF <rider>" trigger targets whatever the rider names
# (mana thresholds, kicked, bargained, treasure-mana), NOT generic spell density —
# so the spell_payoff comma-form hit must demote from Spellslinger defining. Riders
# that name instant/sorcery/noncreature spells (Alania's "first instant spell") keep
# the genuine spellslinger read.
_CAST_RIDER_RE = re.compile(r"whenever you cast a spell, if ([^.]{0,80})")


def detect_conditional_cast_rider(text: str, profile: CardProfile) -> None:
    if not text:
        return
    for line in text.lower().split("\n"):
        m = _CAST_RIDER_RE.search(line)
        if m and not re.search(r"instant|sorcery|noncreature", m.group(1)):
            profile.add_signal(Signal(
                id="CONDITIONAL_CAST_RIDER",
                label="Cast trigger gated by a non-spell-type rider",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.cast_rider.v1", rule_version="1.0",
                            matched_text=m.group(0)[:70], span=None,
                            note="The 'if <rider>' condition retargets the payoff (big mana / kicker / bargain...) — not generic spellslinger density."),
            ))
            return


# Exile-mill (the Circu class, batch #18 known-gap closed in the pre-build fix round):
# exiling the top of a TARGETED player's library is library attrition — mill by another
# zone. The conjunction needs a NEGATIVE condition the tag vocabulary cannot express:
# the same family with a play permission is impulse THEFT (Gonti/Etali), and the
# each-player forms are dominated by theft/hug (Pako, Share the Spoils). Measured:
# 4 cards, all genuine (Ashiok, Circu, Scrib Nibblers, Mindreaver).
_EXILE_MILL_RE = re.compile(
    r"exile the top .{0,25}cards? of target (player|opponent)")
_EXILE_MILL_PLAY_RE = re.compile(r"may play|may cast|may be cast|may look")


def detect_exile_mill(text: str, profile: CardProfile) -> None:
    if not text:
        return
    low = re.sub(r"\([^)]*\)", "", text.lower())
    if _EXILE_MILL_PLAY_RE.search(low):
        return  # access granted somewhere on the card: theft, not mill
    for line in low.split("\n"):
        if _EXILE_MILL_RE.search(line):
            profile.add_signal(Signal(
                id="EXILE_MILL", label="Exiles opponents' library top (mill by exile)",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.exile_mill.v1", rule_version="1.0",
                            matched_text=line.strip()[:60], span=None,
                            note="Targeted top-of-library exile with NO play permission — library attrition, not impulse theft."),
            ))
            profile.add_tag("Mill (exile)", profile.signals[-1].trace)
            return


# Graveyard-count scaling: effects sized by how many cards sit in YOUR graveyard (the
# Lhurgoyf/Undergrowth class — P/T, damage, life, counters "equal to the number of ...
# in your graveyard"). A conjunction the substring vocabulary cannot express safely:
# "in your graveyard" alone is the over-broad phrase graveyard_recast avoids. Measured
# against the DB: 46 cards, all genuine graveyard-count payoffs (Boneyard Wurm,
# Splinterfright, Old Stickfingers, Nethergoyf, Haughty Djinn...).
_GRAVEYARD_SCALING_RE = re.compile(
    r"equal to (?:the number of|twice the number of) [^.]{0,40}in your graveyard",
    re.IGNORECASE)


def detect_graveyard_scaling(text: str, profile: CardProfile) -> None:
    if not text:
        return
    m = _GRAVEYARD_SCALING_RE.search(text)
    if m:
        profile.add_signal(Signal(
            id="GRAVEYARD_SCALING", label="Scales with your graveyard size",
            kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
            trace=Trace(rule_id="content.graveyard_scaling.v1", rule_version="1.0",
                        matched_text=m.group(0)[:60], span=m.span(),
                        note="Effect sized by cards in your graveyard — wants the yard stocked."),
        ))
        profile.add_tag("Graveyard Scaling", profile.signals[-1].trace)


# Control-change direction: "gain control" can be THEFT (you take theirs) or DONATION (you give
# yours away, Zedruu-style). Substring vocabulary cannot express the direction, so this detector
# reads WHO gains control in the same line.
_GAIN_CONTROL_RE = re.compile(r"gains? control", re.IGNORECASE)
_DONATION_RE = re.compile(r"(?:target |an )?(?:opponent|that player|another player)s?\s+gains? control",
                          re.IGNORECASE)


def detect_control_change(text: str, profile: CardProfile) -> None:
    if not text:
        return
    for line in text.split("\n"):
        low = line.lower()
        # Theft by acquisition: an OPPONENT's card ends up under YOUR control (Tergrid-style:
        # "whenever an opponent sacrifices ... put that card ... under your control"). The
        # conjunction (opponent event + under your control, same line) is what vocabulary
        # substrings cannot express.
        if "opponent" in low and "under your control" in low:
            profile.add_signal(Signal(
                id="THEFT_CONTROL", label="Takes control of opponents' permanents",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.control_change.acquire.v1", rule_version="1.0",
                            matched_text=line.strip()[:70], span=None,
                            note="An opponent's card ends up under YOUR control — theft."),
            ))
            profile.add_tag("Theft", profile.signals[-1].trace)
            return
        m = _GAIN_CONTROL_RE.search(line)
        if not m:
            continue
        if _DONATION_RE.search(line):
            profile.add_signal(Signal(
                id="DONATION", label="Gives own permanents to opponents",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.control_change.donation.v1", rule_version="1.0",
                            matched_text=line.strip()[:70], span=None,
                            note="An OPPONENT gains control — donation/politics, the reverse of theft."),
            ))
            profile.add_tag("Donation", profile.signals[-1].trace)
        else:
            profile.add_signal(Signal(
                id="THEFT_CONTROL", label="Takes control of opponents' permanents",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.control_change.theft.v1", rule_version="1.0",
                            matched_text=line.strip()[:70], span=None,
                            note="You gain control — theft."),
            ))
            profile.add_tag("Theft", profile.signals[-1].trace)
        return


# Big-power matters ("power 4 or greater"): a stompy signal ONLY in a positive/synergy context
# (your creatures, cost reduction, pumps). Removal that targets big creatures ("destroy target
# creature with power 4 or greater") mentions the same phrase and must NOT read as stompy.
_POWER_MATTERS_RE = re.compile(r"power [3-9] or greater|power (?:is )?greater than|x is (?:that creature's|its) power|greatest power among", re.IGNORECASE)
_POWER_POSITIVE_RE = re.compile(r"you control|you cast|cost \{?\d|gets? \+|gains?|draw a card|add ", re.IGNORECASE)
_POWER_REMOVAL_RE = re.compile(r"destroy|exile|deals damage to target|fights", re.IGNORECASE)


def detect_power_matters(text: str, profile: CardProfile) -> None:
    if not text:
        return
    for line in text.split("\n"):
        m = _POWER_MATTERS_RE.search(line)
        if not m:
            continue
        if _POWER_REMOVAL_RE.search(line) and not _POWER_POSITIVE_RE.search(line):
            continue  # anti-big removal, not stompy
        if _POWER_POSITIVE_RE.search(line):
            profile.add_signal(Signal(
                id="POWER_MATTERS", label="Big power matters (stompy)",
                kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
                trace=Trace(rule_id="content.power_matters.v1", rule_version="1.0",
                            matched_text=m.group(0), span=None,
                            note="Rewards big-power creatures you control/cast — stompy."),
            ))
            profile.add_tag("Stompy", profile.signals[-1].trace)
            return


# --- Provides detectors (M2-prep): signals the category-counts scorer will consume when it
# migrates off its own oracle heuristics. These are PROVIDES, not archetypes — no bucket.
_TUTOR_ANY_RE = re.compile(r"search your library for a card\b", re.IGNORECASE)
_TUTOR_COND_RE = re.compile(r"search your library for (?:an?|up to)\s+(?!card\b)", re.IGNORECASE)
_MANA_ABILITY_RE = re.compile(r"\{t\}: add ", re.IGNORECASE)


def detect_provides(text: str, profile: CardProfile) -> None:
    if not text:
        return
    low = text.lower()
    if _TUTOR_ANY_RE.search(low):
        profile.add_signal(Signal(
            id="TUTOR_UNCONDITIONAL", label="Unconditional tutor (any card)",
            kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
            trace=Trace(rule_id="content.provides.tutor.v1", rule_version="1.0",
                        matched_text="search your library for a card", span=None,
                        note="Provides: tutors (strong)."),
        ))
    elif _TUTOR_COND_RE.search(low):
        profile.add_signal(Signal(
            id="TUTOR_CONDITIONAL", label="Conditional tutor (restricted card class)",
            kind=EvidenceKind.RULE_RELATION, confidence=Confidence.LIKELY,
            trace=Trace(rule_id="content.provides.tutor.v1", rule_version="1.0",
                        matched_text="search your library for a <class>", span=None,
                        note="Provides: tutors (restricted)."),
        ))
    m = _MANA_ABILITY_RE.search(low)
    if m:
        profile.add_signal(Signal(
            id="MANA_ABILITY", label="Tap-for-mana ability",
            kind=EvidenceKind.RULE_RELATION, confidence=Confidence.STRONG,
            trace=Trace(rule_id="content.provides.mana.v1", rule_version="1.0",
                        matched_text=m.group(0)[:40], span=m.span(),
                        note="Provides: ramp/mana production."),
        ))
