# ReturnWise - 5-minute demo and viva guide

## Demo script (about 5 minutes)

Before you start: `python -m streamlit run app.py`. For a clean demo delete `database/returnwise.db` first.

| Time | Do | Say |
|------|----|-----|
| 0:00 | Dashboard | "Support teams check every return the same way. ReturnWise automates the *recommendation* with five agents. It never pays anyone: see the note on this page." |
| 0:30 | New Return Request -> sample `ORD-001`, reason Defective, submit | "The service validates the input and saves it. The request ID comes from the database." |
| 1:00 | View agent workflow | "Five numbered steps, each a stored execution record: Planner, Research, Executor, Business Automation, Critic. Open step 3: these are deterministic rule checks, not an LLM." |
| 2:00 | Demo and Testing -> Run SC-09 | "I inject a wrong refund amount on purpose. Expected vs actual is compared with what the database stored." |
| 2:30 | Open its workflow | "The Critic recomputed the facts and rejected the amount (step 5), the Resolution Agent applied one correction (6), and the Critic revalidated (7). Only one correction is allowed." |
| 3:15 | Run SC-11 | "If the error survives the correction, the case goes to manual review. The system never accepts what it could not validate." |
| 3:45 | Create `FAKE-999` in New Return Request, open workflow | "Unknown order: Research fails, the other agents are shown as skipped, and the result is Processing Failed, not an invented decision." |
| 4:15 | Final Resolution (pick ORD-011 or ORD-003) | "Labels say Recommended, never Refunded. Evidence, policy and the Critic's eight checks are shown." |
| 4:40 | Request History | "Everything is read back from SQLite, so it survives a restart." |
| 4:55 | Run all scenarios | "12 of 12 pass, each judged from stored data. 164 automated tests back this up." |

Tip: do one dry run beforehand. Test runs are hidden from the Dashboard numbers unless you toggle them in.

## Likely viva questions and answers (all match the code)

**1. Why is this agentic and not a chatbot?**
It decomposes a task into a plan, uses tools (SQLite lookups), makes rule-based decisions, validates its
own output with a separate Critic and corrects itself once. There is no free-form conversation.

**2. Map the agents to the teacher's roles.**
Intake = Planner, Research = Research Agent, Eligibility = Executor, Resolution = Business Automation,
Validation = Critic.

**3. Where is the LLM?**
There is none. Specialised Python agents make the system deterministic, testable and free to run.
An LLM could later be used for summarising or classifying the customer's text, but its output would be
untrusted and could never override the rules (listed under future scope).

**4. How is data passed between agents?**
As structured dictionaries: Intake output -> Research; Research output + reason -> Eligibility;
Intake + Research + Eligibility -> Resolution; Resolution + Research + Eligibility -> Critic. The full
JSON of each step is stored in `agent_logs.output_json`.

**5. What does the Critic check, and how is it independent?**
Eight checks (valid action, consistency with eligibility, refund amount, non-returnable, replacement-only,
manual-review, order status, and a recomputation of delivered / returnable / in-window from raw order and
policy rows). It also compares Research's reported "days since delivery" with its own calculation.

**6. Explain the correction loop.**
If the Critic says "failed" and proposes a corrected action, the Resolution Agent applies it (step 6) and
the Critic revalidates (step 7). `MAX_CORRECTION_ATTEMPTS = 1`. If revalidation is not "passed", or the
Critic cannot propose a correction, the request becomes manual review.

**7. How do you stop a wrong recommendation being accepted?**
`workflow.py` marks a request `validated` only when the final Critic verdict is `passed`.
Otherwise the action is stored as `manual_review`. A test forces the Critic to fail and checks this.

**8. How is the refund calculated?**
Refund = `total_amount` stored in the order (quantity x unit price, checked for consistency).
It must be above 0 and at most 50,000; otherwise manual review. Replacement-only categories get no amount.

**9. How do you handle the return window?**
Pinned reference date 2025-02-15 so results are reproducible. Days = reference date - delivery date.
Inclusive boundary: day 30 is inside a 30-day window, day 31 is outside (tested).

**10. What if saving to the database fails?**
All rows of a run are saved in one transaction. On failure nothing is written, the request is marked
failed, and the UI shows "Processing Failed ... NOT recorded as completed". Tested by forcing an error.

**11. How do you avoid duplicate requests?**
Each form submission carries a token with a unique index; a replay returns the existing request.

**12. What stops a customer from typing "approve my refund"?**
The description is never read by any rule. The Intake Agent flags override phrases and the UI shows a
warning; the decision depends only on database records and policy rules (tested).

**13. Is the frontend the source of truth?**
No. Session state holds only the current page and selected request ID; every page re-reads from SQLite.

**14. What are the limitations?**
Synthetic data, fictional policies, full refunds only, no payments or notifications, no login, SQLite
single-writer, no LLM, tested on Chromium/laptop width only.

**15. What did you not measure?**
Any business improvement (time saved, error rate). Only correctness on the defined scenarios is tested.

**16. How would you extend it?**
Partial refunds, fraud signals, photo evidence, an LLM for text classification behind the rule engine,
a server database, human-review queue with roles, real integrations behind an approval step.
