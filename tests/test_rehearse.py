"""Offline harness tests; no Snowflake connection is opened."""
import contextlib
import importlib.util
import io
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('rehearse', Path(__file__).with_name('rehearse.py'))
rehearse = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rehearse)


class HarnessTests(unittest.TestCase):
    def test_cli_result_shapes(self):
        rows = [{'N': 19}]
        self.assertEqual(rehearse.normalize_results(rows), rows)
        self.assertEqual(rehearse.normalize_results([[{'status': 'OK'}], rows]), rows)
        self.assertEqual(rehearse.normalize_results([]), [])

    def test_identifier_rejects_sql_and_shell_metacharacters(self):
        for value in ['x;DROP TABLE x', 'A B', 'A/B', '"A"', 'A$(id)', '', 'lowercase']:
            with self.assertRaises(Exception):
                rehearse.identifier(value)
        self.assertEqual(rehearse.identifier('LAB_123'), 'LAB_123')

    def test_execute_and_account_guards_required(self):
        with patch('sys.argv', ['rehearse.py']), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                rehearse.main()

    def test_wrong_account_stops_before_database_creation(self):
        from subprocess import CompletedProcess
        with tempfile.TemporaryDirectory() as directory:
            arguments = ['rehearse.py', '--execute', '--connection', 'test',
                         '--expected-account', 'EXPECTED', '--database', 'NEW_DB',
                         '--warehouse', 'NEW_WH']
            response = CompletedProcess([], 0, '[{"ACCOUNT_NAME":"WRONG","VERSION":"test"}]', '')
            with patch.object(rehearse, 'ROOT', Path(directory)), patch('sys.argv', arguments), \
                    patch.object(rehearse.subprocess, 'run', return_value=response) as invoke, \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(AssertionError):
                    rehearse.main()
                self.assertEqual(invoke.call_count, 1)
                self.assertNotIn('CREATE', invoke.call_args.kwargs['input'])

    def test_existing_database_stops_before_setup(self):
        from subprocess import CompletedProcess
        with tempfile.TemporaryDirectory() as directory:
            arguments = ['rehearse.py', '--execute', '--connection', 'test',
                         '--expected-account', 'EXPECTED', '--database', 'NEW_DB',
                         '--warehouse', 'NEW_WH']
            responses = [CompletedProcess([], 0, text, '') for text in [
                '[{"ACCOUNT_NAME":"EXPECTED","VERSION":"test"}]',
                '[{"name":"NEW_DB"}]', '[]']]
            with patch.object(rehearse, 'ROOT', Path(directory)), patch('sys.argv', arguments), \
                    patch.object(rehearse.subprocess, 'run', side_effect=responses) as invoke, \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(AssertionError):
                    rehearse.main()
                self.assertEqual(invoke.call_count, 3)
                self.assertTrue(all('CREATE' not in call.kwargs['input'] for call in invoke.call_args_list))


if __name__ == '__main__':
    unittest.main(verbosity=2)
