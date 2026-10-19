# Workshop: wait, check, publish, recover

## Start here

**Goal:** understand how eleven independent producers can safely feed a two-job pipeline without rebuilding an entire custom orchestration platform.

Read sections 1-7 in order. No login or code execution is required. Diagrams render on GitHub; the surrounding numbered descriptions also work in plain Markdown readers. SQL is optional and changes only an explicitly installed sandbox. Expected examples below are not captured execution results.

For editable boxes and connectors, open [architecture.drawio](architecture.drawio) in draw.io. It contains current and proposed pages. Mermaid diagrams below are the text-source alternative, not automatically synchronized with that file.

**Vocabulary:** a *producer* prepares an input; a *parent* must finish before dependent work; a *child* waits for its parents; a *business date* identifies the day being processed; a *source version* identifies that day's agreed inputs; a *receipt* records successful completion; *idempotent* means repeating a completed request does not count it twice.

## 1. Current pattern: a separate orchestration service

This is a generic architectural pattern, not a description of a named organization.

```mermaid
flowchart TD
  subgraph control [External control service]
    schedule["Scheduler"] --> dispatcher["Dispatcher polls required parents"]
    registry["Relational tables: job definitions and dependencies"] -.-> dispatcher
    state["Relational tables: run statuses and parameters"] -.-> dispatcher
    dispatcher --> executor["Workflow runtime"]
  end
  subgraph warehouse [Data warehouse]
    inputs["Eleven producer outputs"] --> inventory["Inventory procedure"]
    inventory --> prepare["Prepare candidate result"] --> checks["Quality checks defined by the application"]
    checks --> history["Publish historical and current records"]
  end
  executor --> inventory
  history -. "Report execution outcome" .-> state
```

**Question:** Why is this difficult to migrate? **What happens:** the dependency map, runtime and business data are managed in different places. **Example:** a completed job status may refer to the wrong day or to partial data. **Interpretation:** replacing the scheduler does not remove the need for a trustworthy completion contract. **Decision:** identify which parts are scheduling and which are business rules before replacing anything.

## 2. Proposed placement: Snowflake owns the running order

```mermaid
flowchart TD
  subgraph upstream [Independent producers]
    parents["P01 through P11: prepare complete inputs"]
  end
  subgraph snowflake [Snowflake]
    subgraph controls [Application control tables]
      requirements["DEPENDENCIES: required-input checklist"]
      events["PRODUCER_EVENTS: completion receipts"]
      receipts["RECEIPTS: durably captured arrivals"]
      requests["REQUESTS and FILE_MANIFEST: expected dates and file readiness"]
      done["COMPLETIONS: business work committed"]
      quality["QUALITY_RESULTS and FAILURES: evidence"]
    end
    subgraph tasks [Native task definitions]
      bookmark["1. Stream notices new receipts"] --> capture["2. CAPTURE_ROOT saves arrivals"]
      capture --> first["3. INVENTORY_TASK checks readiness and snapshots input"]
      first --> second["4. PUBLISH_TASK checks and publishes history"]
      watchdog["5. WATCHDOG_TASK checks deadlines and retries pending work"]
    end
    subgraph data [Business data and monitoring]
      source["SOURCE_ENTITIES: synthetic input"] --> candidate["CANDIDATES: versioned prepared result"]
      candidate --> target["HISTORY and CURRENT_ENTITIES"]
      target -.-> dmf["Optional DMFs and expectations"]
    end
    events --> bookmark
    capture -.-> receipts
    requirements -.-> first
    receipts -.-> first
    requests -.-> first
    first -.-> candidate
    second -.-> target
    second -.-> done
    second -.-> quality
    watchdog -. "Same procedures, durable pending dates" .-> first
  end
  parents --> events
```

**Running order is not readiness.** `AFTER` expresses which task runs next. `DEPENDENCIES` expresses which independent producers' data is required. The table is a design choice; a single coordinated graph may not need a duplicate dependency map. One graph has one root scheduling model and shares ownership/database/schema. Do not join independent schedules merely to avoid a small table.

The eleven producer jobs are simulated by inserting completion receipts, not by creating eleven artificial scheduled tasks. P01/P02 directly feed inventory; P03-P11 feed publication. The sample waits for all eleven before inventory as a conservative policy. Making inventory start earlier requires a job-specific readiness gate and new tests.

## 3. Walk through one business day

1. **Register expected work.** REQUESTS states which date/version should complete, its deadline and expected quality totals. Without expected work, a producer that never emits a receipt is invisible to an event-only system.
2. **Receive completion receipts.** Producers report success only after the relevant output is complete. Native producers should commit output and receipt together. External producers need a trustworthy equivalent signal. Synthetic fixtures deliberately separate these to exercise orchestration.
3. **Capture arrivals.** The append-only stream tracks inserted receipts. CAPTURE_EVENTS inserts them into RECEIPTS and commits. The stream is a bookmark, not another permanent copy of the records.
4. **Check readiness.** Match every required producer, date, version and watermark; verify the named required file. Duplicates count as one producer. Success with zero changed rows can still be valid.
5. **Snapshot and validate input.** Inventory builds CANDIDATES once for this request, checks it and records its own successful work atomically. Publication uses that same version, not a new source read.
6. **Publish safely.** Validate the candidate again, calculate changed entities, close old history versions and add new ones. Check final history invariants while holding the writer lock. Commit history and publication receipt together.
7. **Recover and monitor.** A consumed stream does not mean business work completed. REQUESTS minus COMPLETIONS remains the durable to-do list. The watchdog can recover without waiting for another event.

**Question:** Ten parents have finished; what should happen? **Example:** the missing parent P11 arrives later. **Expected result:** WAIT first, then processing after the last valid receipt and file readiness. **Interpretation:** a green capture task can coexist with unfinished business work. **Decision:** define readiness by job/date/version, not table modification time.

## 4. Quality is a separate gate

```mermaid
flowchart TD
  ready["Inputs are ready"] --> snapshot["Freeze the candidate version"]
  snapshot --> checks{"Keys, volume and business total pass?"}
  checks -->|Yes| inventory["Commit inventory and its receipt"]
  inventory --> candidate{"Candidate still passes?"}
  candidate -->|Yes| writes["Expire old history and insert changes"]
  writes --> final{"History invariants pass under lock?"}
  final -->|Yes| commit["Commit history and publication receipt"]
  checks -->|No| stop["Rollback active transaction and record failure"]
  candidate -->|No| stop
  final -->|No| stop
  commit -.-> monitoring["Asynchronous DMFs watch published data"]
```

| Check | Location | Sample acceptance rule | Failure action |
|---|---|---|---|
| Missing entity IDs or derived status | RUN_STAGE candidate gate | Zero | Roll back this job and raise an error |
| Duplicate entity IDs | RUN_STAGE candidate gate | Zero | Do not silently choose a survivor |
| Candidate volume | REQUESTS + RUN_STAGE | Exactly 100 or 101 for fixtures | Stop; real thresholds must be business-approved |
| Eligible total | REQUESTS + RUN_STAGE | 0 on day 1; 11 later | Stop on mismatch |
| Multiple current versions / bad or overlapping intervals | Publish transaction | Zero | Roll back history and publication receipt |
| Missing/duplicate published IDs | Optional DMFs + expectations | VALUE = 0 | Record violations; not an automatic task blocker |

**Question:** All parents succeeded but input has duplicate IDs. **What happens:** readiness passes, quality rejects the batch. **Expected evidence:** a failed QUALITY_RESULTS row and no completion for the failed job. **Interpretation:** missing or errored critical checks are not passes. **Decision:** agree which rules stop, warn, or quarantine; this sample stops rather than publishing a partial result.

DMFs measure quality; expectations define acceptable values. Scheduled monitoring is asynchronous. A pipeline must explicitly evaluate a current check if it needs synchronous blocking. The optional monitor watches only current entities; applying duplicate-ID monitoring to all SCD2 history would flag intentional historical versions.

## 5. Failure and recovery without double counting

**Question:** What if publication fails after closing old versions? **What happens:** the publisher rolls back its transaction. Inventory remains committed because it is a separate job. **Expected result:** last good history remains visible; no publication receipt exists. **Interpretation:** the whole pipeline is not one transaction. **Decision:** recover the failed date/version; do not advance the business date during retry.

The lock is a real UPDATE to a pre-existing writer row, not an unenforced primary-key declaration. Completion is checked after taking the lock. Candidate/control-table writes must be restricted to cooperating writers in production. The procedures intentionally avoid nested outer transactions holding the same lock while calling independently committing jobs.

**Stream exercise:** plain SELECT does not advance the stream. A consuming INSERT does, even if it is only recording a test count or filters rows out. The test reads counts into variables, then writes assertions from those variables. Injected capture rollback must leave all ten unconsumed events available.

**Watchdog exercise:** capture all events, then fail publication. The stream may be empty while work remains unfinished. Fix the problem and run the watchdog: it checks durable requests and receipts, not just new events. Automatic task retries complement this behavior; they do not replace idempotency or recovery after a fresh invocation.

## 6. Dummy data and expected results

| Business day | Synthetic change | Expected history after publication |
|---|---|---|
| Day 1: Jan 6, 2025 | Entities 1-100; none eligible | 100 versions, 100 current |
| Day 2: Jan 7, 2025 | Entities 1-10 become eligible; add eligible entity 101 | 111 versions, 101 current |
| Day 3: Jan 8, 2025 | No changes | Still 111 versions, 101 current |

**Question:** Should another run add another historical row? **What happens:** completed job/date/version returns NOOP. **Expected result:** entity counters are 3 for 1-100 and 2 for 101; six job receipts for the three days. **Interpretation:** history changes only when the business value changes. **Decision:** define correction, deletion and historical-rebuild policy separately; those are deliberately rejected or out of scope here.

These numbers describe the generated fixture, not a customer's data. See [test instructions](TESTING.md). This generic implementation has not yet been runtime-validated in Snowflake.

## 7. Choose a bounded pilot

| Decision | Record the agreed rule / owner |
|---|---|
| All eleven before inventory, or only its two direct parents? | |
| What proves complete source and file delivery? | |
| Who controls the immutable candidate version? | |
| Which quality rules stop versus warn? | |
| Who handles late data and failed checks? | |
| How are corrected versions and backfills approved? | |
| Which matched input snapshots prove parity with the old process? | |
| Who approves cutover and rollback? | |

Dynamic tables can replace suitable preparation queries, but they do not automatically define a business-date contract or make refresh and publication one atomic transaction. Compare one real transformation before choosing that alternative. This repository does not deploy a dynamic-table variant.

## Optional technical appendix

Follow the root README for exact script order and safety controls. All tasks are suspended at installation. No account profile is included. Setup is not idempotent: do not rerun against an existing installation. Reading this workbook never executes SQL.

Monitor task history by exact task/database/schema and run identity. Inspect both business COMPLETIONS and task history: a task returning WAIT is successful orchestration, not a published batch. Keep stream consumption within retention; independent consumers need independent streams. No external email/webhook is configured.

Official sources: [task graphs](https://docs.snowflake.com/en/user-guide/tasks-graphs), [triggered tasks](https://docs.snowflake.com/en/user-guide/tasks-triggered), [streams](https://docs.snowflake.com/en/user-guide/streams-intro), [DMFs](https://docs.snowflake.com/en/user-guide/data-quality-working), [expectations](https://docs.snowflake.com/en/user-guide/data-quality-expectations).