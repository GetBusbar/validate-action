"""Targeted action argument tests; no Docker daemon or downloaded image required."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ActionArguments(unittest.TestCase):
    def run_action(self, names='', version='latest', config='config.yaml', providers='', status=0):
        action = Path(os.environ.get('ACTION_UNDER_TEST', ROOT / 'action.yml'))
        script = '\n'.join(line[8:] for line in action.read_text().split('      run: |\n', 1)[1].splitlines())
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'docker').write_text('#!/usr/bin/env python3\nimport json, os, sys\nwith open(os.environ["CALLS"], "a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\nif sys.argv[1] == "run": print("::error::validator-sentinel")\nsys.exit(int(os.environ.get("RUN_STATUS", "0")) if sys.argv[1] == "run" else 0)\n')
            (directory / 'docker').chmod(0o755)
            (directory / 'EXPANDED').touch()
            env = dict(os.environ, PATH=tmp + os.pathsep + os.environ['PATH'],
                       CALLS=str(directory / 'calls'), INPUT_CONFIG=config,
                       INPUT_PROVIDERS=providers, INPUT_VERSION=version, RUN_STATUS=str(status),
                       INPUT_SECRET_ENV=names, GITHUB_WORKSPACE=tmp)
            result = subprocess.run(['bash', '-c', script], cwd=tmp, env=env, text=True, capture_output=True)
            calls = [json.loads(line) for line in (directory / 'calls').read_text().splitlines()] if (directory / 'calls').exists() else []
            return result, calls

    def test_names_forwarded_without_values(self):
        result, calls = self.run_action('ONE,TWO\nTHREE\tFOUR')
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ['ONE', 'TWO', 'THREE', 'FOUR']:
            self.assertIn(name, calls[-1])

    def test_validator_output_is_fenced(self):
        result, _ = self.run_action()
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        fence = next(line for line in lines if line.startswith('::stop-commands::'))
        token = fence.removeprefix('::stop-commands::')
        self.assertTrue(token)
        self.assertEqual(lines[-1], '::' + token + '::')
        self.assertLess(lines.index(fence), lines.index('::error::validator-sentinel'))
        self.assertLess(lines.index('::error::validator-sentinel'), len(lines) - 1)

    def test_custom_catalog_and_failure_propagation(self):
        result, calls = self.run_action(providers='catalog with spaces.yaml', status=17)
        self.assertEqual(result.returncode, 17)
        self.assertIn('BUSBAR_PROVIDERS=catalog with spaces.yaml', calls[-1])
        self.assertEqual(calls[-1][-1], '--validate')

    def test_empty_names_leave_catalog_default(self):
        result, calls = self.run_action()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(arg.startswith('BUSBAR_PROVIDERS=') for arg in calls[-1]))
        self.assertEqual(calls[-1].count('-e'), 1)

    def test_invalid_names_rejected_before_docker(self):
        for name in ['*', 'KEY=value', 'BUSBAR_CONFIG', 'BUSBAR_PROVIDERS', '9KEY']:
            with self.subTest(name=name):
                result, calls = self.run_action(name)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])

    def test_invalid_tag_rejected_before_docker(self):
        result, calls = self.run_action(version='latest\n::error::injected')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_config_remains_one_argument_and_cannot_inject_log_commands(self):
        config = 'file with spaces\n::error::injected'
        result, calls = self.run_action(config=config)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('BUSBAR_CONFIG=' + config, calls[-1])
        self.assertNotIn('\n::error::injected', result.stdout)


if __name__ == '__main__':
    unittest.main()
