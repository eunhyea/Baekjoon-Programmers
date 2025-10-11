# scripts/classify_and_push.py
# 디버그 모드 + 실제 처리 로직 통합 버전
# 워크플로에서 실행될 때 환경변수가 주입되었다고 가정합니다.
# - 필수 env: GITHUB_TOKEN, OPENAI_API_KEY, NOTION_TOKEN, NOTION_DB_ID
# - Python 3.11 로 실행 권장 (type union, f-strings 등 사용)

import os
import sys
import json
import requests
import traceback
from typing import List, Optional
from urllib.parse import quote

# 환경변수 읽기
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")
GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH", "/github/workflow/event.json")

# -------------------
# 유틸/디버그 함수
# -------------------
def print_envs():
    print("[ENV] GITHUB_TOKEN present" if GITHUB_TOKEN else "[ENV-ERR] GITHUB_TOKEN missing")
    print("[ENV] OPENAI_API_KEY present" if OPENAI_API_KEY else "[ENV-ERR] OPENAI_API_KEY missing")
    print("[ENV] NOTION_TOKEN present" if NOTION_TOKEN else "[ENV-ERR] NOTION_TOKEN missing")
    print("[ENV] NOTION_DB_ID present" if NOTION_DB_ID else "[ENV-ERR] NOTION_DB_ID missing")
    print("[ENV] GITHUB_EVENT_PATH:", GITHUB_EVENT_PATH)

def read_event() -> dict:
    if not os.path.isfile(GITHUB_EVENT_PATH):
        print("[EVENT-ERR] event file not found:", GITHUB_EVENT_PATH)
        return {}
    with open(GITHUB_EVENT_PATH, "r", encoding="utf-8") as f:
        e = json.load(f)
    print("[EVENT] loaded event, length:", len(json.dumps(e, ensure_ascii=False)))
    # 처음 2000자만 출력해 확인
    s = json.dumps(e, ensure_ascii=False)
    print(s[:2000])
    return e

def get_changed_files_from_event(event: dict) -> List[str]:
    files: List[str] = []
    for c in event.get("commits", []):
        files += c.get("added", []) + c.get("modified", []) + c.get("removed", [])
    print("[INFO] total changed files found in event:", len(files))
    for i, p in enumerate(files[:200]):
        print(f"  {i+1}. {p}")
    return files

def fetch_files_from_commit(owner: str, repo: str, commit_id: str) -> List[str]:
    """payload의 commit list가 비어있을 때 commit API로 폴백"""
    if not GITHUB_TOKEN:
        print("[WARN] cannot fetch commit files because GITHUB_TOKEN is missing")
        return []
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_id}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
    except Exception as e:
        print("[WARN] fetch commit files exception:", e)
        return []
    if r.status_code != 200:
        print("[WARN] fetch commit files failed:", r.status_code, r.text[:400])
        return []
    data = r.json()
    files = [f.get("filename") for f in data.get("files", []) if f.get("filename")]
    print("[INFO] files from commits API (sample):", files[:100])
    return files

# -------------------
# GitHub contents 읽기 (경로 인코딩 주의)
# -------------------
def get_file_raw(owner: str, repo: str, path: str, ref: str) -> Optional[str]:
    """
    path에 공백/한글/특수문자가 있을 수 있으므로 URL 인코딩합니다.
    """
    if not GITHUB_TOKEN:
        print("[WARN] GITHUB_TOKEN missing, cannot fetch file")
        return None
    encoded_path = quote(path, safe="/")
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}?ref={ref}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3.raw"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
    except Exception as e:
        print(f"[ERROR] requests exception fetching {path}: {e}")
        return None
    if r.status_code == 200:
        return r.text
    else:
        print(f"[WARN] fetch file failed: {path} status:{r.status_code} body:{r.text[:400]}")
        return None

# -------------------
# OpenAI 분류기 (간단)
# -------------------
def classify_with_openai(code: str) -> dict:
    if not OPENAI_API_KEY:
        return {"tags": [], "difficulty": "unknown", "summary": "no api key", "time_complexity": ""}
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
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0
    }
    try:
        r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=30)
    except Exception as e:
        print("[ERROR] OpenAI request exception:", e)
        return {"tags": ["unknown"], "difficulty": "unknown", "summary": str(e)[:200], "time_complexity": ""}
    print("[OpenAI] status_code:", r.status_code)
    if r.status_code != 200:
        print("[OpenAI] body:", r.text[:800])
        return {"tags": ["unknown"], "difficulty": "unknown", "summary": f"OpenAI error {r.status_code}", "time_complexity": ""}
    try:
        text = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("[ERROR] OpenAI response parsing failed:", e)
        print("body:", r.text[:800])
        return {"tags": ["unknown"], "difficulty": "unknown", "summary": r.text[:200], "time_complexity": ""}
    try:
        parsed = json.loads(text)
    except Exception:
        print("[WARN] OpenAI did not return strict JSON; using raw text as summary")
        parsed = {"tags": ["unknown"], "difficulty": "unknown", "summary": text.strip()[:400], "time_complexity": ""}
    return parsed

# -------------------
# Notion에 페이지 생성
# -------------------
def create_notion_page(meta: dict):
    if not NOTION_TOKEN or not NOTION_DB_ID:
        print("[WARN] Notion creds missing, skipping create")
        return
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    properties = {
        "Name": {"title": [{"text": {"content": meta.get("title", "Unknown")}}]},
        "Platform": {"select": {"name": meta.get("platform", "GitHub")}},
        "Algorithm": {"multi_select": [{"name": t} for t in meta.get("tags", [])]},
        "Difficulty": {"select": {"name": meta.get("difficulty", "Unknown")}},
        "Language": {"select": {"name": meta.get("language", "Python")}},
        "URL": {"url": meta.get("url")},
    }
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": properties,
        "children": [
            {"object": "block", "type": "paragraph", "paragraph": {"text": [{"type": "text", "text": {"content": meta.get("summary", "")}}]}}
        ]
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
    except Exception as e:
        print("[ERROR] Notion request exception:", e)
        return
    print("[Notion] status_code:", r.status_code)
    if r.status_code not in (200, 201):
        print("[WARN] Notion create failed:", r.status_code, r.text[:800])
    else:
        print("[OK] Notion page created:", r.json().get("id"))

# -------------------
# 연결 테스트 (디버그용)
# -------------------
def test_openai_connectivity():
    if not OPENAI_API_KEY:
        print("[SKIP] OpenAI key missing")
        return
    try:
        r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, timeout=10)
        print("[OpenAI] connectivity status:", r.status_code)
        print("body-preview:", (r.text or "")[:400])
    except Exception as e:
        print("[OpenAI] exception:", e)

def test_notion_connectivity():
    if not NOTION_TOKEN or not NOTION_DB_ID:
        print("[SKIP] Notion creds missing")
        return
    try:
        url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}"
        r = requests.get(url, headers={"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28"}, timeout=10)
        print("[Notion] connectivity status:", r.status_code)
        print("body-preview:", (r.text or "")[:400])
    except Exception as e:
        print("[Notion] exception:", e)

# -------------------
# main
# -------------------
def main():
    try:
        print_envs()
        event = read_event()
        if not event:
            print("[ERR] no event payload -> exiting")
            return

        owner_repo = event.get("repository", {}).get("full_name", "")
        if not owner_repo:
            print("[ERR] repository info missing in event")
            return
        owner, repo = owner_repo.split("/")

        ref = event.get("ref", "main").split("/")[-1]
        changed_files = get_changed_files_from_event(event)

        # 폴백: event에서 파일을 못 가져오면 commit API로 조회
        if not changed_files:
            commit_id = event.get("after") or event.get("head_commit", {}).get("id")
            if commit_id:
                print("[INFO] changed_files empty -> fetching commit details for", commit_id)
                changed_files = fetch_files_from_commit(owner, repo, commit_id)
            else:
                print("[WARN] no commit id available")

        if not changed_files:
            print("[INFO] No changed files to process. Exiting.")
            # connectivity debug
            test_openai_connectivity()
            test_notion_connectivity()
            return

        # 실제 처리: 확장자 필터
        exts = [".py", ".cpp", ".c", ".java", ".js"]
        for path in changed_files:
            if not any(path.endswith(ext) for ext in exts):
                continue
            print("[PROCESS] handling:", path)
            content = get_file_raw(owner, repo, path, ref)
            if not content:
                print("[WARN] content not fetched for", path)
                continue
            parsed = classify_with_openai(content)
            meta = {
                "title": f"{repo}/{path}",
                "platform": "GitHub",
                "tags": parsed.get("tags", []),
                "difficulty": parsed.get("difficulty", "Unknown"),
                "language": "Python" if path.endswith(".py") else "Other",
                "url": f"https://github.com/{owner}/{repo}/blob/{ref}/{path}",
                "summary": parsed.get("summary", "")[:2000],
                "code_snippet": content[:1500]
            }
            create_notion_page(meta)

    except Exception:
        print("=== UNCAUGHT EXCEPTION ===")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
