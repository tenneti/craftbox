"""Regenerate the CB1 sample exports in ./samples by running the real workflow against a throwaway database.

    .venv\\Scripts\\python.exe scripts\\make_samples.py

Uses only local, deterministic code (no network, no AI, no Dreambox). Safe to re-run; it overwrites only the
files in ./samples. The decisions in the sample plans (which shots are approved/rejected) are scripted here and
stand in for a person's choices; manifests carry a sample reviewer name and today's timestamps.
"""
import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core import execute, get_fixture  # noqa: E402
from app.experiments import ExperimentService  # noqa: E402
from app.lab import LabService  # noqa: E402

OUT = ROOT / "samples"
REVIEWER = "Sample Reviewer"


def write(name, data):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def main():
    with tempfile.TemporaryDirectory() as tmp:
        svc = ExperimentService(Path(tmp) / "samples.db")
        lab = LabService(svc)
        doc = get_fixture("screenwriting", "screenplay")
        sp_exp = svc.create_experiment("screenwriting", "The Closing Hour: revision 1", doc)
        sp_run = svc.run_experiment(sp_exp["id"])
        sp = sp_run["envelope"]["artifact"]
        write("the-closing-hour.screenplay.json", sp)
        write("the-closing-hour.fountain", lab.export(sp_run["id"], "script")["text"])

        runs = {}
        for key, preset in (("A", "intimate"), ("B", "observational")):
            draft = lab.draft_plan(sp_exp["id"], "SC-001", {"preset": preset}, f"Plan {key} ({preset})")
            plan = copy.deepcopy(draft["run"]["envelope"]["artifact"])
            for i, s in enumerate(plan["shots"]):          # scripted director's decisions: approve everything except one rejected shot in A
                s["status"] = "rejected" if (key == "A" and s["shot_id"].endswith("S04")) else "approved"
                if s["status"] == "rejected":
                    s["review_note"] = "The wide holds the distance too long; the OTS on the next shot already says it."
            saved = lab.save_plan(draft["experiment"]["id"], plan, f"Plan {key} (director's decisions)", "scripted sample decisions")
            run_id = saved["run"]["id"]
            svc.submit_for_review(run_id, REVIEWER)
            svc.approve(run_id, REVIEWER, "Sample approval")
            runs[key] = (saved["experiment"]["id"], run_id, saved["run"]["envelope"]["artifact"])
            art = runs[key][2]
            tag = f"plan-{key}-{preset}"
            write(f"{tag}.direction-plan.json", art)
            write(f"{tag}.blocking.json", lab.export(run_id, "blocking")["data"])
            listing = lab.export(run_id, "shot-list")["data"]
            write(f"{tag}.shot-list.json", listing)
            write(f"{tag}.shot-list.csv", lab.export(run_id, "shot-list-csv")["text"])
            write(f"{tag}.shot-plan.json", lab.export(run_id, "shot-plan")["data"])
            write(f"{tag}.shot-manifest.json", lab.export(run_id, "shot-manifest")["data"])
            if key == "A":
                write(f"{tag}.scene-manifest.json", lab.export(run_id, "scene-manifest")["data"])
        write("approaches-A-vs-B.comparison.json", lab.compare_plans(runs["A"][1], runs["B"][1]))

        # script revision after approval: what changes, which shots are affected, and the rebased plan (nothing overwritten)
        rev = copy.deepcopy(doc)
        rev["revision"] = {"number": 2, "note": "Softer line at the platform"}
        rev["scenes"][0]["elements"][16]["text"] = "The day after you left. I waited on the platform until the lights went out."
        sp2_exp = svc.create_experiment("screenwriting", "The Closing Hour: revision 2", rev, parent=sp_exp["id"])
        sp2_run = svc.run_experiment(sp2_exp["id"])
        impact = lab.impact(runs["A"][0], sp2_exp["id"])
        write("change-tracking/revision-1-to-2.compare.json", svc.compare_runs(sp_run["id"], sp2_run["id"]))
        write("change-tracking/plan-A.impact.json", impact)
        rebased = lab.rebase(runs["A"][0], sp2_exp["id"], "Plan A (rebased to revision 2)")
        write("change-tracking/plan-A.rebased.direction-plan.json", rebased["run"]["envelope"]["artifact"])
        write("change-tracking/README.txt",
              "Revision 2 changes one line (SC-001-E17). Plan A's approved shots that cover it went back to 'needs_review' in the rebased plan;\n"
              "every other shot kept its approval. The original approved plan is a separate, unchanged record.\n")
        write("README.md", README.format(secs=sp["analysis"]["totals"]["estimated_seconds"], a=len(runs["A"][2]["shots"]), b=len(runs["B"][2]["shots"]),
                                         affected=len(impact["affected_shots"])))
    print(f"Wrote {sum(1 for _ in OUT.rglob('*') if _.is_file())} files to {OUT}")


README = """# CB1 sample exports: "The Closing Hour"

Generated by `scripts/make_samples.py` from the real Craftbox workflow (no AI, no network). One original
romantic-drama scene, two characters, one location, about {secs} seconds.

| File | What it is |
|---|---|
| `the-closing-hour.screenplay.json` | The screenplay (`filmcraft.screenplay.v1`) with timings, beats and content hashes |
| `the-closing-hour.fountain` | The same screenplay as a readable script (scene and character IDs are kept) |
| `plan-A-intimate.*` | Approach A (close, handheld, reactive): {a} shots. Direction plan, blocking, shot list (JSON and CSV), Cinematography-compatible shot plan, shot manifest, scene manifest |
| `plan-B-observational.*` | Approach B (wide, still, restrained): {b} shots. Same set of files (scene manifest is identical in content, so only A has one) |
| `approaches-A-vs-B.comparison.json` | Side-by-side measures of the two approaches and their stated intent |
| `change-tracking/` | A later script revision: the comparison, which {affected} approved shots it affects, and the rebased plan |

Manifests (`filmcraft.scene_manifest.v1`, `filmcraft.shot_manifest.v1`) are prepared for a future Dreambox Scene Maker
import adapter. They are inert files: `auto_import` is false and nothing here touches Dreambox. Sample decisions,
the reviewer name and timestamps are scripted; a person's real decisions would differ.
"""

if __name__ == "__main__":
    main()
