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
