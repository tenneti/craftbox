"""Scene Lab service: screenplay and direction versions, script-change impact, rebase and gated exports.

Built entirely on CB0's experiment store: every screenplay or plan version is an experiment (with a
parent link) and every result a run, so versioning, hashing, approval and export reuse the same rules.
Nothing here overwrites an experiment, run or export.
"""
import json

from app import config
from app.crafts.direction import exports as dexp
from app.crafts.direction import impact as dimpact
from app.crafts.screenwriting import fountain, screenplay
from app.core import execute
from app.experiments import Conflict, InvalidInput, NotFound, canonical, now
from app.hashing import sha256
from app.logging_setup import log
from app.validation import validate

SCREENPLAY_KINDS = {"screenplay-json", "script"}
PLAN_KINDS = {"blocking", "shot-list", "shot-list-csv", "shot-plan"}
MANIFEST_KINDS = {"scene-manifest", "shot-manifest"}
OVERRIDES = {"acknowledge_stale", "allow_pending"}
SP_WHERE = "craft_id='screenwriting' AND json_extract(input_json,'$.schema')='filmcraft.screenplay.v1'"


def _loads(t):
    return json.loads(t) if t is not None else None


class LabService:
    def __init__(self, svc):
        self.svc = svc

    # ---- helpers ------------------------------------------------------------------------------------
    def _latest_completed(self, experiment):
        runs = [r for r in experiment["runs"] if r["run_status"] == "completed"]
        return runs[-1] if runs else None

    def _artifact(self, run_id):
        return self.svc.get_run(run_id)["envelope"]["artifact"]

    def _screenplay_of(self, experiment_id):
        exp = self.svc.get_experiment(experiment_id)
        if exp["craft_id"] != "screenwriting" or exp["input"].get("schema") != screenplay.SCHEMA:
            raise Conflict("that experiment is not a screenplay version")
        run = self._latest_completed(exp)
        if not run:
            raise Conflict("that screenplay version has no completed run; run it first")
        return exp, run, self._artifact(run["id"])

    def _latest_screenplay(self, project_id):
        with self.svc.db.read() as conn:
            row = conn.execute(f"SELECT id FROM experiments WHERE {SP_WHERE} AND json_extract(input_json,'$.project.id')=? ORDER BY created_at DESC, rowid DESC", (project_id,)).fetchall()
        for r in row:
            exp = self.svc.get_experiment(r["id"])
            run = self._latest_completed(exp)
            if run:
                return exp, run, self._artifact(run["id"])
        return None

    def _plan_of(self, experiment_id):
        exp = self.svc.get_experiment(experiment_id)
        if exp["craft_id"] != "direction":
            raise Conflict("that experiment is not a direction plan")
        run = self._latest_completed(exp)
        if not run:
            raise Conflict("that plan has no completed run")
        return exp, run, self._artifact(run["id"])

    def _create_and_run(self, craft, name, payload, parent, notes=""):
        exp = self.svc.create_experiment(craft, name, payload, notes, parent=parent)
        run = self.svc.run_experiment(exp["id"])
        return {"experiment": self.svc.get_experiment(exp["id"]), "run": run}

    # ---- projects and versions -------------------------------------------------------------------
    def projects(self):
        with self.svc.db.read() as conn:
            rows = conn.execute(f"""SELECT json_extract(input_json,'$.project.id') AS pid, COUNT(*) AS versions, MAX(created_at) AS updated,
                (SELECT json_extract(e2.input_json,'$.project.title') FROM experiments e2 WHERE e2.craft_id='screenwriting' AND json_extract(e2.input_json,'$.project.id')=json_extract(e.input_json,'$.project.id')
                 AND json_extract(e2.input_json,'$.schema')='filmcraft.screenplay.v1' ORDER BY e2.created_at DESC, e2.rowid DESC LIMIT 1) AS title
                FROM experiments e WHERE {SP_WHERE} GROUP BY pid ORDER BY updated DESC""").fetchall()
        return [{"project_id": r["pid"], "title": r["title"], "versions": r["versions"], "updated_at": r["updated"]} for r in rows]

    def overview(self, project_id):
        with self.svc.db.read() as conn:
            sp_rows = conn.execute(f"SELECT id FROM experiments WHERE {SP_WHERE} AND json_extract(input_json,'$.project.id')=? ORDER BY created_at, rowid", (project_id,)).fetchall()
            dir_rows = conn.execute("SELECT id FROM experiments WHERE craft_id='direction' AND json_extract(input_json,'$.screenplay.project.id')=? ORDER BY created_at, rowid", (project_id,)).fetchall()
        if not sp_rows:
            raise NotFound("project not found")
        versions, latest = [], None
        for r in sp_rows:
            exp = self.svc.get_experiment(r["id"])
            run = self._latest_completed(exp)
            last = exp["runs"][-1] if exp["runs"] else None
            entry = {"experiment_id": exp["id"], "name": exp["name"], "created_at": exp["created_at"], "parent_experiment_id": exp["parent_experiment_id"],
                     "revision": (exp["input"].get("revision") or {}).get("number"), "note": (exp["input"].get("revision") or {}).get("note", ""),
                     "run_id": run["id"] if run else None, "run_status": last["run_status"] if last else None,
                     "approval_status": run["approval_status"] if run else None, "scene_hashes": {}, "estimated_seconds": None}
            if run:
                art = self._artifact(run["id"])
                entry["scene_hashes"] = {s["scene_id"]: s["scene_hash"] for s in art["analysis"]["scenes"]}
                entry["estimated_seconds"] = art["analysis"]["totals"]["estimated_seconds"]
                latest = (exp, run, art)
            versions.append(entry)
        plans = []
        for r in dir_rows:
            exp = self.svc.get_experiment(r["id"])
            run = self._latest_completed(exp)
            entry = {"experiment_id": exp["id"], "name": exp["name"], "created_at": exp["created_at"], "parent_experiment_id": exp["parent_experiment_id"],
                     "scene_id": exp["input"]["scene_id"], "run_id": run["id"] if run else None, "run_status": exp["runs"][-1]["run_status"] if exp["runs"] else None,
                     "approval_status": run["approval_status"] if run else None}
            if run:
                plan = self._artifact(run["id"])
                a = plan["analysis"]
                entry.update(approach=plan["approach"]["name"], approach_id=plan["approach"]["id"], shots=len(plan["shots"]), total_seconds=a["total_seconds"],
                             errors=a["readiness"]["errors"], warnings=a["readiness"]["warnings"], status_summary=a["status_summary"],
                             source_revision=plan["source"]["screenplay_revision"], source_ref=plan["source"].get("ref", {}))
                if latest:
                    imp = dimpact.compute(plan, latest[2])
                    entry.update(stale=imp["stale"], affected_shots=len(imp["affected_shots"]), impact_summary=imp["summary"])
            plans.append(entry)
        return {"project_id": project_id, "title": latest[2]["project"]["title"] if latest else None,
                "latest_screenplay": {"experiment_id": latest[0]["id"], "run_id": latest[1]["id"], "revision": (latest[2].get("revision") or {}).get("number")} if latest else None,
                "screenplay_versions": versions, "plans": plans}

    # ---- stateless helpers for the editor ------------------------------------------------------------
    @staticmethod
    def check_screenplay(doc):
        if not isinstance(doc, dict):
            raise InvalidInput("screenplay must be a JSON object")
        problems = validate(doc, "filmcraft.screenplay.v1")
        if problems:
            raise InvalidInput("the screenplay does not match filmcraft.screenplay.v1", problems)

    def analyze_screenplay(self, doc):
        self.check_screenplay(doc)
        try:
            r = execute("screenwriting", doc)
        except ValueError as exc:
            raise InvalidInput(str(exc)) from exc
        return {"artifact": r["artifact"], "warnings": r["warnings"]}

    def export_script(self, doc):
        self.check_screenplay(doc)
        return fountain.export(doc)

    def import_script(self, text, project_id=None, title=None):
        try:
            doc = fountain.parse(text, project_id, title)
        except ValueError as exc:
            raise InvalidInput(str(exc)) from exc
        check = {"ok": True, "error": None, "warnings": []}
        try:
            check["warnings"] = execute("screenwriting", doc)["warnings"]
        except ValueError as exc:
            check.update(ok=False, error=str(exc))
        return {"screenplay": doc, "check": check}

    def idea(self, idea):
        try:
            return screenplay.skeleton(idea)
        except ValueError as exc:
            raise InvalidInput(str(exc)) from exc

    # ---- direction versions ---------------------------------------------------------------------------
    def draft_plan(self, screenplay_experiment_id, scene_id, approach, name, parent=None, note=""):
        exp, run, art = self._screenplay_of(screenplay_experiment_id)
        payload = {"screenplay": art, "scene_id": scene_id, "approach": approach or {}, "source_ref": {"experiment_id": exp["id"], "run_id": run["id"]}, "note": note or ""}
        return self._create_and_run("direction", name, payload, parent)

    def save_plan(self, base_experiment_id, plan, name, note=""):
        base = self.svc.get_experiment(base_experiment_id)
        if base["craft_id"] != "direction":
            raise Conflict("the base experiment is not a direction plan")
        payload = {"screenplay": base["input"]["screenplay"], "scene_id": base["input"]["scene_id"], "plan": plan,
                   "source_ref": base["input"].get("source_ref", {}), "note": note or ""}
        return self._create_and_run("direction", name, payload, base_experiment_id)

    def analyze_plan(self, base_experiment_id, plan):
        base = self.svc.get_experiment(base_experiment_id)
        problems = validate(plan, "filmcraft.direction_plan.v1")
        if problems:
            raise InvalidInput("the plan does not match filmcraft.direction_plan.v1", problems)
        try:
            r = execute("direction", {"screenplay": base["input"]["screenplay"], "scene_id": base["input"]["scene_id"], "plan": plan, "source_ref": base["input"].get("source_ref", {})})
        except ValueError as exc:
            raise InvalidInput(str(exc)) from exc
        return {"analysis": r["artifact"]["analysis"], "warnings": r["warnings"]}

    def _against(self, plan_art, against_experiment_id):
        if against_experiment_id:
            return self._screenplay_of(against_experiment_id)
        latest = self._latest_screenplay(plan_art["project_id"])
        if not latest:
            raise Conflict("no screenplay version to compare against")
        return latest

    def impact(self, plan_experiment_id, against_experiment_id=None):
        exp, run, plan = self._plan_of(plan_experiment_id)
        a_exp, a_run, sp = self._against(plan, against_experiment_id)
        out = dimpact.compute(plan, sp)
        out["against"] = {"experiment_id": a_exp["id"], "run_id": a_run["id"], "revision": (sp.get("revision") or {}).get("number")}
        out["plan"] = {"experiment_id": exp["id"], "run_id": run["id"], "source_revision": plan["source"]["screenplay_revision"]}
        return out

    def rebase(self, plan_experiment_id, against_experiment_id=None, name=None):
        exp, run, plan = self._plan_of(plan_experiment_id)
        a_exp, a_run, sp = self._against(plan, against_experiment_id)
        if not dimpact.compute(plan, sp)["stale"]:
            raise Conflict("this plan already matches that screenplay version; nothing to rebase")
        rebased, imp = dimpact.rebase(plan, sp)
        rev = (sp.get("revision") or {}).get("number")
        payload = {"screenplay": sp, "scene_id": plan["scene_id"], "plan": rebased,
                   "source_ref": {"experiment_id": a_exp["id"], "run_id": a_run["id"]}, "note": f"Rebased onto screenplay revision {rev}. {imp['summary']}"}
        out = self._create_and_run("direction", name or f"{exp['name']} (rebased to rev {rev})", payload, plan_experiment_id)
        out["impact"] = imp
        log("plan.rebased", from_experiment=plan_experiment_id, to_experiment=out["experiment"]["id"], affected=len(imp["affected_shots"]))
        return out

    def compare_plans(self, run_a, run_b):
        rows, arts = [], []
        for rid in (run_a, run_b):
            r = self.svc.get_run(rid)
            if r["craft_id"] != "direction" or r["run_status"] != "completed":
                raise Conflict("both runs must be completed direction plans")
            arts.append(r["envelope"]["artifact"])
        a, b = arts
        if a["scene_id"] != b["scene_id"] or a["project_id"] != b["project_id"]:
            raise Conflict("the plans are for different scenes")

        def m(p):
            an = p["analysis"]; v = an["variety"]
            act = [s for s in p["shots"] if s["status"] != "rejected"]
            return {"Approach": p["approach"]["name"], "Shots": len(act), "Total seconds": an["total_seconds"], "Average shot (s)": an["avg_shot_seconds"],
                    "Close-ups (ECU/CU)": v["close_ups"], "Wide (WS/EWS)": v["wide"], "Distinct setups": v["distinct_setups"], "Variety score": v["variety_score"],
                    "Camera moves (not static)": sum(1 for s in act if s["movement"] != "static"), "Distinct purposes": len(an["purposes"]),
                    "Continuity errors": an["readiness"]["errors"], "Continuity warnings": an["readiness"]["warnings"],
                    "Camera sides used": ", ".join(sorted({s["camera_side"] for s in act})), "Approved shots": an["status_summary"]["approved"]}
        ma, mb = m(a), m(b)
        beats = [{"beat_id": pa["beat_id"], "intensity": pa["intensity"], "a_shots": pa["shots"], "a_avg_seconds": pa["avg_shot_seconds"],
                  "b_shots": pb["shots"], "b_avg_seconds": pb["avg_shot_seconds"]} for pa, pb in zip(a["analysis"]["pacing"], b["analysis"]["pacing"])]
        return {"a": {"run_id": run_a}, "b": {"run_id": run_b}, "metrics": [{"metric": k, "a": ma[k], "b": mb[k], "differs": ma[k] != mb[k]} for k in ma], "beats": beats,
                "interpretation": {"a": a["interpretation"]["directorial_intent"], "b": b["interpretation"]["directorial_intent"]}}

    # ---- exports ---------------------------------------------------------------------------------------------
    def export(self, run_id, kind, overrides=()):
        overrides = [o for o in overrides if o]
        bad = [o for o in overrides if o not in OVERRIDES]
        if bad:
            raise InvalidInput(f"unknown override(s): {', '.join(bad)}")
        run = self.svc.get_run(run_id)
        if run["run_status"] != "completed":
            raise Conflict("only completed runs can be exported")
        art = run["envelope"]["artifact"]
        if run["craft_id"] == "screenwriting" and kind in SCREENPLAY_KINDS and art.get("schema") == screenplay.SCHEMA:
            if kind == "script":
                return {"media_type": "text/plain", "filename": f"{art['project']['id']}.fountain", "text": fountain.export(art)}
            return {"media_type": "application/json", "filename": f"{art['project']['id']}.screenplay.json", "data": art}
        if run["craft_id"] != "direction" or kind not in PLAN_KINDS | MANIFEST_KINDS:
            raise InvalidInput(f"'{kind}' is not an export of a {run['craft_id']} run")
        exp = self.svc.get_experiment(run["experiment_id"])
        sp = exp["input"]["screenplay"]
        names = {c["id"]: c["name"] for c in sp["characters"]}
        scene = next(s for s in sp["scenes"] if s["id"] == art["scene_id"])
        base = f"{art['project_id']}.{art['scene_id']}.{art['approach']['id']}"
        if kind == "blocking":
            return {"media_type": "application/json", "filename": f"{base}.blocking.json", "data": dexp.blocking_export(art, scene)}
        if kind == "shot-list":
            return {"media_type": "application/json", "filename": f"{base}.shot-list.json", "data": dexp.shot_list_export(art, names)}
        if kind == "shot-list-csv":
            return {"media_type": "text/csv", "filename": f"{base}.shot-list.csv", "text": dexp.shot_list_csv(dexp.shot_list_export(art, names))}
        if kind == "shot-plan":
            return {"media_type": "application/json", "filename": f"{base}.shot-plan.json", "data": dexp.shot_plan_export(art, names)}
        return self._manifest(run, exp, art, sp, kind, overrides, base)

    def _manifest(self, run, exp, plan, sp, kind, overrides, base):
        with self.svc.db.read() as conn:
            row = conn.execute("SELECT manifest_json, overrides_json FROM derived_exports WHERE run_id=? AND kind=?", (run["id"], kind)).fetchone()
        if row:
            return {"media_type": "application/json", "filename": f"{base}.{kind}.json", "data": _loads(row["manifest_json"]), "existing": True,
                    "overrides": _loads(row["overrides_json"])}
        if run["approval_status"] not in ("approved", "exported"):
            raise Conflict("only an approved plan can be exported as a manifest. Approval is a manual step in Director review.")
        problems = []
        latest = self._latest_screenplay(plan["project_id"])
        imp = dimpact.compute(plan, latest[2]) if latest else {"stale": False, "summary": ""}
        if imp["stale"] and "acknowledge_stale" not in overrides:
            problems.append("the screenplay has changed since this plan was made (" + imp["summary"] + "). Rebase the plan, or export anyway with 'acknowledge_stale'")
        pending = [s["shot_id"] for s in plan["shots"] if s["status"] in ("proposed", "needs_review")]
        if kind == "shot-manifest" and pending and "allow_pending" not in overrides:
            problems.append(f"{len(pending)} shot(s) are not yet approved or rejected ({', '.join(pending[:6])}{'…' if len(pending) > 6 else ''}). Decide them, or export anyway with 'allow_pending'")
        if problems:
            raise Conflict("; ".join(problems))
        used = [o for o in overrides if (o == "acknowledge_stale" and imp["stale"]) or (o == "allow_pending" and kind == "shot-manifest" and pending)]
        ctx = {"run_id": run["id"], "experiment_id": exp["id"], "exported_at": now(), "app_version": config.VERSION, "overrides": used,
               "source_status": "stale_acknowledged" if (imp["stale"] and "acknowledge_stale" in used) else "current",
               "approval": {"status": "approved", "reviewer": run["reviewer"], "approved_at": run["approval_timestamp"], "note": run["review_note"]}}
        manifest = (dexp.scene_manifest if kind == "scene-manifest" else dexp.shot_manifest)(ctx, plan, sp)
        schema = "filmcraft.scene_manifest.v1" if kind == "scene-manifest" else "filmcraft.shot_manifest.v1"
        problems = validate(manifest, schema)
        if problems:
            raise RuntimeError(f"generated {schema} invalid: {problems[:3]}")
        with self.svc.db.write() as conn:
            conn.execute("INSERT INTO derived_exports (run_id, kind, manifest_id, manifest_json, manifest_sha256, overrides_json, exported_at) VALUES (?,?,?,?,?,?,?)",
                         (run["id"], kind, manifest["manifest_id"], canonical(manifest), manifest["manifest_sha256"], canonical(used), ctx["exported_at"]))
            self.svc._event(conn, exp["id"], run["id"], f"export.{kind}", actor=run["reviewer"] or "local-user", manifest_sha256=manifest["manifest_sha256"], overrides=used)
        log("export.derived", run_id=run["id"], kind=kind, overrides=used)
        return {"media_type": "application/json", "filename": f"{base}.{kind}.json", "data": manifest, "existing": False, "overrides": used}
