# scripts/classify_and_push.py
# 디버그 + 실제 처리 통합 버전 (Python 3.11 권장)
# 주석은 이해하기 쉽게 한국어로 달아뒀습니다.

import os
import sys
import json
import time
import requests
import traceback
import re
from typing import List, Optional
from urllib.parse import quote
from html import unescape

# 환경변수 읽기
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# 사용자가 OPENAI_MODEL을 env로 주지 않으면 기본값 사용
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
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
    print("[ENV] OPENAI_MODEL:", OPENAI_MODEL)
    print("[ENV] GITHUB_EVENT_PATH:", GITHUB_EVENT_PATH)

def read_event() -> dict:
    if not os.path.isfile(GITHUB_EVENT_PATH):
        print("[EVENT-ERR] event file not found:", GITHUB_EVENT_PATH)
        return {}
    with open(GITHUB_EVENT_PATH, "r", encoding="utf-8") as f:
        e = json.load(f)
    print("[EVENT] loaded event, length:", len(json.dumps(e, ensure_ascii=False)))
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
# README.md 파서 (difficulty, url, perf, classification, problem_text 등)
# -------------------
def parse_readme(text: str) -> dict:
    """
    README.md 텍스트를 받아서 다음 항목을 추출하여 dict로 반환.
    - problem_url
    - perf_memory
    - perf_time
    - difficulty
    - problem_text
    - classification_text
    - classification_tags
    """
    if not text:
        return {
            "problem_url": "", "perf_memory": "", "perf_time": "",
            "difficulty": "", "problem_text": "",
            "classification_text": "", "classification_tags": []
        }

    # 0) difficulty 추출 (README 첫 번째 의미있는 라인에서 [..] 내용)
    difficulty = ""
    first_line = ""
    for ln in text.splitlines():
        if ln.strip():
            first_line = ln.strip()
            break
    if first_line:
        m_diff = re.search(r'\[([^\]]+)\]', first_line)
        if m_diff:
            difficulty = m_diff.group(1).strip()

    # 1) [문제 링크](url) or first url
    url_match = re.search(r'\[문제\s*링크\]\s*\(\s*(https?://[^\s\)]+)\s*\)', text)
    if not url_match:
        url_match = re.search(r'https?://[^\s\)]+', text)
    problem_url = url_match.group(1) if url_match else ""

    # 2) perf: memory/time
    mem_match = re.search(r'메모리[:\s]*([\d\.]+\s*MB)', text, flags=re.IGNORECASE)
    time_match = re.search(r'시간[:\s]*([\d\.]+\s*ms)', text, flags=re.IGNORECASE)
    perf_memory = mem_match.group(1) if mem_match else ""
    perf_time = time_match.group(1) if time_match else ""

    # cleaning util
    def _clean_block(block: str) -> str:
        # 코드블럭 제거
        block = re.sub(r"```[\s\S]*?```", "", block)
        # 인라인 코드 `...` -> 내용만 남기기
        block = re.sub(r'`([^`]+)`', r'\1', block)
        # HTML 태그 제거
        block = re.sub(r'<[^>]+>', '', block)
        # 여러 공백(유니코드 포함)을 일반 공백으로 바꾸고 줄 단위로 정리
        block = re.sub(r'[\u00A0\u2000-\u200A\u202F]', ' ', block)
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        return unescape("\n".join(lines)).strip()

    # 3) classification 섹션
    class_blocks = []
    # 헤딩 '분류' 또는 '구분' (1~6 레벨) 뒤의 블록들을 모두 찾음
    pattern = re.compile(r'#{1,6}\s*(?:분류|구분)\s*[\r\n]+([\s\S]+?)(?=\n#{1,6}\s|\n-{3,}\n|$)', flags=re.IGNORECASE)
    for m in pattern.finditer(text):
        raw = m.group(1)
        cleaned = _clean_block(raw)
        if cleaned:
            class_blocks.append(cleaned)

    class_text = "\n\n".join(class_blocks) if class_blocks else ""

    # ------------------
    # 각 블록을 태그로 토큰화
    # 전략:
    # 1) '>'로 경로 표시하면 각 경로 조각을 태그로 사용 (계층적 정보 유지)
    # 2) 아니면 줄 단위 목록 -> 각 줄을 항목으로 사용
    # 3) 한 줄의 경우 쉼표/슬래시/파이프/중점 등으로 분리, 없으면 공백으로 분리
    # 4) 괄호 내용 제거, 앞뒤 공백 제거
    # ------------------
    tags = []
    def _normalize_tag(t: str) -> str:
        t = re.sub(r'\(.*?\)', '', t)            # 괄호 안 내용 제거
        t = re.sub(r'[\u2000-\u200A\u00A0\u202F]', ' ', t)  # 특수 공백 정리
        t = t.replace('\uFEFF', '').strip()      # BOM 제거 가능성
        return re.sub(r'\s{2,}', ' ', t).strip()

    for block in class_blocks:
        # 우선 '>' 기반 분리 시도 (경로 표기)
        if '>' in block:
            parts = [p.strip() for p in re.split(r'\s*>\s*', block) if p.strip()]
            # 각 부분을 정제하여 추가 (예: "탐욕법(Greedy)" -> "탐욕법")
            for p in parts:
                nt = _normalize_tag(p)
                if nt and len(nt) > 0:
                    if nt not in tags:
                        tags.append(nt)
            # 또한 경로 전체(가장 상세한 경로)를 태그로 추가할 수도 있음 (옵션)
            # full_path = " > ".join([_normalize_tag(p) for p in parts if _normalize_tag(p)])
            # if full_path and full_path not in tags:
            #     tags.append(full_path)
            continue

        # 줄 단위로 목록이 있으면 각 줄 처리
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) > 1:
            for ln in lines:
                ln_clean = re.sub(r'^[\-\*\•\·\s]+', '', ln).strip()
                # 분리자로 나누기
                parts = re.split(r'[,\|/;·•\u2022\u2023]+', ln_clean)
                if len(parts) == 1:
                    parts = re.split(r'[\s]+', ln_clean)
                for p in parts:
                    nt = _normalize_tag(p)
                    if nt and len(nt) > 0 and len(nt) > 1:
                        if nt not in tags:
                            tags.append(nt)
            continue

        # 단일라인 블록: 구분자(콤마 등)로 분리, 없으면 공백 분리
        single = lines[0] if lines else block
        parts = re.split(r'[,\|/;·•\u2022\u2023]+', single)
        if len(parts) == 1:
            parts = re.split(r'[\s]+', single)
        for p in parts:
            nt = _normalize_tag(p)
            if nt and len(nt) > 0 and len(nt) > 1:
                if nt not in tags:
                    tags.append(nt)

    # 필터: 너무 짧은 토큰(1 char) 제외, 중복은 이미 제거됨
    classification_tags = [t for t in tags if len(t) > 1]

    # 4) problem description
    prob_text = ""
    m = re.search(r'#{1,6}\s*문제\s*설명\s*[\r\n]+([\s\S]+?)(?:\n#{1,6}\s|\n-{3,}\n|$)', text)
    if m:
        block = m.group(1)
        block = _clean_block(block)
        lines = block.splitlines()
        prob_text = " ".join(lines[:6]) if lines else ""
    else:
        s = _clean_block(text)
        prob_text = " ".join(s.splitlines()[:6])

    return {
        "problem_url": problem_url,
        "perf_memory": perf_memory,
        "perf_time": perf_time,
        "difficulty": difficulty,
        "problem_text": prob_text,
        "classification_text": class_text,
        "classification_tags": class_tags
    }

# -------------------
# OpenAI 분류기 (problem_text 옵션 추가, robust JSON parsing)
# -------------------
def _extract_first_json_block(text: str) -> Optional[str]:
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:i+1]
    return None

def _strip_code_fences_and_trailing(text: str) -> str:
    text = re.sub(r"```(?:[\s\S]*?)```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()

def classify_with_openai(code: str, problem_text: str = "", max_retries: int = 1) -> dict:
    """
    code: 코드 문자열
    problem_text: (옵션) README에서 추출한 문제 설명을 문자열로 전달
    반환: {"tags":[...], "review": "...", "time_complexity": "..."}
    """
    if not OPENAI_API_KEY:
        return {"tags": [], "review": "no api key", "time_complexity": ""}

    # 엄격한 JSON 출력 요구 + few-shot(짧게)
    prompt = f"""
당신은 코딩테스트 풀이 코드를 보고 알고리즘 태그와 간단한 코드리뷰를 JSON으로 반환하는 도우미입니다.
**중요**: 절대 다른 텍스트를 출력하지 말고, 오직 하나의 JSON 객체만 출력하세요. 형식은 정확히 아래 JSON 스키마를 따르세요.

스키마:
{{"tags": ["DP","그리디"], "review": "코드에 대한 간단한 리뷰(한두 문장)", "time_complexity": "O(n)"}}

예시:
{{"tags":["그리디"], "review":"정렬 후 탐색으로 해결. 경계조건 체크 필요.", "time_complexity":"O(n log n)"}}

아래 문제 설명(있으면)과 코드를 참고하여 태그와 리뷰를 작성하세요.
문제 설명:
{problem_text}
코드:
{code}
"""

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {"model": OPENAI_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0}

    attempt = 0
    last_text = ""
    while True:
        attempt += 1
        try:
            r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=30)
        except Exception as e:
            print("[ERROR] OpenAI request exception:", e)
            return {"tags": [], "review": f"OpenAI request exception: {e}", "time_complexity": ""}

        print("[OpenAI] status_code:", r.status_code)
        try:
            last_text = r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print("[ERROR] OpenAI response parse failed:", e, (r.text or "")[:1000])
            last_text = r.text or ""

        # 1) 전체가 JSON인지 시도
        try:
            parsed = json.loads(last_text)
            if isinstance(parsed, dict) and ("tags" in parsed or "review" in parsed):
                return {
                    "tags": parsed.get("tags", []) if isinstance(parsed.get("tags", []), list) else [],
                    "review": str(parsed.get("review", ""))[:1200],
                    "time_complexity": str(parsed.get("time_complexity", ""))[:200]
                }
        except Exception:
            pass

        # 2) 정제 후 중괄호 블록 추출
        stripped = _strip_code_fences_and_trailing(last_text)
        candidate = _extract_first_json_block(stripped)
        if candidate:
            try:
                parsed = json.loads(candidate)
                return {
                    "tags": parsed.get("tags", []) if isinstance(parsed.get("tags", []), list) else [],
                    "review": str(parsed.get("review", ""))[:1200],
                    "time_complexity": str(parsed.get("time_complexity", ""))[:200]
                }
            except Exception as e:
                print("[WARN] extracted JSON parse failed:", e, candidate[:800])

        # 3) 재시도(모델에게 '오직 JSON만' 재요청) — 최대 max_retries 번만
        if attempt <= max_retries:
            print("[INFO] Attempting one retry asking model to return JSON only")
            retry_prompt = (
                "이전 응답에서 JSON이 섞여 나오거나 다른 텍스트가 포함되었습니다. "
                "아래는 이전 모델 응답입니다. 이 응답에서 **오직 하나의 JSON 객체만** 추출하여, "
                "아무 설명 없이 JSON만 다시 출력해 주세요.\n\n"
                f"RESPONSE:\n{last_text}\n\n"
                '스키마: {"tags": [..], "review": "..", "time_complexity": ".."}'
            )
            body = {"model": OPENAI_MODEL, "messages":[{"role":"user","content": retry_prompt}], "temperature": 0}
            time.sleep(0.3)
            continue

        # 4) 최종 fallback
        print("[WARN] Failed to obtain strict JSON from OpenAI; returning fallback")
        fallback = {
            "tags": [],
            "review": (last_text.strip().replace("\n", " ")[:400] if last_text else "model did not return JSON"),
            "time_complexity": ""
        }
        return fallback

# -------------------
# Notion helper: DB schema, wrapping values, create page
# -------------------
_DB_SCHEMA_CACHE = None

def get_database_schema():
    global _DB_SCHEMA_CACHE
    if _DB_SCHEMA_CACHE is not None:
        return _DB_SCHEMA_CACHE
    if not NOTION_TOKEN or not NOTION_DB_ID:
        print("[WARN] Notion creds missing - cannot fetch DB schema")
        return {}
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}"
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
    except Exception as e:
        print("[ERROR] get_database_schema request exception:", e)
        return {}
    if r.status_code != 200:
        print("[WARN] get_database_schema failed:", r.status_code, r.text[:1000])
        return {}
    data = r.json()
    props = data.get("properties", {})
    _DB_SCHEMA_CACHE = props
    print("[Notion] DB schema fetched. properties:", list(props.keys()))
    return props

def _wrap_value_for_property(prop_schema: dict, value):
    ptype = prop_schema.get("type")
    if ptype == "title":
        return {"title": [{"text": {"content": str(value)}}]}
    if ptype == "rich_text":
        return {"rich_text": [{"type": "text", "text": {"content": str(value)}}]}
    if ptype == "select":
        return {"select": {"name": str(value)}}
    if ptype == "multi_select":
        if isinstance(value, (list, tuple)):
            return {"multi_select": [{"name": str(v)} for v in value]}
        else:
            return {"multi_select": [{"name": str(value)}]}
    if ptype == "url":
        return {"url": str(value)}
    if ptype == "number":
        try:
            return {"number": float(value)}
        except Exception:
            return {"number": None}
    if ptype == "checkbox":
        return {"checkbox": bool(value)}
    if ptype == "date":
        return {"date": {"start": str(value)}}
    if ptype == "people":
        return {"people": []}
    return {"rich_text": [{"type": "text", "text": {"content": str(value)}}]}

def create_notion_page(meta: dict):
    """
    meta: {
      title, platform, tags(list), difficulty, language, url,
      problem_text, classification_text, review, time_complexity,
      perf_memory, perf_time, code_snippet
    }
    DB 스키마에 따라 properties를 안전하게 포장하고,
    children에 problem_text/classification_text/review/perf/code를 추가합니다.
    """
    if not NOTION_TOKEN or not NOTION_DB_ID:
        print("[WARN] Notion creds missing, skipping create")
        return

    schema = get_database_schema()
    properties_payload = {}

    mapping = {
        "Name": meta.get("title", ""),
        "Platform": meta.get("platform", ""),
        "Algorithm": meta.get("tags", []),
        "Difficulty": meta.get("difficulty", ""),
        "Language": meta.get("language", ""),
        "URL": meta.get("url", "")
    }

    for prop_name, val in mapping.items():
        if prop_name not in schema:
            print(f"[INFO] property '{prop_name}' not found in DB schema - skipping")
            continue
        prop_schema = schema[prop_name]
        wrapped = _wrap_value_for_property(prop_schema, val)
        properties_payload[prop_name] = wrapped

    # children: 순서대로 문제링크/문제설명/분류/성능/리뷰/코드
    children = []

    # 1) 문제 URL을 명시적으로 보여주려면 paragraph + link 텍스트로 추가
    if meta.get("url"):
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": f"문제 링크: {meta.get('url')}", "link": {"url": meta.get("url")}}}
                ]
            }
        })

    # 2) 문제 설명
    if meta.get("problem_text"):
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": meta.get("problem_text")}}]}
        })

    # 3) classification_text (README의 분류 섹션 원문)
    if meta.get("classification_text"):
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"분류(README): {meta.get('classification_text')}"}}]}
        })

    # 4) 성능 요약
    perf_lines = []
    if meta.get("perf_memory"):
        perf_lines.append(f"메모리: {meta.get('perf_memory')}")
    if meta.get("perf_time"):
        perf_lines.append(f"시간: {meta.get('perf_time')}")
    if perf_lines:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": " | ".join(perf_lines)}}]}
        })

    # 5) LLM 리뷰 및 시간복잡도
    if meta.get("review"):
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"LLM 리뷰: {meta.get('review')}"}}]}
        })
    if meta.get("time_complexity"):
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"추정 시간복잡도: {meta.get('time_complexity')}"}}]}
        })

    # 6) 코드 블록 (길면 자름)
    code_snippet = meta.get("code_snippet", "")
    if code_snippet:
        # Notion이 허용하는 언어 키로 매핑(확장자에서 결정된 meta['language'] 기대)
        lang = (meta.get("language") or "").strip().lower()
        # Notion에서 허용되는 언어를 간단히 추정 (많은 항목 허용)
        allowed = {"python","javascript","java","c","c++","c#","rust","go","kotlin","ruby","plain text"}
        if lang not in allowed:
            lang = "plain text"
        children.append({
            "object": "block",
            "type": "code",
            "code": {
                "rich_text": [{"type": "text", "text": {"content": code_snippet[:15000]}}],
                "language": lang
            }
        })

    payload = {"parent": {"database_id": NOTION_DB_ID}, "properties": properties_payload}
    if children:
        payload["children"] = children

    url = "https://api.notion.com/v1/pages"
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=25)
    except Exception as e:
        print("[ERROR] Notion request exception:", e)
        return
    print("[Notion] status_code:", r.status_code)
    if r.status_code not in (200, 201):
        print("[WARN] Notion create failed:", r.status_code, r.text[:1000])
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
# 확장자 -> Notion 언어 매핑 유틸
# -------------------
def ext_to_language(path: str) -> str:
    path = path.lower()
    if path.endswith(".py"):
        return "python"
    if path.endswith(".js"):
        return "javascript"
    if path.endswith(".java"):
        return "java"
    if path.endswith(".cpp") or path.endswith(".cc") or path.endswith(".cxx") or path.endswith(".c++"):
        return "c++"
    if path.endswith(".c"):
        return "c"
    if path.endswith(".cs"):
        return "c#"
    if path.endswith(".kt") or path.endswith(".kts"):
        return "kotlin"
    # fallback
    return "plain text"

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
            test_openai_connectivity()
            test_notion_connectivity()
            return

        # README 파싱 (같은 폴더에 README가 있으면 붙여넣기)
        attach_map = {}
        for fpath in changed_files:
            if fpath.endswith("README.md") or fpath.lower().endswith("readme.md"):
                content = get_file_raw(owner, repo, fpath, ref)
                if content:
                    parsed_md = parse_readme(content)
                    folder = os.path.dirname(fpath)
                    attach_map[folder] = parsed_md
                    print(f"[INFO] parsed README for folder {folder}: {parsed_md}")

        # 처리할 확장자
        exts = [".py", ".cpp", ".c", ".java", ".js"]
        for path in changed_files:
            if not any(path.endswith(ext) for ext in exts):
                continue
            print("[PROCESS] handling:", path)
            content = get_file_raw(owner, repo, path, ref)
            if not content:
                print("[WARN] content not fetched for", path)
                continue

            folder = os.path.dirname(path)
            readme_info = attach_map.get(folder, {})
            problem_text = readme_info.get("problem_text", "") if readme_info else ""
            problem_url = readme_info.get("problem_url", "") if readme_info else ""
            perf_memory = readme_info.get("perf_memory", "") if readme_info else ""
            perf_time = readme_info.get("perf_time", "") if readme_info else ""
            difficulty = readme_info.get("difficulty", "") if readme_info else ""
            classification_text = readme_info.get("classification_text", "") if readme_info else ""
            classification_tags = readme_info.get("classification_tags", []) if readme_info else []

            # LLM 분류 (문제 설명 포함)
            parsed = classify_with_openai(content, problem_text=problem_text)

            # tags 병합: README 분류 우선, LLM 태그 추가, 중복 제거
            llm_tags = parsed.get("tags", []) or []
            tags = []
            # 우선 README tags (원문) 넣고, LLM 태그 추가
            for t in classification_tags + llm_tags:
                if isinstance(t, str) and t.strip():
                    tt = t.strip()
                    if tt not in tags:
                        tags.append(tt)

            # language 결정
            language = ext_to_language(path)

            # --- 파일명에서 확장자 제거하고 '제목' 만들기 ---
            filename = os.path.basename(path)            # "이어 붙인 수.py" 또는 "이어 붙인 수.py"
            name_no_ext, _ext = os.path.splitext(filename)  # ("이어 붙인 수", ".py")
            
            # 정제: 유니코드 공백(넓은 공백, NBSP 등)들을 일반 공백으로 바꾸고 중복 공백은 하나로 축소
            # 주요 유니코드 공백들: \u00A0 (NBSP), \u2000-\u200A (various spaces), \u202F, \u2005, BOM \uFEFF 등
            title = re.sub(r'[\u00A0\u2000-\u200A\u202F\u2005\uFEFF]', ' ', name_no_ext)  # 특수 공백 정리
            title = unescape(title)                          # 혹시 HTML 이스케이프가 있으면 되돌리기
            title = re.sub(r'\s+', ' ', title).strip()       # 연속 공백 -> 하나, 앞뒤 공백 제거

            # --- platform 추출 ---
            raw_platform = path.split('/', 1)[0] if '/' in path else path
            # 정리: 유니코드 공백 정리 및 앞뒤 공백 제거
            platform = re.sub(r'[\u00A0\u2000-\u200A\u202F]', ' ', raw_platform).strip()

            meta = {
                "title": title,
                "platform": platform,
                "tags": tags,
                "difficulty": difficulty,
                "language": language,
                "url": problem_url or f"https://github.com/{owner}/{repo}/blob/{ref}/{path}",
                "problem_text": problem_text,
                "classification_text": classification_text,
                "review": parsed.get("review", "")[:2000],
                "time_complexity": parsed.get("time_complexity", ""),
                "perf_memory": perf_memory,
                "perf_time": perf_time,
                "code_snippet": content[:1500]
            }
            create_notion_page(meta)

    except Exception as e:
        print("=== UNCAUGHT EXCEPTION ===", e)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
