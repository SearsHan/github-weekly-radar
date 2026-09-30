#!/usr/bin/env python3
"""Fail closed; validate every displayed field before publishing anything."""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

CATEGORIES = {'AI', 'Agent', 'MCP', 'Codex / Skills', '自动化', 'AI 设计',
              '音视频', '数据 / RAG', '开发工具', '效率工具', '开源工具'}
PLACEHOLDERS = re.compile(
    r'请(?:先)?(?:查看|参考)|以官方\s*README.*为准|自动中文分析.*(?:不可用|未完成)|'
    r'官方描述为|下一次更新.*重试|评估是否适合自己的工作流|'
    r'项目目标与\s*README\s*所述能力一致|\b(?:TODO|TBD|placeholder)\b', re.I)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def chinese(value, minimum, label):
    require(isinstance(value, str) and value.strip(), f'{label}: 缺少文本')
    count = len(re.findall(r'[\u3400-\u9fff]', value))
    require(count >= minimum, f'{label}: 中文内容不足（至少 {minimum} 字）')
    letters = len(re.findall(r'[A-Za-z\u3400-\u9fff]', value))
    require(count / max(1, letters) >= .20, f'{label}: 英文占比过高')
    require(not PLACEHOLDERS.search(value), f'{label}: 包含占位内容')


def timestamp(value, label):
    require(isinstance(value, str), f'{label}: 时间无效')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, f'{label}: 缺少时区')
    return parsed


def validate(payload):
    require(isinstance(payload, dict), '数据必须是对象')
    updated = timestamp(payload.get('updated_at'), 'updated_at')
    iso = updated.isocalendar()
    require(payload.get('period') == f'{iso.year}-W{iso.week:02d}', '周次与时间不一致')
    require(payload.get('source') == 'GitHub Trending · This week', '来源必须是本周榜')
    selection = payload.get('selection', {})
    require(isinstance(selection, dict), 'selection 必须是对象')
    require(selection.get('url') == 'https://github.com/trending?since=weekly', '缺少本周榜来源')
    timestamp(selection.get('fetched_at'), 'selection.fetched_at')
    require(selection.get('method') == 'radar-score-v1', '筛选规则未知')
    require(isinstance(selection.get('snapshot_sha256'), str) and
            re.fullmatch(r'[0-9a-f]{64}', selection['snapshot_sha256']), '榜单快照哈希无效')
    require(type(payload.get('analyzed_count')) is int and payload['analyzed_count'] >= 10,
            '候选不足十个')
    items = payload.get('items')
    require(isinstance(items, list) and len(items) == 10, '必须完整包含十个项目')
    seen = set()
    for rank, item in enumerate(items, 1):
        label = f'第 {rank} 个项目'
        require(isinstance(item, dict), f'{label}: 类型错误')
        repo = item.get('repo')
        require(isinstance(repo, str) and re.fullmatch(r'[\w.-]+/[\w.-]+', repo), f'{label}: repo 无效')
        require(repo.lower() not in seen, f'{label}: 重复项目')
        seen.add(repo.lower())
        require(type(item.get('rank')) is int and item['rank'] == rank, f'{repo}: 排名不连续')
        require(item.get('analysis_version') == 3, f'{repo}: 必须重新阅读 README')
        require(item.get('name') == repo.split('/')[1], f'{repo}: 名称不符')
        require(isinstance(item.get('language'), str) and item['language'].strip(), f'{repo}: language 缺失')
        for field, minimum in [('summary', 65), ('problem', 25), ('why_context', 20),
                               ('why_now', 20), ('recommendation_reason', 20)]:
            chinese(item.get(field), minimum, f'{repo}.{field}')
        for field, low, high, minimum in [('core_features', 3, 5, 5),
                                         ('audience', 2, 4, 4), ('use_cases', 2, 4, 6)]:
            values = item.get(field)
            require(isinstance(values, list) and low <= len(values) <= high, f'{repo}.{field}: 条数不符')
            for value in values:
                chinese(value, minimum, f'{repo}.{field}')
            require(len(set(values)) == len(values), f'{repo}.{field}: 内容重复')
        require(item.get('difficulty') in ('入门', '中等', '较高'), f'{repo}: difficulty 无效')
        cats = item.get('category')
        require(isinstance(cats, list) and 1 <= len(cats) <= 3 and
                all(isinstance(c, str) and c in CATEGORIES for c in cats), f'{repo}: category 无效')
        for field in ('stars', 'weekly_stars', 'score'):
            require(type(item.get(field)) is int and item[field] >= 0, f'{repo}.{field}: 数值无效')
        require(item['score'] <= 100, f'{repo}: score 超出范围')
        require(item['github_url'] == f'https://github.com/{repo}', f'{repo}: GitHub 链接不符')
        require(item['clone'] == f'git clone https://github.com/{repo}.git', f'{repo}: clone 不符')
        download = item.get('download_url', '')
        require(isinstance(download, str) and download.startswith(f'https://github.com/{repo}/archive/refs/heads/')
                and download.endswith('.zip'), f'{repo}: 下载链接不符')
        release = item.get('release_url')
        require(release is None or (isinstance(release, str) and
                release.startswith(f'https://github.com/{repo}/releases/')), f'{repo}: release 不符')
        source = item.get('readme_source', {})
        require(isinstance(source, dict), f'{repo}: README 来源无效')
        sha, path = source.get('commit'), source.get('path')
        require(isinstance(sha, str) and re.fullmatch(r'[0-9a-f]{40}', sha), f'{repo}: README commit 无效')
        require(isinstance(path, str) and 'readme' in path.lower(), f'{repo}: README path 无效')
        require(source.get('url') == f'https://github.com/{repo}/blob/{sha}/{path}', f'{repo}: README URL 不符')
        require(source.get('language') in ('zh', 'en'), f'{repo}: README 语言无效')
        require(isinstance(source.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', source['sha256']), f'{repo}: README 哈希无效')
        timestamp(source.get('fetched_at'), f'{repo}.readme_source.fetched_at')
        install = item.get('install')
        require('install' in item and (install is None or isinstance(install, str) and install.strip()), f'{repo}: install 必须为命令或 null')
        if install is not None:
            excerpt = item.get('install_source_excerpt')
            require(isinstance(excerpt, str) and install in excerpt, f'{repo}: 安装命令缺少原文证据')
    return payload


def read_validated(path):
    return validate(json.loads(Path(path).read_text(encoding='utf-8')))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file', nargs='?', default='site/data/latest.json')
    args = parser.parse_args()
    try:
        read_validated(args.file)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f'校验失败，禁止发布：{exc}\n')
    print('校验通过：10/10 个完整中文项目，全部必填字段与 README 来源有效。')


if __name__ == '__main__':
    main()
