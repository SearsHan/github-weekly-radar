#!/usr/bin/env python3
"""Collect evidence only. Never write site/data or invoke any model."""
import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

FOCUS = {'mcp': 10, 'agent': 9, 'codex': 10, 'skill': 8, 'automation': 7,
         'browser': 6, 'design': 7, 'image': 5, 'video': 5, 'audio': 5,
         'llm': 5, 'ai': 4, 'rag': 6, 'memory': 6}
TRENDING = 'https://github.com/trending?since=weekly'
SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'github-weekly-radar', 'Accept': 'application/vnd.github+json'})
if os.getenv('GITHUB_TOKEN'):
    SESSION.headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def get(url):
    response = SESSION.get(url, timeout=45)
    response.raise_for_status()
    return response


def api(repo, resource=''):
    return get(f'https://api.github.com/repos/{repo}{resource}').json()


def parse_trending(html):
    rows, seen = [], set()
    for row in BeautifulSoup(html, 'html.parser').select('article.Box-row'):
        link = row.select_one('h2 a')
        if not link:
            continue
        repo = link['href'].strip('/')
        match = re.search(r'([\d,]+)\s+stars this week', row.get_text(' ', strip=True), re.I)
        if not re.fullmatch(r'[\w.-]+/[\w.-]+', repo) or not match or repo.lower() in seen:
            raise ValueError('Trending 格式变化或重复项目，禁止降级抓取')
        seen.add(repo.lower())
        rows.append({'repo': repo, 'weekly_stars': int(match[1].replace(',', '')),
                     'trending_rank': len(rows) + 1})
    if len(rows) < 10:
        raise ValueError('Trending 本周候选不足十个')
    return rows[:35]


def score(description, topics, weekly):
    text = (description + ' ' + ' '.join(topics)).lower()
    bonus = sum(value for word, value in FOCUS.items() if word in text)
    return min(100, round(min(60, weekly / 250) + bonus + 20))


def readme(repo, branch):
    commit = api(repo, '/branches/' + quote(branch, safe=''))['commit']['sha']
    tree = api(repo, '/git/trees/' + commit + '?recursive=1')
    if tree.get('truncated'):
        raise ValueError(f'{repo}: 文件树不完整，无法确认中文 README')
    paths = [entry['path'] for entry in tree['tree'] if entry['type'] == 'blob'
             and re.match(r'^readme(?:[._-].*)?$', Path(entry['path']).name, re.I)]
    # Prefer explicit Chinese translations, then the default root README.
    zh = [p for p in paths if re.search(r'(?i)(?:^|[/._-])(?:zh(?:[-_]cn|[-_]hans)?|cn|chinese|中文|简体)(?:[/._-]|$)', p)]
    root = [p for p in paths if '/' not in p]
    for path in sorted(set(zh), key=lambda p: (p.count('/'), p.lower())) + sorted(root, key=lambda p: (p.lower() != 'readme.md', p.lower())):
        url = f'https://raw.githubusercontent.com/{repo}/{commit}/{quote(path, safe="/")}'
        raw = get(url).content
        text = raw.decode('utf-8-sig')
        if len(text.strip()) < 200:
            continue
        is_zh = len(re.findall(r'[\u3400-\u9fff]', text)) >= 80
        if path in zh and not is_zh:
            continue
        return text, {'url': f'https://github.com/{repo}/blob/{commit}/{path}',
                      'path': path, 'commit': commit, 'language': 'zh' if is_zh else 'en',
                      'sha256': hashlib.sha256(raw).hexdigest(), 'fetched_at': now()}
    raise ValueError(f'{repo}: 无法读取足够完整的 README')


def collect(destination, cache=None):
    cache = cache or {}
    html = get(TRENDING).text
    rows = parse_trending(html)
    fetched = now()
    candidates = []
    for row in rows:
        meta = api(row['repo'])
        if meta.get('archived') or meta.get('disabled'):
            continue
        candidates.append({**row, 'repo': meta['full_name'], 'name': meta['name'],
                           'description': meta.get('description') or '',
                           'topics': meta.get('topics') or [],
                           'language': meta.get('language') or 'Mixed',
                           'stars': meta['stargazers_count'], 'default_branch': meta['default_branch'],
                           'github_url': meta['html_url'],
                           'score': score(meta.get('description') or '', meta.get('topics') or [], row['weekly_stars'])})
    candidates.sort(key=lambda p: (-p['score'], -p['weekly_stars'], p['trending_rank']))
    if len(candidates) < 10:
        raise ValueError('有效候选不足十个，保持旧版')
    selected = []
    for rank, project in enumerate(candidates[:10], 1):
        repo = project['repo']
        cached = cache.get(repo.lower())
        if cached is not None:
            text, source = None, cached['readme_source']
        else:
            text, source = readme(repo, project['default_branch'])
        release = SESSION.get(f'https://api.github.com/repos/{repo}/releases/latest', timeout=45)
        if release.status_code == 404:
            release_url = None
        else:
            release.raise_for_status()
            release_url = release.json()['html_url']
        selected.append({**project, 'rank': rank, 'readme': text, 'readme_source': source,
                         'clone': f'git clone https://github.com/{repo}.git',
                         'download_url': f'https://github.com/{repo}/archive/refs/heads/{project["default_branch"]}.zip',
                         'release_url': release_url, 'cached_item': cached})
        print(f'{rank}/10：{repo} — ' + ('复用已校验中文介绍' if cached else f'已读取 README ({source["language"]})'), flush=True)
    packet = {'selection': {'url': TRENDING, 'fetched_at': fetched, 'method': 'radar-score-v1',
                            'snapshot_sha256': hashlib.sha256(html.encode()).hexdigest()},
              'analyzed_count': len(candidates), 'candidates': candidates, 'projects': selected}
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'sources.json').write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding='utf-8')
    (destination / 'trending.html').write_text(html, encoding='utf-8')
    print(f'证据保存至 {destination}/sources.json；线上数据未修改。')
    return packet


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('work/daily'))
    collect(parser.parse_args().output)
