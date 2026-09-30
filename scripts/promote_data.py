#!/usr/bin/env python3
"""Validate the entire candidate and source packet before an atomic local swap."""
import argparse
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from validate_data import read_validated, require, timestamp


def check_sources(payload, packet):
    require(payload['selection'] == packet['selection'], '榜单来源不符')
    require(payload['analyzed_count'] == packet['analyzed_count'], '候选数量不符')
    fetched = timestamp(packet['selection']['fetched_at'], 'fetched_at')
    current = datetime.now(timezone.utc)
    require(current - timedelta(hours=36) <= fetched <= current + timedelta(minutes=5), '榜单快照已过期或来自未来')
    require(len(packet['projects']) == 10, 'README 证据不足十个')
    require(fetched <= timestamp(payload['updated_at'], 'updated_at') <= current + timedelta(minutes=5), '更新时间无效')
    for item, source in zip(payload['items'], packet['projects']):
        for field in ('repo', 'name', 'rank', 'language', 'stars', 'weekly_stars', 'score',
                      'github_url', 'download_url', 'clone', 'release_url', 'readme_source'):
            require(item[field] == source[field], f'{item["repo"]}.{field}: 与采集证据不符')
        require(isinstance(source.get('readme'), str) and len(source['readme'].strip()) >= 200, '缺少完整 README')
        if item['install'] is not None:
            require(item['install_source_excerpt'] in source['readme'], f'{item["repo"]}: 安装命令非 README 原文')


def promote(candidate, sources, target):
    payload = read_validated(candidate)
    check_sources(payload, json.loads(Path(sources).read_text(encoding='utf-8')))
    content = (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.latest-', suffix='.json', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print('10/10 校验通过，候选已原子替换。提交前请核对 diff。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('candidate')
    parser.add_argument('--sources', required=True)
    parser.add_argument('--target', default='site/data/latest.json')
    args = parser.parse_args()
    try:
        promote(args.candidate, args.sources, args.target)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f'禁止替换，上一版保持不变：{exc}\n')
