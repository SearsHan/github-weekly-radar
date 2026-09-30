import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from promote_data import promote
from validate_data import validate


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads((ROOT / 'site/data/latest.json').read_text())
        current = datetime.now(timezone.utc)
        iso = current.isocalendar()
        self.payload['updated_at'] = current.isoformat()
        self.payload['period'] = f'{iso.year}-W{iso.week:02d}'
        self.payload['selection']['fetched_at'] = current.isoformat()
        self.packet = {'selection': copy.deepcopy(self.payload['selection']),
                       'analyzed_count': self.payload['analyzed_count'], 'projects': []}
        for item in self.payload['items']:
            source = copy.deepcopy(item)
            source['readme'] = '这里是用于验证发布事务边界的完整原文证据。' * 20
            if item['install']:
                source['readme'] += '\n' + item['install_source_excerpt']
            self.packet['projects'].append(source)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / 'latest.json'
        self.target.write_bytes(b'previous successful online data\n')
        self.before = self.target.read_bytes()

    def attempt(self, payload=None, packet=None):
        folder = Path(self.temp.name)
        (folder / 'candidate.json').write_text(json.dumps(payload or self.payload))
        (folder / 'sources.json').write_text(json.dumps(packet or self.packet))
        promote(folder / 'candidate.json', folder / 'sources.json', self.target)

    def reject(self, payload=None, packet=None):
        with self.assertRaises((ValueError, KeyError, TypeError)):
            self.attempt(payload, packet)
        self.assertEqual(self.target.read_bytes(), self.before)

    def test_complete_batch_is_published(self):
        self.attempt()
        self.assertEqual(json.loads(self.target.read_text()), self.payload)

    def test_ninth_success_tenth_failure_preserves_previous_bytes(self):
        self.payload['items'][-1]['summary'] = 'An English description of the project.'
        self.reject()

    def test_partial_batch_and_duplicate_repo_are_rejected(self):
        partial = copy.deepcopy(self.payload)
        partial['items'].pop()
        self.reject(partial)
        duplicate = copy.deepcopy(self.payload)
        duplicate['items'][-1]['repo'] = duplicate['items'][0]['repo']
        self.reject(duplicate)

    def test_missing_or_english_displayed_fields_are_rejected(self):
        for field in ['problem', 'why_context', 'why_now', 'recommendation_reason',
                      'core_features', 'audience', 'use_cases', 'difficulty', 'category']:
            with self.subTest(field=field):
                damaged = copy.deepcopy(self.payload)
                del damaged['items'][4][field]
                self.reject(damaged)
        for field in ['problem', 'core_features', 'audience', 'use_cases']:
            with self.subTest(field=field):
                damaged = copy.deepcopy(self.payload)
                damaged['items'][4][field] = ['Only English text'] if isinstance(damaged['items'][4][field], list) else 'Only English text'
                self.reject(damaged)

    def test_chinese_wrapper_cannot_hide_placeholder(self):
        self.payload['items'][0]['summary'] += '自动中文分析暂时不可用；官方描述为：example'
        self.reject()

    def test_unread_readme_and_fabricated_install_are_rejected(self):
        incomplete = copy.deepcopy(self.packet)
        incomplete['projects'][-1]['readme'] = ''
        self.reject(packet=incomplete)
        command = next(x for x in self.payload['items'] if x['install'])
        command['install'] = 'pip install fabricated-package'
        command['install_source_excerpt'] = command['install']
        self.reject()

    def test_stale_source_and_changed_metadata_are_rejected(self):
        stale = copy.deepcopy(self.packet)
        stale['selection']['fetched_at'] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        candidate = copy.deepcopy(self.payload)
        candidate['selection'] = stale['selection']
        self.reject(candidate, stale)
        self.payload['items'][0]['stars'] += 1
        self.reject()

    def test_failure_during_atomic_replace_leaves_previous_file(self):
        with patch('promote_data.os.replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.attempt()
        self.assertEqual(self.target.read_bytes(), self.before)
        self.assertEqual(list(self.target.parent.glob('.latest-*')), [])

    def test_cloud_workflow_gates_commit_deployment_and_restore(self):
        paths = list((ROOT / '.github/workflows').glob('*.yml'))
        self.assertEqual([p.name for p in paths], ['daily-radar.yml'])
        workflow = paths[0].read_text()
        for forbidden in ['models.github.ai', 'models: read', 'git push --force']:
            self.assertNotIn(forbidden, workflow)
        self.assertIn("cron: '15 1 * * *'", workflow)
        self.assertIn('needs: prepare', workflow)
        self.assertIn('python scripts/verify_pages.py', workflow)
        self.assertLess(workflow.index('Require ten complete Chinese projects'), workflow.index('git commit'))
        self.assertIn('test "$current" = "$EXPECTED_COMMIT"', workflow)


if __name__ == '__main__':
    unittest.main()
