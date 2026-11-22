"""Checks that the rules the dataset promises actually hold. Run: python -m unittest discover -s tests"""
import copy
import csv
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from pipeline import archive, cluster, codebook as cb, coder, collect, enrich, export, pages, run, store as st
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

    def test_similar_wording_alone_is_not_enough(self):
        a = case(["Tesla in self-driving mode involved in Mesa crash, investigation finds"])
        b = case(["Pedestrian killed in I-80 crash involving Tesla in self-driving mode, CHP investigates"])
        self.assertFalse(cluster.same_incident(a, b, CFG))

    def test_same_road_same_week_different_events(self):
        a = case(["Video shows Tesla hit CHP car on I-80 in Fairfield; driver says he slept with Full Self-Driving on"])
        b = case(["Pedestrian killed in I-80 crash involving Tesla in self-driving mode, CHP investigates"], day=22)
        self.assertFalse(cluster.same_incident(a, b, CFG))

    def test_long_running_case_does_not_attract_unrelated_news(self):
        # The case has coverage in June and again in November. A November report that resembles
        # only the June headline is too far from it to be matched.
        a = case(["Tesla sued over fatal Texas home crash linked to Autopilot",
                  "NTSB: driver overrode self-driving before deadly Katy crash"])
        a["sources"][0]["published"] = "2026-06-24T12:00:00Z"
        b = case(["Tesla sued over fatal Texas highway crash linked to Autopilot"])
        self.assertFalse(cluster.same_incident(a, b, CFG))
        a["sources"][0]["published"] = "2026-11-18T12:00:00Z"
        self.assertTrue(cluster.same_incident(a, b, CFG))

    def test_grouping_respects_dates(self):
        import datetime as dt
        first = item("US judge upholds $243 million verdict against Tesla over fatal Autopilot crash")
        later = item("US judge upholds $243 million verdict against Tesla over fatal Autopilot crash")
        later.published = first.published - dt.timedelta(days=120)
        later.source = "Another Paper"
        self.assertEqual(len(cluster.group_items([first, later], CFG)), 2)
        later.published = first.published - dt.timedelta(days=1)
        self.assertEqual(len(cluster.group_items([first, later], CFG)), 1)


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

    def test_private_names_found_by_role_family_tie_and_age(self):
        text = ("A Tesla Model 3, driven by Alex Sample, hit the home of Robin Placeholder. "
                "The suit was brought by the daughter of Jo Story. Story, who was 71, had stopped. "
                "It killed 22-year-old Sam Middle Name. Pat Doe Roe, a 25-year-old Naples man, stopped to help. "
                "Lee Gu, 37, of Millstone was heading north. Fire Company Number 1 helped on November 12. "
                "A 37-year-old Millstone Township woman was driving. The Tesla Cybercab Has Already Crashed 8 Times.")
        names = coder.private_names([{"given": text}])
        for expected in ("Alex Sample", "Sample", "Robin Placeholder", "Jo Story", "Story", "Sam Middle Name",
                         "Middle Name", "Pat Doe Roe", "Roe", "Lee Gu", "Gu"):
            self.assertIn(expected, names)
        for wrong in ("Township", "Number", "November", "Crashed", "Millstone Township", "Tesla Model"):
            self.assertNotIn(wrong, names)
        self.assertEqual(coder.scrub("Gu told police on November 2", names, "[name]"), "[name] told police on November 2")

    def test_incident_date_after_coverage_is_removed(self):
        out = self.run_check(answer(
            vehicle_make={"value": "Tesla", "quote": "a Tesla Model Y struck construction equipment", "source": 1},
            incident_date={"value": "2027-01-05", "quote": "early Thursday", "source": 1}))
        self.assertNotIn("incident_date", out["coding"]["values"])

    def test_unstated_year_far_in_the_past_is_removed(self):
        # "early Thursday" names no year; a 2021 date would be a guess (often a misread model year).
        old = self.run_check(answer(incident_date={"value": "2021-11-19", "quote": "early Thursday", "source": 1}))
        self.assertNotIn("incident_date", old["coding"]["values"])
        self.assertEqual(old["coding"]["unsupported_values_removed"], 1)
        recent = self.run_check(answer(incident_date={"value": "2026-11-19", "quote": "early Thursday", "source": 1}))
        self.assertEqual(recent["coding"]["values"]["incident_date"], "2026-11-19")

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


class EarlierCases(unittest.TestCase):
    def published(self, cid, title, day, city=None):
        c = case([title], day=day, status="published")
        c["case_id"] = cid
        c["coding"] = {"values": {"location_city": city} if city else {}, "narrative": "What was reported."}
        return c

    def read(self, text):
        return [{"n": 1, "publisher": "Example News", "published": "2026-11-20T12:00:00Z",
                 "title": "Lawsuit says driver-assist feature failed before fatal crash", "summary": "", "text": text}]

    def test_coded_city_in_the_text_makes_an_earlier_case_a_candidate(self):
        new = case(["Lawsuit says driver-assist feature failed before fatal crash"], day=20)
        old = self.published("SDI-00003", "Man killed on interstate; police cite self-driving mode", 2, city="Vallejo")
        far = self.published("SDI-00004", "Robotaxi blocks tram line for an hour", 2, city="Phoenix")
        got = run.earlier_cases(new, self.read("The crash happened on Interstate 80 in Vallejo last month."), [old, far])
        self.assertEqual([e["ref"] for e in got], ["SDI-00003"])
        self.assertIn("Vallejo", got[0]["facts"])

    def test_coverage_within_days_makes_an_earlier_case_a_candidate(self):
        new = case(["Tesla in self-driving mode kills pedestrian"], day=20)
        close = self.published("SDI-00005", "Man, 71, dies crossing interstate at night", 19)
        got = run.earlier_cases(new, self.read(""), [close])
        self.assertEqual([e["ref"] for e in got], ["SDI-00005"])

    def test_message_lists_the_coded_facts(self):
        old = self.published("SDI-00003", "Man killed on interstate", 2, city="Vallejo")
        old["coding"]["values"]["incident_date"] = "2026-10-22"
        got = run.earlier_cases(case(["Different words entirely"], day=20), self.read("in Vallejo"), [old])
        user = coder.build_messages({}, self.read("in Vallejo"), got, CFG)[1]["content"]
        self.assertIn("ref SDI-00003: incident date 2026-10-22; Vallejo", user)


class Request(unittest.TestCase):
    def test_message_names_the_answer_format(self):
        # The service refuses a JSON-format request unless the message itself says "JSON".
        reports = [{"n": 1, "publisher": "Example News", "published": "2026-11-01T12:00:00+00:00",
                    "title": "Tesla on Autopilot hits parked truck", "summary": "", "text": "x" * 500}]
        messages = coder.build_messages({}, reports, [], CFG)
        user = next(m["content"] for m in messages if m["role"] == "user")
        self.assertIn("json", user.lower())
        self.assertTrue(user.rstrip().endswith(coder.ANSWER_REMINDER))


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
        for name in ("index.html", "search.html", "about.html", "sampling.html", "cases/SDI-00001.html", "sitemap.xml", "robots.txt",
                     "data/cases.csv", "data/self-driving-incidents.zip", "data/site-data.js", "CODEBOOK.md"):
            self.assertIn(name, first)

    def test_labels_say_mentioned_never_confirmed(self):
        export.export_all(published_store(), CFG)
        home = (self.root / "index.html").read_text()
        self.assertIn("Self-driving mode mentioned in coverage", home)
        self.assertIn("Said to be in use; not officially confirmed", home)
        self.assertIn("consortium@crimrxiv.com", home)
        for name in ("index.html", "search.html", "about.html", "sampling.html", "cases/SDI-00001.html"):
            self.assertIn("A project of Scott Jacques and Miranda Baumann. Miranda drives a Tesla. Dedicated to Bob.",
                          (self.root / name).read_text())
        for label in list(export.FEATURE_BADGE.values()) + [t["label"] for t in CFG["tags"]]:
            self.assertNotIn("confirmed", label.lower())
        self.assertNotIn("Jane", home)

    def test_homepage_puts_search_before_the_ten_latest(self):
        s = published_store()
        template = s["cases"][0]
        for i in range(2, 14):
            c = copy.deepcopy(template)
            c["key"], c["case_id"] = f"k{i}", f"SDI-{i:05d}"
            s["cases"].append(c)
        export.export_all(s, CFG)
        home = (self.root / "index.html").read_text()
        self.assertLess(home.index("Download the dataset"), home.index('id="search-title"'))
        self.assertLess(home.index('id="search-title"'), home.index('id="latest-title"'))
        self.assertEqual(home.count('<li class="incident"'), 10)
        self.assertIn("The 10 most recent", home)

    def test_json_key_order_does_not_depend_on_how_the_case_was_loaded(self):
        s = published_store()
        ev = s["cases"][0]["coding"]["evidence"]
        self.assertGreater(len(ev), 1)
        export.export_all(copy.deepcopy(s), CFG)
        first = (self.root / "data" / "cases.json").read_bytes()
        s["cases"][0]["coding"]["evidence"] = dict(reversed(list(ev.items())))
        export.export_all(s, CFG)
        self.assertEqual(first, (self.root / "data" / "cases.json").read_bytes())

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


class Archive(unittest.TestCase):
    """Full text goes to a separate private folder, one file per report, and never into this repository."""
    BODY = "Police said the Tesla left the road. " * 20

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def fetch(self, src):
        self.calls.append(src["url"])
        return ("", "") if "blocked" in src["url"] else (self.BODY, "publisher")

    def rows(self):
        with open(self.root / "index.csv", encoding="utf-8", newline="") as fh:
            return {r["url"]: r for r in csv.DictReader(fh)}

    def store(self):
        s = published_store()
        s["cases"][0]["sources"].append({"publisher": "Paywall Post", "title": "Blocked report",
                                         "url": "https://example.com/blocked", "published": "2026-11-20T12:00:00Z",
                                         "summary": None})
        waiting = case(["Tesla in Autopilot mode crashes into parked police car"], day=21)
        s["cases"].append(waiting)
        return s

    def test_nothing_happens_without_a_connected_archive(self):
        with mock.patch.dict(os.environ, {archive.ENV: ""}):
            self.assertIsNone(archive.update(self.store(), CFG, fetch=self.fetch))
        self.assertEqual(self.calls, [])

    def test_archive_inside_the_public_repository_is_refused(self):
        with mock.patch.dict(os.environ, {archive.ENV: str(archive.ROOT / "data")}):
            with self.assertRaises(ValueError):
                archive.archive_dir()

    def test_saves_one_file_per_report_of_published_cases_only(self):
        s = self.store()
        before = json.dumps(s, sort_keys=True)
        tally = archive.update(s, CFG, root=self.root, fetch=self.fetch)
        self.assertEqual(json.dumps(s, sort_keys=True), before)          # the public record is untouched
        rows = self.rows()
        published = [x["url"] for x in s["cases"][0]["sources"]]
        self.assertEqual(sorted(rows), sorted(published))                # the waiting case is not archived
        good = rows[published[0]]
        self.assertEqual((good["status"], good["case_id"], good["copy_from"]), ("saved", "SDI-00001", "publisher"))
        text = (self.root / good["file"]).read_text()
        self.assertTrue(good["file"].startswith("texts/SDI-00001/"))
        self.assertIn(f"URL: {published[0]}", text)
        self.assertTrue(text.rstrip().endswith(self.BODY.strip()))
        self.assertEqual(int(good["chars"]), len(self.BODY.strip()))
        blocked = rows["https://example.com/blocked"]
        self.assertEqual((blocked["status"], blocked["file"], blocked["attempts"]), ("unavailable", "", "1"))
        self.assertEqual(tally["saved"], len(published) - 1)

    def test_saved_text_is_not_fetched_again_and_blocked_reports_are_retried_on_later_days_only(self):
        s = self.store()
        archive.update(s, CFG, root=self.root, fetch=self.fetch, today="2026-11-22")
        first = {p.name: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.calls.clear()
        archive.update(s, CFG, root=self.root, fetch=self.fetch, today=st.now_iso()[:10])
        self.assertEqual(self.calls, [])                                 # same day: nothing is tried again
        self.assertEqual(first, {p.name: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        for day in ("2026-12-01", "2026-12-02", "2026-12-03", "2026-12-04"):
            rows = self.rows()
            for r in rows.values():                                      # pretend the last try was earlier
                r["retrieved"] = "2026-11-01T00:00:00Z" if r["status"] != "saved" else r["retrieved"]
            archive.save_index(self.root, {r["text_id"]: r for r in rows.values()})
            archive.update(s, CFG, root=self.root, fetch=self.fetch, today=day)
        self.assertEqual(self.calls, ["https://example.com/blocked"] * 2)  # three tries in all, then left alone
        self.assertEqual(self.rows()["https://example.com/blocked"]["attempts"], "3")

    def test_file_follows_a_report_that_moves_to_another_case(self):
        s = self.store()
        archive.update(s, CFG, root=self.root, fetch=self.fetch)
        url = s["cases"][0]["sources"][0]["url"]
        old = self.root / self.rows()[url]["file"]
        s["cases"][0]["case_id"] = "SDI-00009"
        archive.update(s, CFG, root=self.root, fetch=self.fetch)
        row = self.rows()[url]
        self.assertEqual(row["case_id"], "SDI-00009")
        self.assertTrue(row["file"].startswith("texts/SDI-00009/"))
        self.assertTrue((self.root / row["file"]).exists())
        self.assertFalse(old.exists())

    def test_complete_text_keeps_short_lines_but_needs_a_real_article(self):
        para = "<p>Troopers said the driver told them the car was in self-driving mode when it left the road.</p>"
        article = "<html><body><h1>Tesla crash</h1>" + para.replace("Troopers", "Troopers A") \
                  + "<p>No one was hurt.</p>" + "".join(para.replace("Troopers", f"Officer {i}") for i in range(6)) \
                  + "<p>Sign up now</p><p>Sign up now</p></body></html>"
        teasers = "<html><body><h1>Video</h1>" + "".join(f"<p>Story {i}</p>" for i in range(200)) + "</body></html>"

        class Reply:
            status_code, headers, encoding = 200, {"content-type": "text/html"}, "utf-8"
            def __init__(self, body): self.body = body
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def iter_content(self, n): yield self.body.encode()

        src = {"url": "https://example.com/a", "resolved": True}
        with mock.patch.object(enrich.requests, "get", return_value=Reply(article)):
            text = enrich.complete_text(src)
        self.assertIn("Tesla crash", text)
        self.assertIn("No one was hurt.", text)
        self.assertEqual(text.count("Sign up now"), 1)
        with mock.patch.object(enrich.requests, "get", return_value=Reply(teasers)):
            self.assertEqual(enrich.complete_text(src), "")
        self.assertEqual(enrich.complete_text({"url": "https://example.com/a", "resolved": False}), "")

    def test_export_writes_no_article_text_into_the_repository(self):
        tmp = Path(self.tmp.name) / "site"
        with mock.patch.object(export, "ROOT", tmp), mock.patch.object(export, "DATA", tmp / "data"), \
                mock.patch.object(pages, "ROOT", tmp):
            export.export_all(published_store(), CFG)
        self.assertEqual([p for p in tmp.rglob("*.txt") if p.name != "robots.txt"], [])


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
