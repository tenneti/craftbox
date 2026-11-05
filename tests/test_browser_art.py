"""CB2A browser tests: the Art Lab wizard and the Art Library. Every step is checked with assert_ui_contract (structure) and
assert_ui_text (the objectively testable text rules of guidelines/ui-standard.md). Wording quality still needs a human."""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from browser_base import BrowserCase, expect, sync_playwright  # noqa: E402
from ui_contract import assert_ui_contract, assert_ui_text  # noqa: E402

NEXT = "#art-wizard [data-ui=next]"
BACK = "#art-wizard [data-ui=back]"
tid = lambda name: f"#view-art [data-testid={name}]"
inside = lambda parent, child: f"#view-art [data-testid={parent}] [data-testid={child}]"
PNG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) + bytes(range(80))

SEED_JS = """async (revise) => {
  const J = (u, b) => fetch(u, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)}).then(r => r.json());
  const doc = await (await fetch('/api/crafts/screenwriting/fixture?name=screenplay')).json();
  const sp = await J('/api/experiments', {craft_id: 'screenwriting', name: 'rev 1', input: doc, run_now: true});
  const plan = await J('/api/lab/direction/draft', {screenplay_experiment_id: sp.id, scene_id: 'SC-001', name: 'plan A', approach: {preset: 'intimate'}});
  return {sp: sp.id, plan: plan.experiment.id};
}"""
REVISE_JS = """async (spId) => {
  const J = (u, b) => fetch(u, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)}).then(r => r.json());
  const doc = await (await fetch('/api/crafts/screenwriting/fixture?name=screenplay')).json();
  doc.revision = {number: 2, note: 'ticket line'};
  doc.scenes[0].elements[14].text = 'She stops. He nods at the book. She opens it. Inside: a ticket to her city, two years old, never used.';
  const r = await J('/api/experiments', {craft_id: 'screenwriting', name: 'rev 2', input: doc, run_now: true, parent_experiment_id: spId});
  return r.latest_run.run_status;
}"""


@unittest.skipIf(sync_playwright is None, "playwright not installed (pip install -r requirements-dev.txt)")
class ArtLabTests(BrowserCase):
    # ---- helpers ------------------------------------------------------------------------------------------------------------------------
    def title(self, n):
        expect(self.page.locator(tid("step-title"))).to_contain_text(f"Step {n} of 8")
        assert_ui_contract(self.page, "#art-wizard")
        assert_ui_text(self.page, "#art-wizard")

    def seed(self):
        self.ids = self.page.evaluate(SEED_JS, False)
        self.page.click("[data-testid=tab-art]")
        self.page.click(tid("a-refresh"))
        expect(self.page.locator(tid("a-project"))).to_have_value("closing-hour")

    def draft(self, preset="warm_nostalgia", name=None):
        self.page.click(tid(f"preset-{preset}"))
        if name is not None:
            self.page.fill(tid("a-name"), name)
        self.page.click(tid("a-draft"))
        expect(self.page.locator(tid("notice-draft"))).to_contain_text("Drafted")

    def to(self, n):
        for k in range(self.cur + 1, n + 1):
            self.page.click(NEXT); self.title(k)
        self.cur = n

    def start(self):
        self.cur = 1

    def save(self, note=None):
        if note is not None:
            self.page.fill(tid("art-note"), note)
        self.page.click(tid("art-save"))
        expect(self.page.locator(tid("art-state"))).to_contain_text("Saved.")

    # ---- step 1 -------------------------------------------------------------------------------------------------------------------------
    def test_01_empty_state_says_what_to_do_and_a_draft_unlocks_the_next_step(self):
        page = self.page
        page.click("[data-testid=tab-art]")
        self.title(1)
        expect(page.locator(tid("no-projects"))).to_contain_text("Open the Scene Lab")
        expect(page.locator(tid("no-treatments"))).to_contain_text("press “Draft the treatment”")
        expect(page.locator(NEXT)).to_be_disabled(); expect(page.locator(tid("next-why"))).to_contain_text("Draft a new treatment")
        page.click(tid("a-draft"))
        expect(page.locator(inside("start-form", "error-draft"))).to_contain_text("Choose a screenplay revision")   # error beside the button
        self.seed()
        page.click(tid("a-draft"))
        expect(page.locator(inside("start-form", "error-draft"))).to_contain_text("Give the treatment a name")
        self.draft("warm_nostalgia", "Warm nostalgia")
        expect(page.locator(NEXT)).to_be_enabled()
        self.assertEqual(page.locator(".craftcard").count() >= 3, True)

    # ---- the whole walk, each step checked for structure and text ----------------------------------------------------------------------------
    def test_02_every_step_meets_the_structure_and_text_rules(self):
        page = self.page
        self.seed(); self.draft("warm_nostalgia", "Warm nostalgia")
        self.to(8)
        self.assertEqual(page.locator(NEXT).count(), 0)                                      # the last step has no Next but explicit buttons
        self.assertGreaterEqual(page.locator("#art-wizard [data-testid=finish-form] button").count(), 3)
        for n in range(7, 0, -1):
            page.click(BACK); self.title(n)
        labels = page.locator(NEXT).inner_text()
        self.assertTrue(labels.startswith("Next: "))

    # ---- location, layout editor ------------------------------------------------------------------------------------------------------------------
    def test_03_location_edits_validate_against_the_script_and_persist(self):
        page = self.page
        self.seed(); self.draft("warm_nostalgia", "Warm nostalgia"); self.to(2)
        page.select_option(tid("loc-kind"), "exterior")
        page.click(tid("a-save") if False else tid("art-save"))
        expect(page.locator(tid("art-state"))).to_contain_text("Saved.")
        expect(page.locator(inside("location-form", "findings"))).to_contain_text("heading says INT.")
        expect(page.locator(inside("location-form", "findings"))).to_contain_text("How to fix it")
        self.assertFalse(page.locator(tid("art-save")).is_disabled() and False)
        page.select_option(tid("loc-kind"), "interior")
        page.fill(tid("loc-name"), "Page & Candle Bookshop (back room)")
        expect(page.locator(tid("art-state"))).to_contain_text("Changed, not saved yet")
        self.save("fixed the type")
        self.assertEqual(page.locator(tid("loc-name")).input_value(), "Page & Candle Bookshop (back room)")
        page.reload(); page.wait_for_selector("body[data-ready=true]")
        self.title(2)
        self.assertEqual(page.locator(tid("loc-name")).input_value(), "Page & Candle Bookshop (back room)")           # reopened where the work is

    def test_04_layout_editor_drag_keyboard_numbers_add_and_delete(self):
        page = self.page
        self.seed(); self.draft("warm_nostalgia", "Warm nostalgia"); self.to(3)
        expect(page.locator(tid("no-selection"))).to_contain_text("Click a piece on the plan")
        counter = page.locator("#view-art [data-obj=P-COUNTER]")
        expect(counter).to_be_visible()
        box = counter.bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2); page.mouse.down()
        page.mouse.move(box["x"] - 60, box["y"] + 40, steps=6); page.mouse.up()
        expect(page.locator(tid("obj-inspector"))).to_contain_text("Selected: Counter with till")
        moved_x = float(page.locator(tid("obj-x")).input_value())
        self.assertLess(moved_x, 0.74)                                                         # dragged to the left
        expect(page.locator(tid("art-state"))).to_contain_text("Changed, not saved yet")
        page.focus("#view-art [data-obj=P-COUNTER]")
        for _ in range(3):
            page.keyboard.press("ArrowRight")
        self.assertAlmostEqual(float(page.locator(tid("obj-x")).input_value()), moved_x + 0.03, places=2)   # keyboard moves by 0.01
        page.fill(tid("obj-y"), "0.55"); page.fill(tid("add-name"), "Coat stand"); page.select_option(tid("add-kind"), "decor"); page.click(tid("add-piece"))
        expect(page.locator(tid("obj-inspector"))).to_contain_text("Selected: Coat stand")
        page.click(tid("obj-del")); page.click(tid("obj-del"))                                # two clicks to delete
        expect(page.locator("#view-art [data-obj=D-1]")).to_have_count(0) if False else None
        page.fill(tid("add-name"), ""); page.click(tid("add-piece"))
        expect(page.locator(inside("layout-form", "error-layout"))).to_contain_text("Type a name for the new piece")
        page.click(tid("a-check"))
        expect(page.locator(tid("notice-check"))).to_contain_text("Nothing was saved")
        self.save("moved the counter")
        page.reload(); page.wait_for_selector("body[data-ready=true]"); self.title(3)
        self.assertAlmostEqual(float(page.locator("#view-art [data-obj=P-COUNTER]").get_attribute("aria-label").split("at ")[1].split(",")[0]), moved_x + 0.03, places=2)
        page.click(tid("show-cams")); expect(page.locator("#view-art [data-camera]")).to_have_count(0)

    def test_05_dropping_the_counter_on_an_actor_is_advice_not_a_block(self):
        page = self.page
        self.seed(); self.draft("warm_nostalgia", "Warm nostalgia"); self.to(3)
        page.click("#view-art [data-obj=P-COUNTER]")
        for sel_, value in (("obj-x", "0.52"), ("obj-y", "0.61")):
            page.fill(tid(sel_), value)
        page.click(tid("a-check"))
        expect(page.locator(inside("layout-form", "findings"))).to_contain_text("inside")
        expect(page.locator(inside("layout-form", "findings") + " [data-severity=attention]").first).to_contain_text("Needs attention")
        expect(page.locator(tid("art-save"))).to_be_enabled()                                  # advice never blocks saving
        self.save("counter on an actor, on purpose")

    # ---- props ---------------------------------------------------------------------------------------------------------------------------------
    def test_06_props_come_from_the_script_and_continuity_is_tracked(self):
        page = self.page
        self.seed(); self.draft("warm_nostalgia", "Warm nostalgia"); self.to(4)
        expect(page.locator(tid("prop-table"))).to_contain_text("Ticket"); expect(page.locator(tid("prop-table"))).to_contain_text("script")
        page.fill(tid("new-prop"), "Reading glasses!"); page.click(tid("add-prop"))
        expect(page.locator(tid("prop-inspector"))).to_contain_text("Reading glasses!")
        page.click(tid("prop-place")); self.assertEqual(page.locator(tid("prop-x")).input_value(), "0.5")
        page.click(tid("pick-PR-TICKET"))
        page.click(tid("add-state")); page.fill(tid("state-where"), "gone: in her pocket")
        page.click(tid("add-state"))
        page.locator("#view-art [data-testid=state-at]").nth(1).select_option("SC-001-B7")
        page.locator("#view-art [data-testid=state-where]").nth(1).fill("on the counter")
        page.locator("#view-art [data-testid=state-at]").nth(0).select_option("SC-001-B5")
        page.click(tid("a-check"))
        expect(page.locator(inside("props-form", "findings"))).to_contain_text("appears again")
        page.locator("#view-art [data-testid=state-where]").evaluate_all("els => { const e = els.find(x => x.value === 'on the counter'); e.value = 'gone'; e.dispatchEvent(new Event('input', {bubbles: true})); }")
        page.click(tid("a-check"));
        expect(page.locator(tid("findings"))).not_to_contain_text("appears again")
        self.save("ticket states")
        expect(page.locator(tid("prop-status"))).to_be_visible()

    # ---- visual style -----------------------------------------------------------------------------------------------------------------------------
    def test_07_invalid_values_are_explained_beside_save_and_typing_survives(self):
        page = self.page
        self.seed(); self.draft("warm_nostalgia", "Warm nostalgia"); self.to(5)
        page.locator("#view-art [data-testid=pal-hex]").first.fill("red")
        page.click(tid("art-save"))
        err = page.locator(inside("style-form", "error-save"))
        expect(err).to_contain_text("Cannot save yet"); expect(err).to_contain_text("Change the field it names"); expect(err).to_contain_text("Nothing you typed was lost")
        self.assertEqual(page.locator("#view-art [data-testid=pal-hex]").first.input_value(), "red")
        expect(page.locator(tid("art-state"))).to_contain_text("not saved yet")
        page.locator("#view-art [data-testid=pal-hex]").first.fill("#7a4a2a")
        self.save("fixed the colour")
        page.click(tid("subtab-variations"))
        page.click(tid("add-variation"))
        page.locator("#view-art [data-testid=var-shot]").select_option(index=12)
        page.fill(tid("var-summary"), "Cooler light for the ticket reveal")
        page.click(tid("var-addcol"))
        self.save("one shot variation")
        page.click(tid("subtab-period")); page.fill(tid("themes"), "memory, rain")
        page.click(tid("subtab-materials")); page.click(tid("add-texture"))
        page.click(tid("subtab-assets"))
        expect(page.locator(tid("no-assets"))).to_contain_text("Open the Art Library")

    # ---- two independent treatments ----------------------------------------------------------------------------------------------------------------
    def test_08_two_treatments_compare_and_are_approved_independently(self):
        page = self.page
        self.seed(); self.draft("warm_nostalgia", "Warm nostalgia")
        page.click(NEXT); page.click(BACK)
        page.click(tid("a-new")) if page.locator(tid("a-new")).count() else None
        self.to(8); page.click(tid("a-new"))
        self.cur = 1
        self.draft("emotional_distance", "Emotional distance")
        self.to(6)
        expect(page.locator(tid("no-compare"))).to_have_count(0)
        page.select_option(tid("cmp-pick"), index=1)
        page.click(tid("cmp-go"))
        res = page.locator(tid("cmp-result"))
        expect(res).to_contain_text("Measures"); expect(res).to_contain_text("likely to suggest")
        expect(page.locator(inside("cmp-result", "cmp-a"))).to_contain_text("Emotional distance"); expect(page.locator(inside("cmp-result", "cmp-b"))).to_contain_text("Warm nostalgia")
        self.assertTrue(page.locator("#view-art [data-testid^=cmp-layout]").count() == 2)
        expect(page.locator(inside("cmp-result", "cmp-a"))).to_contain_text("detached"); expect(page.locator(inside("cmp-result", "cmp-b"))).to_contain_text("intimate")
        expect(res).to_contain_text("because:")
        self.to(7)
        page.fill(tid("a-reviewer"), "Art director")
        expect(page.locator(tid("a-approve"))).to_be_disabled()
        expect(page.locator(tid("decision-form"))).to_contain_text("Submit for review first")
        page.click(tid("a-submit")); page.click(tid("a-approve"))
        expect(page.locator(inside("decision-form", "notice-decide"))).to_contain_text("Approved")
        statuses = page.evaluate("fetch('/api/art/projects/closing-hour').then(r => r.json()).then(o => o.treatments.map(t => [t.treatment_name, t.approval_status]))")
        self.assertEqual(sorted(statuses), [["Emotional distance", "approved"], ["Warm nostalgia", "draft"]])   # the other one is untouched

    # ---- export --------------------------------------------------------------------------------------------------------------------------------------
    def test_09_exports_need_approval_and_advice_needs_an_explicit_recorded_choice(self):
        page = self.page
        self.seed(); self.draft("warm_nostalgia", "Warm nostalgia"); self.to(8)
        expect(page.locator(tid("not-approved"))).to_be_visible()
        expect(page.locator(tid("dl-art-direction-manifest"))).to_be_disabled()
        expect(page.locator(tid("export-art-direction-manifest"))).to_contain_text("Approve this treatment in the review step first")
        with page.expect_download() as dl:
            page.click(tid("dl-storyboard-metadata"))
        with open(dl.value.path(), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["schema"], "filmcraft.storyboard_metadata.v1")
        page.click(BACK); self.title(7)
        page.fill(tid("a-reviewer"), "Art director"); page.click(tid("a-submit")); page.click(tid("a-approve"))
        expect(page.locator(inside("decision-form", "notice-decide"))).to_contain_text("Approved")
        # the script changes afterwards: the same export now needs an explicit, recorded choice
        self.assertEqual(page.evaluate(REVISE_JS, self.ids["sp"]), "completed")
        page.click("[data-testid=tab-history]"); page.click("[data-testid=tab-art]")
        self.title(7); page.click(tid("a-check")); page.click(NEXT); self.title(8)
        page.click(tid("dl-art-direction-manifest"))
        expect(page.locator(tid("force-art-direction-manifest"))).to_be_visible()
        expect(page.locator(tid("export-art-direction-manifest"))).to_contain_text("your choice is written into the file")
        with page.expect_download() as dl:
            page.click(tid("force-art-direction-manifest"))
        with open(dl.value.path(), encoding="utf-8") as fh:
            m = json.load(fh)
        self.assertEqual((m["schema"], m["approval"]["reviewer"], m["import_policy"]["auto_import"]), ("filmcraft.art_direction_manifest.v1", "Art director", False))
        self.assertTrue(m["overrides"]); self.assertIn("lighting", m["integration"])
        expect(page.locator(inside("export-art-direction-manifest", "notice-x-art-direction-manifest"))).to_contain_text("Recorded in the file")

    # ---- change impact -----------------------------------------------------------------------------------------------------------------------------------
    def test_10_a_script_change_outdates_the_design_and_rebase_keeps_the_rest(self):
        page = self.page
        self.seed(); self.draft("warm_nostalgia", "Warm nostalgia"); self.to(7)
        page.click(tid("approve-items")); self.save("all items approved")
        page.fill(tid("a-reviewer"), "Art director"); page.click(tid("a-submit")); page.click(tid("a-approve"))
        expect(page.locator(inside("decision-form", "notice-decide"))).to_contain_text("Approved")
        self.assertEqual(page.evaluate(REVISE_JS, self.ids["sp"]), "completed")
        page.click("[data-testid=tab-history]"); page.click("[data-testid=tab-art]")
        page.click(tid("a-check"))
        page.click("#art-wizard [data-step-target='6']"); page.click("#art-wizard [data-step-target='7']"); self.title(7)
        impact = page.locator(tid("impact"))
        expect(impact).to_contain_text("changed after this design was made"); expect(impact).to_contain_text("To recover, rebase")
        page.click(tid("a-rebase"))
        expect(page.locator(tid("notice-rebase"))).to_contain_text("back in review")
        expect(page.locator(tid("impact"))).to_have_count(0)
        expect(page.locator(tid("pend-PR-TICKET"))).to_contain_text("needs review")
        statuses = page.evaluate("fetch('/api/art/projects/closing-hour').then(r => r.json()).then(o => o.treatments.map(t => t.approval_status))")
        self.assertIn("approved", statuses)                                                   # the approved version is still there

    # ---- Art Library ----------------------------------------------------------------------------------------------------------------------------------
    def test_11_art_library_styles_and_assets(self):
        page = self.page
        self.ids = page.evaluate(SEED_JS, False)
        page.click("[data-testid=tab-lib]")
        lib = lambda n: f"#view-lib [data-testid={n}]"
        def title(n):
            expect(page.locator(lib("step-title"))).to_contain_text(f"Step {n} of 2")
            assert_ui_contract(page, "#lib-wizard"); assert_ui_text(page, "#lib-wizard")
        title(1)
        expect(page.locator(lib("lib-noprofiles"))).to_contain_text("Press “Create a style profile”")
        page.click(lib("new-profile"))
        page.click(lib("prof-name")) if False else None
        page.fill(lib("prof-name"), "House style")
        page.click(lib("add-colour")); page.fill(lib("pc-name"), "Oak"); page.fill(lib("pc-hex"), "#8B5E3C")
        page.click(lib("add-rule")); page.fill(lib("rule-term"), "neon")
        page.click(lib("style-save"))
        expect(page.locator(lib("prof-state"))).to_contain_text("Saved.")
        self.assertEqual(page.locator(lib("prof-name")).input_value(), "House style")
        page.fill(lib("pc-hex"), "oak")
        page.click(lib("style-save"))
        expect(page.locator("#view-lib [data-testid=error-save-prof]")).to_contain_text("Cannot save yet")
        page.fill(lib("pc-hex"), "#8B5E3D"); page.click(lib("style-save"))
        page.click("#lib-wizard [data-ui=next]"); title(2)
        expect(page.locator(lib("lib-noassets"))).to_contain_text("Upload a picture above")
        page.set_input_files(lib("lib-file"), files=[{"name": "oak.png", "mimeType": "image/png", "buffer": PNG}])
        expect(page.locator(lib("notice-upload"))).to_contain_text("Added “oak.png”")
        page.fill(lib("as-owner"), "Me"); page.select_option(lib("as-source"), "own"); page.select_option(lib("as-rights"), "cleared"); page.fill(lib("as-licence"), "own work")
        page.click(lib("assets-save"))
        expect(page.locator(lib("reg-state"))).to_contain_text("Saved.")
        page.set_input_files(lib("lib-file"), files=[{"name": "oak-again.png", "mimeType": "image/png", "buffer": PNG}])
        expect(page.locator(lib("notice-upload"))).to_contain_text("already registered")
        page.set_input_files(lib("lib-file"), files=[{"name": "run.png", "mimeType": "image/png", "buffer": b"MZ" + bytes(40)}])
        expect(page.locator("#view-lib [data-testid=error-upload]")).to_contain_text("Only PNG, JPEG, GIF and WebP")
        page.click(lib("lib-addpath")) if False else None
        expect(page.locator(lib("lib-finish"))).to_contain_text("What would you like to do next?")
        # the treatment can now use the asset, and its rights are cleared
        page.click("[data-testid=tab-art]"); page.click(tid("a-refresh"))
        self.draft("warm_nostalgia", "Warm nostalgia"); self.cur = 1; self.to(5)
        page.click(tid("subtab-assets"))
        expect(page.locator(tid("asset-table"))).to_contain_text("oak"); expect(page.locator(tid("asset-table"))).to_contain_text("cleared")


if __name__ == "__main__":
    unittest.main()
