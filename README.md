# GitHub Weekly Radar

面向中文用户的 GitHub 本周精选榜：十个项目，完整中文介绍、功能、场景、推荐理由和官方来源。

## 更新与发布

- 每日 09:15（Asia/Shanghai）由本项目关联的 ChatGPT / Codex 定时任务阅读榜单与 README，生成中文内容。任务在桌面应用中运行；电脑和应用需要保持运行、GitHub 连接需要有仓库写入权限。
- GitHub Actions **不抓取、不调用模型、不生成或提交数据**。仅 `main` 上 `site/data/latest.json` 的变动触发校验与 Pages 部署，没有定时或手动抓取入口。
- 任意一个项目缺少中文介绍、必填字段、README 来源或正确安装证据时，整批拒绝更新。采集或生成失败保留上一版；Actions 校验失败不会部署；部署失败保留上一次成功部署的 Pages。
- 无英文兜底、占位文案、部分成功发布，也不需要 GitHub Models 或 OpenAI API 密钥。

## 每日任务的固定流程

详细操作与失败规则见 [docs/daily-update.md](docs/daily-update.md)。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/collect_sources.py --output work/daily
# ChatGPT 逐个阅读 work/daily/sources.json 中的 README，生成 work/daily/candidate.json。
python3 scripts/validate_data.py work/daily/candidate.json
python3 scripts/promote_data.py work/daily/candidate.json --sources work/daily/sources.json
```

采集脚本只输出完整证据，不会修改网站数据。`promote_data.py` 检查十个项目、全部字段和采集证据后原子替换文件；提交后仍需核对同一提交的 Actions 和线上 JSON。

## 精选规则

读取 `https://github.com/trending?since=weekly`，最多取前 35 个候选。沿用 `radar-score-v1`：近七天 Star 增长（最高 60 分），叠加元数据中 MCP、Agent、Codex、Skills、自动化、设计、音视频、RAG 等方向的匹配分和基础 20 分，总分最高 100。按分数、本周 Star、Trending 原排名排序选十个。README 优先中文翻译，其次默认 README；来源固定到仓库 commit 并记录内容哈希。

## 目录

```text
site/                         # 网页和经校验的 latest.json
scripts/collect_sources.py    # 只读采集榜单、元数据、完整 README
scripts/validate_data.py      # 完整中文内容与结构校验（标准库）
scripts/promote_data.py       # 对照采集证据、原子更新
tests/                        # 失败保留上一版等回归检查
docs/daily-update.md          # ChatGPT 每日操作规范
.github/workflows/deploy-pages.yml  # 仅校验和部署
```

## 验证与预览

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_data.py site/data/latest.json
python3 -m http.server 8080 --directory site
```

Pages 设置保留 GitHub Actions 作为发布来源。修改应用代码时，将已核验的数据随同提交（包括实际重新采集的更新时间），再触发部署；普通代码或说明修改不会触发数据更新。
