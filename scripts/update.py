#!/usr/bin/env python3
import json,re,requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'site'/'data'; DATA.mkdir(parents=True,exist_ok=True)
HEAD={'Accept':'application/vnd.github+json','User-Agent':'github-weekly-radar'}
FOCUS={'mcp':10,'agent':9,'codex':10,'skill':8,'automation':7,'browser':6,'design':7,'image':5,'video':5,'audio':5,'llm':5,'ai':4}
def trending():
    h=requests.get('https://github.com/trending?since=weekly',headers={'User-Agent':'Mozilla/5.0'},timeout=30).text
    s=BeautifulSoup(h,'html.parser'); out=[]
    for row in s.select('article.Box-row'):
        a=row.select_one('h2 a')
        if not a: continue
        repo='/'.join(a.get('href','').strip('/').split('/')[:2]); txt=' '.join(row.stripped_strings)
        m=re.search(r'([\d,]+)\s+stars this week',txt,re.I); weekly=int(m.group(1).replace(',','')) if m else 0
        out.append((repo,weekly))
    return out
def meta(repo):
    r=requests.get('https://api.github.com/repos/'+repo,headers=HEAD,timeout=30)
    if r.status_code!=200:return None
    j=r.json(); d=(j.get('description') or '')+' '+' '.join(j.get('topics') or [])
    bonus=sum(v for k,v in FOCUS.items() if k in d.lower()); return j,bonus
def main():
    old={x['repo']:x for x in json.loads((DATA/'latest.json').read_text())['items']} if (DATA/'latest.json').exists() else {}
    rows=[]
    for repo,w in trending()[:30]:
        m=meta(repo)
        if not m: continue
        j,b=m; score=min(100,round(min(60,w/250)+b+20)); rows.append((score,w,j))
    rows.sort(reverse=True,key=lambda x:(x[0],x[1])); items=[]
    for rank,(score,w,j) in enumerate(rows[:10],1):
        repo=j['full_name']; prev=old.get(repo,{})
        summary=prev.get('summary') or j.get('description') or '请查看项目 README 获取详细介绍。'
        cat=prev.get('category') or ['开源工具']; diff=prev.get('difficulty') or '中等'
        base=dict(prev); base.update({'rank':rank,'repo':repo,'name':j['name'],'language':j.get('language') or 'Mixed','stars':j.get('stargazers_count',0),'weekly_stars':w,'score':score,'github_url':j['html_url'],'download_url':f"https://github.com/{repo}/archive/refs/heads/{j.get('default_branch','main')}.zip",'clone':f'git clone https://github.com/{repo}.git','summary':summary,'category':cat,'difficulty':diff})
        for k,v in {'problem':'请查看项目 README 了解它解决的具体问题。','why_now':f'近 7 天新增约 {w:,} Star。','core_features':['项目详情以官方 README 为准'],'audience':['开源项目使用者'],'use_cases':['评估是否适合自己的工作流'],'recommendation_reason':'进入本周高增长候选，并与 AI / Agent / 自动化等方向有一定匹配。','install':None,'release_url':None}.items(): base.setdefault(k,v)
        items.append(base)
    now=datetime.now(timezone.utc).astimezone(); iso=now.isocalendar(); payload={'period':f'{iso.year}-W{iso.week:02d}','updated_at':now.isoformat(timespec='seconds'),'source':'GitHub Trending · This week','analyzed_count':len(rows),'items':items}
    (DATA/'latest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8'); print('updated',len(items))
if __name__=='__main__':main()
