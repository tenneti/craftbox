"""CB0 browser tests: the single-craft wizard and History (Playwright + Edge). See browser_base for the plumbing.
Every wizard step is checked with assert_ui_contract (guidelines/ui-standard.md)."""
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))   # so `python -m unittest tests.test_browser` finds the helpers

from browser_base import BrowserCase, expect, sync_playwright  # noqa: E402
from ui_contract import assert_ui_contract  # noqa: E402

NEXT = "#view-new [data-ui=next]"
BACK = "#view-new [data-ui=back]"
GLOBAL_IDS = {"detail-notice", "continue-wizard", "duplicate", "compare", "cmp-selection", "cmp-summary"}   # header tabs and the History view


def tid(name):   # the page holds several wizards: scope CB0 selectors to the single-craft view
    return f"[data-testid={name}]" if name.startswith("tab-") or name in GLOBAL_IDS else f"#view-new [data-testid={name}]"


@unittest.skipIf(sync_playwright is None, "playwright not installed (pip install -r requirements-dev.txt)")
class BrowserTests(BrowserCase):
    def start(self):
        self.page.click("[data-testid=tab-new]")   # the Scene Lab is the default tab; these tests drive the single-craft wizard

    # ---- helpers -------------------------------------------------------------------------
    def title(self, n):
        expect(self.page.locator(tid("step-title"))).to_contain_text(f"Step {n} of 5")
        assert_ui_contract(self.page, "#wizard")

    def choose(self, craft):
        self.page.click(f"[data-craft={craft}]")
        self.page.click(NEXT)
        self.title(2)
        expect(self.page.locator(tid("input-json"))).not_to_have_value("")  # example finished loading

    def save(self, name):
        self.page.fill(tid("exp-name"), name)
        self.page.click(tid("experiment-save"))
        expect(self.page.locator(tid("save-state"))).to_contain_text("Saved as")

    def to_run(self, craft="screenwriting", name="exp", payload=None):
        self.choose(craft)
        if payload is not None:
            self.page.fill(tid("input-json"), json.dumps(payload))
        self.save(name)
        self.page.click(NEXT)
        self.title(3)

    def run_it(self):
        self.page.click(tid("run-experiment"))
        expect(self.page.locator(tid("run-result"))).to_be_visible()

    def to_review(self, **kw):
        self.to_run(**kw)
        self.run_it()
        self.page.click(NEXT)
        self.title(4)

    def history(self):
        self.page.click(tid("tab-history"))
        self.page.wait_for_selector("#exp-table tbody tr, #exp-empty:not([hidden])")

    # ---- step 1 --------------------------------------------------------------------------
    def test_01_choose_step_explains_itself_and_blocks_planned(self):
        page = self.page
        self.title(1)
        expect(page.locator(tid("step-intro"))).to_contain_text("filmmaking job")
        self.assertEqual(page.locator("#wizard-mount .craftcard").count(), 23)
        self.assertEqual(page.locator("#wizard-mount .craftcard:not(.planned)").count(), 6)
        expect(page.locator(NEXT)).to_be_disabled()
        expect(page.locator(tid("next-why"))).to_contain_text("Choose a craft")
        page.click("[data-craft=costume]")
        expect(page.locator(NEXT)).to_be_disabled()
        expect(page.locator(tid("next-why"))).to_contain_text("planned")
        page.fill(tid("craft-filter"), "camera")
        self.assertLess(page.locator("#wizard-mount .craftcard").count(), 23)
        page.fill(tid("craft-filter"), "zzz")
        expect(page.locator(tid("craft-list"))).to_contain_text("No craft matches")

    # ---- step 2: one Save, nothing lost --------------------------------------------------
    def test_02_input_errors_appear_beside_the_buttons(self):
        page = self.page
        self.choose("screenwriting")
        self.assertIn("romance-pilot", page.locator(tid("input-json")).input_value())
        expect(page.locator(NEXT)).to_be_disabled()
        expect(page.locator(tid("next-why"))).to_contain_text("Save the experiment first")
        page.click(tid("experiment-save"))  # no name
        expect(page.locator(f"{tid('input-form')} [data-testid=error-save]")).to_contain_text("name")
        page.fill(tid("exp-name"), "x")
        page.fill(tid("input-json"), "{not json")
        page.click(tid("try-input"))
        expect(page.locator(f"{tid('input-form')} [data-testid=error-try]")).to_contain_text("not valid JSON")
        page.click(tid("experiment-save"))
        expect(page.locator(f"{tid('input-form')} [data-testid=error-save]")).to_contain_text("not valid JSON")
        self.assertEqual(page.locator(tid("input-json")).input_value(), "{not json")  # typing survived the errors
        page.fill(tid("input-json"), json.dumps({"project_id": "p"}))
        page.click(tid("experiment-save"))
        expect(page.locator(f"{tid('input-form')} [data-testid=error-save]")).to_contain_text("missing required property")
        assert_ui_contract(page, "#wizard")

    def test_03_saving_never_clears_and_shows_state(self):
        page = self.page
        self.choose("screenwriting")
        text_before = None
        page.fill(tid("exp-name"), "Keep me")
        page.fill(tid("exp-notes"), "some notes")
        text_before = page.locator(tid("input-json")).input_value()
        page.click(tid("experiment-save"))
        expect(page.locator(tid("save-state"))).to_contain_text("Saved as “Keep me”")
        self.assertEqual(page.locator(tid("input-json")).input_value(), text_before)
        self.assertEqual(page.locator(tid("exp-name")).input_value(), "Keep me")
        self.assertEqual(page.locator(tid("exp-notes")).input_value(), "some notes")
        expect(page.locator(tid("experiment-save"))).to_be_disabled()  # nothing changed, and it says why
        expect(page.locator(tid("experiment-save"))).to_have_attribute("title", "Nothing has changed since the last save.")
        expect(page.locator(NEXT)).to_be_enabled()
        page.fill(tid("exp-name"), "Keep me v2")
        expect(page.locator(tid("save-state"))).to_contain_text("Changed, not saved yet")
        expect(page.locator(NEXT)).to_be_disabled()
        expect(page.locator(tid("experiment-save"))).to_be_enabled()
        page.click(tid("experiment-save"))
        expect(page.locator(tid("save-state"))).to_contain_text("Keep me v2")
        self.history()
        self.assertEqual(page.locator("#exp-table tbody tr").count(), 2)  # a change creates a new experiment

    def test_04_drafts_survive_failed_request_and_reload(self):
        page = self.page
        self.choose("cinematography")
        page.fill(tid("exp-name"), "Draft survives")
        data = json.loads(page.locator(tid("input-json")).input_value())
        data["shots"][0]["lens_mm"] = 77
        page.fill(tid("input-json"), json.dumps(data))
        page.route("**/api/experiments", lambda route: route.abort())
        page.click(tid("experiment-save"))
        expect(page.locator(f"{tid('input-form')} [data-testid=error-save]")).to_be_visible()
        self.assertEqual(page.locator(tid("exp-name")).input_value(), "Draft survives")
        page.unroute("**/api/experiments")
        page.reload(); page.wait_for_selector("body[data-ready=true]")
        self.title(2)  # reopened where the work was
        self.assertEqual(page.locator(tid("exp-name")).input_value(), "Draft survives")
        self.assertEqual(json.loads(page.locator(tid("input-json")).input_value())["shots"][0]["lens_mm"], 77)

    def test_05_saved_experiment_reopens_at_its_step_after_reload(self):
        page = self.page
        self.to_review(name="Reload me")
        page.reload(); page.wait_for_selector("body[data-ready=true]")
        self.title(4)
        expect(page.locator(tid("review-form"))).to_contain_text("Reload me")

    # ---- steps 3-5: lifecycle ------------------------------------------------------------
    def test_06_full_lifecycle_approve_and_export(self):
        page = self.page
        self.to_run(name="Lifecycle approve")
        expect(page.locator(NEXT)).to_be_disabled()
        expect(page.locator(tid("next-why"))).to_contain_text("Run the experiment first")
        self.run_it()
        expect(page.locator(tid("run-result"))).to_contain_text("completed")
        page.click(tid("run-experiment"))  # run again -> repeatable
        expect(page.locator(tid("repro"))).to_contain_text("Repeatable")
        page.click(tid("verify-run"))
        expect(page.locator(f"{tid('run-form')} [data-testid=notice-run]")).to_contain_text("Verified")
        page.click(NEXT); self.title(4)
        expect(page.locator(tid("approve"))).to_be_disabled()
        expect(page.locator(tid("review-form"))).to_contain_text("Submit for review first")
        page.click(tid("submit-review"))
        expect(page.locator(tid("review-status"))).to_contain_text("Waiting for your decision")
        page.click(tid("approve"))  # no reviewer yet
        expect(page.locator(f"{tid('review-form')} [data-testid=error-review]")).to_contain_text("name")
        page.fill(tid("reviewer"), "Tester")
        page.fill(tid("review-note"), "looks right")
        page.click(tid("approve"))
        expect(page.locator(tid("review-status"))).to_contain_text("Approved")
        self.assertEqual(page.locator(tid("review-note")).input_value(), "looks right")  # not cleared
        page.click(NEXT); self.title(5)
        self.assertEqual(page.locator(NEXT).count(), 0)
        with page.expect_download() as dl:
            page.click(tid("export-manifest"))
        with open(dl.value.path(), encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertEqual((manifest["schema"], manifest["approval"]["reviewer"]), ("filmcraft.export_manifest.v1", "Tester"))
        expect(page.locator(f"{tid('export-form')} [data-testid=notice-export]")).to_contain_text("Nothing was sent to Dreambox")
        page.click(BACK); self.title(4)
        expect(page.locator(tid("review-status"))).to_contain_text("already exported")
        page.click(NEXT); page.click(tid("new-experiment"))
        self.title(1)
        self.assertEqual(page.locator("#wizard-mount .craftcard.selected").count(), 1)  # craft stays chosen for the next attempt

    def test_07_reject_requires_note_and_is_advice_not_a_dead_end(self):
        page = self.page
        self.to_review(name="Reject me")
        page.click(tid("submit-review"))
        page.fill(tid("reviewer"), "Tester")
        page.click(tid("reject"))
        expect(page.locator(f"{tid('review-form')} [data-testid=error-review]")).to_contain_text("note")
        page.fill(tid("review-note"), "Wrong lens")
        page.click(tid("reject"))
        expect(page.locator(tid("review-status"))).to_contain_text("Rejected")
        expect(page.locator(tid("submit-review"))).to_be_enabled()  # can resubmit
        page.click(NEXT); self.title(5)
        expect(page.locator(tid("export-manifest"))).to_be_disabled()
        expect(page.locator(tid("export-form"))).to_contain_text("approve this result first")

    def test_08_failed_run_is_explained_and_cannot_be_reviewed(self):
        page = self.page
        bad = json.loads(self._fixture("screenwriting"))
        bad["slugline"] = "UNKNOWN"
        self.to_run(name="Bad slugline", payload=bad)
        self.run_it()
        expect(page.locator(tid("run-result"))).to_contain_text("The craft rejected this input")
        page.click(NEXT); self.title(4)
        expect(page.locator(tid("review-status"))).to_contain_text("failed, so there is nothing to review")
        expect(page.locator(tid("submit-review"))).to_be_disabled()

    def test_09_slow_actions_show_a_progress_panel(self):
        page = self.page
        self.to_run(name="Slow")

        def slow(route):
            time.sleep(1.2)
            route.continue_()

        page.route("**/api/experiments/*/run", slow)
        page.click(tid("run-experiment"))
        expect(page.locator(f"{tid('run-form')} [data-ui=progress]")).to_contain_text("Running")
        expect(page.locator(tid("run-result"))).to_be_visible()
        expect(page.locator("[data-ui=progress]")).to_have_count(0)

    # ---- the three pilots -----------------------------------------------------------------
    def _fixture(self, craft):
        return self.page.evaluate("c => fetch(`/api/crafts/${c}/fixture`).then(r => r.text())", craft)

    def test_10_all_three_pilots_work_through_the_wizard(self):
        page = self.page
        # Screenwriting -> scene; Cinematography (fixture needs a real scene) ; Editing fed by cinematography's output
        self.to_review(craft="screenwriting", name="Pilot scene")
        page.click(NEXT); self.title(5)
        page.click(tid("new-experiment"))
        scene = page.evaluate("""async () => {
            const fx = await (await fetch('/api/crafts/screenwriting/fixture')).json();
            return (await (await fetch('/api/crafts/screenwriting/run', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(fx)})).json()).artifact; }""")
        cam = json.loads(self._fixture("cinematography"))
        cam["scene"] = scene
        self.choose("cinematography")
        page.fill(tid("input-json"), json.dumps(cam))
        self.save("Pilot camera")
        page.click(NEXT); self.title(3); self.run_it()
        self.assertIn("filmcraft.shot_plan.v1", page.locator(tid("run-output")).inner_text())
        plan = json.loads(page.locator(tid("run-output")).inner_text())
        page.click(tid("tab-history")); page.click("[data-testid=tab-new]")
        page.click(NEXT); page.click(NEXT); page.click(tid("new-experiment"))
        self.choose("editing")
        page.fill(tid("input-json"), json.dumps({"shot_plan": plan}))
        self.save("Pilot edit")
        page.click(NEXT); self.title(3); self.run_it()
        self.assertIn("filmcraft.edit_plan.v1", page.locator(tid("run-output")).inner_text())

    def test_11_try_without_saving_saves_nothing(self):
        page = self.page
        self.choose("screenwriting")
        page.click(tid("try-input"))
        expect(page.locator(tid("try-output"))).to_contain_text("Not saved")
        self.history()
        self.assertEqual(page.locator("#exp-table tbody tr").count(), 0)
        expect(page.locator("#exp-empty")).to_contain_text("Nothing here yet")

    # ---- history ---------------------------------------------------------------------------
    def test_12_history_compare_across_experiments_duplicate_and_resume(self):
        page = self.page
        self.choose("cinematography")
        self.save("Cam A")
        data = json.loads(page.locator(tid("input-json")).input_value())
        data["shots"][0]["lens_mm"] = 35
        page.fill(tid("input-json"), json.dumps(data))
        page.fill(tid("exp-name"), "Cam B")
        page.click(tid("experiment-save"))
        expect(page.locator(tid("save-state"))).to_contain_text("Cam B")
        page.click(NEXT); self.run_it()
        self.history()
        page.locator("#exp-table tbody tr", has_text="Cam A").click()
        page.click(tid("continue-wizard"))  # no runs yet -> resumes at the Run step
        self.title(3); self.run_it()
        page.click(tid("tab-history"))
        page.locator("#exp-table tbody tr", has_text="Cam A").click()
        expect(page.locator("#detail h2")).to_have_text("Cam A")
        page.locator(".run input.cmp").first.check()
        page.locator("#exp-table tbody tr", has_text="Cam B").click()
        expect(page.locator("#detail h2")).to_have_text("Cam B")
        page.locator(".run input.cmp").first.check()
        page.click(tid("compare"))
        expect(page.locator(tid("cmp-summary"))).to_contain_text("Outputs differ")
        expect(page.locator("#compare-body")).to_contain_text("artifact.shots[SC-001-A].lens_mm")
        page.click("#duplicate")
        expect(page.locator(f"#detail h2")).to_have_text("Cam B (copy)")
        page.select_option("#f-craft", "editing")
        expect(page.locator("#exp-table tbody tr")).to_have_count(0)

    def test_13_history_check_repeatable_and_events(self):
        page = self.page
        self.to_review(name="Events")
        page.click(tid("submit-review"))
        expect(page.locator(tid("review-status"))).to_contain_text("Submitted")
        self.history()
        page.locator("#exp-table tbody tr", has_text="Events").click()
        page.locator(".run button.verify").first.click()
        expect(page.locator(tid("detail-notice"))).to_contain_text("Verified")
        page.locator(".run button.history").first.click()
        expect(page.locator(".events li")).to_have_count(4)  # created, run, submit, verify
        page.click(tid("continue-wizard"))
        self.title(4)


if __name__ == "__main__":
    unittest.main()
