# Licensing: Decision Needed

**Current state:** the repository is public, but `LICENSE` says *proprietary, all rights reserved*. That
works for showing your work. It does not answer the first question a client asks: *what do we get to
keep?* Pick one model before the first engagement, and put it in both the statement of work and the
repository.

| Model | Client gets | You keep | Fits |
|---|---|---|---|
| **A. Perpetual licence to the rebranded copy** (recommended) | A perpetual, non-exclusive, non-transferable licence to use and modify the copy made for them (`make init SLUG=<client>`), inside their organisation | The template, and the right to reuse it with other clients | Assessments and jumpstarts, where the client runs the result themselves |
| **B. Work-for-hire on deliverables, template licensed** | Ownership of engagement-specific deliverables (their waves, policies, reports) plus a licence to the template code embedded in them | The template and all generic improvements | Clients whose procurement insists on owning deliverables |
| **C. Open-source core plus paid services** | Everything, under an OSI licence (Apache-2.0) | Reputation and support revenue; competitors can use the code | Building an audience and inbound leads |
| **D. Status quo (proprietary, view only)** | Nothing to keep without a separate agreement | Everything | Portfolio only, with no client deployments |

**Recommendation:** A, with B as the fallback for procurement teams that require ownership. Keep the
public repository's `LICENSE` as it is (view only), and grant client rights through the statement of
work. Have a lawyer review the licence-grant clause before the first contract. This page is a decision
aid, not legal advice.

Questions to settle in the statement of work:
- Who owns improvements made during the engagement? (Suggested: generic improvements flow back to the
  template; client-specific ones stay with the client.)
- Can the client hand the copy to a third-party operator (an MSP)?
- Support and updates after delivery: included for N months, or a separate retainer?
