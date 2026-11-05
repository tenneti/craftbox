"""Lighting service: lighting plans (versions), reusable setups, change impact, comparison and gated exports.

Built on CB0's experiment store, the CB1 Lab service and the CB2A Art service. Every plan version is an experiment (with a parent link)
and every result a run, so versioning, hashing and approval are the same as everywhere else. Plans are independent of each other:
approving one never touches another, and a plan never modifies the art treatment, the direction plan or the screenplay it is based on.
"""
import json

from app import config
from app.crafts.lighting import exports as lexp
from app.crafts.lighting import impact as limpact
from app.crafts.lighting import plan as lpl
from app.core import execute
from app.experiments import Conflict, InvalidInput, NotFound, canonical, now
from app.logging_setup import log
from app.validation import validate

LIGHT_WHERE = "craft_id='lighting' AND json_extract(input_json,'$.screenplay.project.id')=?"
SETUP_SCHEMA = "filmcraft.lighting_setup.v1"
WORKING = {"lighting-plan-json", "light-schedule-csv", "lighting-instructions"}
MANIFESTS = {"lighting-manifest"}
OVERRIDES = {"acknowledge_stale", "allow_open_findings", "allow_pending", "allow_unapproved_art"}


def _loads(t):
    return json.loads(t) if t is not None else None


class LightService:
    def __init__(self, svc, lab, art, data_dir):
        self.svc, self.lab, self.art, self.data_dir = svc, lab, art, data_dir

    # ---- helpers ---------------------------------------------------------------------------------------------------
    def _artifact(self, run_id):
        return self.svc.get_run(run_id)["envelope"]["artifact"]

    def _plan_exp(self, experiment_id):
        exp = self.svc.get_experiment(experiment_id)
        if exp["craft_id"] != "lighting" or "screenplay" not in exp["input"]:
            raise Conflict("that experiment is not a lighting plan")
        run = self.lab._latest_completed(exp)
        if not run:
            raise Conflict("that lighting plan has no completed run")
        return exp, run, self._artifact(run["id"])

    def _create_and_run(self, name, payload, parent, notes=""):
        exp = self.svc.create_experiment("lighting", name, payload, notes, parent=parent)
        run = self.svc.run_experiment(exp["id"])
        return {"experiment": self.svc.get_experiment(exp["id"]), "run": run}

    def _art_of(self, art_experiment_id):
        exp, run, art = self.art._treatment(art_experiment_id)
        return exp, run, art

    def _art_lineage_latest(self, project_id, scene_id, ref_id):
        """The newest version of an art treatment descended from ``ref_id`` (or ``ref_id`` itself)."""
        with self.svc.db.read() as conn:
            rows = conn.execute("SELECT id, parent_experiment_id FROM experiments WHERE craft_id='art_direction' AND json_extract(input_json,'$.screenplay.project.id')=? "
                                "AND json_extract(input_json,'$.scene_id')=? ORDER BY created_at, rowid", (project_id, scene_id)).fetchall()
        order = {r["id"]: i for i, r in enumerate(rows)}
        children = {}
        for r in rows:
            children.setdefault(r["parent_experiment_id"], []).append(r["id"])
        best, stack = ref_id, [ref_id]
        while stack:
            cur = stack.pop()
            for c in children.get(cur, []):
                stack.append(c)
                if order.get(c, -1) > order.get(best, -1):
                    best = c
        return best

    def _upstream(self, art_ref, plan_ref, project_id, scene_id):
        """The newest art treatment and direction plan in the lineage the plan was made from."""
        art_id = self._art_lineage_latest(project_id, scene_id, art_ref)
        a = self._art_of(art_id)
        plan = None
        if plan_ref:
            plan = self.art._plan_artifact(self.art._plan_lineage_latest(project_id, scene_id, plan_ref))
        return art_id, a, plan

    def presets(self):
        return [{"id": k, "name": v["name"], "summary": v["summary"], "art_preset": v["art_preset"]} for k, v in lpl.PRESETS.items()]

    # ---- overview ----------------------------------------------------------------------------------------------------------
    def overview(self, project_id):
        with self.svc.db.read() as conn:
            rows = conn.execute(f"SELECT id FROM experiments WHERE {LIGHT_WHERE} ORDER BY created_at, rowid", (project_id,)).fetchall()
        latest_sp = self.lab._latest_screenplay(project_id)
        items = []
        for r in rows:
            exp = self.svc.get_experiment(r["id"])
            run = self.lab._latest_completed(exp)
            entry = {"experiment_id": exp["id"], "name": exp["name"], "created_at": exp["created_at"], "parent_experiment_id": exp["parent_experiment_id"], "scene_id": exp["input"]["scene_id"],
                     "run_id": run["id"] if run else None, "run_status": exp["runs"][-1]["run_status"] if exp["runs"] else None, "approval_status": run["approval_status"] if run else None}
            if run:
                doc = self._artifact(run["id"])
                an = doc["analysis"]
                entry.update(plan_id=doc["plan"]["id"], plan_name=doc["plan"]["name"], preset=doc["plan"].get("preset"), attention=an["readiness"]["attention"], notes=an["readiness"]["notes"], lights=len(doc["lights"]),
                             adjustments=len(doc["adjustments"]), needs_review=an["readiness"]["pending_review"], art_treatment_id=doc["source"]["art"]["treatment_id"], art_treatment_name=doc["source"]["art"]["treatment_name"],
                             source_revision=doc["source"]["screenplay_revision"], source_ref=doc["source"].get("ref") or {})
                if latest_sp:
                    ref = doc["source"].get("ref") or {}
                    try:
                        art_id, a, plan = self._upstream(ref.get("art_experiment_id"), ref.get("plan_experiment_id"), project_id, doc["scene_id"])
                        imp = limpact.compute(doc, latest_sp[2], a[2], plan[2] if plan else None)
                        entry.update(stale=imp["stale"], affected=len(imp["affected_lights"]) + len(imp["affected_adjustments"]), impact_summary=imp["summary"])
                    except (Conflict, NotFound, KeyError):
                        entry.update(stale=None, impact_summary="The art treatment this plan was made for could not be found.")
            items.append(entry)
        return {"project_id": project_id, "plans": items, "setups": self.setups(project_id)}

    # ---- plans ------------------------------------------------------------------------------------------------------------------
    def _payload(self, screenplay_art, scene_id, art_exp, art_art, plan_exp, plan_art, extra):
        sp_exp, _, sp = screenplay_art
        payload = {"screenplay": sp, "scene_id": scene_id, "art_direction": art_art, "source_ref": {"screenplay_experiment_id": sp_exp["id"], "art_experiment_id": art_exp["id"], "plan_experiment_id": plan_exp["id"] if plan_exp else None}}
        if plan_art:
            payload["direction_plan"] = plan_art
        payload.update(extra)
        return payload

    def draft(self, screenplay_experiment_id, art_experiment_id, preset, name, plan_experiment_id=None, setup_experiment_id=None, parent=None):
        sp = self.lab._screenplay_of(screenplay_experiment_id)
        art_exp, _, art_art = self._art_of(art_experiment_id)
        plan_exp = plan_art = None
        ref_plan = plan_experiment_id or (art_art["source"].get("ref") or {}).get("plan_experiment_id")
        if ref_plan:
            plan_exp, _, plan_art = self.lab._plan_of(ref_plan)
        extra = {"preset": preset or "blank", "plan_name": name}
        if setup_experiment_id:
            extra["setup"] = self._setup_doc(setup_experiment_id)
            extra["preset"] = "setup"
        payload = self._payload(sp, art_art["scene_id"], art_exp, art_art, plan_exp, plan_art, extra)
        return self._create_and_run(name or lpl.PRESETS.get(preset or "blank", {}).get("name", "Lighting plan"), payload, parent)

    def save(self, base_experiment_id, light, name, note=""):
        base = self.svc.get_experiment(base_experiment_id)
        if base["craft_id"] != "lighting" or "screenplay" not in base["input"]:
            raise Conflict("the base experiment is not a lighting plan")
        payload = {k: v for k, v in base["input"].items() if k in ("screenplay", "scene_id", "art_direction", "direction_plan", "source_ref")}
        payload.update({"light": light, "note": note or ""})
        return self._create_and_run(name, payload, base_experiment_id)

    def analyze(self, base_experiment_id, light):
        base = self.svc.get_experiment(base_experiment_id)
        problems = validate(light, "filmcraft.lighting_plan.v1")
        if problems:
            raise InvalidInput("the lighting plan does not match filmcraft.lighting_plan.v1", problems)
        payload = {k: v for k, v in base["input"].items() if k in ("screenplay", "scene_id", "art_direction", "direction_plan", "source_ref")}
        payload["light"] = light
        try:
            r = execute("lighting", payload)
        except ValueError as exc:
            raise InvalidInput(str(exc)) from exc
        return {"analysis": r["artifact"]["analysis"], "warnings": r["warnings"]}

    def impact(self, experiment_id):
        exp, run, doc = self._plan_exp(experiment_id)
        latest = self.lab._latest_screenplay(doc["project_id"])
        if not latest:
            raise Conflict("no screenplay version to compare against")
        ref = doc["source"].get("ref") or {}
        art_id, a, plan = self._upstream(ref.get("art_experiment_id"), ref.get("plan_experiment_id"), doc["project_id"], doc["scene_id"])
        out = limpact.compute(doc, latest[2], a[2], plan[2] if plan else None)
        out["against"] = {"screenplay_experiment_id": latest[0]["id"], "screenplay_revision": (latest[2].get("revision") or {}).get("number"), "art_experiment_id": art_id, "plan_experiment_id": plan[0]["id"] if plan else None}
        return out

    def rebase(self, experiment_id, name=None):
        exp, run, doc = self._plan_exp(experiment_id)
        latest = self.lab._latest_screenplay(doc["project_id"])
        if not latest:
            raise Conflict("no screenplay version to rebase onto")
        ref = doc["source"].get("ref") or {}
        art_id, a, plan = self._upstream(ref.get("art_experiment_id"), ref.get("plan_experiment_id"), doc["project_id"], doc["scene_id"])
        plan_art = plan[2] if plan else None
        if not limpact.compute(doc, latest[2], a[2], plan_art)["stale"]:
            raise Conflict("this plan already matches the latest script, art design and direction plan; nothing to rebase")
        rebased, imp = limpact.rebase(doc, latest[2], a[2], plan_art)
        payload = {"screenplay": latest[2], "scene_id": doc["scene_id"], "art_direction": a[2], "light": rebased,
                   "source_ref": {"screenplay_experiment_id": latest[0]["id"], "art_experiment_id": art_id, "plan_experiment_id": plan[0]["id"] if plan else None},
                   "note": f"Rebased onto screenplay revision {(latest[2].get('revision') or {}).get('number')}. {imp['summary']}"}
        if plan_art:
            payload["direction_plan"] = plan_art
        out = self._create_and_run(name or f"{exp['name']} (rebased)", payload, experiment_id)
        out["impact"] = imp
        log("light.rebased", from_experiment=experiment_id, to_experiment=out["experiment"]["id"])
        return out

    def compare(self, run_a, run_b):
        docs = []
        for rid in (run_a, run_b):
            r = self.svc.get_run(rid)
            if r["craft_id"] != "lighting" or r["run_status"] != "completed" or r["envelope"]["artifact"].get("schema") != "filmcraft.lighting_plan.v1":
                raise Conflict("both runs must be completed lighting plans")
            exp = self.svc.get_experiment(r["experiment_id"])
            docs.append((r["envelope"]["artifact"], exp))
        (a, ea), (b, eb) = docs
        if a["scene_id"] != b["scene_id"] or a["project_id"] != b["project_id"]:
            raise Conflict("the plans are for different scenes")
        ma, mb = a["analysis"]["metrics"], b["analysis"]["metrics"]
        labels = [("lights_on", "Lights switched on"), ("natural_sources", "Natural sources"), ("separation_lights", "Backlights and rims"), ("mean_kelvin", "Average colour temperature (K)"), ("key_kelvin", "Key light colour temperature (K)"),
                  ("key_softness", "Key light softness (0 hard, 1 soft)"), ("key_fill_ratio", "Key to fill ratio on the people"), ("peak_key_fill_ratio", "Key to fill ratio at the peak of the scene"), ("contrast", "Contrast across the playing area"),
                  ("shadow_fraction", "Share of the playing area in shadow"), ("mean_level", "Average level on the playing area (0-1)"), ("motivated_fraction", "Share of lights with a visible reason"), ("adjusted_shots", "Shots with their own adjustment")]

        def key(doc):
            k = next((l for l in doc["lights"] if l["role"] == "key"), None) or next((l for l in doc["lights"] if l["role"] == "motivated"), None)
            return {k2: k[k2] for k2 in ("id", "name", "source", "x", "y", "rotation_deg", "intensity", "color_temp_k", "beam_angle_deg", "softness")} if k else None
        la, lb = {l["id"]: l for l in a["lights"]}, {l["id"]: l for l in b["lights"]}

        def view(exp):
            art = exp["input"]["art_direction"]
            return {"layout": art["layout"], "props": art["props"], "palette": art["style"].get("palette", []), "treatment": art["treatment"]}
        return {"a": {"run_id": run_a, "plan": a["plan"], "art_treatment": a["source"]["art"]["treatment_name"], "key": key(a)}, "b": {"run_id": run_b, "plan": b["plan"], "art_treatment": b["source"]["art"]["treatment_name"], "key": key(b)},
                "metrics": [{"metric": lbl, "key": k, "a": ma.get(k), "b": mb.get(k), "differs": ma.get(k) != mb.get(k)} for k, lbl in labels],
                "readings": {"a": a["analysis"]["reading"], "b": b["analysis"]["reading"]},
                "differences": {"lights_only_a": sorted(l["name"] for i, l in la.items() if i not in lb), "lights_only_b": sorted(l["name"] for i, l in lb.items() if i not in la),
                                "moved": sorted(la[i]["name"] for i in la if i in lb and (abs(la[i]["x"] - lb[i]["x"]) > 0.03 or abs(la[i]["y"] - lb[i]["y"]) > 0.03))},
                "intent": {"a": a["plan"].get("intent", ""), "b": b["plan"].get("intent", "")}, "conditions": {"a": a["conditions"], "b": b["conditions"]},
                "docs": {"a": {"lights": a["lights"], "stage": {"width_m": view(ea)["layout"]["width_m"], "depth_m": view(ea)["layout"]["depth_m"]}, "art": view(ea)}, "b": {"lights": b["lights"], "stage": {"width_m": view(eb)["layout"]["width_m"], "depth_m": view(eb)["layout"]["depth_m"]}, "art": view(eb)}},
                "model_note": a["analysis"]["model_note"]}

    # ---- reusable setups ----------------------------------------------------------------------------------------------------
    def setups(self, project_id):
        with self.svc.db.read() as conn:
            rows = conn.execute("SELECT id FROM experiments WHERE craft_id='lighting' AND json_extract(input_json,'$.schema')=? AND json_extract(input_json,'$.project_id')=? ORDER BY created_at, rowid", (SETUP_SCHEMA, project_id)).fetchall()
        latest = {}
        for r in rows:
            exp = self.svc.get_experiment(r["id"])
            run = self.lab._latest_completed(exp)
            if run:
                doc = self._artifact(run["id"])
                s = doc["setup"]
                latest[s["id"]] = {"setup_id": s["id"], "name": s["name"], "summary": s.get("summary", ""), "experiment_id": exp["id"], "run_id": run["id"], "lights": len(s["lights"]), "from_scene_id": s.get("from_scene_id", ""),
                                   "by_role": doc["analysis"]["by_role"], "created_at": exp["created_at"]}
        return list(latest.values())

    def _setup_doc(self, experiment_id):
        exp = self.svc.get_experiment(experiment_id)
        if exp["craft_id"] != "lighting" or exp["input"].get("schema") != SETUP_SCHEMA:
            raise Conflict("that experiment is not a lighting setup")
        run = self.lab._latest_completed(exp)
        if not run:
            raise Conflict("that lighting setup has no completed run")
        return self._artifact(run["id"])

    def save_setup(self, plan_experiment_id, setup_id, name, summary="", parent=None):
        exp, run, doc = self._plan_exp(plan_experiment_id)
        lights = [{k: v for k, v in l.items() if k not in ("previous_status",)} for l in doc["lights"]]
        payload = {"schema": SETUP_SCHEMA, "project_id": doc["project_id"], "setup": {"id": setup_id, "name": name, "summary": summary, "from_scene_id": doc["scene_id"], "from_plan_id": doc["plan"]["id"], "lights": lights}}
        problems = validate(payload, SETUP_SCHEMA)
        if problems:
            raise InvalidInput("the setup does not match filmcraft.lighting_setup.v1", problems)
        made = self.svc.create_experiment("lighting", name, payload, f"Saved from plan {doc['plan']['name']}", parent=parent)
        run = self.svc.run_experiment(made["id"])
        return {"experiment": self.svc.get_experiment(made["id"]), "run": run}

    # ---- exports -------------------------------------------------------------------------------------------------------------------
    def export(self, run_id, kind, overrides=()):
        overrides = [o for o in overrides if o]
        bad = [o for o in overrides if o not in OVERRIDES]
        if bad:
            raise InvalidInput(f"unknown override(s): {', '.join(bad)}")
        run = self.svc.get_run(run_id)
        if run["craft_id"] != "lighting" or run["run_status"] != "completed":
            raise InvalidInput("only a completed lighting plan can be exported this way")
        art_doc = run["envelope"]["artifact"]
        if art_doc.get("schema") == SETUP_SCHEMA:
            if kind != "lighting-setup-json":
                raise InvalidInput(f"'{kind}' is not an export of a lighting setup")
            return {"media_type": "application/json", "filename": f"{art_doc['project_id']}.{art_doc['setup']['id']}.lighting-setup.json", "data": art_doc}
        if kind not in WORKING | MANIFESTS:
            raise InvalidInput(f"'{kind}' is not an export of a lighting plan")
        exp = self.svc.get_experiment(run["experiment_id"])
        sp, art, plan = exp["input"]["screenplay"], exp["input"]["art_direction"], exp["input"].get("direction_plan")
        base = f"{art_doc['project_id']}.{art_doc['scene_id']}.{art_doc['plan']['id']}"
        ctx = {"run_id": run["id"], "experiment_id": exp["id"], "exported_at": now(), "app_version": config.VERSION, "approval": {"status": run["approval_status"], "reviewer": run["reviewer"], "approved_at": run["approval_timestamp"], "note": run["review_note"]}}
        if kind == "lighting-plan-json":
            return {"media_type": "application/json", "filename": f"{base}.lighting-plan.json", "data": art_doc}
        if kind == "light-schedule-csv":
            return {"media_type": "text/csv", "filename": f"{base}.light-schedule.csv", "text": lexp.schedule_csv(art_doc, art, plan)}
        if kind == "lighting-instructions":
            return {"media_type": "application/json", "filename": f"{base}.lighting-instructions.json", "data": self._instructions(art_doc, art, plan, ctx)}
        return self._manifest(run, exp, art_doc, sp, art, plan, overrides, base)

    def _instructions(self, doc, art, plan, ctx):
        ins = lexp.instructions(doc, art, plan, ctx)
        bad = validate(ins, "filmcraft.lighting_instructions.v1")
        if bad:
            raise RuntimeError(f"generated lighting instructions invalid: {bad[:3]}")
        return ins

    def _manifest(self, run, exp, doc, sp, art, plan, overrides, base):
        with self.svc.db.read() as conn:
            row = conn.execute("SELECT manifest_json, overrides_json FROM derived_exports WHERE run_id=? AND kind=?", (run["id"], "lighting-manifest")).fetchone()
        if row:
            return {"media_type": "application/json", "filename": f"{base}.lighting-manifest.json", "data": _loads(row["manifest_json"]), "existing": True, "overrides": _loads(row["overrides_json"])}
        if run["approval_status"] not in ("approved", "exported"):
            raise Conflict("only an approved lighting plan can be exported as a manifest. Approving is a separate step in the review screen.")
        problems, used = [], []
        try:
            imp = self.impact(exp["id"])
        except (Conflict, NotFound, KeyError):
            imp = {"stale": False, "summary": ""}
        if imp["stale"]:
            if "acknowledge_stale" in overrides:
                used.append("acknowledge_stale")
            else:
                problems.append(f"the script, the art design or the director's plan changed after this plan was made ({imp['summary']}). Rebase the plan, or export anyway with 'acknowledge_stale'")
        att = doc["analysis"]["readiness"]["attention"]
        if att:
            if "allow_open_findings" in overrides:
                used.append("allow_open_findings")
            else:
                problems.append(f"{att} finding(s) still need attention. Fix them, or export anyway with 'allow_open_findings'")
        pending = [l["id"] for l in doc["lights"] if l["status"] == "needs_review"] + [a["id"] for a in doc.get("adjustments", []) if a["status"] == "needs_review"]
        if pending:
            if "allow_pending" in overrides:
                used.append("allow_pending")
            else:
                problems.append(f"{len(pending)} item(s) are waiting for review ({', '.join(pending[:5])}). Review them, or export anyway with 'allow_pending'")
        art_status = self._art_approval(exp)
        if art_status not in ("approved", "exported"):
            if "allow_unapproved_art" in overrides:
                used.append("allow_unapproved_art")
            else:
                problems.append(f"the art treatment this plan is lit for is not approved yet (it is {art_status or 'missing'}). Approve it in the Art Lab, or export anyway with 'allow_unapproved_art'")
        if problems:
            raise Conflict("; ".join(problems))
        ctx = {"run_id": run["id"], "experiment_id": exp["id"], "exported_at": now(), "app_version": config.VERSION, "overrides": used,
               "source_status": "stale_acknowledged" if "acknowledge_stale" in used else "current",
               "approval": {"status": "approved", "reviewer": run["reviewer"], "approved_at": run["approval_timestamp"], "note": run["review_note"]}}
        manifest = lexp.lighting_manifest(ctx, doc, art, plan, sp)
        manifest["art_reference"]["art_approval_status"] = art_status
        manifest["manifest_sha256"] = ""
        from app.hashing import sha256
        manifest["manifest_sha256"] = sha256({k: v for k, v in manifest.items() if k != "manifest_sha256"})
        bad = validate(manifest, "filmcraft.lighting_manifest.v1")
        if bad:
            raise RuntimeError(f"generated filmcraft.lighting_manifest.v1 invalid: {bad[:3]}")
        with self.svc.db.write() as conn:
            conn.execute("INSERT INTO derived_exports (run_id, kind, manifest_id, manifest_json, manifest_sha256, overrides_json, exported_at) VALUES (?,?,?,?,?,?,?)",
                         (run["id"], "lighting-manifest", manifest["manifest_id"], canonical(manifest), manifest["manifest_sha256"], canonical(used), ctx["exported_at"]))
            self.svc._event(conn, exp["id"], run["id"], "export.lighting-manifest", actor=run["reviewer"] or "local-user", manifest_sha256=manifest["manifest_sha256"], overrides=used)
        log("export.derived", run_id=run["id"], kind="lighting-manifest", overrides=used)
        return {"media_type": "application/json", "filename": f"{base}.lighting-manifest.json", "data": manifest, "existing": False, "overrides": used}

    def _art_approval(self, exp):
        ref = (exp["input"].get("source_ref") or {}).get("art_experiment_id")
        if not ref:
            return None
        try:
            _, run, _ = self._art_of(self._art_lineage_latest(exp["input"]["screenplay"]["project"]["id"], exp["input"]["scene_id"], ref))
        except (Conflict, NotFound, KeyError):
            return None
        approved = self._latest_approved_art(exp, ref)
        return approved or run["approval_status"]

    def _latest_approved_art(self, exp, ref):
        """'approved' if the exact treatment version the plan was made for (or any later one) has an approved run."""
        project_id, scene_id = exp["input"]["screenplay"]["project"]["id"], exp["input"]["scene_id"]
        latest = self._art_lineage_latest(project_id, scene_id, ref)
        for eid in {ref, latest}:
            e = self.svc.get_experiment(eid)
            if any(r["approval_status"] in ("approved", "exported") for r in e["runs"] if r["run_status"] == "completed"):
                return "approved"
        return None
