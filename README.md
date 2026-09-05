# GitHub Weekly Radar

每周只精选 **10 个**真正值得研究、下载和使用的 GitHub 项目。

## 已实现

- GitHub Trending `This week` 自动抓取
- 固定 Top 10
- 近 7 天新增 Star、总 Star、Radar Score
- 中文详细介绍、核心功能、解决问题、为什么本周值得关注
- 针对 Codex / MCP / AI 设计 / 自动化 / 内容生产的推荐理由
- GitHub、ZIP 下载、Latest Release、Git Clone、安装命令
- 分类筛选、排序、浏览器本地收藏
- 历史周榜归档
- 手机 / 桌面响应式网页
- GitHub Actions 每天 09:15（中国标准时间）更新
- GitHub Pages 自动发布

## 目录

```text
site/                 # GitHub Pages 网站
  index.html
  styles.css
  app.js
  data/latest.json
  data/archive/
scripts/update.py     # 抓取、评分、AI 分析
.github/workflows/    # 定时更新 + Pages 部署
```

## 部署

1. 在 GitHub 新建公开仓库 `github-weekly-radar`。
2. 把本项目全部文件上传到仓库根目录。
3. `Settings → Pages → Build and deployment → Source` 选择 **GitHub Actions**。
4. 打开 `Actions`，运行一次 **Update and deploy GitHub Weekly Radar**。
5. Pages 地址通常是：`https://<username>.github.io/github-weekly-radar/`。

## AI 中文分析（推荐开启）

不配置 AI 密钥时，更新脚本仍可自动刷新 GitHub 排名和项目元数据；新进入榜单的项目会使用保守的官方描述兜底。

如要让新项目也自动生成完整中文介绍：

1. 仓库 `Settings → Secrets and variables → Actions → Secrets`
2. 添加 `OPENAI_API_KEY`
3. 可在 `Variables` 添加 `OPENAI_MODEL`；默认使用 `gpt-5.6-luna`

密钥只存在 GitHub Actions Secrets 中，不要写进仓库文件。

## 手动刷新

`Actions → Update and deploy GitHub Weekly Radar → Run workflow`

## 本地预览

```bash
cd site
python3 -m http.server 8080
```

打开 `http://localhost:8080`。
