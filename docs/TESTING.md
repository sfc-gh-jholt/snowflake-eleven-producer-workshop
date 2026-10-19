# Validation and evidence

## Status

The generic SQL is supplied for sandbox testing. **No Snowflake runtime pass count is claimed.** Local static checks do not validate Snowflake syntax, transactions, permissions, scheduler timing or monitor execution.

Run `05_tests.sql` once on a fresh setup with tasks suspended. It fails on the first incorrect assertion. Intentional failure tests accept only their expected custom exception codes; unrelated errors are not accepted as proof of safety. A client must stop on any unexpected error.

## Included deterministic scenarios

- No receipts; ten of eleven; duplicate receipts; wrong date/version; incomplete watermark; failed producer.
- Plain SELECT leaves stream offset unchanged; injected capture rollback preserves receipts; committed capture consumes them.
- Required file incomplete; zero-row successful producer accepted.
- Duplicate candidate keys block business writes; correction permits retry.
- Failure after history expiration rolls back publication without rolling back the previously successful inventory job.
- Recovery from durable pending work when the stream is already empty.
- Three dates, changed/new/unchanged entities, replay, counters and completion counts.
- Empty capture is harmless.

## Live-trigger acceptance

Run sections of `06_live_trigger.sql` sequentially. Record task history with `SCHEDULED_FROM=TRIGGER`; do not use manual EXECUTE TASK as evidence of event triggering. Confirm ten-parent WAIT, last-parent release, two new business completions, and no duplicate current versions. Trigger timing is asynchronous (default minimum interval is 30 seconds), not an immediate delivery guarantee.

The optional watchdog task is installed but not resumed automatically. Its procedure is called by deterministic tests; that is not a measured recurring-schedule test. DMF installation/evaluation is also separate.

## Before production

- Add independent row-level expected-result comparison, source deletion policy, invalid-reference checks, null/volume/business-total failure scenarios, alternate-version rejection tests and silent-producer alert tests.
- Test simultaneous trigger/watchdog/manual invocations, procedure failure during evidence logging, retries after partial graph completion, and permissions under the intended owner role.
- Confirm no direct table writer can bypass the immutable-candidate and writer-lock contracts.
- Validate DMF privileges, expectations, schedule, cost and notification delivery.
- Define data retention, stream staleness recovery and event pruning; verify load/throughput, latency and recovery objectives.
- Capture environment/version/test time without publishing account IDs, query IDs or private data in public issues.

Export local evidence only after reviewing it. `test-results/` is ignored by Git. Run `07_stop.sql` and check no executions remain active. Disable optional DMF schedules separately.