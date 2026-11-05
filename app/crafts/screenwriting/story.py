"""Story development audit: the six-phase process in guidelines/story-process.md as data plus rule-based checks.

The writer's answers live in ``screenplay.story`` (all optional, so work in progress always saves). ``audit`` turns them into
per-phase items with a status: ``ok`` (answered and the check passes), ``advice`` (answered, but a check suggests a second look)
or ``missing`` (not answered yet). It is advice only: nothing here ever blocks saving, planning or approving. Some checks are
cross-checks against the script itself (hook timing, beat order, dialogue density); the rest check completeness.
"""

MASTER_PLOTS = [
    ("overcoming_the_monster", "Overcoming the Monster"), ("rags_to_riches", "Rags to Riches"), ("the_quest", "The Quest"),
    ("voyage_and_return", "Voyage and Return"), ("rebirth", "Rebirth"), ("comedy", "Comedy"), ("tragedy", "Tragedy"), ("man_in_a_hole", "Man in a Hole"),
]
LABOV = [("abstract", "Abstract (the summary hook)"), ("orientation", "Orientation (context and setting)"), ("complicating_action", "Complicating action (rising conflict)"),
         ("evaluation", "Evaluation (why the story matters)"), ("resolution", "Result / resolution (the outcome)"), ("coda", "Coda (bridge back to present relevance)")]
CIRCLE = [("you", "You"), ("need", "Need"), ("go", "Go"), ("search", "Search"), ("find", "Find"), ("take", "Take (the price paid)"), ("return", "Return"), ("change", "Change")]
HOOK_SECONDS = 15           # the "15-second hook" from the process
DIALOGUE_DENSE_WPM = 110    # above this the iceberg (sparse dialogue) advice appears; a guess
PHASES = [
    (1, "Concept audit and baseline", "Stops you launching into a static situation that lacks friction, stakes or purpose."),
    (2, "Tellability and disruption", "Removes cliché openings and keeps the audience engaged from the first line."),
    (3, "Empathy and character design", "Gives you relatable, active characters the audience admires and invests in."),
    (4, "Conflict escalation and curiosity", "Prevents a sagging middle by building friction and trusting the audience with subtext."),
    (5, "Structure and evaluation", "Makes sure the story carries theme and answers the audience's question: so what?"),
    (6, "Execution, revision and testing", "Turns the blueprint into a polished story that works as a safe rehearsal of human choices."),
]


def _t(v):
    return v.strip() if isinstance(v, str) else ""


def _item(items, id_, label, status, message):
    items.append({"id": id_, "label": label, "status": status, "message": message})


def audit(doc, scene_analyses):
    """Return ``{"phases": [...], "overall": {...}}`` for ``doc['story']`` (None or {} gives all 'missing')."""
    st = doc.get("story") or {}
    chars = {c["id"] for c in doc["characters"]}
    beats = [(s["id"], b) for s in doc["scenes"] for b in s.get("beats", [])]
    beat_ids = [b["id"] for _, b in beats]
    beat_pos = {b: i for i, b in enumerate(beat_ids)}
    elements = {e["id"]: e for s in doc["scenes"] for e in s["elements"]}
    start_of = {e["id"]: e["start_seconds"] for a in scene_analyses for e in a["elements"]}
    phases = []

    def phase(n):
        items = []
        phases.append({"phase": n, "title": PHASES[n - 1][1], "helps": PHASES[n - 1][2], "items": items})
        return items

    # ---- phase 1: the five pillars, the minimal narrative test, the master plot ----------------------------------
    it, p = phase(1), st.get("pillars") or {}
    for key, label in (("setting", "Setting (world and context)"), ("core_conflict", "Core conflict (the primary risk or obstacle)"),
                       ("plot", "Plot (connected cause-and-effect events)"), ("theme", "Theme (the underlying message)")):
        v = _t(p.get(key)) or (_t(doc["project"].get("theme")) if key == "theme" else "")
        if not v:
            _item(it, key, label, "missing", "Not answered yet.")
        elif len(v) < 12:
            _item(it, key, label, "advice", "Very short. Say it in a full sentence so others can test it.")
        else:
            _item(it, key, label, "ok", v if len(v) < 90 else v[:87] + "…")
    pid = p.get("protagonist_id")
    _item(it, "protagonist", "Characters: protagonist", "ok" if pid in chars else "missing",
          "Chosen." if pid in chars else "Pick who the story follows.")
    aid, anote = p.get("antagonist_id"), _t(p.get("antagonist_note"))
    if aid in chars or anote:
        same = aid and aid == pid
        _item(it, "antagonist", "Characters: antagonist (person or force)", "advice" if same else "ok",
              "The protagonist cannot also be the antagonist; name the opposing person or force." if same else (anote or "Chosen."))
    else:
        _item(it, "antagonist", "Characters: antagonist (person or force)", "missing", "Name the person or force that stands in the way.")
    sup = [c for c in p.get("supporting_ids", []) if c in chars]
    _item(it, "supporting", "Characters: supporting cast", "ok" if sup else "advice",
          f"{len(sup)} named." if sup else "None named. That is fine for a two-hander; add them if others shape the story.")
    mn = st.get("minimal_narrative") or {}
    e1, e2, jn = _t(mn.get("event_1")), _t(mn.get("event_2")), _t(mn.get("juncture"))
    if not (e1 and e2 and jn):
        _item(it, "minimal", "Minimal narrative test", "missing", "Needs two events in time order and the juncture that joins them.")
    elif e1.lower() == e2.lower():
        _item(it, "minimal", "Minimal narrative test", "advice", "The two events are the same. A plot needs something to happen *after* the first thing.")
    else:
        _item(it, "minimal", "Minimal narrative test", "ok", f"“{e1}” {jn} “{e2}”")
    mp = st.get("master_plot")
    _item(it, "master_plot", "Master plot arc", "ok" if mp in dict(MASTER_PLOTS) else "missing",
          dict(MASTER_PLOTS).get(mp, "Choose a classic template to measure your story against."))

    # ---- phase 2: breach, hook, defamiliarization -----------------------------------------------------------------
    it = phase(2)
    br = st.get("breach") or {}
    ok = _t(br.get("norm")) and _t(br.get("violation"))
    _item(it, "breach", "Canonical script breach", "ok" if ok else "missing",
          f"Norm: {_t(br.get('norm'))[:70]} / Breach: {_t(br.get('violation'))[:70]}" if ok else "Name the everyday expectation and exactly how the inciting incident violates it.")
    hk = st.get("hook") or {}
    eid = hk.get("element_id")
    if not _t(hk.get("text")):
        _item(it, "hook", "The 15-second hook", "missing", "Write the opening breach in a sentence, then point to the script line that delivers it.")
    elif eid not in start_of:
        _item(it, "hook", "The 15-second hook", "advice", "Point to the script line that delivers the hook so its timing can be checked.")
    elif start_of[eid] > HOOK_SECONDS:
        _item(it, "hook", "The 15-second hook", "advice", f"The hook line lands at {start_of[eid]:.0f} s. Aim for the first {HOOK_SECONDS} s.")
    else:
        _item(it, "hook", "The 15-second hook", "ok", f"Delivered by {eid} at {start_of[eid]:.0f} s (inside the first {HOOK_SECONDS} s).")
    df = st.get("defamiliarization") or {}
    _item(it, "defamiliarization", "Defamiliarization lens", "ok" if df.get("technique") and _t(df.get("description")) else "missing",
          _t(df.get("description"))[:100] if df.get("technique") and _t(df.get("description")) else "Choose a technique and describe how a familiar situation will be seen in an unexpected way.")

    # ---- phase 3: empathy, consciousness, agency ---------------------------------------------------------------------
    it, em = phase(3), st.get("empathy") or {}
    if not _t(em.get("vulnerability")):
        _item(it, "vulnerability", "Vulnerability calibration", "missing", "Describe how the struggle is framed to invite shared feeling.")
    elif em.get("distress_risk") == "high":
        _item(it, "vulnerability", "Vulnerability calibration", "advice", "You rated the distress risk high: readers may look away. Show more control, humour or dignity.")
    elif em.get("distress_risk") not in ("low", "medium"):
        _item(it, "vulnerability", "Vulnerability calibration", "advice", "Rate the risk that this reads as overwhelming personal distress.")
    else:
        _item(it, "vulnerability", "Vulnerability calibration", "ok", _t(em["vulnerability"])[:100])
    _item(it, "consciousness", "Consciousness representation", "ok" if em.get("consciousness") else "missing",
          dict([("free_indirect_discourse", "Free indirect discourse"), ("interior_monologue", "Interior monologue (e.g. voice-over)"), ("psycho_narration", "Psycho-narration"),
                ("behavioural_only", "Behaviour and objects only")]).get(em.get("consciousness"), "Choose how the audience reaches a character's thoughts."))
    _item(it, "target", "Strategic empathy target", "ok" if em.get("target") else "missing",
          dict([("bounded", "Bounded (in-group)"), ("ambassadorial", "Ambassadorial (out-group or cause)"), ("broadcast", "Broadcast (universal vulnerability)")]).get(em.get("target"), "Who should feel with these people?"))
    ag = st.get("agency") or {}
    ch = [c for c in ag.get("choices", []) if _t(c.get("text"))]
    if not ch:
        _item(it, "agency", "Agency and effort", "missing", "List the hard choices the protagonist makes under pressure.")
    elif any(not _t(c.get("cost")) for c in ch):
        _item(it, "agency", "Agency and effort", "advice", "Some choices have no cost. A difficult choice costs something; say what.")
    else:
        _item(it, "agency", "Agency and effort", "ok", f"{len(ch)} costly choice(s) listed.")

    # ---- phase 4: unity of opposites, gaps, subtext -------------------------------------------------------------------------
    it, cf = phase(4), st.get("conflict") or {}
    _item(it, "unity", "Unity of opposites", "ok" if _t(cf.get("unity_of_opposites")) else "missing",
          _t(cf.get("unity_of_opposites"))[:100] or "Why can neither side simply walk away?")
    eg = [g for g in cf.get("expectation_gaps", []) if _t(g.get("action")) and _t(g.get("reaction"))]
    if not eg:
        _item(it, "expectation", "Expectation gap", "missing", "Map decision points where the world answers an action unexpectedly.")
    elif len(eg) < 2 or any(g.get("beat_id") not in beat_pos for g in eg) or any(not _t(g.get("stakes")) for g in eg):
        _item(it, "expectation", "Expectation gap", "advice", "Aim for at least two, each tied to a beat and saying how the stakes rise.")
    else:
        _item(it, "expectation", "Expectation gap", "ok", f"{len(eg)} decision points mapped to beats.")
    ig = [g for g in cf.get("information_gaps", []) if _t(g.get("withheld"))]
    if not ig:
        _item(it, "information", "Information gap", "missing", "What does the audience not know yet, and when do they find out?")
    elif any(g.get("reveal_beat_id") not in beat_pos for g in ig):
        _item(it, "information", "Information gap", "advice", "Choose the beat where each withheld fact is revealed.")
    elif any(beat_pos[g["reveal_beat_id"]] == 0 for g in ig):
        _item(it, "information", "Information gap", "advice", "A fact revealed in the very first beat opens no gap; withhold it for longer.")
    else:
        _item(it, "information", "Information gap", "ok", f"{len(ig)} withheld fact(s) with a reveal beat.")
    sub = [s for s in cf.get("subtext", []) if _t(s.get("unspoken"))]
    wpm = max((a["pacing"]["dialogue_words_per_minute"] for a in scene_analyses), default=0)
    if not sub:
        _item(it, "subtext", "Subtext (iceberg)", "missing", "Name what is felt but not said, and the line that carries it.")
    elif wpm > DIALOGUE_DENSE_WPM:
        _item(it, "subtext", "Subtext (iceberg)", "advice", f"Dialogue runs at {wpm:.0f} spoken words a minute, which is dense; submerge more under action and silence.")
    else:
        _item(it, "subtext", "Subtext (iceberg)", "ok", f"{len(sub)} unspoken layer(s); dialogue density {wpm:.0f} words/min.")

    # ---- phase 5: Labov and the story circle -----------------------------------------------------------------------------------
    it, lb = phase(5), st.get("labov") or {}
    for key, label in LABOV:
        v = lb.get(key) or {}
        _item(it, f"labov_{key}", label, "ok" if _t(v.get("text")) else "missing", _t(v.get("text"))[:100] or "Not answered yet.")
    cr = st.get("circle") or {}
    done = [k for k, _ in CIRCLE if _t((cr.get(k) or {}).get("text"))]
    mapped = [beat_pos[cr[k]["beat_id"]] for k, _ in CIRCLE if (cr.get(k) or {}).get("beat_id") in beat_pos]
    if len(done) < len(CIRCLE):
        _item(it, "circle", "Story circle (8 steps)", "missing" if not done else "advice", f"{len(done)} of 8 steps answered." if done else "Walk the journey from You to Change.")
    elif mapped and mapped != sorted(mapped):
        _item(it, "circle", "Story circle (8 steps)", "advice", "The beats you linked go backwards somewhere; the journey should move forward through the script.")
    elif len(mapped) < len(CIRCLE):
        _item(it, "circle", "Story circle (8 steps)", "advice", "All 8 steps are written; link each to a beat to check the order.")
    else:
        _item(it, "circle", "Story circle (8 steps)", "ok", "All 8 steps written and in script order.")

    # ---- phase 6: draft, feedback, polish, flight simulator ---------------------------------------------------------------------------
    it, rv = phase(6), st.get("revision") or {}
    n_lines = len(elements)
    _item(it, "draft", "First draft", "ok" if n_lines >= 8 else ("advice" if n_lines else "missing"),
          f"{n_lines} script line(s) written." if n_lines >= 8 else ("Only a few lines so far. Keep going: finish the draft before polishing." if n_lines else "No script lines yet. Write the whole draft without stopping to edit."))
    fb = [f for f in rv.get("feedback", []) if _t(f.get("note"))]
    open_fb = [f for f in fb if f.get("status") != "addressed"]
    _item(it, "feedback", "Outside feedback", "missing" if not fb else ("advice" if open_fb else "ok"),
          "Share the draft and record what readers say." if not fb else (f"{len(open_fb)} note(s) still open." if open_fb else f"{len(fb)} note(s), all addressed."))
    pol = rv.get("polish") or {}
    left = [k for k in ("prose", "tone", "word_choice", "consistency") if not pol.get(k)]
    _item(it, "polish", "Polishing and proofreading", "ok" if not left else ("missing" if len(left) == 4 else "advice"),
          "Prose, tone, word choice and consistency are done." if not left else f"Still to do: {', '.join(x.replace('_', ' ') for x in left)}.")
    sim = rv.get("simulator") or {}
    if not (_t(sim.get("question")) and _t(sim.get("moral_choice"))):
        _item(it, "simulator", "Flight simulator verification", "missing", "Say what human dynamic or moral choice the audience can safely rehearse.")
    else:
        _item(it, "simulator", "Flight simulator verification", "ok" if sim.get("verified") else "advice",
              "Verified." if sim.get("verified") else "Written; tick it off once a reader confirms the story really works as a safe rehearsal.")

    flat = [i for ph in phases for i in ph["items"]]
    counts = {s: sum(1 for i in flat if i["status"] == s) for s in ("ok", "advice", "missing")}
    for ph in phases:
        ph["ok"] = sum(1 for i in ph["items"] if i["status"] == "ok")
        ph["total"] = len(ph["items"])
    return {"phases": phases, "overall": {**counts, "total": len(flat), "percent": round(100 * counts["ok"] / len(flat)),
            "note": "Advice only: nothing here blocks saving, planning or approval."}}
