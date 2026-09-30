import copy
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from daily_update import analyze, build_candidate, load_cache, run, SCHEMA
from promote_data import check_sources


class DailyUpdateTests(unittest.TestCase):
    def setUp(self):
        self.original = json.loads((ROOT / 'site/data/latest.json').read_text())
        self.cache = {x['repo'].lower(): copy.deepcopy(x) for x in self.original['items']}
        self.packet = {'selection': copy.deepcopy(self.original['selection']),
                       'analyzed_count': self.original['analyzed_count'], 'projects': []}
        self.packet['selection']['fetched_at'] = datetime.now(timezone.utc).isoformat()
        for item in self.original['items']:
            self.packet['projects'].append({**copy.deepcopy(item), 'readme': None, 'description': '', 'topics': [], 'cached_item': copy.deepcopy(item)})

    def new_project(self, index=9):
        project = self.packet['projects'][index]
        item = self.cache.pop(project['repo'].lower())
        project['cached_item'] = None
        project['readme'] = '这是用于测试完整新项目介绍生成流程的原文。' * 20
        if item['install']:
            project['readme'] += '\n' + item['install_source_excerpt']
        return {f: copy.deepcopy(item.get(f)) for f in SCHEMA['properties']}

    def test_existing_projects_never_call_model_even_without_key(self):
        generator = Mock(side_effect=AssertionError('should not call model'))
        with patch.dict(os.environ, {}, clear=True):
            data, cache, generated = build_candidate(self.packet, self.cache, generator)
        self.assertEqual(generated, 0)
        generator.assert_not_called()
        for before, after in zip(self.original['items'], data['items']):
            self.assertEqual(before['summary'], after['summary'])
            self.assertEqual(before['readme_source'], after['readme_source'])
        self.assertEqual(len(cache['items']), 10)

    def test_only_new_project_is_generated_and_returning_project_is_cached(self):
        detail = self.new_project()
        generator = Mock(return_value=detail)
        data, registry, generated = build_candidate(self.packet, self.cache, generator)
        self.assertEqual(generated, 1)
        generator.assert_called_once()
        self.assertEqual(generator.call_args[0][0]['repo'], self.packet['projects'][-1]['repo'])
        returning = registry['items'][data['items'][-1]['repo'].lower()]
        # A repository that drops out remains in the durable cache.
        registry['items']['historical/tool'] = {**copy.deepcopy(returning), 'repo': 'historical/tool',
            'name': 'tool', 'github_url': 'https://github.com/historical/tool',
            'download_url': 'https://github.com/historical/tool/archive/refs/heads/main.zip',
            'clone': 'git clone https://github.com/historical/tool.git', 'release_url': None}
        registry['items']['historical/tool']['readme_source']['url'] = registry['items']['historical/tool']['readme_source']['url'].replace(returning['repo'], 'historical/tool')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cache.json'
            path.write_text(json.dumps(registry))
            self.assertIn('historical/tool', load_cache(self.original, path))

    def test_new_project_without_key_fails_before_any_publish(self):
        self.new_project()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'OPENAI_API_KEY'):
                build_candidate(self.packet, self.cache)

    def test_tenth_bad_analysis_preserves_previous_file(self):
        detail = self.new_project()
        detail['summary'] = 'English only'
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            latest = folder / 'latest.json'
            latest.write_text(json.dumps(self.original, ensure_ascii=False))
            before = latest.read_bytes()
            # Remove cached tenth entry also from the validated source latest,
            # by making the collector's new repository genuinely unseen.
            project = self.packet['projects'][-1]
            old_repo = project['repo']
            new_repo = 'new-owner/new-tool'
            project.update(repo=new_repo, name='new-tool', github_url=f'https://github.com/{new_repo}',
                           clone=f'git clone https://github.com/{new_repo}.git',
                           download_url=f'https://github.com/{new_repo}/archive/refs/heads/main.zip', release_url=None)
            project['readme_source']['url'] = project['readme_source']['url'].replace(old_repo, new_repo)
            collector = Mock(return_value=self.packet)
            with self.assertRaises(ValueError):
                run(latest, folder / 'cache.json', folder / 'work', collector, Mock(return_value=detail))
            self.assertEqual(latest.read_bytes(), before)
            self.assertFalse((folder / 'cache.json').exists())

    def test_cache_cannot_be_silently_rewritten(self):
        data, _, _ = build_candidate(self.packet, self.cache, Mock())
        data['items'][0]['summary'] += '偷偷修改已有介绍。'
        with self.assertRaisesRegex(ValueError, '不得覆盖缓存'):
            check_sources(data, self.packet)

    def test_http_failure_or_model_refusal_has_no_fallback(self):
        self.new_project()
        response = Mock(ok=False, status_code=401)
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only'}), patch('daily_update.requests.post', return_value=response):
            with self.assertRaisesRegex(ValueError, 'HTTP 401'):
                analyze(self.packet['projects'][-1])
        response = Mock(ok=True, status_code=200)
        response.json.return_value = {'choices': [{'finish_reason': 'stop', 'message': {'refusal': 'refused'}}]}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only'}), patch('daily_update.requests.post', return_value=response):
            with self.assertRaisesRegex(ValueError, '模型拒绝'):
                analyze(self.packet['projects'][-1])


if __name__ == '__main__':
    unittest.main()
