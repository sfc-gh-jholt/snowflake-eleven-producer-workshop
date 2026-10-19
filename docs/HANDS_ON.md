# Hands-on: predict, run, inspect, explain

**Duration:** approximately 150 minutes including design discussion. Basic SQL familiarity required. Use a new isolated sandbox and one worksheet session. All fixtures are synthetic. Read [preflight](../sql/00_preflight.sql) with your administrator before creating anything. Keep real account names, roles and query IDs private.

## Execution rules

Run in the order below, not filename sort order. Stop at the first unexpected error. Do not wrap scripts or scenario calls in a transaction: business procedures own their commits. Select complete procedure definitions including both `$$` delimiters in Snowsight. CLI users can run a reviewed file with `snow sql -c <approved-connection> --enable-templating NONE -f sql/<file.sql>`; a nonzero exit means stop.

The installer is deliberately not rerunnable. Never replace an existing database to reset the lab. Pick a new namespace consistently, or have an administrator review a deliberate teardown. Scenario procedures are individually callable but share state: run 1 through 5 once in order. Their definitions can be reinstalled without resetting the data.

## 1. Preflight and setup

Run `00_preflight.sql`. Before installation, both named-object SHOW queries should return no exact matching name. Review CREATE DATABASE / CREATE WAREHOUSE and task-owner EXECUTE TASK privileges, including inherited grants. Edition confirmation is a **manual administrator checkpoint**, not inferred from visible system functions. If optional monitor rights are unknown, skip DMFs.

Run `00_setup.sql`. Its final SELECTs should show **11 dependencies, 11 distinct producers, one writer-control row, and zero requests**. If names already exist, stop; do not continue into fixtures. No task exists yet.

## 2. Warm-up: two producers, one result

Run `00_warmup.sql` one section at a time. This uses a separate WARMUP schema. Predict each result before executing:

1. No receipts: `TRY_PUBLISH` returns **WAIT**.
2. Insert A twice: still **WAIT**, published rows **0**.
3. Insert B: **COMMITTED**.
4. Call again: **NOOP**; published rows **2**, total amount **30**, completion rows **1**.

Explain why two arrivals are not the same thing as two required producers. This deliberately simple single-session exercise is not a production-safe concurrent publisher. The main lab adds locking, source versions, data quality, historical publication and independent recovery.

## 3. Install the full pattern

Run `01_fixtures.sql`. The date summary must show **100/0, 101/11, 101/11** (row count / eligible count), totaling **302** input rows. READINESS has **three rows**, each with **11 missing parents** and **FILE_READY=TRUE**. They are not ready merely because the data is present.

Run `02_procedures.sql`. SHOW PROCEDURES returns four business procedures. Its smoke CALL returns **WAIT** and completion count **0**.

Run `03_tasks.sql`. SHOW TASKS returns **four rows, all suspended**. Completion count is still **0**. A task graph has been defined, not run.

## 4. Run five failure-oriented scenarios

Install `05_tests.sql`; it defines six procedures (assert helper plus five scenarios), and runs no scenario. Use `05_run_tests.sql` as the guided worksheet. Select one CALL and its checkpoint at a time.

| CALL | Cumulative passing assertions | Expected state afterward |
|---|---:|---|
| `TEST_01_RECEIPTS_AND_STREAM()` | 5 | Jan 6 has 1 missing parent; 10 durable receipts; 0 completions |
| `TEST_02_READINESS_CONTRACT()` | 7 | Jan 6 has 0 missing parents, file ready; 0 completions |
| `TEST_03_QUALITY_AND_DAY_ONE()` | 10 | 100 history, 100 current, 2 completions |
| `TEST_04_ROLLBACK_AND_RECOVERY()` | 13 | 111 history, 101 current, 4 completions; recovery required no new event |
| `TEST_05_REPLAY_AND_PARITY()` | 19 | 111 history, 101 current, 6 completions; exact historical rows verified |

At the end, TEST_RESULTS must have **19 rows, 19 true, 0 false**. READINESS has **three rows with MISSING_PARENTS=0 and FILE_READY=TRUE**. One failed DUPLICATE_KEYS quality row and the deliberately injected publication failure are expected; a failed assertion is not. The full-row comparison checks eligible flags and validity dates, not just aggregate counts. Inventory has 101 entities and 302 total day counts.

## 5. Prove actual triggering

Run `06_live_trigger.sql` **one numbered section at a time**. Do not use Run All or EXECUTE TASK.

- Sections 1-2 resume children before the root and insert ten receipts for Jan 9.
- Section 3: poll every 15 seconds, up to five minutes. Wait for the publish child to finish. The root must have a successful `SCHEDULED_FROM=TRIGGER` run; readiness must show **1 missing parent**, and Jan 9 must have **0 completions**. A skipped root with a false stream predicate can be normal; find the successful run for this batch.
- Only then run section 4 to insert P11.
- Section 5: poll again. Require a later successful publish run and **2 Jan 9 completions**. Final totals: **111 history, 101 current, 8 completions**. The duplicate-current query must return **zero rows**.

If five minutes pass without the expected state, stop the exercise and inspect task errors. Do not declare a pass from submission or an older successful run. The watchdog remains suspended here to isolate the stream-trigger behavior.

## 6. Compare a dynamic-table preparation path

Run `08_dynamic_table_alternative.sql` after deterministic tests. It isolates Jan 7 in DT_LAB, declares INCREMENTAL preparation and compares all rows against the procedural candidate. Expected **101 rows, 11 eligible, zero bidirectional differences**.

After changing entity 11's input and refreshing: prepared has **12 eligible**, while FROZEN_CANDIDATE remains **11**. Repair and refresh returns prepared to **11**. The script suspends the DT before exiting. DOWNSTREAM on this standalone lab leaf is intentional: use manual refresh, not a recurring timed schedule.

This is a working alternative for preparation, **not a second complete publisher**. In a real hybrid, enforce date/version readiness and quality before freezing the prepared result, then retain the transactional publisher. A fresh DT result alone is not evidence that eleven external producers have completed one agreed business batch.

## 7. Optional monitoring

With edition and privileges confirmed, run `04_optional_dmfs.sql` once. The final evaluation returns **two expectations**, each **VALUE=0** and **EXPECTATION_VIOLATED=FALSE**. The script enables hourly serverless monitoring; proceed to shutdown afterward. A direct evaluation does not prove that the recurring schedule or notifications ran. This lab configures no notifications.

## 8. Stop and verify

Run `07_stop.sql` last, regardless of optional-path choices. Expect **four suspended tasks**, an **empty DATA_METRIC_SCHEDULE**, and a **suspended PREPARED DT if installed**. The in-flight query should show no EXECUTING rows; if a task was already running, wait and inspect again. DMF schedule changes can take ten minutes to propagate. Do not use UNSET to stop DMFs: it restores their default schedule.

The dedicated X-Small warehouse auto-suspends after 60 idle seconds. Objects and evidence are retained; stopping compute does not delete stored data. Do not continue querying on that warehouse if you want it to remain idle.

## Troubleshooting

| Symptom | Inspect and act |
|---|---|
| Database/warehouse already exists | Stop. Do not use OR REPLACE. Change all namespace references or choose a reviewed fresh rehearsal namespace. |
| Missing EXECUTE TASK / warehouse privileges | Have the admin check the task **owner role**, not only the interactive user. Do not auto-grant privileges. |
| WAIT with eleven event rows | Check captured RECEIPTS, distinct producer, date, source version, status, watermark and file readiness. Raw event row count is not readiness. |
| WAIT_EARLIER_DATE | An earlier requested date has not published. Fix oldest work first; don't edit dates to bypass ordering. |
| Quality rejection | Inspect QUALITY_RESULTS and FAILURES. Repair the specific fixture before retrying the failed business stage. Do not change expected thresholds to hide a failure. |
| Empty stream, unfinished business batch | Inspect REQUESTS minus publication COMPLETIONS. The watchdog procedure can retry durable work; new events are not required. |
| Live trigger never fires | Check task states, root condition, stream contents, task owner and task history. Do not consume the stream with INSERT SELECT while investigating. |
| Test fails after rerunning | Scenarios mutate state. Test definitions are rerunnable; scenarios and fixtures are not reset scripts. |
| DMF capability/edition unavailable | Skip optional script 04; synchronous business gates still work. |
| DT differs from frozen result | During the controlled mutation this is expected. Compare the same immutable source version before judging parity. |

## Instructor automation

For a fresh end-to-end rehearsal, the opt-in runner uses an existing local CLI connection, exact account guard, isolated names, bounded trigger polling and private JSON evidence. It never creates credentials, grants privileges, or deletes a database. Run from the repository root:

```sh
python3 tests/rehearse.py --execute --connection APPROVED_CONNECTION \
  --expected-account APPROVED_ACCOUNT_NAME \
  --database ELEVEN_REHEARSAL_UNIQUE --warehouse ELEVEN_REHEARSAL_WH_UNIQUE
```

Add `--include-dmfs` only after approving edition, privileges and monitoring cost. Outputs go to ignored `test-results/`; never publish raw evidence. The runner stops schedules in a `finally` block. If cleanup reports an error, inspect and stop remaining work manually. Never treat a partial run as validation.
