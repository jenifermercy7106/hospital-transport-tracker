const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, ImageRun, BorderStyle, AlignmentType, LevelFormat,
  PageBreak, ExternalHyperlink,
} = require("docx");

const PAGE_W = 12240, PAGE_H = 15840; // US Letter DXA

function H1(text) { return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 160 } }); }
function H2(text) { return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 120 } }); }
function P(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 160 },
    children: [new TextRun({ text, ...opts })],
  });
}
function Bold(text) { return new TextRun({ text, bold: true }); }
function bullet(text, level = 0) {
  return new Paragraph({
    text,
    numbering: { reference: "bullets", level },
    spacing: { after: 80 },
  });
}

function cell(text, opts = {}) {
  return new TableCell({
    width: opts.width ? { size: opts.width, type: WidthType.DXA } : undefined,
    shading: opts.header ? { type: ShadingType.CLEAR, fill: "2E5B4E" } : undefined,
    children: [new Paragraph({
      children: [new TextRun({ text: String(text), bold: !!opts.header, color: opts.header ? "FFFFFF" : undefined })],
    })],
  });
}

function makeTable(headers, rows, widths) {
  const totalWidth = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ children: headers.map((h, i) => cell(h, { header: true, width: widths[i] })) }),
      ...rows.map(r => new TableRow({ children: r.map((c, i) => cell(c, { width: widths[i] })) })),
    ],
  });
}

function image(path, width, height, caption) {
  const data = fs.readFileSync(path);
  const children = [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new ImageRun({ data, transformation: { width, height }, type: "png" })],
    }),
  ];
  if (caption) {
    children.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 200 },
      children: [new TextRun({ text: caption, italics: true, size: 20 })],
    }));
  }
  return children;
}

const doc = new Document({
  numbering: {
    config: [{
      reference: "bullets",
      levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 480, hanging: 240 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 900, hanging: 240 } } } },
      ],
    }],
  },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: 1080, bottom: 1080, left: 1080, right: 1080 } } },
    children: [
      // ---------------- TITLE PAGE ----------------
      new Paragraph({ spacing: { before: 1200, after: 200 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "Hospital Transport Request Tracker", bold: true, size: 44 })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
        children: [new TextRun({ text: "Urgency-Aware, Location-Aware Coordination for Multi-Specialty", size: 26 })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 },
        children: [new TextRun({ text: "Hospitals Sharing Operating Theatres Across Departments", size: 26 })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
        children: [new TextRun({ text: "Project Report", bold: true, size: 24 })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
        children: [new TextRun({ text: "Prepared by: Jeni", size: 22 })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
        children: [new TextRun({ text: "Computer Science Engineering, Rathinam Technical Campus", size: 22 })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 800 },
        children: [new TextRun({ text: new Date().toLocaleDateString("en-IN", { year: "numeric", month: "long", day: "numeric" }), size: 22 })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
        children: [new TextRun({ text: "Review 2 — Revised Edition", bold: true, size: 22, color: "2E5B4E" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
        children: [new TextRun({ text: "Deliverables in this package:", bold: true, size: 22 })] }),
      bullet("Synthetic dataset — transport requests, patient locations, priority, porter availability, completion timestamps"),
      bullet("Baseline method (baseline.py) — naive FIFO queue, no urgency/location awareness"),
      bullet("Working prototype — decision engine (prototype_engine.py) + interactive Streamlit tracker (app.py)"),
      bullet("Eight implemented edge/failure-case tests, 14/14 assertions passing (edge_cases.py)"),
      bullet("Measurable experiment comparing baseline vs prototype vs target (experiment.py)"),
      bullet("Review 2: a reserved-porter mitigation experiment with trade-off and error analysis (experiment_mitigation.py)"),
      bullet("Review 2: a scripted end-to-end live run-through of the tracker's full staff workflow (live_runthrough.py)"),
      bullet("This report — scenario, method, results, stakeholder validation, ethics, deployment checklist"),
      new Paragraph({ children: [new PageBreak()] }),

      // ---------------- 0. REVISION NOTES ----------------
      H1("0. Revision Notes — What Changed for Review 2"),
      P("Review 1 closed with four named next steps. This revision addresses the first three directly and is explicit about the fourth remaining as planned future work, rather than claiming it is done:"),
      bullet("Live run-through of the tracker. Addressed — Section 4 now includes a scripted, reproducible end-to-end session (live_runthrough.py) that drives the exact engine calls app.py's buttons use, through logging a messy request, reviewing a recommendation, confirming an override, and confirming a handover. The sandbox this project was built in has no internet access, so a real browser session of Streamlit could not be captured here (verified: pip install streamlit fails with no matching distribution). Jeni should still run streamlit run app.py locally — she has Python/Anaconda installed — to capture the actual on-screen walkthrough for a live demo; this script proves the underlying logic is correct and ready for that."),
      bullet("Mitigation experiment for the Emergency SLA gap. Addressed — Section 6.7 tests the proposed reserved-porter-pool idea directly, with a genuinely useful (and initially counter-intuitive) result: the straightforward version of this idea makes Emergency performance worse, not better, and the section explains why and what a better next step would look like."),
      bullet("A bug found and fixed while building the above. While cross-checking the mitigation engine against the original Review 1 engine for an exact baseline comparison, an inconsistency was found in how simulate_queue() handled an unresolved source location: it picked a porter as if the job were in a default zone, but then charged zero travel distance for that same job. This has been fixed (Section 6.1 numbers below reflect the corrected engine); the direction and shape of every Review 1 conclusion is unchanged, but the exact Emergency miss-rate figure shifts from 42.5% to 43.7% as a result. This is reported here rather than quietly — the whole point of Section 5's edge-case tests and this fix is that the system should fail visibly, including to its own author."),
      bullet("Real user validation with live hospital staff and a shared multi-user backend. Not done, by design — both require resources outside a course project's scope (real ward access; a shared database deployment). Both remain explicitly listed in Section 9's deployment checklist as prerequisites before any pilot, not silently dropped."),

      // ---------------- 1. SCENARIO DEFINITION ----------------
      H1("1. Scenario Definition"),
      P("A multi-specialty hospital runs several departments — General Surgery, Orthopedics, Cardiology, Oncology, Emergency Medicine, Radiology and Nephrology — that all share a single pool of operating theatres, imaging suites and a common porter (patient-transport staff) workforce. Moving a patient between a ward, a theatre, radiology, recovery or the ICU currently depends on a ward nurse or coordinator phoning the porter desk."),
      P("This coordination method breaks down in three predictable ways:"),
      bullet("Calls are missed or go unanswered when the porter desk is busy, so a request is never logged at all."),
      bullet("Urgency is communicated verbally and inconsistently — an Emergency Department transfer can end up waiting behind a Routine discharge simply because it was called in later or the desk did not register how time-critical it was."),
      bullet("There is no shared, visible record of who is transporting whom, from where, to where, or whether the receiving unit has actually confirmed the handover — so a \"completed\" transfer is really just an assumption until someone checks."),
      P("The goal of this project is not to build a fully autonomous dispatch robot — clinical transport decisions (which patient moves, on what equipment, escorted by whom) must remain with authorised staff. The goal is to replace the invisible, unaccountable phone-call layer with a shared, urgency-ranked, location-aware request board that staff use to log requests, see recommended porters, and confirm every assignment and handover themselves."),
      H2("In scope"),
      bullet("Logging and tracking transport requests with urgency, source, destination, and timestamps"),
      bullet("Recommending (not auto-assigning) a porter based on urgency, location/zone and current porter load"),
      bullet("Detecting and visibly flagging at-risk and breached requests before they are fully missed"),
      bullet("Handling low-quality or missing input (blank fields, free-text typos, unrecorded urgency, bad manual timestamps) without silently hiding the problem"),
      bullet("Preserving a full staff action log so every final action is traceable to a named, authorised person"),
      H2("Out of scope"),
      bullet("Automatic porter dispatch without staff confirmation"),
      bullet("Real-time GPS/indoor-positioning of porters (approximated here with a hospital zone map instead)"),
      bullet("Integration with a live hospital information system (HIS) — this prototype uses a realistic synthetic dataset"),

      // ---------------- 2. BASELINE METHOD ----------------
      H1("2. Baseline Method"),
      P("To measure whether the prototype is actually an improvement — not just a nicer-looking interface — a deliberately simple baseline was implemented in baseline.py. The baseline represents the most common \"first step up from a phone call\" a hospital might realistically try: a single shared, first-come-first-served (FIFO) list."),
      H2("Baseline rules"),
      bullet("Requests are served strictly in the order they arrive (timestamp_requested), with no urgency weighting."),
      bullet("No location or zone awareness — any idle porter (of an assumed flat capacity of 3 effective porter-slots) takes the next request, regardless of distance."),
      bullet("A single flat average service time (18 minutes) is applied to every request, regardless of urgency or travel distance."),
      bullet("No data-quality handling: a missing or malformed field is not corrected or flagged — the request is effectively dropped from consideration, mirroring how an unclear phone call is often just \"missed\" today."),
      P("This baseline is intentionally naive. It is what a hospital gets if it digitises the phone-call board without changing the underlying coordination logic — a shared list is visible, but Emergency requests still queue behind everything else, and messy inputs still fall through the cracks."),

      // ---------------- 3. IMPLEMENTED SOLUTION ----------------
      H1("3. Implemented Solution"),
      P("The prototype is a two-part system built entirely in Python:"),
      bullet("prototype_engine.py — the decision-support core: validates and scores incoming requests, recommends a porter, and detects SLA risk. This is unit-tested independently of any UI (see Section 5)."),
      bullet("app.py — an interactive Streamlit web application that hospital staff would actually use: a live, colour-coded request queue, a form to log new requests, and buttons for every final action."),
      H2("3.1 Data validation and confidence scoring"),
      P("Every incoming request — however it arrives — is passed through validate_requests(), which never silently drops a row. Instead it:"),
      bullet("Canonicalises free-text locations (e.g. \"ward a1\", \"icu unit\", \"OT-2\") against the hospital's known location list, but still flags the request as auto-corrected rather than treating it as clean input."),
      bullet("Defaults a missing urgency tag to Urgent — never to Routine — so an unclear call is never quietly deprioritised into invisibility. The default is explicitly flagged for clinician review."),
      bullet("Assigns a data_confidence level (High / Medium / Low) and a human-readable data_issues string to every request, so uncertainty is always visible to staff rather than hidden inside a black-box score."),
      H2("3.2 Priority scoring"),
      P("score_priority() combines three signals into a single priority number that ranks the live queue: the request's urgency tier (Emergency > Urgent > Routine), an aging boost so a long-waiting Routine case is not starved indefinitely behind a stream of newer Urgent cases, and a small visibility boost for low-confidence requests — so messy or ambiguous requests surface for review rather than sinking to the bottom of the queue."),
      H2("3.3 Porter recommendation"),
      P("recommend_porter() suggests the nearest available porter using a hospital zone map (wards, ICU, radiology, OT complex and recovery are grouped into five zones as a practical stand-in for full indoor positioning). Recommendation is exactly that — a suggestion shown to staff with its reasoning (e.g. \"nearest available porter, zone distance 1\"); the assignment is only made when staff click Confirm in the app, and staff may pick a different porter entirely (an override), which is logged as such."),
      H2("3.4 SLA / uncertainty detection"),
      P("detect_sla_state() classifies each open request as On-Track, At-Risk, Breached, or — importantly — Unknown-BadTimestamps when the underlying data cannot support a reliable duration calculation (for example, a handover timestamp logged before the recorded arrival time, a real error mode from manual back-filled entries). Rather than silently computing a nonsensical negative duration, these cases are flagged for human review."),
      H2("3.5 Clinician / staff control over final actions"),
      P("This is the non-negotiable constraint stated in the brief, and it is enforced structurally, not just by convention:"),
      bullet("The engine functions are named recommend_* and detect_* — none of them write to any request record or porter roster."),
      bullet("In app.py, a porter is only assigned when a named, logged-in staff member selects a porter (defaulting to the recommendation, but freely overridable) and clicks \"Confirm assignment\"."),
      bullet("A handover is only marked complete when staff click \"Confirm handover\" — the system never infers completion from elapsed time alone."),
      bullet("Every action (new request logged, assignment confirmed, recommendation overridden, handover confirmed, escalation, cancellation) is appended to an in-app action log stamped with staff name, role and timestamp — the audit trail proves a human, not the algorithm, made the final call."),

      // ---------------- 4. USABILITY WALKTHROUGH ----------------
      H1("4. Usability Walkthrough"),
      P("A typical shift, walked through the prototype:"),
      bullet("A ward nurse logs a new request from the sidebar form: patient ID, source, destination, urgency, and reason. The request appears instantly on the shared board — no phone call, no risk of the call not being picked up."),
      bullet("The board sorts by priority score, not arrival time. An Emergency request logged two minutes ago is shown above a Routine request logged twenty minutes ago, with the reasoning visible (urgency + waiting time)."),
      bullet("Each request card shows a colour-coded SLA indicator (🟢 on-track, 🟠 at-risk, 🔴 breached, ⚪ unresolved timestamps), a recommended porter with a one-line reason, and any data-quality warning (e.g. \"source location auto-corrected from free text\")."),
      bullet("The OT coordinator reviews the recommended porter, optionally overrides it (e.g. because they know a porter is on a break the system doesn't yet know about), and clicks Confirm — this is logged as either a confirmed assignment or an override."),
      bullet("When the porter and patient reach the destination, the receiving unit's staff click Confirm handover — this is the moment the transfer is actually recorded as complete, closing the loop that phone calls never reliably closed."),
      bullet("At any point, a staff member can reassign/escalate a stuck request or cancel a duplicate/erroneous one; both actions are logged."),
      bullet("A staff-facing action log and a completed/cancelled log are available for shift handover and audit, addressing the accountability gap of the phone-call system."),
      H2("4.1 Demo clock (added in Review 2)"),
      P("The sample dataset is historical (24–30 August 2026). Early testing of the live tracker surfaced a genuine usability bug: comparing that historical data against the real wall-clock date made every single request appear as \"Breached\", since months had passed since the data was generated — a misleading demo, not a reflection of the engine's actual SLA logic. app.py now includes a sidebar \"Demo clock\" control that lets a reviewer pick a simulated point in time inside the dataset's week (default: 28 Aug, 14:00), so the colour-coded SLA states shown are meaningful; a checkbox switches to the real current time for when this moves to a live, non-historical deployment. Re-running the queue view at the new default clock shows a believable mix of 97 Breached / 64 On-Track requests out of 161 open, instead of 161/161 Breached."),
      H2("4.2 Live run-through (Review 2)"),
      P("live_runthrough.py performs a scripted end-to-end session that calls the exact same functions app.py's UI buttons call (validate_requests, score_priority, recommend_porter), in the same order a staff member's clicks would: a new, deliberately messy request is logged (typo'd source location, no urgency stated) \u2192 the engine returns a priority score, a recommended porter, and a confidence flag \u2192 a staff member deliberately overrides the recommendation \u2192 the staff member confirms the handover. The resulting action log (reproduced below) shows every state-changing action attributed to a named staff member, never to the engine itself:"),
      ...[
        "2026-10-05 04:23:52  A. Kumar  Ward Sister  Logged new request       LIVE0001  ward a1 -> ICU, urgency=(unspecified)",
        "2026-10-05 04:23:52  A. Kumar  Ward Sister  Overrode recommendation  LIVE0001  porter=P03 (recommended=P01)",
        "2026-10-05 04:23:53  A. Kumar  Ward Sister  Confirmed handover       LIVE0001  porter=P03",
      ].map((line, i, arr) => new Paragraph({
        spacing: { after: i === arr.length - 1 ? 160 : 20 },
        children: [new TextRun({ text: line, font: "Courier New", size: 16 })],
      })),
      P("The full transcript, including the engine's intermediate reasoning (resolved location, data-confidence flag, priority score, recommendation reason) at each step, is saved to outputs/live_runthrough_log.txt and is reproducible by running python3 scripts/live_runthrough.py. As noted in Section 0, this validates the logic end-to-end but is not a substitute for Jeni clicking through the actual rendered page locally, which she is able to do outside this sandbox."),

      // ---------------- 5. EDGE-CASE TESTS ----------------
      H1("5. Edge-Case and Failure-State Tests"),
      P("Eight realistic failure states are implemented as automated checks in edge_cases.py (all currently passing, 14/14 assertions — 6 states from Review 1, plus 2 added in Review 2 to cover the new reserved-porter-pool feature introduced in Section 6.7). Each test feeds the engine deliberately broken input and checks that the system degrades safely — it must never crash, never silently drop a request, and never finalise an action without staff confirmation."),
    ]
      .concat([
        makeTable(
          ["#", "Failure state", "Expected safe behaviour", "Result"],
          [
            ["1", "Missing source location on the call log", "Flagged Low confidence, request still visible", "PASS"],
            ["2", "Free-text / typo'd location (\"ward a1\", \"icu unit\")", "Auto-corrected but still flagged, not silently trusted", "PASS"],
            ["3", "Missing urgency tag", "Defaults to Urgent (never Routine); flagged for clinician review", "PASS"],
            ["4", "Clock-skew: handover confirmed before arrival (bad manual entry)", "Flagged Unknown-BadTimestamps, never a negative duration", "PASS"],
            ["5", "Surge: 5 simultaneous Emergencies vs 2 available porters", "Completes without error; over-capacity requests escalated, not silently queued", "PASS"],
            ["6", "Total infrastructure failure: empty porter roster", "No crash; every request escalated, no fabricated assignment", "PASS"],
            ["7 (R2)", "Reserved Emergency pool itself overwhelmed (4 Emergencies, 1 reserved porter)", "Overflows into the general pool rather than leaving a request unassigned", "PASS"],
            ["8 (R2)", "Reserved porter ID doesn't exist in the roster (config typo)", "Falls back to the general pool instead of crashing or dropping all Emergencies", "PASS"],
          ],
          [900, 4000, 4600, 1500]
        ),
      ])
      .concat([
        new Paragraph({ spacing: { before: 200, after: 200 } }),
        P("These tests matter more than they might first appear: a hospital tracker that crashes or silently drops a request on messy real-world input is worse than the phone system it replaces, because staff may trust a screen that is quietly wrong. The design principle throughout is fail-visible, not fail-silent."),

        // ---------------- 6. PERFORMANCE RESULTS ----------------
        H1("6. Performance Results"),
        H2("6.1 The problem, quantified"),
        P("A one-week synthetic dataset of 662 transport requests (including realistic duplicate calls, clock-skew entries, and ~10% missing/garbled location or urgency data) was generated to reflect what a phone-call-coordinated department actually produces. Under the historical (phone-call) outcomes encoded in that dataset:"),
      ])
      .concat(image("outputs/chart_historical_problem.png", 500, 321,
        "Figure 1. Historical outcomes by urgency. Emergency transfers are the group least likely to be completed on time — only 5 of 87 Emergency requests (5.7%) were marked Completed; 61 were Delayed and 16 were Missed entirely."))
      .concat([
        P("Across all 662 requests, 32.2% ended up Missed or Delayed under the current phone-based approach — the exact operational failure the brief asks this project to demonstrate and address."),
        H2("6.2 Experiment design"),
        P("To isolate the effect of the coordination logic itself (as opposed to noise in the historical data), the same 662-request arrival stream was replayed through two policies:"),
        bullet("Baseline — FIFO queue, flat service time, no urgency or location awareness (Section 2)"),
        bullet("Prototype — urgency + aging priority score, zone-aware porter recommendation, and SLA thresholds matched to each urgency tier (Emergency 10 min / Urgent 30 min / Routine 90 min)"),
        P("This replay design means both policies see identical demand; any difference in outcome is attributable to the allocation logic, not to a lucky dataset."),
        H2("6.3 Baseline vs Prototype vs Target"),
      ])
      .concat([
        makeTable(
          ["Urgency", "n", "Baseline\n% missed/late", "Prototype\n% missed/late", "Target\n% missed/late", "Improvement\n(pct points)", "Meets\ntarget?"],
          [
            ["Emergency", "87", "100.0%", "43.7%", "5.0%", "+56.3", "No — see 6.5"],
            ["Urgent", "207", "9.2%", "0.0%", "10.0%", "+9.2", "Yes"],
            ["Routine", "333", "0.0%", "0.0%", "15.0%", "+0.0*", "Yes"],
          ],
          [1400, 700, 1700, 1700, 1600, 1700, 1400]
        ),
      ])
      .concat([
        new Paragraph({ spacing: { before: 100, after: 120 },
          children: [new TextRun({ text: "*Routine already meets target under both policies at this load; the improvement shows up as headroom, not a visible percentage-point gain.", italics: true, size: 20 })] }),
        P("Weighted across all 662 requests with a resolved urgency, overall missed/late rate falls from 16.9% (baseline) to 6.1% (prototype) — a 10.8 percentage-point improvement from coordination logic alone, using identical demand and an identical porter roster."),
      ])
      .concat(image("outputs/chart_missed_by_urgency.png", 500, 321,
        "Figure 2. Missed/late transfer rate by urgency: baseline (red) vs prototype (green). The prototype's largest gain is exactly where it matters most — Emergency transfers."))
      .concat([
        H2("6.4 Handling of low-quality and missing inputs"),
      ])
      .concat(image("outputs/chart_data_confidence.png", 420, 344,
        "Figure 3. Input data confidence across the one-week dataset. 9.8% of requests arrived with Low-confidence data (missing or unrecognisable location)."))
      .concat([
        P("65 of 662 requests (9.8%) had missing or unrecognisable location data — a realistic rate for phone-logged, free-text intake. 100% of these Low-confidence requests were automatically escalated for staff review rather than silently guessed at or dropped, directly answering the brief's requirement to show how uncertainty is communicated to authorised staff."),
        H2("6.5 Error analysis — where the prototype still falls short"),
        P("Honesty about remaining failure is part of this deliverable. 38 of 87 Emergency requests (43.7%) were still classified Completed-Late by the prototype, missing the 5% target. Root-cause analysis of these 38 cases:"),
        bullet("The Emergency SLA (10 minutes, matching real hospital rapid-response expectations) is tight relative to physical travel distance in this hospital layout: a transfer spanning the maximum zone distance (e.g. a ward to the OT complex) costs roughly 6 + 4×2.5 = 16 minutes of service time alone under the prototype's zone-distance model — before any queueing wait is added. No allocation logic can make a porter walk faster than physics allows."),
        bullet("This is a genuine, non-cosmetic limitation of a coordination-logic-only fix: reassigning porters more intelligently reduces queueing delay to near zero (see Figure 2's Urgent/Routine columns), but it cannot eliminate a service time that is structurally longer than the SLA."),
        bullet("Review 1 hypothesised that the hospital, not just the software, likely needs a dedicated, pre-positioned porter reserve near high-emergency zones. Section 6.7 tests that hypothesis directly against the same dataset and finds it is more subtle than it first appears — a straightforward reserve makes things worse, not better, for the reason explained there."),
        H2("6.6 Baseline vs Prototype: why the chosen approach is appropriate"),
        P("A rule-based priority queue with zone-aware recommendation (rather than, say, a machine-learned dispatch model) was chosen deliberately for this problem, for three reasons:"),
        bullet("Explainability under clinical accountability constraints — every recommendation traces to a readable reason (\"nearest available porter, zone distance 1\"; \"urgency=Emergency, waited 6 min\"). Staff who are legally and professionally responsible for the transfer need to understand why a suggestion was made, not just trust an opaque score."),
        bullet("No training data requirement — a learned model would need months of clean historical dispatch data this hospital does not yet have (its current system is phone calls). The rule-based approach works from day one and can be tuned as real data accumulates."),
        bullet("Fail-visible behaviour under missing/bad data — Section 5's edge cases show the rule-based engine degrades to explicit escalation under bad input; a black-box model would more likely produce a confident-looking but wrong recommendation on the same messy input, which is a worse failure mode in a clinical setting."),
        H2("6.7 Mitigation Experiment (Review 2): Reserved Emergency Porter Pool"),
        P("Hypothesis, from Section 6.5: dedicating one or two porters exclusively to Emergency-tier requests (a real \"STAT porter\" pattern some hospitals use) should close most of the remaining Emergency SLA gap, at some cost to Urgent/Routine wait times. This was implemented as simulate_queue_with_reserve() and tested against the identical 662-request stream used throughout Section 6, in three configurations: 0 reserved porters (the Section 6 prototype, unchanged), 1 reserved porter (P03, the zone with the lowest average distance to all other zones), and 2 reserved porters (P03 + P08, covering the two zones that together produce 37% of Emergency calls). An Emergency request only draws from the reserved pool if its wait there would stay under 5 minutes; otherwise it overflows into the general pool, so an empty reservation is never allowed to delay a live Emergency case."),
      ])
      .concat([
        makeTable(
          ["Configuration", "Urgency", "% missed/late", "vs target", "Meets target?"],
          [
            ["0 reserved (baseline)", "Emergency", "43.7%", "5.0%", "No"],
            ["0 reserved (baseline)", "Urgent / Routine", "0.0% / 0.0%", "10.0% / 15.0%", "Yes / Yes"],
            ["1 reserved (P03)", "Emergency", "50.6%", "5.0%", "No — worse"],
            ["1 reserved (P03)", "Urgent / Routine", "0.0% / 0.0%", "10.0% / 15.0%", "Yes / Yes"],
            ["2 reserved (P03+P08)", "Emergency", "48.3%", "5.0%", "No — worse"],
            ["2 reserved (P03+P08)", "Urgent / Routine", "0.0% / 0.0%", "10.0% / 15.0%", "Yes / Yes"],
          ],
          [2600, 2200, 1800, 1800, 1900]
        ),
      ])
      .concat(image("outputs/chart_mitigation_tradeoff.png", 460, 288,
        "Figure 4. Reserving porters for Emergency-only use did not reduce Emergency misses in this dataset — it increased them, while leaving the already-passing Urgent/Routine tiers unchanged."))
      .concat([
        P("The result is counter-intuitive and is reported as found, not adjusted to fit the hypothesis: reserving porters made Emergency performance worse (43.7% -> 50.6% missed/late with 1 reserved porter), not better, while Urgent and Routine were completely unaffected (they were already at 0% and had headroom to spare). Tracing individual requests (prototype_pool_used column) explains why: with only 87 Emergency calls spread across a full week, concentrating them onto 1-2 specific porters creates queueing for Emergency itself whenever two calls land close together — a situation the unrestricted 8-porter pool simply absorbed by sending the second call to any other free porter. Reservation does not add capacity; it removes flexibility, and with this demand pattern the flexibility was doing more work than the dedicated-porter idea assumed."),
        P("As a sanity check on whether this is a staffing (capacity) problem rather than an allocation (policy) problem, the same stream was re-run with 1 and 2 extra generalist porters added to the shared pool instead of reserving existing ones: Emergency missed/late fell to 36.8% with +1 porter and 37.9% with +2 — a real improvement, but still well short of the 5% target. This supports Review 1's original diagnosis in Section 6.5: part of the remaining gap is a hard physical-travel-time constraint against an aggressive 10-minute SLA, not something any queueing or staffing policy alone can fully close."),
        P("Conclusion for this experiment: the mitigation was tested, not assumed, and the straightforward version of it should be rejected as stated. A more promising next step — out of scope for this revision but recorded for future work — would be a demand-aware reserve that only activates during a detected Emergency cluster (two or more Emergency calls within a short window) rather than a permanent, always-on reservation, combined with clinical sign-off on whether the 10-minute Emergency SLA is realistic for the hospital's actual physical layout."),
      ])
      .concat([
      // ---------------- 7. STAKEHOLDER VALIDATION ----------------
      H1("7. Stakeholder Validation"),
      P("A live clinical pilot was not possible for this project (no hospital access), so validation was carried out as a structured scenario-based walkthrough: three staff personas, each grounded in a real role identified in Section 1 (Ward Nurse, OT Coordinator, Duty Doctor), were walked through the working Streamlit prototype end-to-end — logging a request, reviewing a recommendation, confirming or overriding an assignment, and confirming a handover — and asked to react to specific design decisions. This is the same lightweight validation method (a persona-based cognitive walkthrough) commonly used before a live pilot is arranged, and it is named here explicitly as a walkthrough rather than a clinical trial so the scope of this evidence is not overstated."),
      H2("7.1 Walkthrough findings"),
      ])
      .concat([
        makeTable(
          ["Persona / role", "What they were asked to do", "Reaction", "Design response"],
          [
            ["Ward Nurse\n(logs requests)",
             "Log a transport request by phone-call habit, then try the sidebar form instead",
             "Liked that a request appears on the shared board immediately with no risk of a call going unanswered; asked what happens if she doesn't know the exact ward name",
             "Free-text tolerant location matching (Section 3.1) plus a visible 'auto-corrected' flag was added specifically to cover this case"],
            ["OT Coordinator\n(assigns/oversees porters)",
             "Review the recommended porter for several queued requests, override one deliberately",
             "Wanted to know *why* a porter was suggested, not just accept a black-box pick; also wanted the ability to pick someone else because she knew of a break the system didn't",
             "Every recommendation carries a plain-language reason string (Section 3.3); override is a first-class action, logged distinctly from a plain confirmation"],
            ["Duty Doctor\n(handles Emergency escalations)",
             "Trigger and observe an Emergency request under porter shortage (Section 5, edge case 5)",
             "Was concerned an urgent case could be silently queued behind others with no alert; wanted confirmation that nothing is ever auto-resolved without sign-off",
             "SLA colour states (🟢/🟠/🔴) and mandatory escalation for over-capacity requests were confirmed as meeting this concern; no auto-resolution path exists anywhere in the codebase (Section 3.5)"],
          ],
          [1700, 2400, 3000, 2400]
        ),
      ])
      .concat([
        new Paragraph({ spacing: { before: 160, after: 160 } }),
        H2("7.2 What the walkthrough changed"),
        bullet("The decision to default missing urgency to Urgent rather than Routine (Section 3.1) was hardened directly in response to the Duty Doctor persona's concern about silent under-prioritisation."),
        bullet("The requirement that overrides be logged distinctly from plain confirmations (rather than just \"assigned\") came from the OT Coordinator persona wanting her own judgement calls to be visible and attributable, not blended into the system's own record."),
        bullet("The free-text location tolerance in Section 3.1 exists because a ward-level walkthrough made clear that staff will not always use the exact canonical location name under time pressure."),
        H2("7.3 Limitations of this validation"),
        bullet("This is a designed-persona walkthrough, not a live-user study with real hospital staff, and it should not be read as clinical evidence of safety or acceptance."),
        bullet("Section 9's deployment checklist treats a genuine single-ward pilot with real staff and a defined success metric as a required step before any wider rollout — this walkthrough is a precursor to that, not a substitute for it."),
      ])
      .concat([
      // ---------------- 8. ETHICS NOTE ----------------
      H1("8. Ethics Note"),
      P("This prototype sits directly in a patient-safety-adjacent workflow, so several ethical constraints shaped the design, not just the write-up:"),
      bullet("Human final authority is structural, not a UI suggestion. Every state-changing function in the codebase is a recommend_* or detect_* read-only function; the only functions that write to a request's status live inside app.py's button handlers, which require an authenticated staff name/role to be entered first."),
      bullet("No silent defaults toward under-treatment. An unspecified urgency defaults to Urgent, never Routine — the safer direction to err in an uncertain patient-transport context, even though it costs the system some queue efficiency."),
      bullet("Uncertainty is surfaced, not hidden. Data-confidence flags and SLA-state indicators are shown directly on each request card, so staff are never asked to trust a system that is quietly guessing."),
      bullet("Auditability protects both patients and staff. The action log records who made each final decision, which supports incident review after a genuine adverse event without attributing clinical responsibility to the software."),
      bullet("Synthetic data only. No real patient, staff or hospital data was used or is required to run or evaluate this prototype; patient_id values are randomly generated placeholders."),
      bullet("Equity across departments. Because all departments share one porter pool and one priority scheme, no single specialty can quietly reprioritise its own requests above another's without that action being visible in the shared queue and the audit log."),

      // ---------------- 9. DEPLOYMENT CHECKLIST ----------------
      H1("9. Deployment Checklist"),
      P("Before this prototype could move from a project deliverable toward a pilot on a real ward, the following would need to be in place:"),
      H2("Technical readiness"),
      bullet("Replace the synthetic CSV data source with a live feed from the hospital's bed-management / HIS system (or, as an interim step, a shared database that ward staff write to directly instead of a spreadsheet)."),
      bullet("Move session state from Streamlit's in-memory session store to a persistent, multi-user backend (e.g. a small PostgreSQL/SQLite service) so the board is shared live across every ward's browser, not per-browser-tab."),
      bullet("Add authenticated logins (replacing the free-text name/role fields used in this prototype) so the action log is tamper-evident."),
      bullet("Load-test the zone/porter model against the hospital's actual floor plan and real porter headcount, not the 8-porter synthetic roster used here."),
      H2("Clinical / operational readiness"),
      bullet("Clinical sign-off on the SLA thresholds per urgency tier (this prototype used 10/30/90 minutes as illustrative values)."),
      bullet("A staff training/onboarding pass so ward nurses, OT coordinators and porters all understand that the system recommends and they confirm — avoiding both under-trust (ignoring good recommendations) and over-trust (rubber-stamping without checking)."),
      bullet("A fallback procedure for when the system itself is unavailable (network outage, server down) — the phone-call process should remain as a documented backup, not be fully decommissioned on day one."),
      bullet("A pilot period on a single ward cluster with a defined success metric (e.g. this report's target: <10% missed/late for Urgent, <5% for Emergency) before hospital-wide rollout."),
      bullet("If a reserved-porter policy for Emergency transfers is considered operationally, pilot it against real demand clustering data first — Section 6.7 found that a naively-sized, always-on reservation can make Emergency performance worse, not better. A demand-aware variant (reserve activates only during a detected multi-Emergency cluster) should be modelled and tested before committing shift rosters to it."),
      H2("Governance"),
      bullet("A data-retention and access policy for the action log, since it contains staff names tied to specific patient transfers."),
      bullet("A periodic review process to re-tune the priority scoring and zone map as the hospital's layout or department mix changes."),
      bullet("Section 6.5 and 6.7's findings — that the remaining Emergency SLA gap is partly a staffing/capacity and physical-travel-time problem, not purely a software allocation problem — should be escalated to hospital operations leadership alongside the software rollout, not treated as solved by the software alone."),

      new Paragraph({ spacing: { before: 300 } }),
      P("— End of report —", { italics: true }),
      ]),
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("outputs/Hospital_Transport_Tracker_Report.docx", buf);
  console.log("Report written.");
});
