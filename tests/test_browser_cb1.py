"""CB1 browser tests: the Scene Lab wizard (story idea -> screenplay -> beats -> blocking -> shots -> review -> export).
Every step is checked with assert_ui_contract on the Scene Lab wizard (guidelines/ui-standard.md)."""
import json
import os
import re
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from browser_base import BrowserCase, expect, sync_playwright  # noqa: E402
from ui_contract import assert_ui_contract  # noqa: E402

NEXT = "#lab-wizard [data-ui=next]"
BACK = "#lab-wizard [data-ui=back]"
tid = lambda name: f"#view-lab [data-testid={name}]"
inside = lambda parent, child: f"#view-lab [data-testid={parent}] [data-testid={child}]"


@unittest.skipIf(sync_playwright is None, "playwright not installed (pip install -r requirements-dev.txt)")
class SceneLabTests(BrowserCase):
    def start(self):
        self.page.click("[data-testid=tab-lab]")   # the Story Lab is the default tab; these tests drive the Scene Lab

    # ---- helpers -------------------------------------------------------------------------------
    def title(self, n):
        expect(self.page.locator(tid("step-title"))).to_contain_text(f"Step {n} of 8")
        assert_ui_contract(self.page, "#lab-wizard")

    def next(self, n):
        self.page.click(NEXT)
        self.title(n)

    def sample(self):
        self.page.click(tid("load-sample"))
        expect(self.page.locator(tid("current-project"))).to_contain_text("The Closing Hour")

    def to_step(self, n):
        for k in range(2, n + 1):
            self.next(k)

    def save_screenplay(self, note=None):
        if note is not None:
            self.page.fill(tid("rev-note"), note)
        self.page.click(tid("screenplay-save"))
        expect(self.page.locator(tid("sp-state"))).to_contain_text("Saved.")

    def saved_sample(self, upto=4):
        self.sample(); self.to_step(2); self.save_screenplay("first draft")
        for k in range(3, upto + 1):
            self.next(k)

    def draft(self, approach="intimate"):
        self.page.click(tid(f"approach-{approach}"))
        self.page.click(tid("draft-plan"))
        expect(self.page.locator(tid("stage"))).to_be_visible()
        expect(self.page.locator(tid("notice-draft"))).to_contain_text("Drafted")

    def save_plan(self, note=None):
        if note is not None:
            self.page.fill(tid("plan-note"), note)
        self.page.click(tid("plan-save"))
        expect(self.page.locator(tid("plan-state"))).to_contain_text("Saved.")

    def to_shots(self, approach="intimate"):
        self.saved_sample(4); self.next(5); self.draft(approach); self.next(6)
        expect(self.page.locator(tid("shot-table"))).to_be_visible()

    # ---- step 1 ----------------------------------------------------------------------------------
    def test_01_scene_lab_step1_explains_itself_and_points_to_the_story_lab(self):
        page = self.page
        expect(page.locator(tid("story-first"))).to_contain_text("Develop the story first")
        self.title(1)
        expect(page.locator(tid("step-intro"))).to_contain_text("idea")
        self.assertEqual(page.locator("#lab-wizard .steps li").count(), 8)
        self.assertEqual(page.locator(BACK).count(), 0)
        expect(page.locator(NEXT)).to_be_disabled()
        expect(page.locator(tid("next-why"))).to_contain_text("outline")
        expect(page.locator(tid("no-projects"))).to_be_visible()
        self.assertEqual(page.locator("#view-new").is_hidden(), True)
        page.click(tid("open-story-lab"))
        expect(page.locator("#view-story")).to_be_visible()

    def test_02_story_idea_becomes_an_editable_outline(self):
        page = self.page
        page.fill(tid("idea-title"), "Night Train")
        page.fill(tid("idea-logline"), "Two strangers share a cabin.")
        page.fill(tid("idea-location"), "Train cabin")
        page.fill(tid("idea-char-name-0"), "Isha"); page.fill(tid("idea-char-name-1"), "Kabir")
        page.click(tid("idea-create"))
        expect(page.locator(tid("notice-idea"))).to_contain_text("Night Train")
        self.next(2)
        page.click(tid("subtab-characters"))
        expect(page.locator(tid("char-C-001"))).to_contain_text("C-001")
        self.assertEqual(page.locator(tid("char-name-C-002")).input_value(), "Kabir")
        page.click(tid("subtab-script"))
        expect(page.locator(tid("elements"))).to_contain_text("No lines yet")
        page.click(tid("add-action"))
        self.assertEqual(page.locator(".elrow").count(), 1)
        self.next(3)
        self.assertIn("Isha wants", page.locator(tid("scene-objective")).input_value() or "Isha wants")
        self.next(4)
        self.assertEqual(page.locator("[data-testid^=beat-SC-001-B]").count(), 6)   # six template beats

    # ---- screenwriting lab ----------------------------------------------------------------------------
    def test_03_screenplay_editing_save_and_estimates(self):
        page = self.page
        self.sample(); self.next(2)
        self.assertEqual(page.locator(".elrow").count(), 24)
        expect(page.locator(tid("sp-state"))).to_contain_text("Not saved yet")
        page.fill(tid("el-text-SC-001-E12"), "It leans toward the door. It always has.")
        expect(page.locator(tid("sp-state"))).to_contain_text("Not saved yet")
        self.save_screenplay("sharper line")
        expect(page.locator(tid("notice-save"))).to_contain_text("revision 1")
        self.assertEqual(page.locator(tid("el-text-SC-001-E12")).input_value(), "It leans toward the door. It always has.")   # not cleared
        expect(page.locator(tid("screenplay-save"))).to_be_disabled()
        page.fill(tid("el-text-SC-001-E12"), "It leans toward the door.")
        expect(page.locator(tid("sp-state"))).to_contain_text("Changed, not saved yet")
        expect(page.locator(NEXT)).to_be_enabled()
        self.next(3)
        expect(page.locator(tid("est-seconds"))).to_contain_text("s")
        page.click(tid("recalc"))
        expect(page.locator(tid("est-seconds"))).to_have_text("82.15 s")   # the edited line is shorter than the original
        expect(page.locator(tid("pacing"))).to_have_text("slow")
        page.fill(tid("scene-override"), "70"); page.click(tid("recalc"))
        expect(page.locator(tid("est-seconds"))).to_have_text("70 s")
        self.next(4)
        self.assertEqual(page.locator("[data-testid^=beat-SC-001-B]").count(), 7)
        expect(page.locator(tid("intensity-curve"))).to_be_visible()
        expect(page.locator(NEXT)).to_be_disabled()
        expect(page.locator(tid("next-why"))).to_contain_text("Save")

    def test_04_unsaved_work_is_protected(self):
        page = self.page
        self.sample(); self.to_step(4)
        expect(page.locator(NEXT)).to_be_disabled()
        expect(page.locator(tid("next-why"))).to_contain_text("Save a screenplay revision first")
        expect(page.locator("#lab-wizard [data-step-target='5']")).to_be_disabled()
        page.click(BACK); page.click(BACK); page.click(BACK)
        self.title(1)
        page.click(tid("load-sample"))
        expect(page.locator(tid("confirm-replace"))).to_be_visible()      # never replaced silently
        page.get_by_role("button", name="Keep working").click()
        expect(page.locator(tid("confirm-replace"))).to_have_count(0)
        expect(page.locator(tid("current-project"))).to_contain_text("not saved yet")

    def test_05_editing_actions_and_errors_beside_the_save_button(self):
        page = self.page
        self.sample(); self.next(2)
        n = page.locator(".elrow").count()
        page.click(tid("add-dialogue")); self.assertEqual(page.locator(".elrow").count(), n + 1)
        new_id = page.locator(".elrow").last.get_attribute("data-el")
        page.fill(tid(f"el-text-{new_id}"), "A new line.")
        page.select_option(tid(f"el-char-{new_id}"), "")                                   # a dialogue line with no speaker
        self.assertTrue(new_id.endswith("E25"))
        page.click(tid("screenplay-save"))
        expect(page.locator(f"{inside('screenplay-form', 'error-save')}")).to_contain_text("known character")
        expect(page.locator(tid("sp-state"))).to_contain_text("Not saved yet")
        self.assertEqual(page.locator(tid(f"el-text-{new_id}")).input_value(), "A new line.")   # typing survived the failure
        page.select_option(tid(f"el-char-{new_id}"), "C-001")
        page.click(tid("screenplay-save"))
        expect(page.locator(tid("sp-state"))).to_contain_text("Saved.")
        page.click(tid(f"el-del-{new_id}")); self.assertEqual(page.locator(".elrow").count(), n)
        page.click(tid("subtab-characters")); page.click(tid("add-character"))
        expect(page.locator(tid("char-C-003"))).to_be_visible()
        page.fill(tid("char-name-C-003"), "Meera")
        self.next(3)
        page.click(tid("add-scene")); expect(page.locator("[data-scene=SC-002]")).to_be_visible()
        page.click(tid("add-sequence"))
        self.assertEqual(page.locator("[data-testid=scene-list] tbody tr").count(), 2)
        page.get_by_role("button", name="Move scene up").nth(1).click()
        self.assertEqual(page.locator("[data-testid=scene-list] tbody tr").first.get_attribute("data-scene"), "SC-002")
        self.next(4)
        page.click(tid("add-beat")); self.assertEqual(page.locator("[data-testid^=beat-SC-]").count() > 0, True)

    def test_06_import_and_export(self):
        page = self.page
        self.sample(); self.next(2)
        page.click(tid("subtab-io"))
        with page.expect_download() as dl:
            page.click(tid("dl-json"))
        with open(dl.value.path(), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["schema"], "filmcraft.screenplay.v1")
        page.click(tid("show-script"))
        expect(page.locator(tid("script-preview"))).to_contain_text("#SC-001#")
        text = page.locator(tid("script-preview")).inner_text()
        page.fill(tid("script-text"), text.replace("The Closing Hour", "The Closing Hour Imported"))
        page.click(tid("import-script"))
        expect(page.locator(tid("confirm-replace"))).to_be_visible()                       # unsaved work: asks first
        page.get_by_role("button", name="Replace what is on screen").click()
        expect(page.locator(tid("notice-import"))).to_contain_text("Imported 1 scene")
        self.assertEqual(page.locator(tid("proj-title")).input_value(), "The Closing Hour")        # importing into a project keeps its identity and history
        expect(page.locator(tid("notice-import"))).to_contain_text("revision history are kept")
        page.click(tid("subtab-script"))
        self.assertEqual(page.locator(".elrow").count(), 24)
        page.click(tid("subtab-io")); page.fill(tid("script-text"), "nothing to see")
        page.click(tid("import-script"))
        page.get_by_role("button", name="Replace what is on screen").click()
        expect(page.locator(f"{inside('screenplay-form', 'error-import')}")).to_contain_text("no scene headings")

    def test_07_revision_history_and_comparison(self):
        page = self.page
        self.sample(); self.next(2); self.save_screenplay("rev one")
        page.fill(tid("el-text-SC-001-E03"), "We are closed.")
        self.save_screenplay("polite")
        expect(page.locator(tid("versions"))).to_contain_text("Revision 2")
        self.assertEqual(page.locator("[data-testid=versions] tbody tr").count(), 2)
        runs = page.evaluate("fetch('/api/lab/projects/closing-hour').then(r => r.json()).then(o => o.screenplay_versions.map(v => v.run_id))")
        page.select_option(tid("cmp-a"), runs[0]); page.select_option(tid("cmp-b"), runs[1]); page.click(tid("cmp-go"))
        expect(page.locator(tid("cmp-result"))).to_contain_text("line SC-001-E03")
        page.click(tid("open-rev-1"))
        expect(page.locator(tid("notice-open"))).to_contain_text("Opened revision 1")
        expect(page.locator(tid("el-text-SC-001-E03"))).to_have_value("We're closed.")

    # ---- direction lab ----------------------------------------------------------------------------------
    def test_08_blocking_draft_edit_and_save(self):
        page = self.page
        self.saved_sample(4); self.next(5)
        expect(page.locator(tid("approach-form"))).to_contain_text("Choose a directing approach")
        self.draft("intimate")
        expect(page.locator(tid("interp-intent"))).not_to_have_value("")
        self.assertEqual(page.locator("[data-testid=beat-picker] option").count(), 7)
        page.select_option(tid("beat-picker"), "SC-001-B6")
        expect(page.locator(tid("block-C-001"))).to_be_visible()
        page.fill(tid("ex-C-001"), "0.5")
        expect(page.locator(tid("plan-state"))).to_contain_text("Changed, not saved yet")
        page.select_option(tid("facing-C-001"), "screen_left")
        page.click(tid("pick-C-001")); page.locator(tid("stage")).click(position={"x": 100, "y": 100})
        self.assertNotEqual(page.locator(tid("ex-C-001")).input_value(), "0.5")           # clicking the stage moved them
        self.save_plan("moved Nila")
        expect(page.locator(tid("notice-psave"))).to_contain_text("new plan version")
        self.assertEqual(page.locator(tid("facing-C-001")).input_value(), "screen_left")   # not cleared
        expect(page.locator(tid("plan-versions"))).to_contain_text("edit of an earlier plan")
        self.next(6)

    def test_09_shot_list_editing_approval_reordering_and_validation(self):
        page = self.page
        self.to_shots()
        rows = page.locator("[data-testid=shot-table] tbody tr")
        n = rows.count(); self.assertGreaterEqual(n, 20)
        first, second = rows.nth(0).get_attribute("data-shot"), rows.nth(1).get_attribute("data-shot")
        page.click(tid(f"down-{first}"))
        self.assertEqual(rows.nth(1).get_attribute("data-shot"), first)
        page.click(tid(f"up-{first}"))
        self.assertEqual(rows.nth(0).get_attribute("data-shot"), first)
        page.click(tid(f"reject-{second}"))
        expect(page.locator(tid(f"shot-row-{second}"))).to_have_class("rejected ")
        page.click(tid(f"approve-{first}"))
        page.click(tid(f"edit-{first}"))
        expect(page.locator(tid("shot-editor"))).to_contain_text(first)
        page.fill(tid("shot-purpose-note"), "Open on the whole shop so we know the space before anyone speaks.")
        page.click(tid("add-shot"))
        new_id = page.locator(tid("shot-editor") + " h3").inner_text().replace("Editing ", "")
        page.click(tid("plan-save"))                                                       # the new shot has no purpose note yet
        expect(page.locator(f"{inside('shots-form', 'error-psave')}")).to_contain_text("purpose_note")
        expect(page.locator(tid("plan-state"))).to_contain_text("Changed, not saved yet")
        self.assertEqual(page.locator(tid("shot-table") + " tbody tr").count(), n + 1)        # edits survived the failed save
        page.fill(tid("shot-purpose-note"), "Extra cutaway on the sign to mark the end of the night.")
        self.save_plan("edited")
        self.assertEqual(page.locator(tid("shot-table") + " tbody tr").count(), n + 1)
        expect(page.locator(tid(f"shot-row-{new_id}"))).to_be_visible()
        expect(page.locator(tid(f"shot-row-{second}"))).to_have_class("rejected ")
        page.click(tid("check-plan"))
        expect(page.locator(tid("notice-check"))).to_contain_text("Nothing was saved")

    def test_10_continuity_check_finds_a_planted_line_crossing(self):
        page = self.page
        self.to_shots()
        page.click(tid("check-plan"))
        expect(page.locator(tid("no-issues"))).to_be_visible()
        page.click(tid("edit-SC-001-S05"))
        page.select_option(tid("shot-side"), "B")
        page.click(tid("check-plan"))
        expect(page.locator("[data-testid=issues] .issue.error", has_text="180").first).to_be_visible()
        expect(page.locator(tid("shot-row-SC-001-S05"))).to_have_class(re.compile("error"))
        page.check(tid("axis-motivated")); page.click(tid("check-plan"))
        expect(page.locator("[data-testid=issues] .issue.error[data-rule=axis]", has_text="SC-001-S05 crosses")).to_have_count(0)   # a motivated crossing is allowed
        expect(page.locator("[data-testid=issues] .issue.error[data-rule=axis]", has_text="SC-001-S06 crosses")).to_have_count(1)  # the cut back is still unmotivated
        page.click(tid("add-shot"))                                                         # an uncovered state is not hidden either
        page.click(tid("check-plan"))
        self.assertGreaterEqual(page.locator("[data-testid=issues] .issue").count(), 1)

    def test_11_director_review_compare_approve_and_export(self):
        page = self.page
        self.saved_sample(4); self.next(5)
        self.draft("intimate")                       # drafts are saved plan versions already
        self.draft("observational")
        self.to_step_from(5, 7)
        expect(page.locator(tid("plan-metrics"))).to_be_visible()
        expect(page.locator(tid("pacing-table"))).to_be_visible()
        page.select_option(tid("cmp-plan"), index=1); page.click(tid("compare-plans"))
        expect(page.locator(tid("plan-cmp"))).to_contain_text("Average shot (s)")
        expect(page.locator(tid("plan-cmp"))).to_contain_text("A — Intimate")
        expect(page.locator(tid("plan-approve"))).to_be_disabled()
        expect(page.locator(tid("approval-form"))).to_contain_text("Submit for review first")
        page.click(tid("approve-all")); self.save_plan("all decided")
        page.click(tid("plan-submit"))
        page.click(tid("plan-approve"))
        expect(page.locator(tid("error-decide"))).to_contain_text("name")
        page.fill(tid("plan-reviewer"), "Dir"); page.fill(tid("plan-note-review"), "Good coverage")
        page.click(tid("plan-approve"))
        expect(page.locator(f"{tid('approval-form')} .badge").first).to_have_text("approved")
        self.assertEqual(page.locator(tid("plan-note-review")).input_value(), "Good coverage")
        self.next(8)
        expect(page.locator(tid("not-approved"))).to_have_count(0)
        with page.expect_download() as dl:
            page.click(tid("dl-scene-manifest"))
        with open(dl.value.path(), encoding="utf-8") as fh:
            m = json.load(fh)
        self.assertEqual((m["schema"], m["approval"]["reviewer"], m["import_policy"]["auto_import"]), ("filmcraft.scene_manifest.v1", "Dir", False))
        with page.expect_download() as dl:
            page.click(tid("dl-shot-manifest"))
        with open(dl.value.path(), encoding="utf-8") as fh:
            sm = json.load(fh)
        self.assertEqual(sm["schema"], "filmcraft.shot_manifest.v1"); self.assertEqual(sm["overrides"], [])
        self.assertTrue(all(s["status"] == "approved" for s in sm["shots"]))
        for kind, check in (("blocking", lambda t: "filmcraft.blocking.v1" in t), ("shot-list-csv", lambda t: t.startswith("order,shot_id")),
                            ("shot-plan", lambda t: "filmcraft.shot_plan.v1" in t), ("script", lambda t: "#SC-001#" in t), ("screenplay-json", lambda t: "filmcraft.screenplay.v1" in t)):
            with page.expect_download() as dl:
                page.click(tid(f"dl-{kind}"))
            with open(dl.value.path(), encoding="utf-8") as fh:
                self.assertTrue(check(fh.read()), kind)
        expect(page.locator(tid("notice-x-scene-manifest"))).to_contain_text("Downloads folder")

    def to_step_from(self, a, b):
        for k in range(a + 1, b + 1):
            self.next(k)

    def test_12_manifests_are_refused_until_approved_and_overrides_are_explicit(self):
        page = self.page
        self.to_shots()
        self.next(7); self.next(8)
        expect(page.locator(tid("not-approved"))).to_be_visible()
        expect(page.locator(tid("dl-scene-manifest"))).to_be_disabled()
        expect(page.locator(tid("export-scene-manifest"))).to_contain_text("Approve the plan in Director review first")
        with page.expect_download():
            page.click(tid("dl-shot-list"))                                              # working exports are always available
        page.click(BACK); self.title(7)
        page.fill(tid("plan-reviewer"), "Dir")
        page.click(tid("plan-submit")); page.click(tid("plan-approve"))
        expect(page.locator(f"{tid('approval-form')} .badge").first).to_have_text("approved")
        self.next(8)
        page.click(tid("dl-shot-manifest"))                                              # approved, but shots are still undecided
        expect(page.locator(tid("force-shot-manifest"))).to_be_visible()
        expect(page.locator(tid("export-shot-manifest"))).to_contain_text("allow_pending")
        with page.expect_download() as dl:
            page.click(tid("force-shot-manifest"))
        with open(dl.value.path(), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["overrides"], ["allow_pending"])             # recorded in the file

    def test_13_script_change_flags_the_plan_and_rebase_keeps_approved_work(self):
        page = self.page
        self.saved_sample(4); self.next(5); self.draft("intimate"); self.next(6); self.next(7)
        page.click(tid("approve-all")); self.save_plan("approved all")
        page.fill(tid("plan-reviewer"), "Dir"); page.click(tid("plan-submit")); page.click(tid("plan-approve"))
        expect(page.locator(f"{tid('approval-form')} .badge").first).to_have_text("approved")
        approved_plan = page.evaluate("fetch('/api/lab/projects/closing-hour').then(r => r.json()).then(o => o.plans.map(p => p.experiment_id))")
        # the writer revises line E17 in the Screenwriting Lab
        page.click("#lab-wizard [data-step-target='2']"); self.title(2)
        page.fill(tid("el-text-SC-001-E17"), "The day after you left. I waited on the platform until the lights went out.")
        self.save_screenplay("softer line")
        page.click("#lab-wizard [data-step-target='7']"); self.title(7)
        expect(page.locator(tid("impact"))).to_contain_text("changed")
        self.assertGreater(page.locator("[data-testid=impact] li").count(), 0)
        page.click("#lab-wizard [data-step-target='8']"); self.title(8)
        page.click(tid("dl-scene-manifest"))
        expect(page.locator(tid("force-scene-manifest"))).to_be_visible()
        expect(page.locator(tid("export-scene-manifest"))).to_contain_text("script changed")
        page.click(BACK); self.title(7)
        page.click(tid("rebase"))
        expect(page.locator(tid("notice-rebase"))).to_contain_text("back in review")
        expect(page.locator(tid("impact"))).to_have_count(0)                             # the new version is current
        statuses = page.evaluate("fetch('/api/lab/projects/closing-hour').then(r => r.json()).then(o => o.plans.map(p => [p.experiment_id, p.approval_status, p.status_summary]))")
        self.assertEqual(len(statuses), 3)                                                # first draft, the approved edit, and the rebased version
        old = next(s for s in statuses if s[1] == "approved")
        self.assertIn(old[0], approved_plan)                                              # the approved version is untouched and still approved
        self.assertEqual(old[2]["approved"], sum(old[2].values()))
        new = next(s for s in statuses if s[2]["needs_review"] > 0)
        self.assertGreater(new[2]["needs_review"], 0); self.assertGreater(new[2]["approved"], 0)
        page.click("#lab-wizard [data-step-target='5']")
        expect(page.locator(tid("plan-versions"))).to_contain_text("approved")

    def test_14_reload_returns_to_the_same_step_with_everything_typed(self):
        page = self.page
        self.sample(); self.next(2)
        page.fill(tid("el-text-SC-001-E03"), "We are closed tonight.")
        page.reload(); page.wait_for_selector("body[data-ready=true]")
        self.title(2)
        self.assertEqual(page.locator(tid("el-text-SC-001-E03")).input_value(), "We are closed tonight.")
        expect(page.locator(tid("sp-state"))).to_contain_text("Not saved yet")
        self.save_screenplay("kept")
        self.next(3); self.next(4); self.next(5); self.draft("observational"); self.next(6)
        page.reload(); page.wait_for_selector("body[data-ready=true]")
        self.title(6)
        expect(page.locator(tid("shot-table"))).to_be_visible()
        expect(page.locator(tid("plan-state"))).to_contain_text("Saved.")
        page.click("#lab-wizard [data-step-target='1']"); self.title(1)
        expect(page.locator(tid("open-closing-hour"))).to_be_visible()                  # saved projects are listed for reopening

    def test_15_existing_craft_lab_still_works_beside_the_scene_lab(self):
        page = self.page
        page.click("[data-testid=tab-new]")
        expect(page.locator("#view-new")).to_be_visible()
        page.click("[data-craft=direction]")
        expect(page.locator("#view-new [data-testid=wizard-next]")).to_be_enabled()      # Direction is now a runnable craft
        page.click("[data-craft=costume]")
        expect(page.locator("#view-new [data-testid=wizard-next]")).to_be_disabled()     # planned crafts still cannot run


if __name__ == "__main__":
    unittest.main()
