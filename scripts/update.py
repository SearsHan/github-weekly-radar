#!/usr/bin/env python3
import base64, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "data"
DATA.mkdir(parents=True, exist_ok=True)

TOKEN = os.getenv("GITHUB_TOKEN", "")
MODEL = os.getenv("GITHUB_MODEL", "openai/gpt-4.1")
HEAD = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "github-weekly-radar",
}
if TOKEN:
    HEAD["Authorization"] = f"Bearer {TOKEN}"

FOCUS = {
    "mcp": 10, "agent": 9, "codex": 10, "skill": 8, "automation": 7,
    "browser": 6, "design": 7, "image": 5, "video": 5, "audio": 5,
    "llm": 5, "ai": 4, "rag": 6, "memory": 6
}
ALLOWED_CATS = ["AI", "Agent", "MCP", "Codex / Skills", "自动化", "AI 设计", "音视频", "数据 / RAG", "开发工具", "效率工具", "开源工具"]
PLACEHOLDERS = ("请查看项目 README", "项目详情以官方 README 为准", "评估是否适合自己的工作流")


def trending():
    html = requests.get(
        "https://github.com/trending?since=weekly",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    ).text
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for row in soup.select("article.Box-row"):
        a = row.select_one("h2 a")
        if not a:
            continue
        repo = "/".join(a.get("href", "").strip("/").split("/")[:2])
        txt = " ".join(row.stripped_strings)
        m = re.search(r"([\d,]+)\s+stars this week", txt, re.I)
        weekly = int(m.group(1).replace(",", "")) if m else 0
        out.append((repo, weekly))
    return out


def gh_get(url, accept=None):
    headers = dict(HEAD)
    if accept:
        headers["Accept"] = accept
    return requests.get(url, headers=headers, timeout=30)


def meta(repo):
    r = gh_get("https://api.github.com/repos/" + repo)
    if r.status_code != 200:
        return None
    j = r.json()
    haystack = ((j.get("description") or "") + " " + " ".join(j.get("topics") or [])).lower()
    bonus = sum(v for k, v in FOCUS.items() if k in haystack)
    return j, bonus


def fetch_readme(repo):
    r = gh_get(
        f"https://api.github.com/repos/{repo}/readme",
        "application/vnd.github.raw+json",
    )
    if r.status_code == 200:
        try:
            return r.text[:12000]
        except Exception:
            pass
    # JSON/base64 fallback
    r = gh_get(f"https://api.github.com/repos/{repo}/readme")
    if r.status_code == 200:
        try:
            raw = base64.b64decode(r.json().get("content", "")).decode("utf-8", "ignore")
            return raw[:12000]
        except Exception:
            return ""
    return ""


def latest_release(repo):
    r = gh_get(f"https://api.github.com/repos/{repo}/releases/latest")
    if r.status_code == 200:
        return r.json().get("html_url")
    return None


def zh_count(s):
    return len(re.findall(r"[\u4e00-\u9fff]", s or ""))


def good_cn(prev):
    if not prev or prev.get("analysis_version") != 2:
        return False
    text = " ".join([
        prev.get("summary", ""),
        prev.get("problem", ""),
        " ".join(prev.get("core_features") or []),
    ])
    return zh_count(text) >= 50 and not any(p in text for p in PLACEHOLDERS)


def fallback_category(j):
    text = ((j.get("description") or "") + " " + " ".join(j.get("topics") or [])).lower()
    cats = []
    rules = [
        ("mcp", "MCP"), ("skill", "Codex / Skills"), ("codex", "Codex / Skills"),
        ("agent", "Agent"), ("rag", "数据 / RAG"), ("knowledge", "数据 / RAG"),
        ("design", "AI 设计"), ("image", "AI 设计"), ("video", "音视频"),
        ("audio", "音视频"), ("voice", "音视频"), ("browser", "自动化"),
        ("automation", "自动化"), ("developer", "开发工具"), ("cli", "开发工具"),
        ("ai", "AI"), ("llm", "AI"),
    ]
    for key, cat in rules:
        if key in text and cat not in cats:
            cats.append(cat)
    return cats[:3] or ["开源工具"]


def model_analyze(projects):
    if not TOKEN or not projects:
        return {}
    compact = []
    for p in projects:
        compact.append({
            "repo": p["repo"],
            "description": p["description"],
            "topics": p["topics"],
            "weekly_stars": p["weekly_stars"],
            "language": p["language"],
            "readme": p["readme"][:9000],
        })

    system = """你是 GitHub 开源项目研究员。根据提供的 GitHub 元数据和 README，为中文用户生成准确、具体、易懂的项目介绍。
严格要求：
1. 只能使用输入中明确提供的信息，不得猜测功能、安装方法、发布原因或适用场景。
2. summary 必须是中文详细介绍，约 100~180 个汉字，先解释项目是什么，再解释核心价值；不能只翻译一句 Description。
3. problem、why_context、recommendation_reason 都用中文。why_context 不要重复 Star 数字。
4. core_features 3~5 条；audience 2~4 条；use_cases 2~4 条，全部中文且具体。
5. difficulty 只能是：入门、中等、较高。
6. category 从以下标签中选 1~3 个：AI、Agent、MCP、Codex / Skills、自动化、AI 设计、音视频、数据 / RAG、开发工具、效率工具、开源工具。
7. install 只有 README 明确给出官方快速安装命令时才填写，并原样保留命令；否则 null。
8. 输出 JSON，不要 Markdown，不要解释。格式：
{"projects":[{"repo":"owner/name","summary":"...","problem":"...","why_context":"...","core_features":["..."],"audience":["..."],"use_cases":["..."],"difficulty":"中等","category":["AI"],"recommendation_reason":"...","install":null}]}
"""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(compact, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "max_tokens": 7000,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    for attempt in range(3):
        try:
            r = requests.post(
                "https://models.github.ai/inference/chat/completions",
                headers=headers,
                json=payload,
                timeout=180,
            )
            if r.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            r.raise_for_status()
            print("MODEL_HTTP", r.status_code, r.headers.get("content-type"), repr(r.text[:500]))
            parsed_response = json.loads(r.text.lstrip("\\ufeff"))
            content = (parsed_response["choices"][0]["message"].get("content") or "").strip()
            # GitHub Models may wrap JSON in markdown fences even when JSON mode is requested.
            if content.startswith("\`\`\`"):
                content = re.sub(r"^\`\`\`(?:json)?\\s*", "", content, flags=re.I)
                content = re.sub(r"\\s*\`\`\`$", "", content)
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                match = re.search(r"\\{.*\\}", content, re.S)
                if not match:
                    raise ValueError("model returned no JSON object: " + repr(content[:300]))
                data = json.loads(match.group(0))
            return {x["repo"]: x for x in data.get("projects", []) if x.get("repo")}
        except Exception as e:
            print("GitHub Models analysis failed:", e)
            time.sleep(3 * (attempt + 1))
    return {}


def normalize_list(value, fallback):
    if isinstance(value, list):
        out = [str(x).strip() for x in value if str(x).strip()]
        return out or fallback
    return fallback


def fallback_cn(j):
    name = j.get("name") or j.get("full_name")
    desc = j.get("description") or ""
    return f"{name} 是一个近期在 GitHub 上增长较快的开源项目。当前自动中文分析暂时不可用；官方描述为：{desc}"


def main():
    old_payload = {}
    if (DATA / "latest.json").exists():
        try:
            old_payload = json.loads((DATA / "latest.json").read_text(encoding="utf-8"))
        except Exception:
            old_payload = {}
    old = {x["repo"]: x for x in old_payload.get("items", [])}

    rows = []
    for repo, weekly in trending()[:35]:
        m = meta(repo)
        if not m:
            continue
        j, bonus = m
        score = min(100, round(min(60, weekly / 250) + bonus + 20))
        rows.append((score, weekly, j))
    rows.sort(reverse=True, key=lambda x: (x[0], x[1]))
    selected = rows[:10]

    pending = []
    readmes = {}
    for score, weekly, j in selected:
        repo = j["full_name"]
        prev = old.get(repo, {})
        if not good_cn(prev):
            readme = fetch_readme(repo)
            readmes[repo] = readme
            pending.append({
                "repo": repo,
                "description": j.get("description") or "",
                "topics": j.get("topics") or [],
                "weekly_stars": weekly,
                "language": j.get("language") or "Mixed",
                "readme": readme,
            })

    analyses = model_analyze(pending)
    items = []
    for rank, (score, weekly, j) in enumerate(selected, 1):
        repo = j["full_name"]
        prev = old.get(repo, {})
        ai = analyses.get(repo, {})

        if ai and zh_count(ai.get("summary", "")) >= 30:
            detail = {
                "summary": ai.get("summary"),
                "problem": ai.get("problem") or "项目目标与 README 所述能力一致。",
                "why_context": ai.get("why_context") or "",
                "core_features": normalize_list(ai.get("core_features"), ["请以官方 README 的功能列表为准"]),
                "audience": normalize_list(ai.get("audience"), ["希望评估该项目的开发者"]),
                "use_cases": normalize_list(ai.get("use_cases"), ["结合官方 README 评估具体使用场景"]),
                "difficulty": ai.get("difficulty") if ai.get("difficulty") in ("入门", "中等", "较高") else "中等",
                "category": [x for x in normalize_list(ai.get("category"), fallback_category(j)) if x in ALLOWED_CATS][:3] or fallback_category(j),
                "recommendation_reason": ai.get("recommendation_reason") or "近期增长明显，值得进一步研究。",
                "install": ai.get("install") or None,
                "analysis_version": 2,
            }
        elif good_cn(prev):
            detail = {
                "summary": prev["summary"],
                "problem": prev["problem"],
                "why_context": prev.get("why_context", ""),
                "core_features": prev["core_features"],
                "audience": prev["audience"],
                "use_cases": prev["use_cases"],
                "difficulty": prev["difficulty"],
                "category": prev["category"],
                "recommendation_reason": prev["recommendation_reason"],
                "install": prev.get("install"),
                "analysis_version": 2,
            }
        else:
            detail = {
                "summary": fallback_cn(j),
                "problem": "自动中文分析暂时未完成，下一次更新会继续重试。",
                "why_context": "近期 GitHub 社区关注度明显上升。",
                "core_features": ["自动中文分析暂时未完成，请先参考官方 README"],
                "audience": ["希望研究该项目的开发者"],
                "use_cases": ["先通过官方 README 与示例评估是否适合自己的工作流"],
                "difficulty": "中等",
                "category": fallback_category(j),
                "recommendation_reason": "进入近 7 天高增长候选，并与关注方向有一定匹配。",
                "install": None,
                "analysis_version": 1,
            }

        item = {
            **detail,
            "rank": rank,
            "repo": repo,
            "name": j["name"],
            "language": j.get("language") or "Mixed",
            "stars": j.get("stargazers_count", 0),
            "weekly_stars": weekly,
            "score": score,
            "github_url": j["html_url"],
            "download_url": f"https://github.com/{repo}/archive/refs/heads/{j.get('default_branch', 'main')}.zip",
            "clone": f"git clone https://github.com/{repo}.git",
            "release_url": latest_release(repo),
            "why_now": f"近 7 天新增约 {weekly:,} Star。" + (detail.get("why_context") or ""),
        }
        items.append(item)

    now = datetime.now(timezone.utc)
    iso = now.isocalendar()
    payload = {
        "period": f"{iso.year}-W{iso.week:02d}",
        "updated_at": now.isoformat(timespec="seconds"),
        "source": "GitHub Trending · This week",
        "analyzed_count": len(rows),
        "items": items,
    }
    (DATA / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"updated {len(items)} projects; AI analyzed {len(analyses)}")


if __name__ == "__main__":
    main()
