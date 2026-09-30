# GitHub Weekly Radar

GitHub 本周精选十个项目，提供完整中文介绍、功能、使用场景、推荐理由与官方 README 来源。

## 云端每日更新

**GitHub Actions 每天自动跑 → 新项目才生成中文介绍 → 十项校验通过才提交与发布 → 失败保留或恢复旧版。**

每天北京时间 09:15（UTC 01:15）在 GitHub 云端执行，可能因 GitHub 排队而延迟。无需保持电脑开机或运行 Codex，也不使用 Codex 定时任务。

- 沿用 radar-score-v1，从 GitHub Trending 本周榜筛选十个项目，刷新排名、Star 和链接。
- 已有合格中文介绍写入持久缓存；离榜后重新上榜仍复用，不重复调用模型。
- 只有未进入缓存的新项目，才读取 README（优先中文，否则英文）并调用 OpenAI API 生成结构化中文介绍。缓存保留原始 README commit、哈希与生成时的证据，不冒充每日重新阅读。
- 十个项目的介绍、功能、受众、场景、分类、难度与来源全部校验通过，才提交 latest.json 和缓存。没有英文、占位或部分成功兜底。
- 同一次 Actions 中直接部署并核对线上 JSON。抓取、模型或校验失败时不提交、不部署；部署或线上核验失败时，在没有后续提交的前提下恢复旧数据并重新发布。恢复也失败时工作流保持失败，不能宣称已恢复。

## 配置模型密钥

1. 到 https://platform.openai.com/api-keys 创建 API Key，并确保该 API 项目可正常使用模型。
2. 仓库 Settings → Secrets and variables → Actions → New repository secret。
3. Name 填 `OPENAI_API_KEY`，Secret 粘贴密钥，点击 Add secret。不要写入仓库、日志或聊天。
4. 默认模型 `gpt-4.1-mini`。可在 Actions Variables 中设置 `OPENAI_MODEL` 使用其他支持 Structured Outputs 的 OpenAI 模型。
5. Actions → **Daily Chinese radar and Pages** → Run workflow，可立即运行验证。

未配置密钥时，全部项目都有缓存仍可刷新；一旦出现新项目，整批更新停止并保留旧版。ChatGPT/Codex 登录凭据不会注入 GitHub Actions，API 调用使用独立 API 项目。

## 文件

```text
site/data/latest.json          # 线上十个完整中文项目
site/data/analysis-cache.json  # 已阅读项目的中文介绍与原始证据缓存
scripts/collect_sources.py    # 采集榜单和元数据，仅新项目读取 README
scripts/daily_update.py       # 复用旧介绍、生成新介绍、整批校验
scripts/validate_data.py      # 中文与结构校验
scripts/promote_data.py       # 与采集或缓存证据核对，原子替换候选
scripts/verify_pages.py       # 比对实际线上数据与提交内容
.github/workflows/daily-radar.yml  # 每日更新、提交、部署、失败恢复
```

完整运行规则见 [docs/daily-update.md](docs/daily-update.md)。

## 本地检查

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
python3 scripts/validate_data.py site/data/latest.json
python3 -m http.server 8080 --directory site
```
