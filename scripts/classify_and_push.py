# scripts/classify_and_push.py
# 사용법: 워크플로에서 실행됨. GitHub 이벤트 파일에서 커밋/변경 파일을 읽고
# 변경된 코드 파일을 OpenAI로 분류한 뒤 Notion에 페이지를 생성합니다.

import os
import json
import base64
import requests
from typing import List

# 환경변수로 주입 (workflow에서 세팅)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")
GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH", "/github/workflow/event.json")

# 간단한 유틸: GitHub API로 파일 내용(원시 텍스트) 가져오기
def get_file_raw(owner: str, repo: str, path: str, ref: str) -> str | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3.raw"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.text
    else:
        print(f"[WARN] fetch file failed: {path} status:{r.status_code}")
        return None

# OpenAI로 분류 (간단 프롬프트 -> JSON 응답 기대)
def classify_with_openai(code: str) -> dict:
    # 프롬프트: 알고리즘 태그, 난이도, 한줄요약, 시간복잡도 JSON으로 반환하도록 요청
    prompt = f"""
다음은 코딩 테스트 풀이 코드입니다. 이 코드에 대해
1) 알고리즘/패턴 태그(최대 3개, 예: DP, BFS, 그리디, 투포인터, 정렬 등),
2) 난이도(쉬움/중간/어려움),
3) 한줄 요약(한국어),
4) 시간복잡도 추정(O(...) 형태)

를 JSON으로 출력하세요. 반드시 JSON만 출력하세요.

코드:
  {code[:3000]}
"""
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": "gpt-4o",       # 실제 사용 가능한 모델로 교체
        "messages": [{"role":"user","content": prompt}],
        "temperature": 0
    }
    r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]

    # LLM이 JSON 외 잡설을 붙일 가능성 대비 간단 파싱 시도
    try:
        parsed = json.loads(text)
    except Exception as e:
        parsed = {"tags": ["unknown"], "difficulty": "unknown", "summary": text.strip()[:200], "time_complexity": ""}
    return parsed

# Notion에 페이지 생성
def create_notion_page(meta: dict):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    properties = {
        "Name": {"title": [{"text": {"content": meta.get("title","Unknown")}}]},
        "Platform": {"select": {"name": meta.get("platform","GitHub")}},
        "Algorithm": {"multi_select": [{"name": t} for t in meta.get("tags", [])]},
        "Difficulty": {"select": {"name": meta.get("difficulty","Unknown")}},
        "Language": {"select": {"name": meta.get("language","Python")}},
        "URL": {"url": meta.get("url")},
    }
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": properties,
        "children": [
            {"object":"block","type":"paragraph","paragraph":{"text":[{"type":"text","text":{"content": meta.get("summary","")}}]}},
            {"object":"block","type":"code","code":{"text":[{"type":"text","text":{"content": meta.get("code_snippet","")}}],"language": meta.get("language","python")}}
        ]
    }
    r = requests.post(url, headers=headers, json=payload)
    if r.status_code not in (200,201):
        print(f"[WARN] Notion create failed: {r.status_code} {r.text}")
    else:
        print("[OK] Notion page created:", r.json().get("id"))

def main():
    # 1) GitHub event 읽기 (push 이벤트)
    with open(GITHUB_EVENT_PATH, "r", encoding="utf-8") as f:
        event = json.load(f)

    # owner/repo 정보
    repo_full = event.get("repository", {}).get("full_name", "")
    if not repo_full:
        print("[ERR] repository info missing in event")
        return
    owner, repo = repo_full.split("/")

    # ref(브랜치)와 커밋 id
    ref = event.get("ref", "main").split("/")[-1]
    # commit list에서 변경된 파일들을 모아서 처리
    changed_files: List[str] = []
    for commit in event.get("commits", []):
        changed_files += commit.get("added", []) + commit.get("modified", []) + commit.get("removed", [])

    # 확장자 필터
    exts = [".py", ".cpp", ".c", ".java", ".js"]
    for path in changed_files:
        if not any(path.endswith(ext) for ext in exts):
            continue
        # 2) 파일 원시 내용 가져오기
        content = get_file_raw(owner, repo, path, ref)
        if not content:
            continue

        # 3) LLM 분류
        parsed = classify_with_openai(content)

        # 4) Notion 생성
        meta = {
            "title": f"{repo}/{path}",
            "platform": "GitHub",
            "tags": parsed.get("tags", []),
            "difficulty": parsed.get("difficulty", "Unknown"),
            "language": "Python" if path.endswith(".py") else "Other",
            "url": f"https://github.com/{owner}/{repo}/blob/{ref}/{path}",
            "summary": parsed.get("summary", "")[:8000],
            "code_snippet": content[:1500]
        }
        create_notion_page(meta)

if __name__ == "__main__":
    main()

  
