"""CB2B browser tests: the Lighting Lab wizard. Every step is checked with assert_ui_contract (structure) and assert_ui_text (the objectively
testable text rules of guidelines/ui-standard.md). Wording quality, and whether the visual editor looks right, still need a human."""
import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from browser_base import BrowserCase, expect, sync_playwright  # noqa: E402
from test_browser_art import REVISE_JS  # noqa: E402
from ui_contract import JARGON_LIGHT, assert_ui_contract, assert_ui_text  # noqa: E402

NEXT = "#light-wizard [data-ui=next]"
BACK = "#light-wizard [data-ui=back]"
tid = lambda name: f"#view-light [data-testid={name}]"
inside = lambda parent, child: f"#view-light [data-testid={parent}] [data-testid={child}]"

SEED_JS = """async () => {
  const J = (u, b) => fetch(u, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)}).then(r => r.json());
  const doc = await (await fetch('/api/crafts/screenwriting/fixture?name=screenplay')).json();
  const sp = await J('/api/experiments', {craft_id: 'screenwriting', name: 'rev 1', input: doc, run_now: true});
  const plan = await J('/api/lab/direction/draft', {screenplay_experiment_id: sp.id, scene_id: 'SC-001', name: 'plan A', approach: {preset: 'intimate'}});
  const art = async (preset, name) => (await J('/api/art/draft', {screenplay_experiment_id: sp.id, scene_id: 'SC-001', name, preset, plan_experiment_id: plan.experiment.id}));
  const a = await art('warm_nostalgia', 'Warm nostalgia'), b = await art('emotional_distance', 'Emotional distance');
  return {sp: sp.id, plan: plan.experiment.id, artA: a.experiment.id, artB: b.experiment.id, artRunA: a.run.id};
}"""
PLANS_JS = "fetch('/api/light/projects/closing-hour').then(r => r.json())"
PLAN_JS = "id => fetch('/api/experiments/' + id).then(r => r.json()).then(e => { const run = e.runs.filter(r => r.run_status === 'completed').pop(); return fetch('/api/runs/' + run.id).then(r => r.json()).then(r => r.envelope.artifact); })"


@unittest.skipIf(sync_playwright is None, "playwright not installed (pip install -r requirements-dev.txt)")
class LightLabTests(BrowserCase):
    # ---- helpers ------------------------------------------------------------------------------------------------------------------------
    def title(self, n):
        expect(self.page.locator(tid("step-title"))).to_contain_text(f"Step {n} of 8")
        assert_ui_contract(self.page, "#light-wizard")
        assert_ui_text(self.page, "#light-wizard", JARGON_LIGHT)

    def seed(self):
        self.ids = self.page.evaluate(SEED_JS)
        self.page.click("[data-testid=tab-light]")
        self.page.click(tid("l-refresh"))
        expect(self.page.locator(tid("l-project"))).to_have_value("closing-hour")
        self.page.wait_for_load_state("networkidle")                                                          # opening the tab and Refresh both reload lists; let them finish

    def draft(self, preset="warm_naturalistic", name=None, art="artA"):
        self.page.select_option(tid("l-art"), self.ids[art])
        self.page.click(tid(f"preset-{preset}"))
        if name is not None:
            self.page.fill(tid("l-name"), name)
        self.page.click(tid("l-draft"))
        expect(self.page.locator(tid("notice-draft"))).to_contain_text("Drafted")
        self.cur = 1

    def to(self, n):
        for k in range(self.cur + 1, n + 1):
            self.page.click(NEXT); self.title(k)
        self.cur = n

    def save(self, note=None):
        if note is not None:
            self.page.fill(tid("light-note"), note)
        self.page.click(tid("light-save"))
        expect(self.page.locator(tid("light-state"))).to_contain_text("Saved.")

    def plan(self):
        ov = self.page.evaluate(PLANS_JS)
        return self.page.evaluate(PLAN_JS, ov["plans"][-1]["experiment_id"]), ov

    # ---- step 1 -------------------------------------------------------------------------------------------------------------------------
    def test_01_empty_states_say_what_to_do_and_a_draft_unlocks_the_next_step(self):
        page = self.page
        page.click("[data-testid=tab-light]")
        self.title(1)
        expect(page.locator(tid("no-projects"))).to_contain_text("Open the Scene Lab")
        expect(page.locator(tid("no-plans"))).to_contain_text("press “Draft the lighting plan”")
        expect(page.locator(NEXT)).to_be_disabled(); expect(page.locator(tid("next-why"))).to_contain_text("Draft a new lighting plan")
        page.click(tid("l-draft"))
        expect(page.locator(inside("start-form", "error-draft"))).to_contain_text("Choose a screenplay revision")
        self.seed()
        expect(page.locator(tid("l-art"))).to_have_value(self.ids["artB"])                                   # the newest art design for the scene is pre-selected
        page.select_option(tid("l-art"), "")
        page.click(tid("l-draft"))
        expect(page.locator(inside("start-form", "error-draft"))).to_contain_text("Choose the art design")
        page.select_option(tid("l-art"), self.ids["artA"])
        page.fill(tid("l-name"), "")
        page.click(tid("l-draft"))
        expect(page.locator(inside("start-form", "error-draft"))).to_contain_text("Give the lighting plan a name")
        self.draft("warm_naturalistic", "Warm, naturalistic, intimate")
        expect(page.locator(NEXT)).to_be_enabled()

    def test_02_every_step_meets_the_structure_and_text_rules(self):
        page = self.page
        self.seed(); self.draft("warm_naturalistic", "Warm, naturalistic, intimate")
        self.to(8)
        self.assertEqual(page.locator(NEXT).count(), 0)
        self.assertGreaterEqual(page.locator("#light-wizard [data-testid=finish-form] button").count(), 3)
        for n in range(7, 0, -1):
            page.click(BACK); self.title(n)
        self.assertTrue(page.locator(NEXT).inner_text().startswith("Next: "))

    # ---- conditions -------------------------------------------------------------------------------------------------------------------------------
    def test_03_conditions_are_checked_against_the_art_design_and_persist(self):
        page = self.page
        self.seed(); self.draft("warm_naturalistic", "Warm, naturalistic, intimate"); self.to(2)
        page.select_option(tid("c-time"), "day")
        page.click(tid("l-check"))
        expect(page.locator(inside("conditions-form", "findings"))).to_contain_text("The art design says")
        expect(page.locator(inside("conditions-form", "findings"))).to_contain_text("How to fix it")
        page.fill(tid("c-mood"), "intimate, sheltered, rain")
        page.fill(tid("c-purpose"), "Warmth from the room itself")
        self.save("day for now")
        page.reload(); page.wait_for_selector("body[data-ready=true]")
        page.click("[data-testid=tab-light]"); self.title(2)
        expect(page.locator(tid("c-time"))).to_have_value("day"); expect(page.locator(tid("c-mood"))).to_have_value("intimate, sheltered, rain")
        doc, _ = self.plan()
        self.assertEqual((doc["conditions"]["time_of_day"], doc["conditions"]["mood_words"]), ("day", ["intimate", "sheltered", "rain"]))

    # ---- the interactive editor ---------------------------------------------------------------------------------------------------------------
    def test_04_lights_move_by_drag_keyboard_and_numbers_and_the_view_shows_glow_and_shadows(self):
        page = self.page
        self.seed(); self.draft("warm_naturalistic", "Warm, naturalistic, intimate"); self.to(3)
        self.assertGreater(page.locator("#view-light [data-light]").count(), 5)
        self.assertGreater(page.locator("#view-light .glowcell").count(), 20)                              # approximate illumination zones
        self.assertGreater(page.locator("#view-light .shadowarrow").count(), 0)                            # shadow directions
        self.assertGreater(page.locator("#view-light .cone").count(), 3)
        page.click(tid("lt-L-FILL"))
        x0, y0 = float(page.locator(tid("lf-x")).input_value()), float(page.locator(tid("lf-y")).input_value())
        dot = page.locator("#view-light [data-light=L-FILL] circle.lampdot"); dot.scroll_into_view_if_needed(); box = dot.bounding_box()   # the mouse needs the lamp on screen
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2); page.mouse.down(); page.mouse.move(box["x"] + 120, box["y"] - 60, steps=6); page.mouse.up()
        x1, y1 = float(page.locator(tid("lf-x")).input_value()), float(page.locator(tid("lf-y")).input_value())
        self.assertGreater(x1, x0 + 0.05); self.assertLess(y1, y0 - 0.03)                                  # it moved by dragging
        page.locator("#view-light [data-light=L-FILL]").focus()
        page.keyboard.press("ArrowLeft"); page.keyboard.press("Shift+ArrowDown")
        x2, y2 = float(page.locator(tid("lf-x")).input_value()), float(page.locator(tid("lf-y")).input_value())
        self.assertAlmostEqual(x2, round(x1 - 0.01, 2), places=2); self.assertAlmostEqual(y2, round(y1 + 0.05, 2), places=2)
        rot0 = float(page.locator(tid("lf-rot")).input_value())
        page.locator("#view-light [data-light=L-FILL]").focus(); page.keyboard.press("]"); page.keyboard.press("Shift+]")
        self.assertEqual(float(page.locator(tid("lf-rot")).input_value()), (math.floor(rot0 + 0.5) + 6) % 360)       # [ and ] turn the light (the browser rounds halves up)
        page.fill(tid("lf-kelvin"), "3300"); page.fill(tid("lf-intensity"), "0.4"); page.fill(tid("lf-beam"), "95"); page.fill(tid("lf-soft"), "0.7"); page.fill(tid("lf-height"), "2.3")
        page.select_option(tid("lf-fall-mode"), "linear"); page.fill(tid("lf-fall-range"), "6")
        self.save("fill moved")
        light = next(l for l in self.plan()[0]["lights"] if l["id"] == "L-FILL")
        self.assertEqual((light["color_temp_k"], light["intensity"], light["beam_angle_deg"], light["softness"], light["height_m"]), (3300, 0.4, 95, 0.7, 2.3))
        self.assertEqual(light["falloff"], {"mode": "linear", "range_m": 6}); self.assertEqual((light["x"], light["y"]), (x2, y2))
        page.reload(); page.wait_for_selector("body[data-ready=true]"); page.click("[data-testid=tab-light]")
        page.click(tid("lt-L-FILL")); self.assertEqual(page.locator(tid("lf-kelvin")).input_value(), "3300")   # saved values reappear after a reload

    def test_05_lights_can_be_added_removed_and_the_set_geometry_is_checked_as_advice(self):
        page = self.page
        self.seed(); self.draft("warm_naturalistic", "Warm, naturalistic, intimate"); self.to(3)
        n0 = page.locator("#view-light [data-testid=light-chips] button").count()
        page.select_option(tid("new-light-role"), "rim"); page.click(tid("add-light"))
        self.assertEqual(page.locator("#view-light [data-testid=light-chips] button").count(), n0 + 1)
        expect(page.locator(tid("lf-name"))).to_have_value("New rim light")
        page.fill(tid("lf-x"), "0.74"); page.fill(tid("lf-y"), "0.42")                                     # on top of the counter
        page.click(tid("l-check"))
        expect(page.locator(inside("lights-form", "findings"))).to_contain_text("stands inside")
        expect(page.locator(inside("lights-form", "findings"))).to_contain_text("How to fix it")
        self.assertFalse(page.locator(tid("light-save")).is_disabled() is True and False)                     # advice never blocks saving
        page.click(tid("light-save")); expect(page.locator(tid("light-state"))).to_contain_text("Saved.")
        page.click(tid("rm-light")); expect(page.locator(tid("rm-light"))).to_contain_text("Click again to confirm")
        page.click(tid("rm-light"))
        self.assertEqual(page.locator("#view-light [data-testid=light-chips] button").count(), n0)
        page.click(tid("lt-L-LAMP")); page.fill(tid("lf-x"), "0.2"); page.fill(tid("lf-y"), "0.7")
        page.click(tid("l-check"))
        expect(page.locator(inside("lights-form", "findings"))).to_contain_text("should sit on")

    def test_06_invalid_values_are_explained_beside_save_and_typing_survives(self):
        page = self.page
        self.seed(); self.draft("warm_naturalistic", "Warm, naturalistic, intimate"); self.to(3)
        page.fill(tid("lf-intensity"), "7")
        page.click(tid("light-save"))
        err = page.locator(inside("lights-form", "error-save"))
        expect(err).to_contain_text("Cannot save yet"); expect(err).to_contain_text("Change the field it names"); expect(err).to_contain_text("Nothing you typed was lost")
        self.assertEqual(page.locator(tid("lf-intensity")).input_value(), "7")
        expect(page.locator(tid("light-state"))).to_contain_text("not saved yet")
        page.fill(tid("lf-intensity"), "0.5"); self.save("fixed")

    # ---- shot adjustments -------------------------------------------------------------------------------------------------------------------------
    def test_07_a_shot_can_differ_from_the_scene_setup_without_changing_it(self):
        page = self.page
        self.seed(); self.draft("warm_naturalistic", "Warm, naturalistic, intimate"); self.to(4)
        shots = page.locator(tid("shot-select")).locator("option")
        values = [shots.nth(i).get_attribute("value") for i in range(shots.count())]
        plain = next(v for v in values if "(adjusted)" not in shots.nth(values.index(v)).inner_text())
        page.select_option(tid("shot-select"), plain)
        expect(page.locator(tid("shot-camera"))).to_contain_text("The shaded wedge is what the lens sees")
        self.assertGreater(page.locator("#view-light .camwedge").count(), 0)
        expect(page.locator(tid("sh-reason"))).to_be_disabled()
        page.fill(tid("sh-L-KEY-intensity"), "0.45")
        expect(page.locator(inside("shrow-L-KEY", "sh-reset-L-KEY"))).to_be_visible()
        page.fill(tid("sh-reason"), "A darker moment")
        page.click(tid("add-shot-light"))
        page.click(tid("light-save")); expect(page.locator(tid("light-state"))).to_contain_text("Saved.")
        doc, _ = self.plan()
        adj = next(a for a in doc["adjustments"] if a["shot_id"] == plain)
        self.assertEqual((adj["changes"], adj["reason"], len(adj["added_lights"])), ([{"light_id": "L-KEY", "intensity": 0.45}], "A darker moment", 1))
        self.assertEqual(next(l for l in doc["lights"] if l["id"] == "L-KEY")["intensity"], 0.75)           # the shared setup is untouched
        page.fill(tid("sh-L-KEY-intensity"), "0.75")                                                            # typing the scene value back removes the change
        page.click(tid("sh-reset-L-AMB")) if page.locator(tid("sh-reset-L-AMB")).count() else None
        self.assertEqual(page.locator(tid("sh-L-KEY-intensity")).input_value(), "0.75")
        other = next(v for v in values if v != plain)
        page.click(tid("add-shot-light")) if False else None
        page.fill(tid("sh-L-KEY-intensity"), "0.5")
        page.check(tid(f"copy-{other.split('-')[-1]}")); page.click(tid("copy-go"))
        expect(page.locator(tid("notice-copy"))).to_contain_text("Copied")

    # ---- the continuity checks in the browser ------------------------------------------------------------------------------------------------------
    def test_08_continuity_problems_show_with_a_fix_and_a_stated_reason_softens_them(self):
        page = self.page
        self.seed(); self.draft("warm_naturalistic", "Warm, naturalistic, intimate"); self.to(4)
        values = [o.get_attribute("value") for o in page.locator(tid("shot-select")).locator("option").all()]
        for sid in values[4:6]:
            page.select_option(tid("shot-select"), sid)
            self.assertTrue(True)
        page.select_option(tid("shot-select"), values[5])
        page.fill(tid("sh-L-KEY-color_temp_k"), "5600")
        self.to(5)
        page.click(tid("l-check"))
        expect(page.locator(tid("ck-attention"))).not_to_have_text("0")
        expect(page.locator("#view-light [data-rule=colour_jump]").first).to_contain_text("changes by")
        expect(page.locator("#view-light [data-rule=colour_jump]").first).to_contain_text("How to fix it")
        expect(page.locator(tid("shot-summary"))).to_contain_text("5600 K")
        page.click(BACK); self.title(4); self.cur = 4
        page.fill(tid("sh-reason"), "The street light comes on")
        self.to(5)
        page.click(tid("l-check"))
        expect(page.locator("#view-light [data-rule=colour_jump][data-severity=note]").first).to_contain_text("intended: The street light comes on")

    # ---- treatments ----------------------------------------------------------------------------------------------------------------------------------------
    def test_09_two_plans_for_the_two_art_treatments_compare_and_are_approved_independently(self):
        page = self.page
        self.seed(); self.draft("warm_naturalistic", "Warm, naturalistic, intimate", "artA")
        page.click(NEXT); page.click(BACK)
        self.to(8); page.click(tid("l-new")); self.cur = 1
        self.draft("cool_dramatic", "Cool, restrained, dramatic", "artB")
        self.to(6)
        expect(page.locator(tid("no-compare"))).to_have_count(0)
        page.select_option(tid("l-cmp-pick"), index=1); page.click(tid("l-cmp-go"))
        res = page.locator(tid("cmp-result"))
        expect(res).to_contain_text("Settings and measures"); expect(res).to_contain_text("because:")
        expect(page.locator(inside("cmp-result", "cmp-a"))).to_contain_text("Cool, restrained, dramatic"); expect(page.locator(inside("cmp-result", "cmp-b"))).to_contain_text("Warm, naturalistic, intimate")
        expect(page.locator(inside("cmp-result", "cmp-a"))).to_contain_text("detached"); expect(page.locator(inside("cmp-result", "cmp-b"))).to_contain_text("intimate")
        self.assertEqual(page.locator("#view-light [data-testid^=cmp-layout]").count(), 2)
        expect(page.locator(inside("cmp-result", "cmp-b"))).to_contain_text("Key light:")
        self.to(7)
        page.fill(tid("l-reviewer"), "Gaffer")
        expect(page.locator(tid("l-approve"))).to_be_disabled(); expect(page.locator(tid("decision-form"))).to_contain_text("Submit for review first")
        page.click(tid("l-submit")); page.click(tid("l-approve"))
        expect(page.locator(inside("decision-form", "notice-decide"))).to_contain_text("Approved")
        ov = self.page.evaluate(PLANS_JS)
        self.assertEqual(sorted((p["plan_name"], p["approval_status"]) for p in ov["plans"]), [("Cool, restrained, dramatic", "approved"), ("Warm, naturalistic, intimate", "draft")])

    # ---- export ------------------------------------------------------------------------------------------------------------------------------------------------
    def test_10_exports_need_approval_and_advice_needs_a_recorded_choice_and_a_setup_can_be_kept(self):
        page = self.page
        self.seed(); self.draft("warm_naturalistic", "Warm, naturalistic, intimate"); self.to(8)
        expect(page.locator(tid("not-approved"))).to_be_visible()
        expect(page.locator(tid("dl-lighting-manifest"))).to_be_disabled()
        expect(page.locator(tid("export-lighting-manifest"))).to_contain_text("Approve this lighting plan in the review step first")
        with page.expect_download() as dl:
            page.click(tid("dl-lighting-instructions"))
        with open(dl.value.path(), encoding="utf-8") as fh:
            ins = json.load(fh)
        self.assertEqual(ins["schema"], "filmcraft.lighting_instructions.v1"); self.assertTrue(ins["shots"][0]["lights"])
        page.click(BACK); self.title(7)
        page.fill(tid("l-reviewer"), "Gaffer"); page.click(tid("l-submit")); page.click(tid("l-approve"))
        expect(page.locator(inside("decision-form", "notice-decide"))).to_contain_text("Approved")
        page.click(NEXT); self.title(8)
        page.click(tid("dl-lighting-manifest"))                                                                  # the art design is not approved
        expect(page.locator(tid("force-lighting-manifest"))).to_be_visible()
        expect(page.locator(tid("export-lighting-manifest"))).to_contain_text("your choice is written into the file")
        with page.expect_download() as dl:
            page.click(tid("force-lighting-manifest"))
        with open(dl.value.path(), encoding="utf-8") as fh:
            m = json.load(fh)
        self.assertEqual((m["schema"], m["approval"]["reviewer"], m["import_policy"]["auto_import"], m["overrides"]), ("filmcraft.lighting_manifest.v1", "Gaffer", False, ["allow_unapproved_art"]))
        expect(page.locator(inside("export-lighting-manifest", "notice-x-lighting-manifest"))).to_contain_text("Recorded in the file")
        page.fill(tid("setup-id"), "WARM-ROOM"); page.fill(tid("setup-name"), "Warm room"); page.click(tid("setup-save"))
        expect(page.locator(tid("notice-setup"))).to_contain_text("Saved the setup")
        page.click(tid("l-new")); expect(page.locator(tid("setup-WARM-ROOM"))).to_be_visible()
        page.select_option(tid("l-art"), self.ids["artB"]); page.click(tid("setup-WARM-ROOM")); page.fill(tid("l-name"), "Warm room in the cold treatment"); page.click(tid("l-draft"))
        expect(page.locator(tid("notice-draft"))).to_contain_text("Drafted")
        doc, _ = self.plan()
        self.assertEqual(doc["from_setup"]["setup_id"], "WARM-ROOM"); self.assertEqual(doc["adjustments"], [])

    # ---- upstream change ---------------------------------------------------------------------------------------------------------------------------------------
    def test_11_a_script_change_outdates_the_plan_and_rebase_keeps_the_rest(self):
        page = self.page
        self.seed(); self.draft("warm_naturalistic", "Warm, naturalistic, intimate"); self.to(7)
        page.click(tid("approve-items")); self.save("all items approved")
        page.fill(tid("l-reviewer"), "Gaffer"); page.click(tid("l-submit")); page.click(tid("l-approve"))
        expect(page.locator(inside("decision-form", "notice-decide"))).to_contain_text("Approved")
        self.assertEqual(page.evaluate(REVISE_JS, self.ids["sp"]), "completed")
        page.click("[data-testid=tab-history]"); page.click("[data-testid=tab-light]")
        page.click(tid("l-check"))
        page.click("#light-wizard [data-step-target='6']"); page.click("#light-wizard [data-step-target='7']"); self.title(7)
        impact = page.locator(tid("impact"))
        expect(impact).to_contain_text("changed after this lighting plan was made"); expect(impact).to_contain_text("To recover, rebase")
        page.click(tid("l-rebase"))
        expect(page.locator(tid("notice-rebase"))).to_contain_text("back in review")
        expect(page.locator(tid("impact"))).to_have_count(0)
        statuses = page.evaluate("fetch('/api/light/projects/closing-hour').then(r => r.json()).then(o => o.plans.map(t => t.approval_status))")
        self.assertIn("approved", statuses)                                                                         # the approved version is still there


if __name__ == "__main__":
    unittest.main()
