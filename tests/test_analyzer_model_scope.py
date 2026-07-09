"""Tests for the parallel universal analyzer: data model + scope layer.
Pure-logic tests against hardcoded oracle text — no DB required."""
from mtgcli.analyzer.model import (
    CardProfile, Signal, Trace, EvidenceKind, Confidence, Polarity,
    NegativeAssertion, ANALYZER_SCHEMA_VERSION,
)
from mtgcli.analyzer.scope import detect_scope, dominant_symmetry


# ── data model ────────────────────────────────────────────────────────────────

def _sig(id="X", **kw):
    tr = Trace(rule_id="r.v1", rule_version="1.0", matched_text="x", note="n")
    return Signal(id=id, label="l", kind=EvidenceKind.FACT, confidence=Confidence.STRONG, trace=tr, **kw)


def test_profile_serializes_round_trip():
    p = CardProfile(name="Test")
    p.add_signal(_sig("A"))
    p.add_tag("Evasion", p.signals[0].trace)
    p.negative_assertions.append(NegativeAssertion(claim="No draw", confidence=Confidence.LIKELY, basis="no pattern"))
    d = p.to_dict()
    assert d["name"] == "Test"
    assert d["schema_version"] == ANALYZER_SCHEMA_VERSION
    assert d["signals"][0]["id"] == "A"
    assert d["signals"][0]["confidence"] == "strong"
    assert "Evasion" in d["tags"]
    assert d["negative_assertions"][0]["claim"] == "No draw"
    # no scores anywhere in the model
    assert "score" not in str(d).lower()


def test_confidence_is_ordinal_not_decimal():
    assert Confidence.EXACT.rank > Confidence.STRONG.rank > Confidence.WEAK.rank


def test_has_signal_helpers():
    p = CardProfile(name="T")
    p.add_signal(_sig("DIES"))
    assert p.has_signal("DIES") and not p.has_signal("DRAW")


# ── scope layer: the generalized GF-1 fix ─────────────────────────────────────

def _profile_for(text):
    p = CardProfile(name="t")
    detect_scope(text, p)
    return p


def test_scope_gargos_targeted_single_not_punisher():
    # "fights up to one target creature you don't control" — targeted removal, NOT a punisher
    p = _profile_for("Whenever a creature you control becomes the target of a spell, "
                     "Gargos fights up to one target creature you don't control.")
    assert dominant_symmetry(p) != "asymmetric_opponents"


def test_scope_toxrill_mass_opponents_is_punisher():
    p = _profile_for("Creatures you don't control get -1/-1 for each slime counter on them.")
    assert dominant_symmetry(p) == "asymmetric_opponents"


def test_scope_symmetric_vs_onesided_wipe_distinguished():
    sym = _profile_for("Destroy each creature.")
    one = _profile_for("Destroy each creature you don't control.")
    assert dominant_symmetry(sym) == "symmetric"
    assert dominant_symmetry(one) == "asymmetric_opponents"


def test_scope_specific_not_swallowed_by_generic():
    # "creature you don't control" must not be re-claimed as a bare/symmetric scope
    p = _profile_for("Target creature you don't control gets -3/-3.")
    syms = {s.symmetry for s in p.signals}
    assert "asymmetric_opponents" in syms or "targeted_opponent" in syms
    assert "symmetric" not in syms


def test_scope_your_creatures_anthem_side():
    p = _profile_for("Creatures you control get +1/+1.")
    assert dominant_symmetry(p) == "asymmetric_self"


# ── timing / replacement layer ────────────────────────────────────────────────

from mtgcli.analyzer.timing import detect_replacement_effects, detect_timing, is_in_replacement_span


def _timed(text):
    p = CardProfile(name="t")
    detect_replacement_effects(text, p)
    detect_timing(text, p)
    return p


def test_timing_repeatable_vs_event_vs_scheduled():
    assert _timed("Whenever a creature dies, draw a card.").has_signal("REPEATABLE_TRIGGER")
    assert _timed("When this creature enters, draw a card.").has_signal("EVENT_TRIGGER")
    assert _timed("At the beginning of your upkeep, draw a card.").has_signal("SCHEDULED_TRIGGER")


def test_replacement_effect_detected_and_not_a_trigger():
    p = _timed("If a creature would die, exile it instead.")
    assert p.has_signal("REPLACEMENT_EFFECT")
    # the 'would die' clause must be inside the replacement span (so a death-trigger layer skips it)
    pos = "If a creature would die, exile it instead.".lower().index("would die")
    assert is_in_replacement_span(p, pos)


def test_optional_and_once_each_turn_flags():
    p = _timed("You may sacrifice a creature. This ability triggers only once each turn.")
    assert p.has_signal("OPTIONAL_EFFECT")
    assert any(s.optional for s in p.get_signals("OPTIONAL_EFFECT"))
    assert p.has_signal("ONCE_EACH_TURN_LIMIT")
    assert p.get_signals("ONCE_EACH_TURN_LIMIT")[0].polarity.value == "restrictive"


def test_real_card_rest_in_peace_has_replacement():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    repo = CardRepository(str(SQLITE_PATH))
    c = repo.get_card_by_exact_name("Rest in Peace")
    if not c:
        import pytest; pytest.skip("card not in DB")
    p = _timed(c["oracle_text"])
    assert p.has_signal("REPLACEMENT_EFFECT")


# ── semantics: negation polarity + counter verb/noun ──────────────────────────

from mtgcli.analyzer.semantics import detect_negation, detect_counter_sense


def _sem(text):
    p = CardProfile(name="t")
    detect_negation(text, p)
    detect_counter_sense(text, p)
    return p


def test_negation_positive_vs_negative():
    pos = _sem("This creature can't be blocked.")
    neg = _sem("Creatures your opponents control can't attack you unless they pay 2.")
    assert pos.has_signal("UNBLOCKABLE")
    assert pos.get_signals("UNBLOCKABLE")[0].polarity.value == "positive"
    assert neg.has_signal("ATTACK_RESTRICTION")
    assert neg.get_signals("ATTACK_RESTRICTION")[0].polarity.value == "negative"
    # can't-be-blocked must NOT be lumped with can't-attack
    assert not pos.has_signal("ATTACK_RESTRICTION")


def test_counter_verb_vs_noun():
    verb = _sem("Counter target spell.")
    noun = _sem("Put a +1/+1 counter on target creature.")
    assert verb.has_signal("COUNTERSPELL_INTERACTION") and "Counterspell" in verb.tags
    assert "Counters Matter" not in verb.tags
    assert noun.has_signal("COUNTER_MARKER") and "Counters Matter" in noun.tags
    assert "Counterspell" not in noun.tags


def test_named_counter_is_noun_sense():
    p = _sem("Put a slime counter on each creature you don't control.")
    assert p.has_signal("COUNTER_MARKER")          # slime counter is a marker, not a counterspell
    assert not p.has_signal("COUNTERSPELL_INTERACTION")


# ── structure: multi-face split + linked abilities ────────────────────────────

from mtgcli.analyzer.structure import (
    split_faces, is_multipart, mark_modal_flexibility, detect_linked_abilities,
)


def test_split_faces_mdfc():
    faces = split_faces("Spell side text.\n---\nThis land enters tapped.", "modal_dfc")
    assert len(faces) == 2
    assert faces[0].part_type == "front_face" and faces[1].part_type == "back_face"


def test_split_faces_adventure_and_single():
    adv = split_faces("Creature text.\n---\nAdventure text.", "adventure")
    assert [f.part_type for f in adv] == ["creature", "adventure"]
    one = split_faces("Just one face.", "normal")
    assert len(one) == 1 and one[0].part_type == "single"


def test_modal_flexibility_signal():
    p = CardProfile(name="t")
    faces = split_faces("A.\n---\nB.", "modal_dfc")
    mark_modal_flexibility(p, faces)
    assert p.has_signal("MODAL_FLEXIBILITY")
    assert p.get_signals("MODAL_FLEXIBILITY")[0].kind.value == "heuristic"


def test_linked_ability_conditional():
    p = CardProfile(name="t")
    detect_linked_abilities("Sacrifice a creature. If you do, draw two cards.", p)
    assert p.has_signal("LINKED_IF_YOU_DO")
    assert p.get_signals("LINKED_IF_YOU_DO")[0].optional is False


# ── mapping: ordinal buckets (no magic sums) ──────────────────────────────────

from mtgcli.analyzer.mapping import ArchetypeSupport, map_archetypes


def test_defining_outweighs_many_weak():
    defining = ArchetypeSupport("X", defining=["d"], supporting=["s"])
    four_weak = ArchetypeSupport("Y", weak=["w1", "w2", "w3", "w4"])
    assert defining.band() == "high"
    assert four_weak.band() == "low"          # 4 weak NEVER beats 1 defining
    assert defining.band() != four_weak.band()


def test_band_thresholds():
    assert ArchetypeSupport("X", defining=["d"], supporting=["s1", "s2"]).band() == "very_high"
    assert ArchetypeSupport("X", supporting=["s1", "s2"]).band() == "medium"
    assert ArchetypeSupport("X", supporting=["s1"]).band() == "low"
    assert ArchetypeSupport("X").band() == "none"


def test_map_archetypes_aristocrats():
    supports = map_archetypes({"death_trigger", "sacrifice_outlet", "token_maker"})
    arist = next((s for s in supports if s.archetype == "Aristocrats"), None)
    assert arist is not None and arist.band() in ("high", "very_high")


# ── analyze_card orchestrator ─────────────────────────────────────────────────

def test_analyze_card_gargos_not_punisher():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.analyzer.analyze import analyze_card
    repo = CardRepository(str(SQLITE_PATH))
    c = repo.get_card_by_exact_name("Gargos, Vicious Watcher")
    if not c:
        import pytest; pytest.skip("card not in DB")
    r = analyze_card(c)
    assert r["dominant_symmetry"] != "asymmetric_opponents"
    assert not any("punisher" in w.lower() for w in r["warnings"])


def test_analyze_card_toxrill_punisher():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.analyzer.analyze import analyze_card
    repo = CardRepository(str(SQLITE_PATH))
    c = repo.get_card_by_exact_name("Toxrill, the Corrosive")
    if not c:
        import pytest; pytest.skip("card not in DB")
    r = analyze_card(c)
    assert r["dominant_symmetry"] == "asymmetric_opponents"
    assert any("punisher" in w.lower() for w in r["warnings"])


# ── content layer: trigger families, scaling, tribal (calibration misses 1-3) ─

from mtgcli.analyzer.content import detect_trigger_families, detect_scaling, detect_tribal


def _content(text):
    p = CardProfile(name="t")
    detect_trigger_families(text, p)
    detect_scaling(text, p)
    detect_tribal(text, p)
    return p


def test_miss1_trigger_family_enters():
    p = _content("Whenever Pantlaza or another Dinosaur you control enters, discover X.")
    assert p.has_signal("TRIGGER_PERMANENT_ENTERS")


def test_miss2_toughness_scaling():
    p = _content("Discover X, where X is that creature's toughness.")
    assert p.has_signal("SCALES_WITH")
    assert any("toughness" in s.trace.matched_text for s in p.get_signals("SCALES_WITH"))


def test_miss2_for_each_scaling_reused():
    p = _content("Draw a card for each creature you control.")
    assert p.has_signal("SCALES_WITH")   # reuses oracle_hooks extract_scaling


def test_miss3_tribal_detected():
    p = _content("Whenever another Dinosaur you control enters, draw a card.")
    assert p.has_signal("TRIBAL_DINOSAUR")
    assert "Dinosaur Tribal" in p.tags


def test_tribal_ignores_non_types():
    # "artifact creatures" — 'artifact' is not a creature type, should not tag tribal
    p = _content("Whenever another artifact you control enters, draw a card.")
    assert not any(s.id.startswith("TRIBAL_") for s in p.signals)


def test_analyze_card_pantlaza_all_three_misses_fixed():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.analyzer.analyze import analyze_card
    repo = CardRepository(str(SQLITE_PATH))
    c = repo.get_card_by_exact_name("Pantlaza, Sun-Favored")
    if not c:
        import pytest; pytest.skip("card not in DB")
    r = analyze_card(c)
    ids = {s["id"] for s in r["signals"]}
    assert "TRIGGER_PERMANENT_ENTERS" in ids     # miss 1
    assert "SCALES_WITH" in ids                   # miss 2
    assert "TRIBAL_DINOSAUR" in ids               # miss 3
    assert "Dinosaur Tribal" in r["tags"]         # tag propagates from face


# ── mapping fixes: miss 5 (repeatable precision) + miss 6 (voltron noise) ──────

def test_miss6_generic_evasion_not_voltron():
    # a card whose only Voltron-ish token is generic 'evasion' must NOT show Voltron
    supports = map_archetypes({"evasion", "trample"})
    assert not any(s.archetype == "Voltron" for s in supports)


def test_miss6_real_voltron_still_detected():
    # equipment/aura + combat damage still maps to Voltron
    supports = map_archetypes({"COMBAT_DAMAGE_TRIGGER", "equipment"})
    volt = next((s for s in supports if s.archetype == "Voltron"), None)
    assert volt is not None and volt.band() in ("high", "very_high")


def test_tribal_surfaces_as_archetype():
    supports = map_archetypes({"TRIBAL_DINOSAUR"})
    tribal = next((s for s in supports if s.archetype == "Dinosaur Tribal"), None)
    assert tribal is not None and tribal.band() == "high"


def test_enters_trigger_maps_to_etb_value():
    supports = map_archetypes({"TRIGGER_PERMANENT_ENTERS"})
    assert any(s.archetype == "ETB Value" for s in supports)


def test_miss5_repeatable_token_precision():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    from mtgcli.deckbuilder.card_profile import matched_tags
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    repo = CardRepository(str(SQLITE_PATH))
    # ETB one-shot token maker: token_maker yes, repeatable no
    reg = repo.get_card_by_exact_name("Regisaur Alpha")
    if reg:
        tags = matched_tags(reg)
        assert "token_maker" in tags and "repeatable_token_maker" not in tags
    # recurring token maker: verified via the SIGNAL (the conjunction detector is the
    # archetype truth since fix B; the tag is create-anchored and search-only)
    oph = repo.get_card_by_exact_name("Ophiomancer")
    if oph:
        from mtgcli.analyzer.analyze import analyze_card
        sigs = [x["id"] for x in analyze_card(oph)["signals"]]
        assert "REPEATABLE_TOKEN_MAKER" in sigs


# ── miss A: self-counter vs broad-counter; miss B: life-loss archetype ─────────

def test_missA_self_counter_not_counters_matter():
    p = CardProfile(name="Valgavoth, Harrower of Souls")
    detect_counter_sense("Put a +1/+1 counter on Valgavoth and draw a card.", p,
                         card_name="Valgavoth, Harrower of Souls")
    assert p.has_signal("COUNTER_MARKER_SELF")
    assert not p.has_signal("COUNTER_MARKER")     # not a broad counters strategy
    assert "Counters Matter" not in p.tags


def test_missA_this_creature_self_counter():
    p = CardProfile(name="X")
    detect_counter_sense("Put a +1/+1 counter on this creature.", p, card_name="X")
    assert p.has_signal("COUNTER_MARKER_SELF")


def test_missA_broad_counter_still_counters_matter():
    p = CardProfile(name="X")
    detect_counter_sense("Put a +1/+1 counter on target creature.", p, card_name="X")
    assert p.has_signal("COUNTER_MARKER")
    assert "Counters Matter" in p.tags


def test_missB_group_slug_maps_to_life_loss():
    supports = map_archetypes({"group_slug", "lifedrain"})
    ll = next((s for s in supports if s.archetype == "Life Loss / Group Slug"), None)
    assert ll is not None and ll.band() in ("high", "very_high")


def test_missB_life_change_trigger_supports_life_loss():
    supports = map_archetypes({"group_slug", "TRIGGER_LIFE_CHANGE"})
    ll = next((s for s in supports if s.archetype == "Life Loss / Group Slug"), None)
    assert ll is not None and "TRIGGER_LIFE_CHANGE" in ll.supporting


def test_valgavoth_end_to_end_misinterpretation_fixed():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.analyzer.analyze import analyze_card
    repo = CardRepository(str(SQLITE_PATH))
    c = repo.get_card_by_exact_name("Valgavoth, Harrower of Souls")
    if not c:
        import pytest; pytest.skip("card not in DB")
    r = analyze_card(c)
    bands = {a["archetype"]: a["band"] for a in r["archetype_support"]}
    # A: not a high Counters Matter deck (self-counter)
    assert bands.get("Counters Matter", "none") != "high"
    # B: the real archetype surfaces
    assert bands.get("Life Loss / Group Slug") in ("high", "very_high", "medium")


# ── batch fixes: #1 commander allowlist, #2 fear vs absolute unblockable ───────

def test_fix1_commander_allowlist():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    repo = CardRepository(str(SQLITE_PATH))
    shorikai = repo.get_card_by_exact_name("Shorikai, Genesis Engine")
    if shorikai:
        assert shorikai["can_be_commander"] is True     # allowlisted
    esika = repo.get_card_by_exact_name("Esika's Chariot")
    if esika:
        assert esika["can_be_commander"] is False        # not a commander, stays blocked


def test_fix2_fear_is_conditional_not_absolute():
    p = CardProfile(name="t")
    detect_negation("Equipped creature has fear. (It can't be blocked except by black creatures.)", p)
    assert p.has_signal("CONDITIONAL_EVASION")
    assert not p.has_signal("UNBLOCKABLE")


def test_fix2_true_unblockable_still_absolute():
    p = CardProfile(name="t")
    detect_negation("Equipped creature can't be blocked.", p)
    assert p.has_signal("UNBLOCKABLE")
    assert not p.has_signal("CONDITIONAL_EVASION")


# ── #3 batch: new archetypes (attack-triggers, -1/-1, evoke, vehicles) ─────────

def test_minus_counters_distinct_from_plus():
    from mtgcli.analyzer.semantics import detect_counter_sense
    minus = CardProfile(name="t")
    detect_counter_sense("Put a -1/-1 counter on target creature.", minus, card_name="t")
    assert minus.has_signal("COUNTER_MARKER_MINUS") and "Minus Counters" in minus.tags
    assert not minus.has_signal("COUNTER_MARKER")
    plus = CardProfile(name="t")
    detect_counter_sense("Put a +1/+1 counter on target creature.", plus, card_name="t")
    assert plus.has_signal("COUNTER_MARKER") and not plus.has_signal("COUNTER_MARKER_MINUS")


def test_minus_counters_maps_to_attrition():
    supports = map_archetypes({"COUNTER_MARKER_MINUS"})
    assert any(s.archetype == "Minus Counters / Attrition" and s.band() == "high" for s in supports)


def test_attack_trigger_maps_to_aggro():
    supports = map_archetypes({"TRIGGER_ATTACKS_OR_COMBAT"})
    assert any(s.archetype == "Attack Triggers / Aggro" and s.band() == "high" for s in supports)


def test_evoke_and_vehicle_detection():
    from mtgcli.analyzer.content import detect_keywords
    ev = CardProfile(name="t")
    detect_keywords("Evoke {G} (You may cast this spell for its evoke cost...)", ev)
    assert ev.has_signal("EVOKE")
    vh = CardProfile(name="t")
    detect_keywords("Crew 8", vh, type_line="Legendary Artifact — Vehicle")
    assert vh.has_signal("VEHICLE")


def test_vehicle_maps_to_vehicles_archetype():
    supports = map_archetypes({"VEHICLE"})
    assert any(s.archetype == "Vehicles" and s.band() == "high" for s in supports)


# ── #3: theft + legendary-matters archetypes (batch pattern) ──────────────────

def test_theft_archetype_maps():
    supports = map_archetypes({"theft"})
    theft = next((s for s in supports if s.archetype == "Theft"), None)
    assert theft is not None and theft.band() == "high"


def test_legendary_matters_detector_and_archetype():
    from mtgcli.analyzer.content import detect_keywords
    p = CardProfile(name="t")
    detect_keywords("Legendary creatures you control get +1/+1.", p)
    assert p.has_signal("LEGENDARY_MATTERS")
    supports = map_archetypes({"LEGENDARY_MATTERS"})
    assert any(s.archetype == "Legendary Matters" and s.band() == "high" for s in supports)


def test_legendary_type_line_not_false_positive():
    from mtgcli.analyzer.content import detect_keywords
    # a plain legendary creature with no legendary-synergy text
    p = CardProfile(name="t")
    detect_keywords("Flying. When this creature enters, draw a card.", p, type_line="Legendary Creature — Angel")
    assert not p.has_signal("LEGENDARY_MATTERS")


def test_batch_dihada_gets_both_archetypes():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.analyzer.analyze import analyze_card
    repo = CardRepository(str(SQLITE_PATH))
    c = repo.get_card_by_exact_name("Dihada, Binder of Wills")
    if not c:
        import pytest; pytest.skip("card not in DB")
    bands = {a["archetype"]: a["band"] for a in analyze_card(c)["archetype_support"]}
    assert bands.get("Legendary Matters") == "high"
    assert bands.get("Theft") == "high"


# ── #5: saga chapter splitting + tax detection + incidental counter ───────────

def test_saga_splits_into_chapters():
    from mtgcli.analyzer.structure import split_faces
    text = ("(As this Saga enters and after your draw step, add a lore counter. Sacrifice after III.)\n"
            "I — Destroy target nonland permanent an opponent controls.\n"
            "II — Search your library for a Forest card.\n"
            "III — Creatures you control gain deathtouch until end of turn.")
    faces = split_faces(text, "saga")
    assert len(faces) == 3
    assert [f.part_type for f in faces] == ["chapter_I", "chapter_II", "chapter_III"]
    assert "destroy" in faces[0].text.lower()


def test_tax_detected_as_stax():
    from mtgcli.analyzer.content import detect_keywords
    p = CardProfile(name="t")
    detect_keywords("Noncreature spells your opponents cast cost {2} more to cast.", p)
    assert p.has_signal("TAX_COST_INCREASE")
    assert "Stax" in p.tags


def test_incidental_counter_on_it_not_counters_matter():
    p = CardProfile(name="Elspeth Conquers Death")
    detect_counter_sense("Return target creature. Put a +1/+1 counter on it.", p,
                         card_name="Elspeth Conquers Death")
    assert p.has_signal("COUNTER_MARKER_SELF")     # incidental, not broad
    assert "Counters Matter" not in p.tags


def test_saga_multirole_preserved():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.analyzer.analyze import analyze_card
    repo = CardRepository(str(SQLITE_PATH))
    c = repo.get_card_by_exact_name("Elspeth Conquers Death")
    if not c:
        import pytest; pytest.skip("card not in DB")
    r = analyze_card(c)
    bands = {a["archetype"]: a["band"] for a in r["archetype_support"]}
    assert len(r["faces"]) == 3                      # split into chapters
    assert bands.get("Counters Matter", "none") != "high"   # 'on it' didn't over-fire
    assert "Reanimator" in bands                     # recursion role preserved


# ── B fix: conjunction-based REPEATABLE_TOKEN_MAKER (Fase 0 false positives) ──

from mtgcli.analyzer.content import detect_repeatable_token_making


def _rtm(text):
    p = CardProfile(name="t")
    detect_repeatable_token_making(text, p)
    return p.has_signal("REPEATABLE_TOKEN_MAKER")


def test_rtm_requires_conjunction_same_clause():
    # trigger + create token in same line → yes
    assert _rtm("Whenever a creature you control deals combat damage to a player, create a 1/1 token.")
    # activated ability spanning sentences in ONE line (Shorikai) → yes
    assert _rtm("{1}, {T}: Draw two cards, then discard a card. Create a 1/1 Pilot creature token.")
    # scheduled trigger → yes
    assert _rtm("At the beginning of your upkeep, create a 1/1 Snake token.")


def test_rtm_rejects_trigger_without_tokens():
    # Gonti: combat-damage trigger but NO token creation → no
    assert not _rtm("Whenever one or more creatures you control deal combat damage to a player, look at the top card of that player's library.")


def test_rtm_rejects_oneshot_etb():
    # Regisaur: ETB one-shot ("When ... enters"), not "whenever" → no
    assert not _rtm("When this creature enters, create a 3/3 green Dinosaur creature token.")


def test_rtm_rejects_opponent_tokens():
    # Nettling Nuisance: the OPPONENT gets the token (downside, not engine) → no
    assert not _rtm("Whenever this creature deals combat damage to a player, that player creates a 4/2 red Pirate creature token.")


def test_gonti_end_to_end_no_go_wide():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.analyzer.analyze import analyze_card
    repo = CardRepository(str(SQLITE_PATH))
    c = repo.get_card_by_exact_name("Gonti, Canny Acquisitor")
    if not c:
        import pytest; pytest.skip("card not in DB")
    bands = {a["archetype"]: a["band"] for a in analyze_card(c)["archetype_support"]}
    assert "Go Wide" not in bands            # Fase 0 false positive: dead
    assert bands.get("Theft") is not None    # its real read survives


def test_krenko_keeps_vehicles_none_shorikai_keeps_high():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.analyzer.analyze import analyze_card
    repo = CardRepository(str(SQLITE_PATH))
    kr = repo.get_card_by_exact_name("Krenko, Mob Boss")
    sh = repo.get_card_by_exact_name("Shorikai, Genesis Engine")
    if kr:
        kb = {a["archetype"]: a["band"] for a in analyze_card(kr)["archetype_support"]}
        assert "Vehicles" not in kb           # fix 1: token_maker no longer implies Vehicles
        assert kb.get("Go Wide") == "high"    # via the precise signal
    if sh:
        sb = {a["archetype"]: a["band"] for a in analyze_card(sh)["archetype_support"]}
        assert sb.get("Vehicles") == "high"   # real vehicle keeps its archetype


# ── coverage gaps de Fase 0: trigger doublers (Isshin) + de-noising (Atraxa) ──

from mtgcli.analyzer.content import detect_trigger_doubler


def test_doubler_attack_context_isshin():
    p = CardProfile(name="t")
    detect_trigger_doubler("If a creature attacking causes a triggered ability of a permanent "
                           "you control to trigger, that ability triggers an additional time.", p)
    assert p.has_signal("TRIGGER_DOUBLER")
    assert p.has_signal("DOUBLES_ATTACK_TRIGGERS")
    supports = map_archetypes({"DOUBLES_ATTACK_TRIGGERS"})
    assert any(s.archetype == "Attack Triggers / Aggro" and s.band() == "high" for s in supports)


def test_doubler_etb_context_panharmonicon():
    p = CardProfile(name="t")
    detect_trigger_doubler("Abilities of artifacts and creatures you control that trigger when a "
                           "permanent enters trigger an additional time.", p)
    assert p.has_signal("DOUBLES_ETB_TRIGGERS")
    assert not p.has_signal("DOUBLES_ATTACK_TRIGGERS")


def test_generic_supporting_tokens_removed():
    # card_advantage alone must NOT imply Theft; lifegain alone must NOT imply Life Loss
    assert not any(s.archetype == "Theft" for s in map_archetypes({"card_advantage"}))
    assert not any(s.archetype == "Life Loss / Group Slug" for s in map_archetypes({"lifegain"}))


def test_isshin_end_to_end_attack_triggers():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.analyzer.analyze import analyze_card
    repo = CardRepository(str(SQLITE_PATH))
    c = repo.get_card_by_exact_name("Isshin, Two Heavens as One")
    if not c:
        import pytest; pytest.skip("card not in DB")
    bands = {a["archetype"]: a["band"] for a in analyze_card(c)["archetype_support"]}
    assert bands.get("Attack Triggers / Aggro") == "high"   # the Fase 0 coverage gap: closed


# ── Fase 0.2 fixes: Lands archetype + Spellslinger de-noise + Sen theft ────────

def test_lands_archetype_from_landfall():
    supports = map_archetypes({"landfall", "extra_land_drop"})
    lands = next((s for s in supports if s.archetype == "Lands / Landfall"), None)
    assert lands is not None and lands.band() in ("high", "very_high")


def test_generic_land_ramp_not_lands_archetype():
    # Cultivate-style ramp goes in every green deck — must NOT imply lands-matter
    assert not any(s.archetype == "Lands / Landfall" for s in map_archetypes({"land_ramp"}))


def test_generic_cheap_spell_not_spellslinger():
    # 3rd occurrence of this noise (Valgavoth, Earthshaker, Aesi) — now dead
    assert not any(s.archetype == "Spellslinger" for s in map_archetypes({"cheap_spell", "card_draw"}))
    # real spellslinger still fires via defining
    assert any(s.archetype == "Spellslinger" and s.band() in ("high", "very_high")
               for s in map_archetypes({"magecraft"}))


def test_aesi_end_to_end_lands():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.analyzer.analyze import analyze_card
    repo = CardRepository(str(SQLITE_PATH))
    c = repo.get_card_by_exact_name("Aesi, Tyrant of Gyre Strait")
    if not c:
        import pytest; pytest.skip("card not in DB")
    bands = {a["archetype"]: a["band"] for a in analyze_card(c)["archetype_support"]}
    assert bands.get("Lands / Landfall") == "high"   # the Fase 0.2 wrong: dead
    assert "Spellslinger" not in bands


def test_sen_triplets_theft_via_exact_phrase():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.analyzer.analyze import analyze_card
    repo = CardRepository(str(SQLITE_PATH))
    c = repo.get_card_by_exact_name("Sen Triplets")
    if not c:
        import pytest; pytest.skip("card not in DB")
    bands = {a["archetype"]: a["band"] for a in analyze_card(c)["archetype_support"]}
    assert bands.get("Theft") == "high" and bands.get("Stax / Prison") == "high"


# ── Fase 1: analyzer embedded additively in commander analysis ────────────────

def test_fase1_analyzer_field_present_and_consistent():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.deckbuilder.commander_analyzer import analyze_commander
    from mtgcli.analyzer.analyze import analyze_card
    repo = CardRepository(str(SQLITE_PATH))
    c = repo.get_card_by_exact_name("Aesi, Tyrant of Gyre Strait")
    if not c:
        import pytest; pytest.skip("card not in DB")
    result = analyze_commander(c)
    # new field present
    assert "analyzer" in result
    an = result["analyzer"]
    assert an["schema_version"].startswith("card-analyzer")
    # consistent with the standalone analyzer
    direct = analyze_card(c)
    assert an["archetype_support"] == direct["archetype_support"]
    assert an["signals"] == [s["id"] for s in direct["signals"]]


def test_fase1_legacy_fields_untouched():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.deckbuilder.commander_analyzer import analyze_commander
    repo = CardRepository(str(SQLITE_PATH))
    c = repo.get_card_by_exact_name("Krenko, Mob Boss")
    if not c:
        import pytest; pytest.skip("card not in DB")
    result = analyze_commander(c)
    for key in ("best_archetype", "role_pressures", "oracle_hooks",
                "wanted_card_patterns", "commander_scores", "engine_profile"):
        assert key in result, f"key {key} missing"


# ── recon fixes: 5 nuevas casillas + vocab falsos + polaridad hug ─────────────

def _bands(name):
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.analyzer.analyze import analyze_card
    c = CardRepository(str(SQLITE_PATH)).get_card_by_exact_name(name)
    if not c:
        import pytest; pytest.skip("card not in DB")
    return {a["archetype"]: a["band"] for a in analyze_card(c)["archetype_support"]}


def test_recon_bruvac_mill():
    b = _bands("Bruvac the Grandiloquent")
    assert b.get("Mill") == "high"
    assert "Reanimator" not in b            # el falso self_mill murió


def test_recon_urza_artifacts():
    assert _bands("Urza, Lord High Artificer").get("Artifacts Matter") == "high"


def test_recon_kynaios_group_hug():
    b = _bands("Kynaios and Tiro of Meletis")
    assert b.get("Group Hug / Politics") == "high"


def test_recon_wheel_and_mill_pieces():
    assert _bands("Windfall").get("Wheels / Forced Draw") == "high"
    assert _bands("Maddening Cacophony").get("Mill") == "high"


def test_recon_carth_superfriends():
    assert _bands("Carth the Lion").get("Superfriends / Planeswalkers") == "high"


def test_hug_polarity_warning():
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    if not SQLITE_PATH.exists():
        import pytest; pytest.skip("DB not built")
    from mtgcli.analyzer.analyze import analyze_card
    repo = CardRepository(str(SQLITE_PATH))
    ky = repo.get_card_by_exact_name("Kynaios and Tiro of Meletis")
    if ky:
        w = " ".join(analyze_card(ky)["warnings"])
        assert "group hug" in w and "punisher" not in w
    vg = repo.get_card_by_exact_name("Valgavoth, Harrower of Souls")
    if vg:
        # un punisher real conserva su warning (si su symmetry es asymmetric_opponents)
        w = " ".join(analyze_card(vg)["warnings"])
        assert "group hug" not in w


# ── caso Kenrith: modal toolbox (criterio #4 del gate) ─────────────────────────

def test_modal_toolbox_detector():
    from mtgcli.analyzer.content import detect_modal_structure
    p = CardProfile(name="t")
    detect_modal_structure("{R}: A.\n{1}{G}: B.\n{2}{W}: C.\n{3}{U}: D.\n{4}{B}: E.", p)
    assert p.has_signal("MODAL_TOOLBOX")
    p2 = CardProfile(name="t2")
    detect_modal_structure("{T}: Add {C}.\n{2}: Draw a card.", p2)   # solo 2 -> no
    assert not p2.has_signal("MODAL_TOOLBOX")


def test_kenrith_toolbox_and_warning():
    b = _bands("Kenrith, the Returned King")
    assert b.get("Toolbox / Goodstuff") == "high"
    from mtgcli.config import SQLITE_PATH
    from mtgcli.cards.repository import CardRepository
    from mtgcli.analyzer.analyze import analyze_card
    c = CardRepository(str(SQLITE_PATH)).get_card_by_exact_name("Kenrith, the Returned King")
    if c:
        w = " ".join(analyze_card(c)["warnings"])
        assert "toolbox" in w.lower() and "user's requested direction" in w


def test_cromat_classic_toolbox():
    assert _bands("Cromat").get("Toolbox / Goodstuff") == "high"
