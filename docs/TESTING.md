# Validation and evidence

## Status

Measured sandbox results and remaining limits are recorded in [VALIDATION.md](VALIDATION.md). Offline checks alone do not validate Snowflake syntax, transactions, permissions, scheduler timing or monitor execution.

Install `05_tests.sql` after setup with tasks suspended; it defines test procedures without running them. Run `05_run_tests.sql` once, or call its five named scenarios one at a time in order. They share a progressive fixture, so they are individually callable but not independently resettable. The definitions are rerunnable; calls and fixtures are not. An unexpected assertion stops the run. Intentional failures accept only expected custom exception codes. Never use an outer transaction around calls that own their transactions.

## Included deterministic scenarios

- No receipts; ten of eleven; duplicate receipts; wrong date/version; incomplete watermark; failed producer.
- Plain SELECT leaves stream offset unchanged; injected capture rollback preserves receipts; committed capture consumes them.
- Required file incomplete; zero-row successful producer accepted.
- Duplicate candidate keys block business writes; correction permits retry.
- Failure after history expiration rolls back publication without rolling back the previously successful inventory job.
- Recovery from durable pending work when the stream is already empty.
- Three dates, changed/new/unchanged entities, replay, counters and completion counts.
- Empty capture is harmless.
- Exact expected historical rows in both directions, including flags and interval endpoints; inventory cardinality and sum.

The five scenarios contribute 5, 2, 3, 3 and 6 assertions: **19 total**. One failed duplicate-key QUALITY_RESULTS row is an expected injected condition, not a failed test. See [the checkpoints](HANDS_ON.md#4-run-five-failure-oriented-scenarios).

## Live-trigger acceptance

Run sections of `06_live_trigger.sql` sequentially. Record task history with `SCHEDULED_FROM=TRIGGER`; do not use manual EXECUTE TASK as evidence of event triggering. Confirm ten-parent WAIT, last-parent release, two new business completions, and no duplicate current versions. Trigger timing is asynchronous (default minimum interval is 30 seconds), not an immediate delivery guarantee.

The optional watchdog task is installed but not resumed automatically. Its procedure is called by deterministic tests; that is not a measured recurring-schedule test. DMF installation/evaluation is also separate.

## Before production

- Add source deletion policy, invalid-reference checks, null/volume/business-total failure scenarios, alternate-version rejection tests and silent-producer alert tests. The included row-level oracle covers the synthetic fixture, not customer parity.
- Test simultaneous trigger/watchdog/manual invocations, procedure failure during evidence logging, retries after partial graph completion, and permissions under the intended owner role.
- Confirm no direct table writer can bypass the immutable-candidate and writer-lock contracts.
- Validate DMF privileges, expectations, schedule, cost and notification delivery.
- Define data retention, stream staleness recovery and event pruning; verify load/throughput, latency and recovery objectives.
- Capture environment/version/test time without publishing account IDs, query IDs or private data in public issues.

## Repeatable instructor rehearsal

`tests/rehearse.py` requires `--execute`, an existing connection, an expected account name and two fresh namespace identifiers. It refuses existing names, runs the actual SQL files with only those namespace substitutions, validates deterministic and live checkpoints, and saves stdout/stderr plus assertion results in private ignored JSON. `--include-dmfs` is an explicit opt-in. See [the exact command](HANDS_ON.md#instructor-automation).

Every run retains its evidence, including failures. Successful results are never synthesized from specifications. The final status requires cleanup success as well as business assertions. Do not rerun the same namespace after an interrupted installation; inspect evidence and choose a fresh namespace.

Export evidence only after reviewing it. `test-results/` is ignored by Git. Run `07_stop.sql` and confirm no executions remain active; it also disables optional DMF scheduling and suspends the optional DT. Never post private JSON, account IDs, query IDs or user/role grants in public issues.