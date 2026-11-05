"""Art Direction service: treatments, style profiles, the asset register, change impact, comparison and gated exports.

Built on CB0's experiment store and the CB1 Lab service. Every treatment version is an experiment (with a parent link) and every
result a run, so versioning, hashing and approval are the same as everywhere else. Treatments are independent: approving one
never touches another. Nothing here overwrites an experiment, run or export.
"""
import json

from app import assetstore, config
from app.crafts.art_direction import exports as aexp
from app.crafts.art_direction import impact as aimpact
from app.crafts.art_direction import layout as lay
from app.core import execute
from app.experiments import Conflict, InvalidInput, NotFound, canonical, now
from app.logging_setup import log
from app.validation import validate

ART_WHERE = "craft_id='art_direction' AND json_extract(input_json,'$.screenplay.project.id')=?"
STYLE_SCHEMA, REGISTER_SCHEMA = "filmcraft.style_profile.v1", "filmcraft.asset_register.v1"
WORKING = {"art-direction-json", "prop-list-csv", "storyboard-metadata"}
MANIFESTS = {"art-direction-manifest", "asset-reference-manifest"}
OVERRIDES = {"acknowledge_stale", "allow_open_findings", "allow_pending"}


def _loads(t):
    return json.loads(t) if t is not None else None


class ArtService:
    def __init__(self, svc, lab, data_dir):
        self.svc, self.lab, self.data_dir = svc, lab, data_dir

    # ---- helpers ---------------------------------------------------------------------------------------------------
    def _latest_completed(self, exp):
        return self.lab._latest_completed(exp)

    def _artifact(self, run_id):
        return self.svc.get_run(run_id)["envelope"]["artifact"]

    def _treatment(self, experiment_id):
        exp = self.svc.get_experiment(experiment_id)
        if exp["craft_id"] != "art_direction" or "screenplay" not in exp["input"]:
            raise Conflict("that experiment is not an art direction treatment")
        run = self._latest_completed(exp)
        if not run:
            raise Conflict("that treatment has no completed run")
        return exp, run, self._artifact(run["id"])

    def _create_and_run(self, name, payload, parent, notes=""):
        exp = self.svc.create_experiment("art_direction", name, payload, notes, parent=parent)
        run = self.svc.run_experiment(exp["id"])
        return {"experiment": self.svc.get_experiment(exp["id"]), "run": run}

    def _plan_experiments(self, project_id, scene_id):
        with self.svc.db.read() as conn:
            rows = conn.execute("SELECT id, parent_experiment_id FROM experiments WHERE craft_id='direction' AND json_extract(input_json,'$.screenplay.project.id')=? "
                                "AND json_extract(input_json,'$.scene_id')=? ORDER BY created_at, rowid", (project_id, scene_id)).fetchall()
        return [(r["id"], r["parent_experiment_id"]) for r in rows]

    def _plan_artifact(self, experiment_id):
        exp = self.svc.get_experiment(experiment_id)
        run = self._latest_completed(exp)
        return (exp, run, self._artifact(run["id"])) if run else None

    def _plan_lineage_latest(self, project_id, scene_id, ref_id):
        """The newest direction plan version descended from ``ref_id`` (or ``ref_id`` itself)."""
        plans = self._plan_experiments(project_id, scene_id)
        children = {}
        for eid, parent in plans:
            children.setdefault(parent, []).append(eid)
        best, stack = ref_id, [ref_id]
        order = {eid: i for i, (eid, _) in enumerate(plans)}
        while stack:
            cur = stack.pop()
            for c in children.get(cur, []):
                stack.append(c)
                if order.get(c, -1) > order.get(best, -1):
                    best = c
        return best

    def latest_register(self, project_id):
        with self.svc.db.read() as conn:
            rows = conn.execute("SELECT id FROM experiments WHERE craft_id='art_direction' AND json_extract(input_json,'$.schema')=? AND json_extract(input_json,'$.project_id')=? ORDER BY created_at DESC, rowid DESC",
                                (REGISTER_SCHEMA, project_id)).fetchall()
        for r in rows:
            exp = self.svc.get_experiment(r["id"])
            run = self._latest_completed(exp)
            if run:
                return exp, run, self._artifact(run["id"])
        return None

    # ---- overview ----------------------------------------------------------------------------------------------------------
    def overview(self, project_id):
        with self.svc.db.read() as conn:
            rows = conn.execute(f"SELECT id FROM experiments WHERE {ART_WHERE} ORDER BY created_at, rowid", (project_id,)).fetchall()
        latest_sp = self.lab._latest_screenplay(project_id)
        items = []
        for r in rows:
            exp = self.svc.get_experiment(r["id"])
            run = self._latest_completed(exp)
            entry = {"experiment_id": exp["id"], "name": exp["name"], "created_at": exp["created_at"], "parent_experiment_id": exp["parent_experiment_id"], "scene_id": exp["input"]["scene_id"],
                     "run_id": run["id"] if run else None, "run_status": exp["runs"][-1]["run_status"] if exp["runs"] else None, "approval_status": run["approval_status"] if run else None}
            if run:
                art = self._artifact(run["id"])
                an = art["analysis"]
                entry.update(treatment_id=art["treatment"]["id"], treatment_name=art["treatment"]["name"], preset=art["treatment"].get("preset"), attention=an["readiness"]["attention"], notes=an["readiness"]["notes"],
                             props=len(art["props"]), objects=len(art["layout"]["objects"]), needs_review=sum(1 for p in art["props"] if p["status"] == "needs_review") + sum(1 for v in art.get("variations", []) if v["status"] == "needs_review"),
                             source_revision=art["source"]["screenplay_revision"])
                if latest_sp:
                    ref = (art["source"].get("ref") or {}).get("plan_experiment_id")
                    plan = None
                    if ref:
                        got = self._plan_artifact(self._plan_lineage_latest(project_id, art["scene_id"], ref))
                        plan = got[2] if got else None
                    imp = aimpact.compute(art, latest_sp[2], plan)
                    entry.update(stale=imp["stale"], affected=len(imp["affected_props"]) + len(imp["affected_variations"]), impact_summary=imp["summary"])
            items.append(entry)
        return {"project_id": project_id, "treatments": items, "styles": self.styles(project_id), "register": self.register_view(project_id)}

    # ---- treatments ---------------------------------------------------------------------------------------------------------
    def presets(self):
        return [{"id": k, "name": v["name"], "summary": v["summary"]} for k, v in lay.PRESETS.items()]

    def _profile(self, style_experiment_id):
        if not style_experiment_id:
            return None
        exp = self.svc.get_experiment(style_experiment_id)
        if exp["craft_id"] != "art_direction" or exp["input"].get("schema") != STYLE_SCHEMA:
            raise Conflict("that experiment is not a style profile")
        run = self._latest_completed(exp)
        if not run:
            raise Conflict("that style profile has no completed run")
        return self._artifact(run["id"])

    def draft(self, screenplay_experiment_id, scene_id, preset, name, plan_experiment_id=None, style_experiment_id=None, parent=None, note=""):
        exp, run, sp = self.lab._screenplay_of(screenplay_experiment_id)
        plan_art = None
        if plan_experiment_id:
            _, _, plan_art = self.lab._plan_of(plan_experiment_id)
        reg = self.latest_register(sp["project"]["id"])
        payload = {"screenplay": sp, "scene_id": scene_id, "preset": preset or "blank", "treatment_name": name, "source_ref": {"screenplay_experiment_id": exp["id"], "plan_experiment_id": plan_experiment_id}, "note": note or ""}
        if plan_art:
            payload["direction_plan"] = plan_art
        if style_experiment_id:
            payload["style_profile"] = self._profile(style_experiment_id)
        if reg:
            payload["asset_register"] = reg[2]
        return self._create_and_run(name or lay.PRESETS.get(preset or "blank", {}).get("name", "Treatment"), payload, parent)

    def save(self, base_experiment_id, art, name, note=""):
        base = self.svc.get_experiment(base_experiment_id)
        if base["craft_id"] != "art_direction" or "screenplay" not in base["input"]:
            raise Conflict("the base experiment is not an art direction treatment")
        payload = {k: v for k, v in base["input"].items() if k in ("screenplay", "scene_id", "direction_plan", "style_profile", "source_ref")}
        payload.update({"art": art, "note": note or ""})
        reg = self.latest_register(base["input"]["screenplay"]["project"]["id"])
        if reg:
            payload["asset_register"] = reg[2]
        return self._create_and_run(name, payload, base_experiment_id)

    def analyze(self, base_experiment_id, art):
        base = self.svc.get_experiment(base_experiment_id)
        problems = validate(art, "filmcraft.art_direction.v1")
        if problems:
            raise InvalidInput("the treatment does not match filmcraft.art_direction.v1", problems)
        payload = {k: v for k, v in base["input"].items() if k in ("screenplay", "scene_id", "direction_plan", "style_profile", "source_ref")}
        payload["art"] = art
        reg = self.latest_register(base["input"]["screenplay"]["project"]["id"])
        if reg:
            payload["asset_register"] = reg[2]
        try:
            r = execute("art_direction", payload)
        except ValueError as exc:
            raise InvalidInput(str(exc)) from exc
        return {"analysis": r["artifact"]["analysis"], "warnings": r["warnings"]}

    def _against(self, exp, art):
        project_id = art["project_id"]
        latest = self.lab._latest_screenplay(project_id)
        if not latest:
            raise Conflict("no screenplay version to compare against")
        ref = (art["source"].get("ref") or {}).get("plan_experiment_id")
        plan = None
        if ref:
            got = self._plan_artifact(self._plan_lineage_latest(project_id, art["scene_id"], ref))
            plan = got
        return latest, plan

    def impact(self, treatment_experiment_id):
        exp, run, art = self._treatment(treatment_experiment_id)
        latest, plan = self._against(exp, art)
        out = aimpact.compute(art, latest[2], plan[2] if plan else None)
        out["against"] = {"screenplay_experiment_id": latest[0]["id"], "screenplay_revision": (latest[2].get("revision") or {}).get("number"),
                          "plan_experiment_id": plan[0]["id"] if plan else None}
        return out

    def rebase(self, treatment_experiment_id, name=None):
        exp, run, art = self._treatment(treatment_experiment_id)
        latest, plan = self._against(exp, art)
        plan_art = plan[2] if plan else None
        if not aimpact.compute(art, latest[2], plan_art)["stale"]:
            raise Conflict("this treatment already matches the latest screenplay and direction plan; nothing to rebase")
        rebased, imp = aimpact.rebase(art, latest[2], plan_art)
        payload = {"screenplay": latest[2], "scene_id": art["scene_id"], "art": rebased,
                   "source_ref": {"screenplay_experiment_id": latest[0]["id"], "plan_experiment_id": (plan[0]["id"] if plan else None)},
                   "note": f"Rebased onto screenplay revision {(latest[2].get('revision') or {}).get('number')}. {imp['summary']}"}
        if plan_art:
            payload["direction_plan"] = plan_art
        if exp["input"].get("style_profile"):
            payload["style_profile"] = exp["input"]["style_profile"]
        reg = self.latest_register(art["project_id"])
        if reg:
            payload["asset_register"] = reg[2]
        out = self._create_and_run(name or f"{exp['name']} (rebased)", payload, treatment_experiment_id)
        out["impact"] = imp
        log("art.rebased", from_experiment=treatment_experiment_id, to_experiment=out["experiment"]["id"])
        return out

    def compare(self, run_a, run_b):
        arts = []
        for rid in (run_a, run_b):
            r = self.svc.get_run(rid)
            if r["craft_id"] != "art_direction" or r["run_status"] != "completed" or r["envelope"]["artifact"].get("schema") != "filmcraft.art_direction.v1":
                raise Conflict("both runs must be completed art direction treatments")
            arts.append(r["envelope"]["artifact"])
        a, b = arts
        if a["scene_id"] != b["scene_id"] or a["project_id"] != b["project_id"]:
            raise Conflict("the treatments are for different scenes")
        ma, mb = a["analysis"]["metrics"], b["analysis"]["metrics"]
        labels = [("central_objects", "Objects in the middle of the stage"), ("furniture", "Furniture"), ("decor", "Decor"), ("props", "Props"), ("personal_props", "Personal props"),
                  ("open_floor", "Open floor"), ("warmth", "Palette warmth (−1 cool, +1 warm)"), ("brightness", "Palette brightness"), ("saturation", "Palette saturation"), ("contrast", "Palette contrast"),
                  ("textures", "Textures"), ("materials", "Materials"), ("variations", "Shot variations"), ("peak_gap", "Distance between the two people at the peak"), ("peak_obstructions", "Objects between them at the peak")]
        oa = {o["id"]: o for o in a["layout"]["objects"]}
        ob = {o["id"]: o for o in b["layout"]["objects"]}
        pa, pb = {p["name"].lower(): p for p in a["props"]}, {p["name"].lower(): p for p in b["props"]}
        return {"a": {"run_id": run_a, "treatment": a["treatment"]}, "b": {"run_id": run_b, "treatment": b["treatment"]},
                "metrics": [{"metric": lbl, "key": k, "a": ma.get(k), "b": mb.get(k), "differs": ma.get(k) != mb.get(k)} for k, lbl in labels],
                "readings": {"a": a["analysis"]["reading"], "b": b["analysis"]["reading"]},
                "palettes": {"a": a["style"].get("palette", []), "b": b["style"].get("palette", [])},
                "differences": {"objects_only_a": sorted(oa[i]["name"] for i in oa if i not in ob), "objects_only_b": sorted(ob[i]["name"] for i in ob if i not in oa),
                                "moved": sorted(oa[i]["name"] for i in oa if i in ob and (abs(oa[i]["x"] - ob[i]["x"]) > 0.03 or abs(oa[i]["y"] - ob[i]["y"]) > 0.03)),
                                "props_only_a": sorted(p["name"] for k, p in pa.items() if k not in pb), "props_only_b": sorted(p["name"] for k, p in pb.items() if k not in pa)},
                "intent": {"a": a["treatment"].get("intent", ""), "b": b["treatment"].get("intent", "")}}

    # ---- style profiles and asset register -------------------------------------------------------------------------------------
    def styles(self, project_id):
        with self.svc.db.read() as conn:
            rows = conn.execute("SELECT id FROM experiments WHERE craft_id='art_direction' AND json_extract(input_json,'$.schema')=? AND json_extract(input_json,'$.project_id')=? ORDER BY created_at, rowid",
                                (STYLE_SCHEMA, project_id)).fetchall()
        latest = {}
        for r in rows:
            exp = self.svc.get_experiment(r["id"])
            run = self._latest_completed(exp)
            if run:
                art = self._artifact(run["id"])
                p = art["profile"]
                latest[p["id"]] = {"profile_id": p["id"], "name": p["name"], "summary": p.get("summary", ""), "experiment_id": exp["id"], "run_id": run["id"], "colours": len(p.get("palette", [])),
                                   "constraints": len(p.get("constraints", [])), "approval_status": run["approval_status"], "created_at": exp["created_at"], "profile": p}
        return list(latest.values())

    def register_view(self, project_id):
        got = self.latest_register(project_id)
        if not got:
            return {"experiment_id": None, "run_id": None, "assets": []}
        exp, run, art = got
        return {"experiment_id": exp["id"], "run_id": run["id"], "assets": [{**a, "file_present": assetstore.present(self.data_dir, a["sha256"])} for a in art["assets"]], "analysis": art["analysis"]}

    def upload(self, data, filename):
        return assetstore.store(self.data_dir, data, filename)

    def from_path(self, path):
        return assetstore.ingest_path(self.data_dir, path)

    # ---- exports -------------------------------------------------------------------------------------------------------------------
    def export(self, run_id, kind, overrides=()):
        overrides = [o for o in overrides if o]
        bad = [o for o in overrides if o not in OVERRIDES]
        if bad:
            raise InvalidInput(f"unknown override(s): {', '.join(bad)}")
        run = self.svc.get_run(run_id)
        if run["craft_id"] != "art_direction" or run["run_status"] != "completed" or run["envelope"]["artifact"].get("schema") != "filmcraft.art_direction.v1":
            raise InvalidInput("only a completed art direction treatment can be exported this way")
        if kind not in WORKING | MANIFESTS:
            raise InvalidInput(f"'{kind}' is not an export of an art direction treatment")
        art = run["envelope"]["artifact"]
        exp = self.svc.get_experiment(run["experiment_id"])
        sp = exp["input"]["screenplay"]
        plan = exp["input"].get("direction_plan")
        base = f"{art['project_id']}.{art['scene_id']}.{art['treatment']['id']}"
        if kind == "art-direction-json":
            return {"media_type": "application/json", "filename": f"{base}.art-direction.json", "data": art}
        if kind == "prop-list-csv":
            return {"media_type": "text/csv", "filename": f"{base}.props.csv", "text": aexp.prop_csv(art)}
        if kind == "storyboard-metadata":
            return {"media_type": "application/json", "filename": f"{base}.storyboard-metadata.json", "data": aexp.storyboard_metadata(art, plan)}
        return self._manifest(run, exp, art, sp, kind, overrides, base)

    def _manifest(self, run, exp, art, sp, kind, overrides, base):
        with self.svc.db.read() as conn:
            row = conn.execute("SELECT manifest_json, overrides_json FROM derived_exports WHERE run_id=? AND kind=?", (run["id"], kind)).fetchone()
        if row:
            return {"media_type": "application/json", "filename": f"{base}.{kind}.json", "data": _loads(row["manifest_json"]), "existing": True, "overrides": _loads(row["overrides_json"])}
        if run["approval_status"] not in ("approved", "exported"):
            raise Conflict("only an approved treatment can be exported as a manifest. Approving is a separate step in the review screen.")
        problems, used = [], []
        try:
            imp = self.impact(exp["id"])
        except (Conflict, NotFound):
            imp = {"stale": False, "summary": ""}
        if imp["stale"]:
            if "acknowledge_stale" in overrides:
                used.append("acknowledge_stale")
            else:
                problems.append(f"the screenplay or the director's plan changed after this design was made ({imp['summary']}). Rebase the treatment, or export anyway with 'acknowledge_stale'")
        att = art["analysis"]["readiness"]["attention"]
        if att:
            if "allow_open_findings" in overrides:
                used.append("allow_open_findings")
            else:
                problems.append(f"{att} finding(s) still need attention. Fix them, or export anyway with 'allow_open_findings'")
        pending = [p["id"] for p in art["props"] if p["status"] == "needs_review"] + [v["id"] for v in art.get("variations", []) if v["status"] == "needs_review"]
        if pending:
            if "allow_pending" in overrides:
                used.append("allow_pending")
            else:
                problems.append(f"{len(pending)} design item(s) are waiting for review ({', '.join(pending[:5])}). Review them, or export anyway with 'allow_pending'")
        if problems:
            raise Conflict("; ".join(problems))
        ctx = {"run_id": run["id"], "experiment_id": exp["id"], "exported_at": now(), "app_version": config.VERSION, "overrides": used,
               "source_status": "stale_acknowledged" if "acknowledge_stale" in used else "current",
               "approval": {"status": "approved", "reviewer": run["reviewer"], "approved_at": run["approval_timestamp"], "note": run["review_note"]}}
        reg = self.latest_register(art["project_id"])
        register = reg[2] if reg else None
        if kind == "art-direction-manifest":
            manifest = aexp.art_manifest(ctx, art, sp)
            schema = "filmcraft.art_direction_manifest.v1"
        else:
            status = {a["sha256"]: assetstore.present(self.data_dir, a["sha256"]) for a in (register or {}).get("assets", [])}
            manifest = aexp.asset_manifest(ctx, art, register, status)
            schema = "filmcraft.asset_reference_manifest.v1"
        bad = validate(manifest, schema)
        if bad:
            raise RuntimeError(f"generated {schema} invalid: {bad[:3]}")
        with self.svc.db.write() as conn:
            conn.execute("INSERT INTO derived_exports (run_id, kind, manifest_id, manifest_json, manifest_sha256, overrides_json, exported_at) VALUES (?,?,?,?,?,?,?)",
                         (run["id"], kind, manifest["manifest_id"], canonical(manifest), manifest["manifest_sha256"], canonical(used), ctx["exported_at"]))
            self.svc._event(conn, exp["id"], run["id"], f"export.{kind}", actor=run["reviewer"] or "local-user", manifest_sha256=manifest["manifest_sha256"], overrides=used)
        log("export.derived", run_id=run["id"], kind=kind, overrides=used)
        return {"media_type": "application/json", "filename": f"{base}.{kind}.json", "data": manifest, "existing": False, "overrides": used}
