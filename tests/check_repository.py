"""Offline structural checks, not a SQL compiler or runtime test."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class RepositoryChecks(unittest.TestCase):
    def test_editable_diagrams(self):
        pages = ET.parse(ROOT / 'docs/architecture.drawio').getroot().findall('diagram')
        self.assertEqual(len(pages), 2)
        for page in pages:
            cells = page.findall('./mxGraphModel/root/mxCell')
            identifiers = {cell.get('id') for cell in cells}
            self.assertEqual(len(cells), len(identifiers))
            for cell in cells:
                if cell.get('edge') == '1':
                    self.assertIn(cell.get('source'), identifiers)
                    self.assertIn(cell.get('target'), identifiers)
                    self.assertEqual(cell.find('mxGeometry').get('relative'), '1')

    def test_scripts_exist(self):
        required = {
            '00_preflight.sql', '00_setup.sql', '00_warmup.sql', '01_fixtures.sql',
            '02_procedures.sql', '03_tasks.sql', '04_optional_dmfs.sql',
            '05_tests.sql', '05_run_tests.sql', '06_live_trigger.sql', '07_stop.sql',
            '08_dynamic_table_alternative.sql',
        }
        self.assertTrue(required.issubset({path.name for path in (ROOT / 'sql').glob('*.sql')}))

    def test_setup_does_not_replace_existing_database(self):
        setup = (ROOT / 'sql/00_setup.sql').read_text()
        self.assertIn('CREATE DATABASE ELEVEN_PRODUCER_LAB;', setup)
        self.assertNotIn('CREATE OR REPLACE', setup)
        self.assertIn('ROWCOUNT => 11', setup)

    def test_no_automatic_task_start(self):
        for name in ['00_setup.sql', '01_fixtures.sql', '02_procedures.sql', '03_tasks.sql']:
            self.assertNotRegex((ROOT / 'sql' / name).read_text(), r'ALTER TASK\s+\w+\s+RESUME')

    def test_trigger_has_no_schedule(self):
        tasks = (ROOT / 'sql/03_tasks.sql').read_text()
        root = tasks.split('CREATE TASK INVENTORY_TASK')[0]
        self.assertIn('SYSTEM$STREAM_HAS_DATA', root)
        self.assertNotIn('SCHEDULE=', root)
        self.assertIn('AFTER CAPTURE_ROOT', tasks)
        self.assertIn('AFTER INVENTORY_TASK', tasks)

    def test_transaction_and_quality_safeguards(self):
        procedures = (ROOT / 'sql/02_procedures.sql').read_text()
        for token in ['ROLLBACK', 'WRITER_LOCK', 'DUPLICATE_KEYS', 'HISTORY_INVARIANTS',
                      'EXPECTED_ELIGIBLE', 'EXCEPTION WHEN OTHER', "RETURN 'NOOP'"]:
            self.assertIn(token, procedures)
        drain = procedures.split('CREATE PROCEDURE DRAIN_STAGE')[1].split('CREATE PROCEDURE WATCHDOG')[0]
        self.assertNotIn('BEGIN TRANSACTION;', drain)

    def test_balanced_procedure_delimiters(self):
        for path in (ROOT / 'sql').glob('*.sql'):
            self.assertEqual(path.read_text().count('$$') % 2, 0, path.name)

    def test_no_external_resources_or_private_paths(self):
        for folder in ['sql', 'docs']:
            for path in (ROOT / folder).rglob('*'):
                if path.is_file():
                    text = path.read_text()
                    self.assertNotRegex(text, r'/Users/|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY')
                    self.assertNotRegex(text, r'https://[^\s)"<>]+\.slack\.com|snowflakecomputing\.com')

    def test_guided_exercises_and_named_scenarios(self):
        tests = (ROOT / 'sql/05_tests.sql').read_text()
        runner = (ROOT / 'sql/05_run_tests.sql').read_text()
        for name in ['TEST_01_RECEIPTS_AND_STREAM', 'TEST_02_READINESS_CONTRACT',
                     'TEST_03_QUALITY_AND_DAY_ONE', 'TEST_04_ROLLBACK_AND_RECOVERY',
                     'TEST_05_REPLAY_AND_PARITY']:
            self.assertIn('PROCEDURE ' + name + '()', tests)
            self.assertIn('CALL ' + name + '();', runner)
        self.assertIn('MINUS SELECT * FROM HISTORY', tests)
        self.assertIn('19 passes', runner)
        for name in ['WORKBOOK.md', 'HANDS_ON.md', 'FACILITATOR.md', 'VALIDATION.md']:
            self.assertTrue((ROOT / 'docs' / name).is_file())

    def test_stop_covers_optional_compute(self):
        stop = (ROOT / 'sql/07_stop.sql').read_text()
        self.assertIn("SET DATA_METRIC_SCHEDULE = ''", stop)
        self.assertIn('PREPARED SUSPEND', stop)
        self.assertLess(stop.index('CAPTURE_ROOT SUSPEND'), stop.index('INVENTORY_TASK SUSPEND'))

    def test_readiness_is_deduplicated_join(self):
        setup = (ROOT / 'sql/00_setup.sql').read_text()
        self.assertIn('AS PRODUCER', setup)
        self.assertIn('SELECT DISTINCT PRODUCER,PROCESS_DATE,SOURCE_VERSION', setup)
        self.assertIn('LEFT JOIN valid_receipts', setup)

    def test_rehearsal_is_explicit_and_guarded(self):
        runner = (ROOT / 'tests/rehearse.py').read_text()
        self.assertIn("'--execute'", runner)
        self.assertIn("'--expected-account'", runner)
        self.assertIn("'database does not exist'", runner)
        self.assertIn('finally:', runner)
        self.assertNotIn('shell=True', runner)
        self.assertIn("file('07_stop.sql')", runner)

    def test_python_syntax(self):
        import ast
        for path in (ROOT / 'tests').glob('*.py'):
            ast.parse(path.read_text(), filename=str(path))

    def test_local_markdown_links(self):
        import re
        documents = [ROOT / 'README.md', *(ROOT / 'docs').glob('*.md')]
        for path in documents:
            for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
                if '://' in target or target.startswith('#'):
                    continue
                self.assertTrue((path.parent / target.split('#')[0]).exists(), (path.name, target))

    def test_expected_counts_match_generator_math(self):
        history = {}
        counters = {}
        for day in range(3):
            for entity in range(1, 101 + (day > 0)):
                eligible = day > 0 and (entity <= 10 or entity == 101)
                counters[entity] = counters.get(entity, 0) + 1
                versions = history.setdefault(entity, [])
                if not versions or versions[-1] != eligible:
                    versions.append(eligible)
        self.assertEqual(sum(map(len, history.values())), 111)
        self.assertEqual(len(history), 101)
        self.assertEqual(counters[1], 3)
        self.assertEqual(counters[101], 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)