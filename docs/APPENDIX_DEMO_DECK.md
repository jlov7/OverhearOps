---
title: OverhearOps – 2‑Slide Demo & Talk Track
paginate: true
theme: default
marp: true
---

<!-- _class: lead -->
# OverhearOps  
### Listen‑first agent for engineering threads

**The story (one line):**  
When a Teams thread starts looping on a flaky CI failure, OverhearOps quietly **listens**, spins up a **micro‑team**, explores **2–3 plans** in parallel, and proposes a **traceable, safe, replayable** fix.

**What you’ll see**
- **Teams‑style thread (CI flake or Security alert)** → *Suggest Plans*  
- **Plan A/B/C** with confidence & cost ribbons  
- **Winner** chosen by judge + **uncertainty gate**  
- **Dry‑run PR diff & Jira summary** (no real writes)
- **Mode/Provider + plan count cues** in the run summary

**Why this is new**
- *Overhearing* paradigm (listen‑first, intervene only when helpful)  
- **AgentInit‑style** team initialisation (diversity + expertise)  
- **Multi‑branch execution** (offline replay + LangGraph checkpoints)
- **Provider modes** (offline fixtures now; replay/live ready)

**Live path (60s)**
1. Play the CI flake or Security alert thread  
2. Click **Suggest Plans**  
3. Show diff, Jira summary  
4. Open **Trace & Action‑graph**  
5. Show **Reproduce** command

---

# Governance, Safety & Enterprise Value

**Trust by design**
- **Traceability:** OpenTelemetry spans → **Action‑graph** (who did what, when)  
- **Reproducibility:** **Replay hash**; deterministic run with seed + determinism test  
- **Safety:** **Coordinator+Guard** blocks prompt‑injection categories  
- **Abstain policy:** Ships only when confidence clears threshold
- **Provider transparency:** Mode + provider surfaced in Governance

**Enterprise fit**
- **Teams‑compatible** message shape (`chatMessage`)  
- **Adaptive‑Card‑like** UI (≤ v1.5 features)  
- **Adapter seam:** demo ↔︎ Graph ↔︎ Agents Playground  
- **Observability backends:** local Jaeger, or LangSmith/Langfuse via OTEL

**What to measure next**
- Trigger precision/recall on threads  
- Invocation correctness (from action‑graph)  
- Outcome quality (patch applies; tests pass)  
- Safety ASR on mini‑suite = **0**  
- Cost/latency vs. branch width (≤ 3)
 - Offline vs live fidelity (fixture drift)

---

## 60‑second talk track

**Builder’s opener (10s).**
“I kept seeing Teams threads re‑litigate the same fixes. I wanted an agent that **listens first**, then only joins when it can genuinely reduce toil.”

**What it does (15s).**
“OverhearOps watches a Teams‑shaped stream, composes a small micro‑team tailored to the thread, explores two or three fix plans in parallel, then uses a judge and an uncertainty gate to decide whether to act. It only proposes a **dry‑run** PR and a **clear Jira**—and today it runs on **offline fixtures** so it’s safe and deterministic.”

**Why you can trust it (20s).**
“Every step is **traceable** with OpenTelemetry and rendered as an **action‑graph**. You can **replay** a run with a seed to get the same timeline and verdict. A **Coordinator+Guard** safety layer screens for prompt‑injection and tool misuse. If confidence is low, it **abstains**.”

**So what for the enterprise (15s).**
“This is a reusable pattern: *listen → weigh → work → write*. It slots into Teams, respects Adaptive Card constraints, and routes traces to whichever observability stack you already use. The result is fewer noisy threads, faster triage, and audit‑ready artefacts clients can trust.”

---
```
OverhearOps flow
 ┌──────────┐   ┌──────────────┐   ┌────────┐   ┌──────────┐   ┌─────────┐
 │ Teams‑like│→ │ Overhear/     │→ │ Plan A │→  │ Execute   │→  │ Judge + │
 │  thread   │  │ intent filter │   │ Plan B │   │ (dry‑run) │   │ Uncertainty
 └──────────┘   └──────────────┘   │ Plan C │   └──────────┘   │   Gate  │
                                    └────────┘                  └─────────┘
                                         │                           │
                                         └────────►  Ship (if confident)
                                                         │
                                   OTEL spans → Action‑graph & Replay hash
```

---

## Demo smoke checklist

- **Threads available:** `/threads` lists `ci_flake` and `security_alert`
- **Run summary cues:** Mode/Provider badges + plans executed count visible
- **Safety summary:** Allowed/Blocked status with categories rendered
- **Replay determinism:** `uv run pytest tests/test_determinism.py::test_determinism_offline -v`
- **Governance modal:** Trace IDs + replay hash present

## Q&A crib sheet (quick answers)

* **Is it safe to run?**
  Yes—demo mode only uses synthetic data and produces **dry‑run** artefacts. The safety layer blocks risky patterns and we log attempts.

* **What if it’s wrong?**
  It can **abstain**. Plans are proposals with confidence bands; humans approve.

* **How do we integrate with real Teams?**
  There’s an **adapter seam**. Switch to Graph when consent is granted. Until then, use **Agents Playground** to preview Adaptive Cards.

* **How do we govern this in production?**
  Every run is **traceable** (OTEL), **replayable** (seed/hash), and **auditable** (action‑graph + artefacts). We can enforce policy gates before any writes.

* **What’s the cost/latency profile?**
  Kept in check by small branch width (≤3), **SLM for classification**, and streaming. Costs are surfaced per plan as a ribbon.

---

## “If something goes wrong” fallback (15‑second recovery)

* Show the **action‑graph JSON** and **replay hash** on disk (`runs/<id>`).
* Open **Jaeger** to prove spans are emitted.
* Flip to **playground mode** and paste the **Plan Card** into Agents Playground.
* Narrate the abstain policy and safety banner.
