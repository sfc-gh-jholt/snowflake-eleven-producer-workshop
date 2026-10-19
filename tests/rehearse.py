"""Explicit opt-in Snowflake rehearsal. Never runs on import; no credentials stored.

Uses the installed Snowflake CLI, stops on errors, records private evidence, and
suspends work in finally. Each file is a separate autocommit session: never wrap
transaction-owning procedures in an outer transaction.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def identifier(value):
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,100}", value):
        raise argparse.ArgumentTypeError("Use an uppercase unquoted SQL identifier")
    return value


def normalize_results(output):
    """Snowflake CLI returns flat rows for one statement, nested sets for many."""
    return output[-1] if output and isinstance(output[0], list) else output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', required=True)
    parser.add_argument('--connection', required=True)
    parser.add_argument('--expected-account', required=True)
    parser.add_argument('--database', type=identifier, required=True)
    parser.add_argument('--warehouse', type=identifier, required=True)
    parser.add_argument('--include-dmfs', action='store_true')
    args = parser.parse_args()
    evidence_dir = ROOT / 'test-results'
    evidence_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    evidence_path = evidence_dir / f'rehearsal-{timestamp}.json'
    report = {'started_at': timestamp, 'database': args.database,
              'warehouse': args.warehouse, 'steps': [], 'passed': False}
    created = False
    cleanup_ok = False

    def persist():
        evidence_path.write_text(json.dumps(report, indent=2) + '\n')

    def run(label, sql):
        sql = sql.replace('ELEVEN_PRODUCER_LAB', args.database)
        sql = sql.replace('ELEVEN_PRODUCER_WH', args.warehouse)
        result = subprocess.run(
            ['snow', 'sql', '-c', args.connection, '--enable-templating', 'NONE',
             '--format', 'JSON', '--stdin'], input=sql, text=True,
            capture_output=True, timeout=240, check=False)
        entry = {'label': label, 'sql_sha256': hashlib.sha256(sql.encode()).hexdigest(),
                 'at': datetime.now(timezone.utc).isoformat(),
                 'exit_code': result.returncode, 'stdout': result.stdout,
                 'stderr': result.stderr}
        report['steps'].append(entry)
        persist()
        if result.returncode:
            raise RuntimeError(f'{label} failed: {result.stderr}')
        print(f'PASS {label}', flush=True)
        return json.loads(result.stdout)

    def query(label, sql):
        output = run(label, sql)
        return normalize_results(output)

    def file(name):
        return run(name, (ROOT / 'sql' / name).read_text())

    def require(condition, label):
        report['steps'].append({'label': label, 'assertion': bool(condition)})
        persist()
        if not condition:
            raise AssertionError(label)
        print(f'PASS {label}', flush=True)

    def await_completions(expected, timeout=300):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rows = query('live completion poll',
                "SELECT COUNT(*) AS N FROM ELEVEN_PRODUCER_LAB.DEMO.COMPLETIONS "
                "WHERE PROCESS_DATE='2025-01-09'")
            if rows[0]['N'] == expected:
                return
            time.sleep(15)
        raise TimeoutError('Live publication did not complete within five minutes')

    try:
        rows = query('account guard', 'SELECT CURRENT_ACCOUNT_NAME() AS ACCOUNT_NAME, CURRENT_VERSION() AS VERSION')
        require(rows[0]['ACCOUNT_NAME'] == args.expected_account, 'connected account matches explicit approval')
        report['account'] = rows[0]
        # SHOW LIKE treats underscores as wildcards; test exact names in returned rows.
        databases = query('database collision guard', f"SHOW DATABASES LIKE '{args.database}'")
        warehouses = query('warehouse collision guard', f"SHOW WAREHOUSES LIKE '{args.warehouse}'")
        require(not any(row['name'] == args.database for row in databases), 'database does not exist')
        require(not any(row['name'] == args.warehouse for row in warehouses), 'warehouse does not exist')
        file('00_preflight.sql')
        # The guard above established these names were absent. Partial setup is retained.
        created = True
        for name in ['00_setup.sql', '00_warmup.sql', '01_fixtures.sql',
                     '02_procedures.sql', '03_tasks.sql', '05_tests.sql', '05_run_tests.sql']:
            output = file(name)
            if name == '00_warmup.sql':
                outcomes = [row['TRY_PUBLISH'] for result in output for row in result
                            if 'TRY_PUBLISH' in row]
                require(outcomes == ['WAIT', 'WAIT', 'COMMITTED', 'NOOP'],
                        'warmup receipt and replay outcomes')
                totals = [row for result in output for row in result if 'TOTAL' in row]
                require(totals == [{'PUBLISHED_ROWS': 2, 'TOTAL': 30}], 'warmup output totals')
        rows = query('deterministic result assertion',
            'SELECT COUNT(*) AS N,COUNT_IF(PASSED) AS PASSES FROM ELEVEN_PRODUCER_LAB.DEMO.TEST_RESULTS')
        require(rows[0] == {'N': 19, 'PASSES': 19}, '19 of 19 assertions passed')
        if args.include_dmfs:
            output = file('04_optional_dmfs.sql')
            metrics = output[-1]
            require(len(metrics) == 2 and all(row['VALUE'] == 0 and
                    str(row['EXPECTATION_VIOLATED']).lower() == 'false' for row in metrics),
                    'two DMF expectations passed')
        output = file('08_dynamic_table_alternative.sql')
        parity = [row for result in output for row in result if 'DIFFERENCES' in row]
        require(parity == [{'DIFFERENCES': 0}], 'dynamic-table exact row parity')
        checkpoints = [row for result in output for row in result if 'ELIGIBLE_COUNT' in row]
        require([row['ELIGIBLE_COUNT'] for row in checkpoints] == [11, 12, 11, 11],
                'DT refresh changes prepared data but not frozen candidate')
        live = (ROOT / 'sql/06_live_trigger.sql').read_text()
        pre_release, post_release = live.split('-- 4. Last parent arrives.', 1)
        run('live sections 1-3', pre_release)
        # Wait for a completed publish-task run before checking ten-parent WAIT.
        deadline = time.monotonic() + 300
        history_sql = """SELECT NAME,STATE,SCHEDULED_FROM,ERROR_MESSAGE
FROM TABLE(SNOWFLAKE.INFORMATION_SCHEMA.TASK_HISTORY(
 TASK_NAME=>'PUBLISH_TASK',SCHEDULED_TIME_RANGE_START=>DATEADD('hour',-1,CURRENT_TIMESTAMP()),RESULT_LIMIT=>10000))
WHERE DATABASE_NAME='ELEVEN_PRODUCER_LAB' AND SCHEMA_NAME='DEMO'
ORDER BY SCHEDULED_TIME DESC"""
        while time.monotonic() < deadline:
            history = query('ten-parent graph poll', history_sql)
            if any(row['STATE'] == 'FAILED' for row in history):
                raise RuntimeError('Live task failed; inspect private history evidence')
            if any(row['STATE'] == 'SUCCEEDED' for row in history):
                break
            time.sleep(15)
        else:
            raise TimeoutError('Ten-parent graph did not finish in five minutes')
        rows = query('ten-parent checkpoint', """SELECT MISSING_PARENTS,FILE_READY,
(SELECT COUNT(*) FROM ELEVEN_PRODUCER_LAB.DEMO.COMPLETIONS WHERE PROCESS_DATE='2025-01-09') AS COMPLETIONS
FROM ELEVEN_PRODUCER_LAB.DEMO.READINESS WHERE PROCESS_DATE='2025-01-09'""")
        require(rows[0] == {'MISSING_PARENTS': 1, 'FILE_READY': True, 'COMPLETIONS': 0},
                'ten-parent WAIT observed before release')
        release, verification = post_release.split('-- 5. Wait', 1)
        release = '-- 4. Last parent arrives.' + release
        run('release P11', 'USE DATABASE ELEVEN_PRODUCER_LAB; USE SCHEMA DEMO; USE WAREHOUSE ELEVEN_PRODUCER_WH;\n' + release)
        await_completions(2)
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            history = query('final publish terminal-state poll', history_sql)
            if any(row['STATE'] == 'FAILED' for row in history):
                raise RuntimeError('Publish task failed after release')
            if sum(row['STATE'] == 'SUCCEEDED' for row in history) >= 2:
                break
            time.sleep(15)
        else:
            raise TimeoutError('Final publish task did not finish')
        run('live final checkpoints', 'USE DATABASE ELEVEN_PRODUCER_LAB; USE SCHEMA DEMO; USE WAREHOUSE ELEVEN_PRODUCER_WH;\n-- 5. Wait' + verification)
        root_history = query('real-trigger evidence', history_sql.replace("TASK_NAME=>'PUBLISH_TASK'", "TASK_NAME=>'CAPTURE_ROOT'"))
        require(sum(row['STATE'] == 'SUCCEEDED' and row['SCHEDULED_FROM'] == 'TRIGGER'
                    for row in root_history) >= 2, 'both root runs were real triggers')
        rows = query('final business counts', """SELECT
(SELECT COUNT(*) FROM ELEVEN_PRODUCER_LAB.DEMO.HISTORY) AS HISTORY_ROWS,
(SELECT COUNT(*) FROM ELEVEN_PRODUCER_LAB.DEMO.CURRENT_ENTITIES) AS CURRENT_ROWS,
(SELECT COUNT(*) FROM ELEVEN_PRODUCER_LAB.DEMO.COMPLETIONS) AS COMPLETIONS""")
        require(rows[0] == {'HISTORY_ROWS': 111, 'CURRENT_ROWS': 101, 'COMPLETIONS': 8},
                'final business counts match')
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        if created:
            try:
                stopped = file('07_stop.sql')
                require(not any(row.get('STATE') == 'EXECUTING' for row in stopped[-1]),
                        'no lab task execution remains in flight')
                schedules = [row for result in stopped for row in result
                             if row.get('key') == 'DATA_METRIC_SCHEDULE']
                require(len(schedules) == 1 and schedules[0]['value'] == '',
                        'DMF schedule is disabled')
                dynamic_tables = query('suspended DT evidence',
                    'SHOW DYNAMIC TABLES IN SCHEMA ELEVEN_PRODUCER_LAB.DT_LAB')
                require(all(row['scheduling_state'] == 'SUSPENDED' for row in dynamic_tables),
                        'all lab dynamic tables suspended')
                rows = query('suspended task evidence', 'SHOW TASKS IN SCHEMA ELEVEN_PRODUCER_LAB.DEMO')
                require(len(rows) == 4 and all(row['state'] == 'suspended' for row in rows),
                        'all four tasks suspended')
                cleanup_ok = True
            except Exception as cleanup_error:
                report['cleanup_error'] = str(cleanup_error)
                print(f'CLEANUP REQUIRES ATTENTION: {cleanup_error}', flush=True)
        report['cleanup_ok'] = cleanup_ok
        report['passed'] = report['passed'] and cleanup_ok
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        persist()
        print(f'Private evidence: {evidence_path}', flush=True)
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
