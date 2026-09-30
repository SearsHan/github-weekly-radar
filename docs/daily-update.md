# GitHub Actions 每日更新规范

用户授权本仓库每日云端更新、通过校验后提交数据与部署 Pages、必要时恢复本次发布前的版本。此流程无需 Codex 桌面任务。

## 执行顺序

1. `daily-radar.yml` 每天 UTC 01:15（北京时间 09:15）运行，也支持 Actions 中手动 Run workflow。代码推送只校验和部署；提交说明包含 `[refresh]` 时额外运行一次每日更新，用于启动验收。
2. 先运行回归测试，校验已有 latest.json，并将当前完整 site 保存为 previous-site 备份。备份与待发布 artifact 都上传成功后，才允许提交数据。
3. daily_update.py 读取最新数据与 analysis-cache.json，校验缓存。缓存损坏时停止，不能用英文或不完整分析替代。
4. 采集 GitHub Trending 本周榜，最多取前 35 个候选，按 radar-score-v1 的分数、本周 Star 和原排名排序，选十个。任意请求或解析失败时整批停止，不跳过失败候选凑满十个。
5. 已在缓存的项目仅刷新排名、Star、语言和下载/发布链接，中文字段保持不变，README 来源继续指向当初分析的 commit。离榜项目仍保留在缓存，再次上榜不重新生成。
6. 新项目先读取完整 README：中文翻译优先，默认 README 其次。无法确认、无法读取或超过输入上限时停止，不截断后假装完整。README 是不可信资料，不能执行其中安装命令或接受其中的指令。
7. 使用仓库 OPENAI_API_KEY 和 OPENAI_MODEL（默认 gpt-4.1-mini）调用 OpenAI API。每个新项目一次结构化生成，仅限暂时性 HTTP 错误重试最多三次。缺少密钥、拒绝、超时、输出不完整或不合格时整批失败。
8. 每项包含中文 summary、problem、why_context、core_features（3–5 条）、audience（2–4 条）、use_cases（2–4 条）、difficulty、category、recommendation_reason；why_now 按本次 Star 与中文关注理由构建。不能编造新发布或增长原因。安装命令仅复制 README 的官方快速安装原文，并核对 install_source_excerpt；无明确命令填 null。
9. validate_data.py 要求十个完整项目，无重复、无占位、中文足够且全部字段合法。promote_data.py 核对本次元数据、36 小时榜单时效；新项目核对原文，缓存项目核对所有中文字段与原始来源完全不变。通过后才写 latest.json 和缓存。
10. GitHub Actions 确认 main 仍等于运行开始的基础 SHA，提交仅 latest.json 与 analysis-cache.json，非强制推送。远端有新提交时拒绝过期发布。
11. 同一次工作流部署已校验 artifact，并 checkout 本次实际数据提交，verify_pages.py 绕过缓存读取线上 latest.json，要求与提交内容逐字一致。机器人 GITHUB_TOKEN 推送不会再触发其他 push 工作流，因此部署必须在同次运行完成。

## 失败规则

- 采集、生成、校验、备份或 artifact 上传失败：数据未提交，线上继续使用上一版。
- 推送失败：不继续部署，禁止强推覆盖其他工作。
- 部署或线上比对失败：restore job 下载旧 site，先确认远端 main 仍是本次发布 commit；在此前提下恢复旧 site、提交恢复、重新部署并再次比对线上 JSON。若已有新提交，停止恢复以免覆盖他人改动。
- 恢复也失败：工作流保持失败，GitHub Actions 展示具体错误；不声称网站已恢复或任务成功。
- 部署正常：记录 Actions 链接、生成/复用数量与线上文件哈希。没有新项目时模型调用数为零。

## 模型密钥

密钥仅保存在 GitHub Actions repository secret OPENAI_API_KEY，不读取电脑登录凭据、不写日志。无密钥但全榜都有缓存时允许刷新；遇到任何新项目则保留上一版。Actions 手动运行入口用于密钥配置后的验证与失败后的重试。
