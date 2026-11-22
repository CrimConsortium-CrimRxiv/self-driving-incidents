"""The codebook: every coded variable is defined once, here.

The same definitions drive the coding instructions, the checks applied to the coder's answers,
the downloadable codebook, and the labels shown on the website.
"""
from __future__ import annotations

VERSION = "0.1"
REVIEW_STATUS = "machine-coded, not yet reviewed"
NOT_STATED = "not_stated"

CLAIMANTS = ["driver", "passenger", "police", "prosecutor", "manufacturer", "regulator", "ntsb",
             "plaintiff_or_plaintiff_lawyer", "defense_lawyer", "court_or_jury", "witness",
             "news_outlet", "other"]

# kind: date | enum | multi | int | text
VARIABLES = [
    # ---- the incident
    {"name": "incident_date", "label": "Incident date", "group": "Incident", "kind": "date",
     "desc": "Date the incident happened, as stated in coverage: YYYY-MM-DD, or YYYY-MM or YYYY when "
             "only that much is given. Work out relative dates (\"Thursday night\") from the report's "
             "publication date."},
    {"name": "incident_type", "label": "Type of incident", "group": "Incident", "kind": "enum",
     "values": {
         "collision": "The vehicle struck, or was struck by, something or someone.",
         "near_miss_or_erratic_driving": "No collision reported: a near miss, swerving, running a signal, wrong-way travel or similar.",
         "traffic_stop_or_violation": "No collision reported: the coverage centres on a police stop, citation or arrest.",
         "driver_asleep_or_absent": "No collision reported: the person in the car was seen asleep, out of the driver's seat, or absent.",
         "low_speed_or_parking_manoeuvre": "Something that happened while parking, summoning or creeping at walking pace.",
         "other": "An identifiable incident that fits none of the above."},
     "desc": "What kind of event the coverage describes."},
    {"name": "collision_with", "label": "Collided with", "group": "Incident", "kind": "multi",
     "values": {
         "passenger_vehicle": "Car, SUV, pickup or van.", "truck_or_bus": "Heavy truck, tractor-trailer or bus.",
         "motorcycle": "Motorcycle or scooter.", "bicycle": "Bicycle or e-bike.", "pedestrian": "Person on foot.",
         "emergency_or_police_vehicle": "Police, fire, ambulance or tow vehicle.", "train": "Train or tram.",
         "fixed_object": "Pole, tree, barrier, wall, building and the like.",
         "construction_zone_or_equipment": "Work-zone equipment, barrels or vehicles.",
         "animal": "Animal.", "other": "Anything else."},
     "desc": "What the vehicle collided with, if there was a collision."},
    {"name": "vehicle_make", "label": "Vehicle make", "group": "Incident", "kind": "text",
     "desc": "Make of the vehicle whose automated-driving feature is in question (for example Tesla)."},
    {"name": "vehicle_model", "label": "Vehicle model", "group": "Incident", "kind": "text",
     "desc": "Model, as named in coverage (for example Model Y, Cybertruck, Cybercab)."},
    {"name": "vehicle_model_year", "label": "Model year", "group": "Incident", "kind": "int",
     "desc": "Model year of that vehicle, when coverage gives it."},
    {"name": "location_city", "label": "City or locality", "group": "Place and time", "kind": "text",
     "desc": "City, town or county where the incident happened."},
    {"name": "location_state_region", "label": "State or region", "group": "Place and time", "kind": "text",
     "desc": "State, province or region, written in full."},
    {"name": "location_country", "label": "Country", "group": "Place and time", "kind": "text",
     "desc": "Country, written in full (for example United States)."},
    {"name": "road_type", "label": "Road setting", "group": "Place and time", "kind": "enum",
     "values": {
         "highway_or_freeway": "Interstate, freeway, motorway or other limited-access road.",
         "urban_or_suburban_street": "City or suburban street.", "rural_road": "Rural or country road.",
         "intersection": "At a junction or signal.", "parking_lot_or_driveway": "Car park, garage or driveway.",
         "rail_crossing": "Railway or tram crossing.", "other": "Any other setting."},
     "desc": "Where on the road network the incident happened."},
    {"name": "time_of_day", "label": "Time of day", "group": "Place and time", "kind": "enum",
     "values": {"daytime": "In daylight.", "night": "After dark.", "dawn_or_dusk": "Around sunrise or sunset."},
     "desc": "When in the day the incident happened."},
    # ---- automation
    {"name": "system_named", "label": "Automated-driving feature named", "group": "Automation", "kind": "multi",
     "values": {
         "autopilot": "Tesla Autopilot or Autosteer.",
         "full_self_driving": "Tesla Full Self-Driving (FSD), supervised or otherwise.",
         "robotaxi_or_driverless_service": "A robotaxi or other vehicle operating with no driver.",
         "summon_or_autopark": "Summon, Smart Summon or Autopark.",
         "unspecified": "\"Self-driving mode\", \"driver assistance\" and similar, with no product named."},
     "desc": "Which automated-driving feature(s) the coverage names. Naming a feature is not evidence it was in use."},
    {"name": "engagement_status", "label": "Was the feature in use?", "group": "Automation", "kind": "enum",
     "values": {
         "confirmed_by_official_source": "A police or regulator finding, a court finding, or the manufacturer's own data report states the feature was in use.",
         "claimed": "Someone says it was in use (for example the driver, or police relaying the driver's account) and coverage reports no official confirmation.",
         "alleged_in_legal_filing": "The claim that it was in use is made in a lawsuit or criminal case.",
         "under_investigation": "Coverage says whether it was in use is unknown or being investigated.",
         "disputed": "Sources in the coverage contradict each other about whether it was in use.",
         "reported_not_engaged": "An official source or the manufacturer says it was not in use.",
         "mentioned_only": "The feature is mentioned as background; nobody in the coverage says it was in use."},
     "desc": "The strongest statement the coverage supports about whether the feature was in use at the time. "
             "This records what coverage reports; it is not a finding by this dataset."},
    {"name": "engagement_claimed_by", "label": "Who says it was in use", "group": "Automation", "kind": "multi",
     "values": {c: "" for c in CLAIMANTS},
     "desc": "Everyone the coverage reports as saying the feature was in use."},
    {"name": "driver_seat_occupied", "label": "Someone in the driver's seat", "group": "Automation", "kind": "enum",
     "values": {"yes": "A person was in the driver's seat.", "no": "The driver's seat was empty."},
     "desc": "Whether coverage says a person was in the driver's seat."},
    {"name": "driver_condition_mentioned", "label": "Driver condition mentioned", "group": "Automation", "kind": "multi",
     "values": {
         "alcohol_or_drugs": "Alcohol or drug impairment is alleged or reported.",
         "asleep_or_drowsy": "The driver is said to have been asleep or drowsy.",
         "distracted": "Phone use or another distraction is reported.",
         "medical_event": "A medical emergency is reported.",
         "not_supervising": "Hands off the wheel, eyes off the road, or otherwise not monitoring."},
     "desc": "Conditions of the person responsible for the vehicle that coverage mentions. Mentions, not findings."},
    # ---- harm
    {"name": "fatalities", "label": "Deaths reported", "group": "Harm", "kind": "int",
     "desc": "Number of people coverage reports as killed. 0 only when coverage says nobody died."},
    {"name": "injuries", "label": "Injuries reported", "group": "Harm", "kind": "int",
     "desc": "Number of people coverage reports as injured but not killed. 0 only when coverage says nobody was hurt."},
    {"name": "persons_harmed", "label": "Who was harmed", "group": "Harm", "kind": "multi",
     "values": {
         "subject_vehicle_driver": "The driver of the vehicle in question.",
         "subject_vehicle_passenger": "A passenger in that vehicle.",
         "other_vehicle_occupant": "Someone in another vehicle.", "motorcyclist": "A motorcyclist.",
         "cyclist": "A cyclist.", "pedestrian": "A pedestrian.",
         "emergency_or_road_worker": "A police officer, firefighter, medic, tow operator or road worker."},
     "desc": "Roles of the people reported killed or injured."},
    # ---- response
    {"name": "police_action", "label": "Police action", "group": "Official response", "kind": "enum",
     "values": {"investigating": "Police are investigating.", "citation_issued": "A citation or ticket was issued.",
                "arrest_made": "Someone was arrested."},
     "desc": "The furthest police action that coverage reports."},
    {"name": "criminal_charges", "label": "Criminal charges", "group": "Official response", "kind": "text",
     "desc": "Charges reported, in a few words (for example \"DUI; reckless driving\"). No names."},
    {"name": "criminal_case_stage", "label": "Criminal case stage", "group": "Official response", "kind": "enum",
     "values": {"charged": "Charges filed or announced.", "plea": "A plea was entered.", "trial": "At trial.",
                "convicted": "Found guilty.", "acquitted": "Found not guilty.", "sentenced": "Sentenced.",
                "dismissed": "Charges dropped or dismissed."},
     "desc": "The furthest stage of any criminal case that coverage reports."},
    {"name": "civil_litigation", "label": "Civil litigation", "group": "Official response", "kind": "enum",
     "values": {"lawsuit_filed": "A lawsuit has been filed.", "trial": "At trial.",
                "verdict_for_plaintiff": "Verdict for the person suing.",
                "verdict_for_defendant": "Verdict for the party sued.", "settled": "Settled.",
                "dismissed": "Dismissed."},
     "desc": "The furthest stage of any lawsuit about the incident that coverage reports."},
    {"name": "regulator_involved", "label": "Regulator or safety board", "group": "Official response", "kind": "multi",
     "values": {"nhtsa": "U.S. National Highway Traffic Safety Administration.",
                "ntsb": "U.S. National Transportation Safety Board.",
                "state_regulator": "A U.S. state agency such as a DMV or utilities commission.",
                "non_us_regulator": "A regulator outside the United States."},
     "desc": "Regulators or safety boards that coverage says are involved in this incident."},
    {"name": "responsibility_attributed_to", "label": "Responsibility attributed to", "group": "Official response",
     "kind": "multi",
     "values": {"driver": "The person responsible for the vehicle.",
                "automation_or_manufacturer": "The automated-driving feature or its maker.",
                "other_road_user": "Another driver, rider or pedestrian.",
                "road_or_weather_conditions": "Road design, work zones, weather or lighting."},
     "desc": "Where anyone quoted or cited in coverage places responsibility. This records attributions made "
             "by others; the dataset never judges fault."},
    {"name": "coverage_stage", "label": "Stage of coverage", "group": "Coverage", "kind": "enum",
     "values": {"initial_report": "First reports of the incident.",
                "follow_up_investigation": "Later reporting on an investigation or new findings.",
                "legal_proceeding": "Reporting on charges, a lawsuit, a trial or a verdict.",
                "retrospective": "A look back at an older incident."},
     "desc": "What the most recent coverage is mainly about."},
]

CLAIM_TOPICS = {
    "automation_engaged": "Says the feature was in use.",
    "automation_not_engaged": "Says the feature was not in use.",
    "automation_performance": "Describes what the feature did or failed to do.",
    "driver_behavior": "Describes what the person responsible for the vehicle did or their condition.",
    "cause_or_responsibility": "Says what caused the incident or who is responsible.",
    "other": "Any other claim worth recording.",
}

BY_NAME = {v["name"]: v for v in VARIABLES}

CASE_FIELDS = [
    ("case_id", "Permanent identifier for the case (for example SDI-00012)."),
    ("maker", "Vehicle maker the case was collected under."),
    ("first_reported", "Date of the earliest report found (YYYY-MM-DD)."),
    ("last_reported", "Date of the most recent report found."),
    ("sort_date", "Date used to order cases: the incident date when coded, otherwise first_reported."),
    ("headline", "A representative headline, in the publisher's words."),
    ("headline_publisher", "Publisher of that headline."),
    ("source_summary", "A publisher's own one-line summary of its report (not written by this project)."),
    ("source_summary_publisher", "Publisher of that summary."),
    ("n_sources", "Number of reports attached to the case."),
    ("auto_model", "Vehicle model found by word matching in headlines (uncoded cases only rely on this)."),
    ("auto_location", "Place name found by word matching in headlines."),
    ("auto_tags", "Word-match labels, each worded \"mentioned in coverage\"."),
    ("narrative", "Short neutral account of what coverage reports, drafted by the machine coder."),
    ("review_status", "\"machine-coded, not yet reviewed\" until a person has checked the record."),
    ("coder", "Model that drafted the coding."),
    ("coded_at", "When the coding was drafted (UTC)."),
    ("codebook_version", "Version of this codebook used."),
    ("text_basis", "Fullest text the coder could read for the case: full_text, summary or headline."),
    ("unsupported_values_removed", "How many values the coder proposed that were removed because their "
                                   "supporting quotation could not be found in the report."),
    ("merged_ids", "Retired case IDs whose reports were joined into this case because they described the "
                   "same event (see `retired_ids.csv`). Blank for most cases."),
    ("url", "Address of the case's page on the website."),
]


def prompt_codebook() -> str:
    """Compact rendering for the coding instructions."""
    lines = []
    for v in VARIABLES:
        if v["kind"] in ("enum", "multi"):
            opts = "; ".join(f"{k} = {d}" if d else k for k, d in v["values"].items())
            many = "one of" if v["kind"] == "enum" else "list of any of"
            lines.append(f"- {v['name']} ({many}): {v['desc']} Options: {opts}")
        else:
            lines.append(f"- {v['name']} ({v['kind']}): {v['desc']}")
    return "\n".join(lines)


def markdown() -> str:
    out = [f"# Codebook, version {VERSION}", "",
           "Every case is one incident in which a vehicle's automated-driving feature is claimed, "
           "questioned or confirmed to be involved, as described in published reports.", "",
           "Coded values are drafted by a language model that reads only the reports attached to the "
           f"case. Each record is marked \"{REVIEW_STATUS}\" until a person has checked it. A value is "
           "kept only when the model also supplies a quotation that is found, word for word, in the "
           "report it cites; otherwise the value is removed and counted in "
           "`unsupported_values_removed`. A blank cell (or `not_stated`) means the reports read by the "
           "coder did not state it. It does not mean \"no\".", "",
           "## Files", "",
           "| File | One row per | Contents |", "|---|---|---|",
           "| `cases.csv` | case | Identifiers, dates, headline, publisher summary, every coded variable, narrative |",
           "| `evidence.csv` | coded value | The quotation and report supporting each coded value |",
           "| `claims.csv` | claim | Who said what about the incident, with quotation and report |",
           "| `sources.csv` | report | Publisher, headline, link, date, and how much of it the coder could read |",
           "| `screened_out.csv` | report group | Items collected but not treated as a case, and why |",
           "| `retired_ids.csv` | retired case ID | Case IDs no longer in use, the case each was joined into, when and why |",
           "| `cases.json` | case | Everything above, nested |", "",
           "Variables that allow several values are joined with `; ` in `cases.csv`.", "",
           "## Case fields", "", "| Field | Meaning |", "|---|---|"]
    out += [f"| `{n}` | {d} |" for n, d in CASE_FIELDS]
    group = None
    for v in VARIABLES:
        if v["group"] != group:
            group = v["group"]
            out += ["", f"## Coded variables: {group}", ""]
        kind = {"enum": "one value", "multi": "one or more values", "int": "whole number",
                "text": "short text", "date": "date"}[v["kind"]]
        out += [f"### `{v['name']}`: {v['label']}", "", f"{v['desc']} ({kind})", ""]
        if v.get("values"):
            out += ["| Value | Meaning |", "|---|---|"]
            out += [f"| `{k}` | {d or k.replace('_', ' ').capitalize() + '.'} |" for k, d in v["values"].items()]
            out.append("")
    out += ["## Claims (`claims.csv`)", "",
            "| Field | Meaning |", "|---|---|",
            "| `claimant` | Who made the claim: " + ", ".join(f"`{c}`" for c in CLAIMANTS) + " |",
            "| `topic` | " + " ".join(f"`{k}`: {d}" for k, d in CLAIM_TOPICS.items()) + " |",
            "| `paraphrase` | The claim in neutral words, without private individuals' names |",
            "| `quote` | Words from the report that carry the claim |",
            "| `source_url` | The report the quotation comes from |", "",
            "## Retired case IDs (`retired_ids.csv`)", "",
            "A case ID is permanent. When two published cases are found to describe the same event, a "
            "person who has checked the reports joins them: the lower ID is kept, every report moves to "
            "it, and it is coded again from all the reports together. The other ID is retired. It is "
            "never given to another case, and its web address stays in place and points to the case "
            "that holds its reports. Cases are joined only when the reports themselves show one event "
            "(for example the same date, place and people); cases that merely look alike stay separate.", "",
            "| Field | Meaning |", "|---|---|",
            "| `retired_id` | The case ID that is no longer in use |",
            "| `merged_into` | The case that now holds its reports |",
            "| `retired_on` | Date the two were joined (YYYY-MM-DD) |",
            "| `n_reports_moved` | Number of reports the retired case held when it was joined |",
            "| `reason` | What in the reports shows the two were one event |", "",
            "## Screening", "",
            "A group of reports becomes a case only when the coder judges that it is mainly about one "
            "identifiable incident and that an automated-driving feature is said, or asked, to be "
            "involved. Round-ups of several incidents, statistics, product news, opinion and reports "
            "about other makers are listed in `screened_out.csv` with the reason.", ""]
    return "\n".join(out)
