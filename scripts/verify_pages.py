#!/usr/bin/env python3
"""A deployment succeeds only when the served JSON equals the validated commit."""
import argparse
import hashlib
import time
import urllib.request
from pathlib import Path

from validate_data import read_validated


def verify(path, url, attempts=12, delay=15):
    read_validated(path)
    expected = Path(path).read_bytes()
    for attempt in range(attempts):
        request = urllib.request.Request(url + ('&' if '?' in url else '?') + f'verify={time.time_ns()}',
                                         headers={'Cache-Control': 'no-cache', 'User-Agent': 'github-weekly-radar'})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                served = response.read()
            if served == expected:
                print('Pages 数据已一致：' + hashlib.sha256(expected).hexdigest())
                return
        except OSError:
            pass
        if attempt + 1 < attempts:
            time.sleep(delay)
    raise ValueError('Pages 数据未与本次提交一致，部署验收失败')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', default='site/data/latest.json')
    parser.add_argument('--url', default='https://searshan.github.io/github-weekly-radar/data/latest.json')
    args = parser.parse_args()
    verify(args.file, args.url)
