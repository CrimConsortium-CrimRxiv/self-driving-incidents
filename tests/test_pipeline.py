"""Checks that the rules the dataset promises actually hold. Run: python -m unittest discover -s tests"""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from pipeline import cluster, codebook as cb, coder, collect, export, pages, store as st
from pipeline.common import load_config

CFG = load_config()


def item(title, source="Example News", snippet=None, day=20):
    return collect.Item(title=title, norm=collect.normalize_title(title), url=f"https://example.com/{abs(hash(title))}",
                        source=source, published=datetime(2026, 11, day, 12, tzinfo=timezone.utc), snippet=snippet)


def case(titles, day=20, summary=None, status="pending"):
    return {"key": "k1", "case_id": None, "status": status, "maker": "Tesla", "added": "2026-11-20T00:00:00Z",
            "updated": "2026-11-20T00:00:00Z", "headline": titles[0], "headline_publisher": "Example News",
            "source_summary": summary, "source_summary_publisher": "Example News" if summary else None,
            "auto": {"model": None, "location": None, "tags": []},
            "sources": [{"publisher": f"Paper {i}", "title": t, "url": f"https://example.com/{day}/{i}",
                         "published": f"2026-11-{day:02d}T12:00:00Z", "summary": None} for i, t in enumerate(titles)],
            "coding": None, "needs_coding": True, "code_attempts": 0, "exclusion_reason": None}


REPORT_TEXT = ("Indiana State Police said a Tesla Model Y struck construction equipment on Interstate 70 in Vigo County "
               "early Thursday. Troopers said the driver, Jane Q. Example, 34, told them the car was in self-driving "
               "mode. Example was arrested on suspicion of operating while intoxicated. No injuries were reported.")


def reports():
    r = [{"n": 1, "url": "https://example.com/a", "publisher": "Example News", "published": "2026-11-19T15:00:00Z",
          "title": "Woman arrested after self-driving Tesla hits construction equipment", "summary": "", "text": REPORT_TEXT}]
    r[0]["given"] = r[0]["title"] + " \n " + REPORT_TEXT
    return r


def answer(**variables):
    return {"screen": {"is_specific_incident": True, "multiple_incidents": False, "automation_in_question": True,
                       "reason": "One crash in Indiana."},
            "same_incident_as": None, "variables": variables, "claims": [],
            "narrative": "Police said a Tesla struck construction equipment. Jane Q. Example was arrested."}


class Relevance(unittest.TestCase):
    def test_keeps_feature_plus_event_even_without_maker(self):
        kept = collect.relevant([item("Woman arrested after self-driving car hits construction equipment")], CFG)
        self.assertEqual(len(kept), 1)

    def test_drops_crash_with_no_feature_named(self):
        self.assertEqual(collect.relevant([item("Tesla Model 3 crashes into storefront in Ohio")], CFG), [])

    def test_drops_feature_news_with_no_event(self):
        self.assertEqual(collect.relevant([item("Tesla Full Self-Driving gets a new version this week")], CFG), [])

    def test_drops_market_news(self):
        self.assertEqual(collect.relevant([item("Tesla stock falls after Autopilot crash report")], CFG), [])

    def test_feature_may_be_named_in_feed_description(self):
        kept = collect.relevant([item("Driver found asleep before highway crash", snippet="The Tesla was on Autopilot, police said.")], CFG)
        self.assertEqual(len(kept), 1)


class Matching(unittest.TestCase):
    def test_same_event_different_wording(self):
        a = case(["Woman arrested after self-driving Tesla crashes into construction equipment on I-70 in Vigo County"])
        b = case(["Indiana driver charged with OWI after Tesla in self-driving mode hits Vigo County Interstate 70 work zone equipment"], day=21)
        self.assertTrue(cluster.same_incident(a, b, CFG))

    def test_different_states_never_match(self):
        a = case(["Tesla on Autopilot hits parked police car in Florida"])
        b = case(["Tesla on Autopilot hits parked police car in California"])
        self.assertFalse(cluster.same_incident(a, b, CFG))

    def test_unrelated_events_do_not_match(self):
        a = case(["Tesla on autopilot crashed into 2 trucks in Somerset County while driver did her makeup"])
        b = case(["Tesla driver allegedly asleep with Full Self-Driving on crashes into police vehicle in California"])
        self.assertFalse(cluster.same_incident(a, b, CFG))


class Quotes(unittest.TestCase):
    def test_exact_quote_found(self):
        self.assertEqual(coder.find_quote("told them the car was in self-driving mode", reports(), 1)[1], 1)

    def test_curly_quotes_and_spacing_tolerated(self):
        self.assertIsNotNone(coder.find_quote("  No injuries   were reported. ", reports(), 1))

    def test_invented_quote_rejected(self):
        self.assertIsNone(coder.find_quote("Autopilot was confirmed to be engaged at the time", reports(), 1))

    def test_too_short_quote_rejected(self):
        self.assertIsNone(coder.find_quote("Tesla", reports(), 1))


class Checking(unittest.TestCase):
    def run_check(self, raw, earlier=()):
        c = case(["Woman arrested after self-driving Tesla hits construction equipment"])
        return coder.check(raw, c, reports(), list(earlier), CFG, "test-model")

    def test_value_without_real_quote_is_removed_and_counted(self):
        out = self.run_check(answer(
            vehicle_make={"value": "Tesla", "quote": "a Tesla Model Y struck construction equipment", "source": 1},
            fatalities={"value": 2, "quote": "two people were killed at the scene", "source": 1}))
        self.assertEqual(out["decision"], "publish")
        self.assertIn("vehicle_make", out["coding"]["values"])
        self.assertNotIn("fatalities", out["coding"]["values"])
        self.assertEqual(out["coding"]["unsupported_values_removed"], 1)

    def test_values_outside_the_codebook_are_dropped(self):
        out = self.run_check(answer(
            vehicle_make={"value": "Tesla", "quote": "a Tesla Model Y struck construction equipment", "source": 1},
            engagement_status={"value": "definitely_on", "quote": "told them the car was in self-driving mode", "source": 1},
            made_up_variable={"value": "x", "quote": "No injuries were reported", "source": 1}))
        self.assertEqual(set(out["coding"]["values"]), {"vehicle_make"})

    def test_private_names_removed_from_narrative_and_quotes(self):
        out = self.run_check(answer(
            vehicle_make={"value": "Tesla", "quote": "a Tesla Model Y struck construction equipment", "source": 1},
            police_action={"value": "arrest", "quote": "Example was arrested on suspicion of operating while intoxicated", "source": 1}))
        coding = out["coding"]
        self.assertNotIn("Example", coding["narrative"])
        self.assertNotIn("Example", json.dumps(coding["evidence"]))

    def test_incident_date_after_coverage_is_removed(self):
        out = self.run_check(answer(
            vehicle_make={"value": "Tesla", "quote": "a Tesla Model Y struck construction equipment", "source": 1},
            incident_date={"value": "2027-01-05", "quote": "early Thursday", "source": 1}))
        self.assertNotIn("incident_date", out["coding"]["values"])

    def test_round_up_is_screened_out(self):
        raw = answer()
        raw["screen"]["multiple_incidents"] = True
        self.assertEqual(self.run_check(raw)["decision"], "exclude")

    def test_no_feature_in_question_is_screened_out(self):
        raw = answer()
        raw["screen"]["automation_in_question"] = False
        self.assertEqual(self.run_check(raw)["decision"], "exclude")

    def test_other_maker_is_screened_out(self):
        out = self.run_check(answer(vehicle_make={"value": "Waymo", "quote": "a Tesla Model Y struck construction equipment", "source": 1}))
        self.assertEqual(out["decision"], "exclude")
        self.assertIn("Other maker", out["reason"])

    def test_merge_only_into_a_listed_earlier_case(self):
        raw = answer()
        raw["same_incident_as"] = "SDI-00009"
        self.assertEqual(self.run_check(raw)["decision"], "publish")
        self.assertEqual(self.run_check(raw, [{"ref": "SDI-00009"}])["decision"], "merge")


def published_store():
    c = case(["Woman arrested after self-driving Tesla hits construction equipment in Vigo County, Indiana"],
             summary="State police say the driver told troopers the car was in self-driving mode.", status="published")
    c["case_id"] = "SDI-00001"
    c["sources"][0]["url"] = "https://example.com/a"
    raw = answer(
        vehicle_make={"value": "Tesla", "quote": "a Tesla Model Y struck construction equipment", "source": 1},
        system_named={"value": ["unspecified"], "quote": "told them the car was in self-driving mode", "source": 1},
        engagement_status={"value": "claimed", "quote": "told them the car was in self-driving mode", "source": 1},
        location_state_region={"value": "Indiana", "quote": "Indiana State Police said", "source": 1})
    c["coding"] = coder.check(raw, c, reports(), [], CFG, "test-model")["coding"]
    c["coding"]["coded_at"] = "2026-11-20T00:00:00Z"
    return {"schema": 1, "next_id": 2, "next_key": 2, "cases": [c]}


class Export(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [mock.patch.object(export, "ROOT", root), mock.patch.object(export, "DATA", root / "data"),
                        mock.patch.object(pages, "ROOT", root)]
        for p in self.patches:
            p.start()
        self.root = root

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in sorted(self.root.rglob("*")) if p.is_file()}

    def test_second_export_changes_nothing(self):
        s = published_store()
        export.export_all(copy.deepcopy(s), CFG)
        first = self.snapshot()
        export.export_all(copy.deepcopy(s), CFG)
        self.assertEqual(first, self.snapshot())
        for name in ("index.html", "search.html", "about.html", "cases/SDI-00001.html", "sitemap.xml", "robots.txt",
                     "data/cases.csv", "data/self-driving-incidents.zip", "data/site-data.js", "CODEBOOK.md"):
            self.assertIn(name, first)

    def test_labels_say_mentioned_never_confirmed(self):
        export.export_all(published_store(), CFG)
        home = (self.root / "index.html").read_text()
        self.assertIn("Self-driving mode mentioned in coverage", home)
        self.assertIn("Said to be in use; not officially confirmed", home)
        self.assertIn("consortium@crimrxiv.com", home)
        for label in list(export.FEATURE_BADGE.values()) + [t["label"] for t in CFG["tags"]]:
            self.assertNotIn("confirmed", label.lower())
        self.assertNotIn("Jane", home)

    def test_pending_and_excluded_cases_stay_off_the_site(self):
        s = published_store()
        hidden = case(["Tesla Cybercab has crashed 8 times, data shows"], status="excluded")
        hidden["exclusion_reason"] = "Covers several incidents; not split into cases."
        waiting = case(["Tesla in Autopilot mode crashes into parked police car"])
        s["cases"] += [hidden, waiting]
        export.export_all(s, CFG)
        home = (self.root / "index.html").read_text()
        self.assertNotIn("crashed 8 times", home)
        self.assertNotIn("parked police car", home)
        self.assertIn("crashed 8 times", (self.root / "data" / "screened_out.csv").read_text())


class Store(unittest.TestCase):
    def test_ids_are_assigned_once_and_in_order(self):
        s = {"schema": 1, "next_id": 1, "next_key": 1, "cases": []}
        a, b = st.new_case(s, "Tesla"), st.new_case(s, "Tesla")
        st.assign_id(s, b), st.assign_id(s, a), st.assign_id(s, b)
        self.assertEqual((b["case_id"], a["case_id"], s["next_id"]), ("SDI-00001", "SDI-00002", 3))


class Codebook(unittest.TestCase):
    def test_every_variable_is_documented(self):
        for v in cb.VARIABLES:
            self.assertTrue(v["label"] and v["desc"] and v["group"], v["name"])
        self.assertIn("mentioned_only", cb.BY_NAME["engagement_status"]["values"])


if __name__ == "__main__":
    unittest.main()
