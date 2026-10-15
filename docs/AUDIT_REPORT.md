# ReturnWise - Audit and Verification Report

Baseline: the supplied v1.0 project, run fresh in this environment (Python 3.13.16, pytest, Streamlit 1.66):
**59 tests collected, 59 passed** before any change.
Final: **164 tests collected, 164 passed, 0 failed, 0 skipped** (`python -m pytest -q`, about 9 s),
also re-run from a fresh `git clone` simulation.

## 1. Confirmed issues in v1.0 (found by reading the code; the one marked * was also reproduced by running the original code)

| # | Issue | Where | Fix |
|---|-------|-------|-----|
| 1 | Saving the recommendation was wrapped in `try/except` that only logged; the workflow still returned `success: True` | `workflow.py` | One-transaction save; failure -> `success False`, request marked `failed`, UI says "NOT recorded as completed" |
| 2 | Logs, status and recommendation were written in separate transactions (partial results possible) | `workflow.py`, `repository.py` | `save_workflow_result()` writes all rows in one transaction with rollback |
| 3 | UI badge text "Refunded" although no refund is executed | `app.py` | Label set in `services/presentation.py`; test asserts no "refunded/payment completed" text on any page |
| 4 | Agent Timeline and Final Resolution read `last_workflow_result` from session state -> stale, empty after history selection or restart | `app.py` | Pages re-read the selected request from the database on every render |
| 5 | Only text summaries were stored; structured outputs, evidence, rule checks and the correction history were lost | `agent_logs` | `input_json` / `output_json` / `step_type` / `verdict` columns (backward-compatible migration) |
| 6 | No protection against double submit / rerun duplicates | `request_service.py` | `client_token` + unique index; duplicate returns the existing request |
| 7 | Demo "Run" only displayed the result; no expected-vs-actual; `force_bad` was never used, so the correction loop was never actually demonstrated | `app.py` | `demo_service.py`: 12 scenarios, checks against stored data, labelled fault injection |
| 8 | Early exit (unknown order / bad input) reported `reject`, `validation failed`, confidence "high" and showed no skipped agents | `workflow.py` | Outcome `failed` ("Processing Failed"), no invented recommendation, skipped agents stored |
| 9 * | Correctable case ended in manual review: for ineligible + wrong refund amount the Critic proposed `reject` **with** `corrected_amount=100.0`; the correction copied that amount; revalidation failed | `validation_agent.py`, `workflow.py` | Corrected amount now follows the corrected action (amount only for refund); regression test |
| 10 | Revalidation result `manual_review` was accepted with the corrected (non-manual) action | `workflow.py` | Only a final "passed" verdict yields a validated recommendation; otherwise action = manual review |
| 11 | Critic trusted the Eligibility Agent's conclusions (not independent) | `validation_agent.py` | Check 8 recomputes delivered / returnable / in-window from raw rows and compares the Research evidence |
| 12 | No data-integrity checks (total vs quantity x price, delivery vs order date, status vs dates); ambiguous data was silently processed | agents | `policies/rules.check_order_integrity` -> manual review |
| 13 | `MAX_REFUND_CAP` and other config constants were never used | `config.py` | Cap now enforced in Eligibility; the unused category/window constants were removed (the database policy table is the single source) |
| 14 | JSON policy note said wrong-item claims are accepted for any category; code rejects non-returnable categories | `return_policy.json` | Note corrected; test compares JSON and DB policies |
| 15 | Config advertised optional LLM settings that no code used (misleading) | `config.py` | Removed; README states no LLM is used |
| 16 | `tests/test_policy.py` tests helper functions defined inside the test file, not the real code | tests | Kept (still valid) and added real tests of `policies/rules.py` and the agents |
| 17 | Sample-order selector was inside a form so it could not fill the order field; Google Fonts `@import` needed internet | `app.py` | Callback-based selector; system font stack |
| 18 | Dashboard counted only "passed" actions and had no eligible / failed / correction metrics | `repository.py` | Metrics redefined (see docstring) and shown with tooltips |

Not changed: pinned reference date 2025-02-15 (documented, needed for reproducibility); seed data was
checked and found consistent (every order has a product and policy, totals equal quantity x price,
dates and statuses agree), so no seed values were changed.

## 2. Changed behaviour you should know about

* `tests/test_workflow.py::test_sc05_unknown_order_id` asserted that an unknown order produces a
  "reject" recommendation. It now asserts **Processing Failed with no recommendation**, because an order
  that was never found was never evaluated. This was a deliberate change of semantics, not a loosened check.
* A request that ends in manual review stores action `manual_review` even if an agent had proposed
  something else; the proposed action is mentioned in the explanation and kept in the timeline.

## 3. Agent-by-agent verification

| Agent | Verified by | Result |
|-------|-------------|--------|
| Intake | missing / blank / malformed order ID, bad reason, alias reason, override text, never invents order data | pass |
| Research | unknown order, missing policy, evidence content, inconsistent totals, boundary arithmetic | pass |
| Eligibility | refund = stored total (incl. qty 2), replacement-only, five ineligible cases name the failed rule, reason "other", data issues, refund cap | pass |
| Resolution | uses Eligibility output, never overrides "ineligible", handles empty permitted list, evidence lines, correction function | pass |
| Critic | 8 checks, wrong amount, negative amount, amount above total, wrong action, tampered evidence, approval of an expired order even when upstream agents agreed | pass |

## 4. Workflow and persistence verification

Automated: execution order 1-5 (and 1-7 with correction), output of each agent feeds the next
(checked through stored JSON), early stop with skipped agents saved, exactly one correction
(validation called twice at most), revalidation, manual review after failed correction, no approval
without a "passed" verdict, agent crash -> failed with no internal detail leaked, persistence failure ->
not success, full rollback of a partially failing save, duplicate token -> one request, customer
override text does not change the decision, determinism, migration of a v1.0 database file.

Mutation check (done in a scratch copy, then discarded): changing the window boundary (`<=` to `<`),
forcing the Critic to always pass, swallowing the persistence error, and allowing two corrections each
made at least one test fail.

## 5. What was verified how

| Area | Automated (pytest) | Browser (Chromium via Playwright, screenshots inspected) |
|------|--------------------|-----------------------------------------------------------|
| Navigation and active highlight | yes | yes |
| Form validation, request ID, duplicate protection | yes | validation error and successful submit seen |
| Agent timeline, correction loop, skipped agents | yes (text/logic) | seen: normal run, correction loop, failed run |
| Final resolution wording | yes | seen |
| History search / filter | yes (logic) | table seen; row-selection click **not** exercised in the browser |
| Dashboard numbers | yes | seen after demo run |
| Demo page pass/fail | yes | "Run all" seen, 12 of 12 passed |
| Visual quality, icons, colours | no | inspected at 1440x900 only |

Not verified: Windows execution (commands are standard but were not run on Windows), other browsers,
phone-sized layouts, very large databases.

## 6. Test inventory (164)

test_agents 38, test_workflow_extra 21, test_ui 17, test_workflow 17, test_policy 17,
test_database_extra 15, test_validation 14, test_demo_scenarios 14, test_database 11.

## 7. Manual browser checklist (not automatable here)

1. Click a row in the Dashboard or History table, then "Open agent workflow".
2. Resize the window to about 1280 px wide and confirm no horizontal page scroll.
3. Reload the browser tab, open Request History and re-open an old request: the same timeline appears.
4. Stop and restart `streamlit run`, repeat step 3.
