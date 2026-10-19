# Measured validation

## Result

**Passed on 2026-10-19 in an isolated instructor sandbox.** Snowflake version **10.37.102**, Business Critical edition, X-Small dedicated warehouse. Runtime scope: the synthetic workshop, not production readiness or a customer-comprehension study. Account identifiers and raw query evidence remain private.

Initial execution used `ELEVEN_PRODUCER_LAB`. It exposed defects that were repaired before a separate fresh-namespace rehearsal. **The clean rehearsal completed at 15:40:48 UTC with `passed=true` and `cleanup_ok=true`.** It installed the corrected setup and all exercise scripts, passed all 19 assertions and both live-trigger phases, and stopped scheduled work. Private `test-results/` JSON retains per-script execution evidence. A final shutdown hardening change (skip an absent optional DT schema and filter task history by each task name) was separately executed successfully after that rehearsal.

## Measured component results

| Component | Observed result |
|---|---|
| Setup and fixtures | 11 dependencies; one writer row; 3 requests; 302 source rows |
| Two-producer warm-up | WAIT, WAIT, COMMITTED, NOOP; 2 published rows; sum 30; 1 completion |
| Named deterministic scenarios | 19 assertions passed; zero failed assertions |
| Three-day output | 111 history versions, 101 current entities, 6 business completions |
| Independent oracle | Zero missing/extra historical rows; 101 inventory entities; total day count 302 |
| Actual stream triggering | Ten-parent graph completed with one missing parent and zero Jan 9 completions; P11 released two Jan 9 completions |
| Final live output | 111 history versions, 101 current entities, 8 total completions |
| Dynamic-table comparison | INCREMENTAL; 101 rows / 11 eligible; zero row differences; source mutation changed prepared eligible total to 12 while frozen remained 11; repair restored 11 |
| Optional DMFs | NULL_COUNT=0 and DUPLICATE_COUNT=0; both expectations not violated on direct evaluation |
| Original sandbox shutdown | Four tasks suspended; DT suspended; DMF schedule empty; no executing tasks observed |
| Offline checks | 15 structural checks and 5 harness safety/result-format tests passed |

## Defects discovered and corrected

- The dependency generator referenced `PRODUCER` without defining the projection alias. Added the alias.
- The original READINESS view's nested correlated subquery created successfully but failed when queried from RUN_STAGE. Replaced it with distinct successful receipt/file sets and explicit joins.
- During development, a CTE with SELECT INTO in the row oracle failed compilation. Moved it inside an outer SELECT INTO.
- The new preflight initially passed CURRENT_ROLE() directly into IDENTIFIER in SHOW GRANTS; changed to a session variable after a compilation failure.
- An optional-object cleanup probe showed `IF EXISTS` does not skip an absent parent schema. Shutdown now checks for DT_LAB before issuing the optional DT suspension.
- The new rehearsal harness initially assumed CLI results were always nested. Single-statement JSON is flat; normalization and offline regression coverage now handle both forms. This failure occurred before object creation.

The earlier review's suspected line breaks inside SQL identifiers were a web-fetch formatting artifact, not a repository defect.

## Still not validated

- Scheduled watchdog recurrence (its procedure was exercised), sustained concurrency, stress throughput, retry after evidence-logging failure or stream-staleness recovery.
- Production least-privilege ownership: rehearsal used an administrative sandbox role. Preflight does not certify a customer's role hierarchy.
- Recurring DMF measurements, cost at production scale, or notification delivery. Direct expectation evaluation is not evidence of scheduled delivery; no notification integration is installed.
- Deleted-source entities, corrected same-day versions, backfills, complex calendars and every possible quality-failure branch.
- Customer transformations, source-tool semantic parity, visual draw.io rendering or measured learner comprehension.
- Full Guardian toolchain or comprehensive security certification. Offline structural tests and focused runtime tests are not substitutes.

## Evidence handling and reruns

`tests/rehearse.py` records each script's stdout/stderr, execution timestamp, assertion outcomes and cleanup status in ignored local JSON. It requires an exact expected account name and refuses existing database or warehouse names. Keep failed-run evidence. Never paste raw records, account/user/role details or query IDs into public issues.

Use [TESTING.md](TESTING.md) and [HANDS_ON.md](HANDS_ON.md) to reproduce. The public document reports sanitized outcomes; private evidence identifies the exact validation namespace and execution. Changes to executable SQL require another fresh rehearsal before updating the pass claim.
