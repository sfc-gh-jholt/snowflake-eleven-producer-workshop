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
        self.assertEqual(len(list((ROOT / 'sql').glob('*.sql'))), 8)

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