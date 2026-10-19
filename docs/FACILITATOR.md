# Facilitator guide: migrate the contract, not just the scheduler

## Audience and outcomes

For data engineers who can run SQL, but need not know streams, tasks or dynamic tables. Plan **150 minutes** with one instructor sandbox per group. An architect and an operations owner should attend the final exercise. The goal is not to memorize procedures: each participant should map a real workflow, explain its completion contract, demonstrate safe retry, and identify what stays outside Snowflake.

Before the session, rehearse on a fresh namespace, complete preflight with the account administrator, and keep private result evidence. Do not grant administrative privileges to attendees. Provide an approved lab role or use an instructor-led account. Optional DMFs require Enterprise Edition or higher and serverless monitoring costs. The core path does not.

## Run of show

| Minutes | Activity | Instructor cue / participant checkpoint |
|---|---|---|
| 0-10 | Outcomes and preflight | Ask what 'done' means today. Confirm empty namespace, owner privileges, and budget. |
| 10-25 | Setup and two-producer warm-up | Ask whether two A receipts replace B. Predict WAIT / WAIT / COMMITTED / NOOP before running. |
| 25-45 | Workbook sections 1-2 and migration mapping | Draw the customer's actual dependencies on paper. Eleven producers is not eleven sequential jobs. |
| 45-60 | Fixtures, procedures and suspended tasks | Show three business dates, 302 input rows, four suspended tasks. No business completions yet. |
| 60-85 | Five named scenarios | Select one CALL at a time. Pause on duplicate rejection and publish rollback. Expected cumulative passes: 5, 7, 10, 13, 19. |
| 85-100 | Actual stream-trigger exercise | Wait for the graph with ten producers. Require no publication before inserting P11. Show TRIGGER, not EXECUTE TASK. |
| 100-115 | Dynamic-table comparison; optional DMFs | DT result matches all 101 rows. Modify one source flag: prepared changes, frozen does not. DMF pass is not a commit gate. |
| 115-140 | Customer migration exercise and pilot agreement | Fill the migration worksheet; choose one bounded flow, parity criteria, owner, cutover and rollback. |
| 140-150 | Stop and teach-back | Suspend tasks, DT and DMF schedule. Participants explain why green task status is not business completion. |

Allow another 15-30 minutes for first-time account access. If time runs short, omit the optional DMFs rather than rushing the ten-parent checkpoint or cleanup. For a 90-minute overview, use instructor-led SQL and defer customer mapping to a separate session; do not call that a completed migration workshop.

## How to deliver the SQL

Use [HANDS_ON.md](HANDS_ON.md) as the participant screen. Keep the workbook open beside it. Never select the entire live-trigger file. During waits, explain stream bookmarks and ask participants to predict durable state rather than refreshing without a hypothesis.

For each exercise use: **predict, run, inspect, explain**. A mismatch stops the group. Capture the exact first error privately, inspect the relevant state, and use the troubleshooting section. Do not re-run the full fixtures or change an assertion to force a pass. Recovery of an interrupted test is instructor work; a new sandbox is the simplest reset.

## Discussion prompts and answer key

- Ten producers finished, but capture is green: is the business day published? **No. Check readiness and business completions.**
- The same receipt arrives twice: can it replace the missing producer? **No. Readiness uses distinct producer/date/version matches.**
- Inventory succeeded and publication failed: which work rolls back? **Publication only. Its history updates and completion receipt are one transaction.**
- The stream is empty: does that mean no work remains? **No. Requests without publication completions remain pending.**
- Why not convert everything to dynamic tables? **Use DTs for suitable declarative preparation; this sample also needs an explicit batch contract and atomic multi-target publication.**
- Does this replace Airflow or Control-M everywhere? **No. External execution, cross-platform orchestration and enterprise calendars may remain there.**

## Acceptance, not a satisfaction score

Ask each group to produce: a dependency list for its own workflow; a mapping for every node; the source-complete signal; three deliberately bad input cases; row-level parity criteria; and a named rollback decision owner. A successful teach-back requires participants to explain WAIT, failure, recovery and NOOP without reading the answer key.

A runtime pass proves the synthetic lab works in the tested environment. It does not prove customer comprehension, production throughput, security, or that their eleven transformations have been ported. Record anonymous learner feedback and revise confusing steps after the first customer session.
