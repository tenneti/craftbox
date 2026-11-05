"""Story Lab browser tests: the six-phase story process (guidelines/story-process.md) as a 6-step wizard.
Every step is checked with assert_ui_contract on the Story Lab wizard (guidelines/ui-standard.md)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from browser_base import BrowserCase, expect, sync_playwright  # noqa: E402
from ui_contract import assert_ui_contract  # noqa: E402

NEXT = "#story-wizard [data-ui=next]"
BACK = "#story-wizard [data-ui=back]"
tid = lambda name: f"#view-story [data-testid={name}]"
inside = lambda parent, child: f"#view-story [data-testid={parent}] [data-testid={child}]"


@unittest.skipIf(sync_playwright is None, "playwright not installed (pip install -r requirements-dev.txt)")
class StoryLabTests(BrowserCase):
    def title(self, n):
        expect(self.page.locator(tid("step-title"))).to_contain_text(f"Step {n} of 6")
        assert_ui_contract(self.page, "#story-wizard")

    def settle(self):
        """Wait for the automatic check made on entering a step to finish, so it cannot race the next action."""
        self.page.wait_for_function("!document.querySelector('#view-story [data-ui=progress]') && document.querySelector('#view-story [data-testid=audit] h3, #view-story [data-testid=start-form]')")

    def next(self, n):
        self.page.click(NEXT)
        self.title(n)
        self.settle()

    def sample(self):
        self.page.click(tid("start-sample"))
        expect(self.page.locator(tid("phase1-form"))).to_be_visible()

    def check(self):
        self.settle()
        box = self.page.locator(tid("audit"))
        before = int(box.get_attribute("data-checks") or 0)
        self.page.click(tid("story-check"))
        self.page.wait_for_function("b => Number(document.querySelector('#view-story [data-testid=audit]').dataset.checks) > b", arg=before)
        expect(box.locator("h3")).to_contain_text("answered well")

    def status(self, item):
        return self.page.locator(f"#view-story [data-item={item}]").get_attribute("data-status")

    def test_01_story_lab_is_the_default_and_covers_the_six_phases(self):
        page = self.page
        expect(page.locator("#view-story")).to_be_visible()
        self.title(1)
        self.assertEqual(page.locator("#story-wizard .steps li").count(), 6)
        self.assertEqual(page.locator(BACK).count(), 0)
        expect(page.locator(NEXT)).to_be_disabled()
        expect(page.locator(tid("next-why"))).to_contain_text("Create the project")
        expect(page.locator(tid("step-intro"))).to_contain_text("five pillars")
        self.sample()
        for n, key in ((2, "b-norm"), (3, "e-vuln"), (4, "c-unity"), (5, "lb-text-abstract"), (6, "draft-status")):
            self.next(n)
            expect(page.locator(tid(key)).first).to_be_visible()
        self.assertEqual(page.locator(NEXT).count(), 0)                                    # last step: explicit buttons, no Next
        expect(page.locator(tid("continue-scene-lab"))).to_be_visible()
        for n in (5, 4, 3, 2, 1):
            page.click(BACK); self.title(n)

    def test_02_a_new_story_starts_with_the_five_pillars_and_an_advice_only_audit(self):
        page = self.page
        page.fill(tid("start-title"), "Night Train"); page.fill(tid("start-logline"), "Two strangers share a cabin.")
        page.fill(tid("start-protagonist"), "Isha"); page.fill(tid("start-antagonist"), "Kabir")
        page.click(tid("start-create"))
        expect(page.locator(tid("phase1-form"))).to_contain_text("the five pillars")
        expect(page.locator(tid("notice-start"))).to_contain_text("Created")
        self.check()
        self.assertEqual(self.status("protagonist"), "ok"); self.assertEqual(self.status("antagonist"), "ok")   # prefilled from the start form
        self.assertEqual(self.status("core_conflict"), "missing"); self.assertEqual(self.status("minimal"), "missing"); self.assertEqual(self.status("master_plot"), "missing")
        page.fill(tid("p-conflict"), "She wants silence; he needs company, and the cabin is only so big.")
        page.fill(tid("mn-1"), "Isha boards the night train"); page.fill(tid("mn-j"), "but when she finds Kabir in her berth,"); page.fill(tid("mn-2"), "they must share the cabin until dawn")
        page.select_option(tid("master-plot"), "voyage_and_return")
        self.check()
        self.assertEqual(self.status("core_conflict"), "ok"); self.assertEqual(self.status("minimal"), "ok"); self.assertEqual(self.status("master_plot"), "ok")
        page.fill(tid("mn-2"), "Isha boards the night train")                                 # same event twice is advice, not an error
        self.check()
        self.assertEqual(self.status("minimal"), "advice")
        expect(page.locator("#view-story [data-testid=sp-state]")).to_contain_text("Not saved yet")
        page.fill(tid("mn-2"), "they must share the cabin until dawn")
        page.fill(tid("story-rev-note"), "pillars")
        page.click(tid("story-save"))
        expect(page.locator("#view-story [data-testid=sp-state]")).to_contain_text("Saved.")
        self.assertEqual(page.locator(tid("p-conflict")).input_value(), "She wants silence; he needs company, and the cabin is only so big.")   # not cleared
        expect(page.locator(tid("story-save"))).to_be_disabled()

    def test_03_hook_timing_is_checked_against_the_script(self):
        page = self.page
        self.sample(); self.next(2); self.check()
        self.assertEqual(self.status("hook"), "ok")
        expect(page.locator(tid("audit"))).to_contain_text("inside the first 15 s")
        page.select_option(tid("h-line"), "SC-001-E24"); self.check()
        self.assertEqual(self.status("hook"), "advice")
        expect(page.locator(tid("audit"))).to_contain_text("Aim for the first 15 s")
        expect(page.locator(tid("story-save"))).to_be_enabled()                              # advice never blocks saving

    def test_04_empathy_conflict_and_structure_inputs(self):
        page = self.page
        self.sample(); self.next(2); self.next(3)
        self.check(); self.assertEqual(self.status("agency"), "ok")
        page.fill(inside("choice-0", "ag-cost"), ""); self.check()
        self.assertEqual(self.status("agency"), "advice")                                    # a choice with no cost
        page.select_option(tid("e-risk"), "high"); self.check()
        self.assertEqual(self.status("vulnerability"), "advice")
        page.click(tid("add-choice")); self.assertEqual(page.locator("#view-story [data-testid^=choice-]").count(), 4)
        self.next(4)
        n = page.locator("#view-story [data-testid^=eg-]").count()
        page.click(tid("add-eg")); self.assertGreater(page.locator("#view-story [data-testid^=eg-]").count(), n)
        page.click(tid("add-sb"))
        page.locator("#view-story [data-testid=sb-unspoken]").last.fill("I am afraid")
        self.check(); self.assertEqual(self.status("subtext"), "ok")
        self.next(5)
        self.check()
        self.assertEqual(self.status("circle"), "ok")
        page.select_option(tid("cr-beat-you"), "SC-001-B7"); self.check()
        self.assertEqual(self.status("circle"), "advice")
        expect(page.locator(tid("audit"))).to_contain_text("go backwards")

    def test_05_revision_phase_tracks_feedback_polish_and_the_flight_simulator(self):
        page = self.page
        self.sample(); self.to_phase6()
        self.check()
        for item in ("feedback", "polish", "simulator"):
            self.assertEqual(self.status(item), "advice", item)
        expect(page.locator(tid("draft-status"))).to_contain_text("24 script line")
        page.select_option(tid("fb-status"), "addressed"); page.check(tid("pol-word_choice")); page.check(tid("sim-ok")); self.check()
        for item in ("feedback", "polish", "simulator"):
            self.assertEqual(self.status(item), "ok", item)
        page.click(tid("add-fb")); self.check()
        self.assertEqual(self.status("feedback"), "ok")                                        # an empty note is not counted
        page.locator("#view-story [data-testid=fb-note]").last.fill("Second reader: the ending lands.")
        self.check(); self.assertEqual(self.status("feedback"), "advice")                      # a new open note
        page.click(tid("story-save")); expect(page.locator("#view-story [data-testid=sp-state]")).to_contain_text("Saved.")

    def to_phase6(self):
        for n in range(2, 7):
            self.next(n)

    def test_06_continue_to_the_scene_lab_keeps_the_same_project_and_shows_the_audit(self):
        page = self.page
        self.sample(); self.to_phase6()
        page.click(tid("story-save")); expect(page.locator("#view-story [data-testid=sp-state]")).to_contain_text("Saved.")
        page.click(tid("continue-scene-lab"))
        expect(page.locator("#view-lab")).to_be_visible()
        expect(page.locator("#lab-wizard [data-testid=step-title]")).to_contain_text("Step 2 of 8")
        self.assertEqual(page.locator("#view-lab .elrow").count(), 24)
        page.click("#lab-wizard [data-step-target='1']")
        expect(page.locator("#view-lab [data-testid=story-health]")).to_contain_text("answered well")
        page.click("[data-testid=tab-story]")
        self.title(6)                                                                            # the Story Lab remembers where you were

    def test_07_reload_keeps_the_tab_the_step_and_every_answer(self):
        page = self.page
        self.sample(); self.next(2)
        self.settle()
        page.fill(tid("b-norm"), "Closing time is for finishing quietly (edited)")
        page.reload(); page.wait_for_selector("body[data-ready=true]")
        self.title(2)
        self.assertEqual(page.locator(tid("b-norm")).input_value(), "Closing time is for finishing quietly (edited)")
        expect(page.locator("#view-story [data-testid=sp-state]")).to_contain_text("Not saved yet")
        page.click("[data-testid=tab-lab]"); page.reload(); page.wait_for_selector("body[data-ready=true]")
        expect(page.locator("#view-lab")).to_be_visible()                                         # the tab you were on is reopened


if __name__ == "__main__":
    unittest.main()
