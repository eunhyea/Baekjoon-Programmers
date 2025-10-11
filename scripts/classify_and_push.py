# scripts/classify_and_push.py (디버그 모드)
import os, json, requests, sys, traceback
from typing import List

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")
GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH", "/github/workflow/event.json")

def print_envs():
    print("[ENV] GITHUB_TOKEN present" if GITHUB_TOKEN else "[ENV-ERR] GITHUB_TOKEN missing")
    print("[ENV] OPENAI_API_KEY present" if OPENAI_API_KEY else "[ENV-ERR] OPENAI_API_KEY missing")
    print("[ENV] NOTION_TOKEN present" if NOTION_TOKEN else "[ENV-ERR] NOTION_TOKEN missing")
    print("[ENV] NOTION_DB_ID present" if NOTION_DB_ID else "[ENV-ERR] NOTION_DB_ID missing")
    print("[ENV] GITHUB_EVENT_PATH:", GITHUB_EVENT_PATH)
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
    """
    path는 GitHub 경로(예: '백준/Bronze/1000. A + B/A + B.py').
    URL에 넣기 전에 quote(..., safe='/')로 인코딩하여
    슬래시는 유지하고 공백/+, 한글 등은 퍼센트 인코딩 합니다.
    """
    encoded_path = quote(path, safe="/")  # '/'는 그대로 두고 나머지는 인코딩
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}?ref={ref}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3.raw"}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 200:
        return r.text
    else:
        print(f"[WARN] fetch file failed: {path} status:{r.status_code} body:{r.text[:400]}")
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

  
def read_event():
    if not os.path.isfile(GITHUB_EVENT_PATH):
        print("[EVENT-ERR] event file not found:", GITHUB_EVENT_PATH)
        return {}
    with open(GITHUB_EVENT_PATH, "r", encoding="utf-8") as f:
        e = json.load(f)
    # 안전하게 출력(길면 잘라서)
    s = json.dumps(e, ensure_ascii=False)
    print("[EVENT] length:", len(s))
    print(s[:2000])  # 처음 2000자만 출력
    return e

def get_changed_files(event):
    files=[]
    for c in event.get("commits", []):
        files += c.get("added", []) + c.get("modified", []) + c.get("removed", [])
    print("[INFO] total changed files found:", len(files))
    # 샘플 출력
    for i,p in enumerate(files[:200]):
        print(f"  {i+1}. {p}")
    return files

def test_openai_connectivity():
    if not OPENAI_API_KEY:
        print("[SKIP] OpenAI key missing")
        return
    try:
        r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, timeout=10)
        print("[OpenAI] status:", r.status_code)
        # 일부 body(짧게)
        print("body-preview:", (r.text or "")[:400])
    except Exception as e:
        print("[OpenAI] exception:", e)

def test_notion_connectivity():
    if not NOTION_TOKEN or not NOTION_DB_ID:
        print("[SKIP] Notion creds missing")
        return
    try:
        url=f"https://api.notion.com/v1/databases/{NOTION_DB_ID}"
        r = requests.get(url, headers={"Authorization": f"Bearer {NOTION_TOKEN}","Notion-Version":"2022-06-28"}, timeout=10)
        print("[Notion] status:", r.status_code)
        print("body-preview:", (r.text or "")[:400])
    except Exception as e:
        print("[Notion] exception:", e)

def main():
    try:
        print_envs()
        event = read_event()
        changed = get_changed_files(event)
        if not changed:
            print("[INFO] No changed files to process (exiting). If you expected files, check your push paths and event payload.")
        else:
            print("[INFO] Would process these files (debug mode - not calling OpenAI/Notion).")
            # 여기서 원래 classify/Notion 로직을 호출하도록 추가하면 됨.
        print("=== Connectivity tests ===")
        test_openai_connectivity()
        test_notion_connectivity()
    except Exception:
        print("=== UNCAUGHT EXCEPTION ===")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
