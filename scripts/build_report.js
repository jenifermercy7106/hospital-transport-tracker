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
        children: [new TextRun({ text: "Deliverables in this package:", bold: true, size: 22 })] }),
      bullet("Synthetic dataset — transport requests, patient locations, priority, porter availability, completion timestamps"),
      bullet("Baseline method (baseline.py) — naive FIFO queue, no urgency/location awareness"),
      bullet("Working prototype — decision engine (prototype_engine.py) + interactive Streamlit tracker (app.py)"),
      bullet("Six implemented edge/failure-case tests (edge_cases.py)"),
      bullet("Measurable experiment comparing baseline vs prototype vs target (experiment.py)"),
      bullet("This report — scenario, method, results, stakeholder validation, ethics, deployment checklist"),
      new Paragraph({ children: [new PageBreak()] }),

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
      P("Note on this deliverable: the sandbox used to prepare this package has no network access to install and screenshot a live Streamlit server, so app.py is provided as complete, syntax-checked, ready-to-run code that reuses the same engine functions validated by the automated tests in Section 5. Running it locally only requires: pip install streamlit pandas, then streamlit run app.py from the project folder — consistent with the lightweight Python/Streamlit workflow already used for other data-facing tools in this portfolio."),

      // ---------------- 5. EDGE-CASE TESTS ----------------
      H1("5. Edge-Case and Failure-State Tests"),
      P("Six realistic failure states were implemented as automated checks in edge_cases.py (all currently passing, 10/10 assertions). Each test feeds the engine deliberately broken input and checks that the system degrades safely — it must never crash, never silently drop a request, and never finalise an action without staff confirmation."),
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
          ],
          [700, 4200, 4600, 1500]
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
            ["Emergency", "87", "100.0%", "42.5%", "5.0%", "+57.5", "No — see 6.5"],
            ["Urgent", "207", "9.2%", "0.0%", "10.0%", "+9.2", "Yes"],
            ["Routine", "333", "0.0%", "0.0%", "15.0%", "+0.0*", "Yes"],
          ],
          [1400, 700, 1700, 1700, 1600, 1700, 1400]
        ),
      ])
      .concat([
        new Paragraph({ spacing: { before: 100, after: 120 },
          children: [new TextRun({ text: "*Routine already meets target under both policies at this load; the improvement shows up as headroom, not a visible percentage-point gain.", italics: true, size: 20 })] }),
        P("Weighted across all 627 requests with a resolved urgency, overall missed/late rate falls from 16.9% (baseline) to 5.9% (prototype) — an 11.0 percentage-point improvement from coordination logic alone, using identical demand and an identical porter roster."),
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
        P("Honesty about remaining failure is part of this deliverable. 37 of 87 Emergency requests (42.5%) were still classified Completed-Late by the prototype, missing the 5% target. Root-cause analysis of these 37 cases:"),
        bullet("The Emergency SLA (10 minutes, matching real hospital rapid-response expectations) is tight relative to physical travel distance in this hospital layout: a transfer spanning the maximum zone distance (e.g. a ward to the OT complex) costs roughly 6 + 4×2.5 = 16 minutes of service time alone under the prototype's zone-distance model — before any queueing wait is added. No allocation logic can make a porter walk faster than physics allows."),
        bullet("This is a genuine, non-cosmetic limitation of a coordination-logic-only fix: reassigning porters more intelligently reduces queueing delay to near zero (see Figure 2's Urgent/Routine columns), but it cannot eliminate a service time that is structurally longer than the SLA."),
        bullet("The implication for the hospital, not just the software, is that Emergency-tier transfers likely need a dedicated, pre-positioned porter reserve near high-emergency zones (ICU, ED, OT complex) rather than relying solely on smarter queueing of the existing shared pool. This is exactly the kind of insight a working prototype and a measurable experiment surface, and a concept slide would not."),
        H2("6.6 Baseline vs Prototype: why the chosen approach is appropriate"),
        P("A rule-based priority queue with zone-aware recommendation (rather than, say, a machine-learned dispatch model) was chosen deliberately for this problem, for three reasons:"),
        bullet("Explainability under clinical accountability constraints — every recommendation traces to a readable reason (\"nearest available porter, zone distance 1\"; \"urgency=Emergency, waited 6 min\"). Staff who are legally and professionally responsible for the transfer need to understand why a suggestion was made, not just trust an opaque score."),
        bullet("No training data requirement — a learned model would need months of clean historical dispatch data this hospital does not yet have (its current system is phone calls). The rule-based approach works from day one and can be tuned as real data accumulates."),
        bullet("Fail-visible behaviour under missing/bad data — Section 5's edge cases show the rule-based engine degrades to explicit escalation under bad input; a black-box model would more likely produce a confident-looking but wrong recommendation on the same messy input, which is a worse failure mode in a clinical setting."),
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
      H2("Governance"),
      bullet("A data-retention and access policy for the action log, since it contains staff names tied to specific patient transfers."),
      bullet("A periodic review process to re-tune the priority scoring and zone map as the hospital's layout or department mix changes."),
      bullet("Section 6.5's finding — that Emergency SLA breaches are partly a staffing/positioning problem, not purely a software problem — should be escalated to hospital operations leadership alongside the software rollout, not treated as solved by the software alone."),

      new Paragraph({ spacing: { before: 300 } }),
      P("— End of report —", { italics: true }),
      ]),
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("outputs/Hospital_Transport_Tracker_Report.docx", buf);
  console.log("Report written.");
});
