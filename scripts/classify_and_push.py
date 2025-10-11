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
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
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
def _extract_first_json_block(text: str) -> str | None:
    """
    응답 텍스트에서 첫 번째 균형잡힌 중괄호 블록을 추출.
    단순 regex보다 안정적: 스택으로 중괄호 개수 카운트.
    """
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
    """```...```나 ```json ...``` 같은 코드펜스 제거, 앞뒤 공백 제거"""
    # 코드펜스 전체를 제거
    text = re.sub(r"```(?:[\s\S]*?)```", "", text)
    # 혹은 마크다운 한줄 코드 `...` 제거
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()

def classify_with_openai(code: str, max_retries: int = 1) -> dict:
    """
    견고한 LLM 분류기
    - code: 코드 문자열
    - 반환: {"tags": [...], "review": "...", "time_complexity": "..."}
    """
    if not OPENAI_API_KEY:
        return {"tags": [], "review": "no api key", "time_complexity": ""}

    # 위에서 제안한 엄격한 prompt (few-shot 포함)
    prompt = f"""
당신은 코딩테스트 풀이 코드를 보고 알고리즘 태그와 간단한 코드리뷰를 JSON으로 반환하는 도우미입니다.
**중요**: 절대 다른 텍스트를 출력하지 말고, 오직 하나의 JSON 객체만 출력하세요. 형식은 정확히 아래 JSON 스키마를 따르세요.

스키마:
{
  "tags": ["DP","그리디"],          
  "review": "제출 코드에 대한 코드리뷰, 정확성 및 효율성 검토(한두 문장)",
  "time_complexity": "O(n)"          
}

예시1:
(코드 생략) -> 출력:
{"tags":["그리디"], "review":"정렬 후 탐색으로 해결. 경계조건 체크 필요.", "time_complexity":"O(n log n)"}

예시2:
(코드 생략) -> 출력:
{"tags":["그래프","BFS"], "review":"BFS로 최단 경로 탐색, 방문체크 누락 주의", "time_complexity":"O(V+E)"}

아래 코드만 보고 판단하세요. **다른 설명은 금지**.
```
{code}
```
    """

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {"model": OPENAI_MODEL, "messages":[{"role":"user","content": prompt.replace("{code}", code)}], "temperature": 0}

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
            print("[ERROR] OpenAI response parse failed:", e, r.text[:1000])
            last_text = r.text or ""

        # 1) 응답 전체가 JSON일 가능성 시도
        try:
            parsed = json.loads(last_text)
            # 정상 JSON이면 필요한 키가 있는지 검사
            if isinstance(parsed, dict) and ("tags" in parsed or "review" in parsed):
                return {
                    "tags": parsed.get("tags", []) if isinstance(parsed.get("tags", []), list) else [],
                    "review": str(parsed.get("review", ""))[:1000],
                    "time_complexity": str(parsed.get("time_complexity", ""))[:200]
                }
        except Exception:
            pass

        # 2) 텍스트 정제 후 균형중괄호 블록 추출
        stripped = _strip_code_fences_and_trailing(last_text)
        candidate = _extract_first_json_block(stripped)
        if candidate:
            try:
                parsed = json.loads(candidate)
                return {
                    "tags": parsed.get("tags", []) if isinstance(parsed.get("tags", []), list) else [],
                    "review": str(parsed.get("review", ""))[:1000],
                    "time_complexity": str(parsed.get("time_complexity", ""))[:200]
                }
            except Exception as e:
                print("[WARN] extracted JSON parse failed:", e, candidate[:800])

        # 3) 재시도(모델에게 '오직 JSON만' 재요청) — 최대 max_retries 번만
        if attempt <= max_retries:
            print("[INFO] Attempting one retry asking model to return JSON only")
            # 재요청 프롬프트: 이전 응답을 첨부하고 JSON만 출력 요청
            retry_prompt = (
                "이전 응답에서 JSON이 섞여 나오거나 다른 텍스트가 포함되었습니다. "
                "아래는 이전 모델 응답입니다. 이 응답에서 **오직 하나의 JSON 객체만** 추출하여, "
                "아래 스키마에 맞춰 **아무 설명 없이** JSON만 다시 출력해 주세요.\n\n"
                f"RESPONSE:\n{last_text}\n\n"
                "스키마: {\"tags\": [..], \"review\": \"..\", \"time_complexity\": \"..\"}"
            )
            body = {"model": OPENAI_MODEL, "messages":[{"role":"user","content": retry_prompt}], "temperature": 0}
            # loop continues and will parse new last_text
            time.sleep(0.3)
            continue

        # 4) 최종 fallback: 최소 정보로 반환
        print("[WARN] Failed to obtain strict JSON from OpenAI; returning fallback")
        fallback = {
            "tags": [],
            "review": (last_text.strip().replace("\n", " ")[:400] if last_text else "model did not return JSON"),
            "time_complexity": ""
        }
        return fallback


# -------------------
# Notion에 페이지 생성
# -------------------
# Notion에 페이지 생성 (DB 스키마 읽어서 안전하게 매핑)
# 기존의 create_notion_page 함수를 아래로 대체하세요.

_DB_SCHEMA_CACHE = None  # 프로세스 내 캐시

def get_database_schema():
    """
    Notion 데이터베이스의 properties 스키마를 가져와서 캐시합니다.
    반환값: dict of { property_name: property_schema_dict }
    """
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
    """
    prop_schema: Notion property schema for that property (dict)
    value: meta 값 (str or list)
    반환: property payload (dict) - ready to put under properties[property_name]
    """
    ptype = prop_schema.get("type")
    # 안전한 변환들
    if ptype == "title":
        return {"title": [{"text": {"content": str(value)}}]}
    if ptype == "rich_text":
        return {"rich_text": [{"type": "text", "text": {"content": str(value)}}]}
    if ptype == "select":
        return {"select": {"name": str(value)}}
    if ptype == "multi_select":
        # value가 리스트면 각각 처리, 아니면 하나로 만듦
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
        # value가 ISO 날짜 문자열이면 그대로 넣음 (예: "2025-10-11")
        return {"date": {"start": str(value)}}
    if ptype == "people":
        # 사람은 id를 넣어야 하므로 기본으로 빈 배열
        return {"people": []}
    # fallback: rich_text로 넣기 (안전)
    return {"rich_text": [{"type": "text", "text": {"content": str(value)}}]}

def create_notion_page(meta: dict):
    """
    meta: {
      title, platform, tags(list), difficulty, language, url, summary, code_snippet
    }
    이 함수를 사용하면 DB 스키마에 맞춰 properties를 생성해서 Notion에 페이지를 만듭니다.
    """
    if not NOTION_TOKEN or not NOTION_DB_ID:
        print("[WARN] Notion creds missing, skipping create")
        return

    # 1) DB 스키마 로드
    schema = get_database_schema()
    if not schema:
        print("[WARN] DB schema unavailable, attempt minimal create with children only")
    properties_payload = {}

    # mapping: 메타 필드명 -> Notion DB 컬럼명 (사용자 DB 컬럼명이 다르다면 여기를 수정)
    # 보통 스크린샷대로라면 "Name", "Platform", "Algorithm", "Difficulty", "Language", "URL"
    # 필요시 여기에 DB 컬럼명과 meta 키를 조정하세요.
    mapping = {
        "Name": meta.get("title", ""),
        "Platform": meta.get("platform", ""),
        "Algorithm": meta.get("tags", []),      # list expected
        "Difficulty": meta.get("difficulty", ""),
        "Language": meta.get("language", ""),
        "URL": meta.get("url", "")
    }

    # 2) schema에 맞게 properties 구성
    for prop_name, val in mapping.items():
        if prop_name not in schema:
            # DB에 해당 컬럼이 없으면 건너뜀 (또는 fallback으로 rich_text 필드에 추가)
            print(f"[INFO] property '{prop_name}' not found in DB schema - skipping")
            continue
        prop_schema = schema[prop_name]
        wrapped = _wrap_value_for_property(prop_schema, val)
        properties_payload[prop_name] = wrapped

    # 3) children (summary + code) - Notion이 요구하는 형식으로 생성
    children = []
    summary_text = meta.get("summary", "")
    if summary_text:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": summary_text}}
                ]
            }
        })
    code_snippet = meta.get("code_snippet", "")
    if code_snippet:
        allowed_languages = {
            "abap","abc","agda","arduino","ascii art","assembly","bash","basic","bnf","c","c#","c++",
            "clojure","coffeescript","coq","css","dart","dhall","diff","docker","ebnf","elixir","elm",
            "erlang","f#","flow","fortran","gherkin","glsl","go","graphql","groovy","haskell","hcl","html",
            "idris","java","javascript","json","julia","kotlin","latex","less","lisp","livescript","llvm ir",
            "lua","makefile","markdown","markup","matlab","mathematica","mermaid","nix","notion formula",
            "objective-c","ocaml","pascal","perl","php","plain text","powershell","prolog","proto","python",
            "r","reason","ruby","rust","sass","scala","scheme","scss","shell","smalltalk","solidity","sql",
            "swift","tcl","toml","typescript","vb.net","vb","verilog","vhdl","vim","xml","yaml"
        }
        
        # 사용자가 준 meta language를 정규화
        lang = (meta.get("language") or "").strip()
        lang_low = lang.lower()

        # mapping for common variants
        lang_aliases = {
            "py": "python",
            "py3": "python",
            "python3": "python",
            "csharp": "c#",
            "cs": "c#",
            "cpp": "c++",
            "js": "javascript",
            "ts": "typescript",
            "plain": "plain text",
            "text": "plain text",
            # 필요하면 여기에 더 추가 가능
        }

        # 1) 직접 허용 리스트에 있는지 확인
        chosen_lang = None
        if lang_low in allowed_languages:
            chosen_lang = lang_low
        # 2) alias로 매핑 가능한지 확인
        elif lang_low in lang_aliases:
            chosen_lang = lang_aliases[lang_low]
        # 3) 대소문자 문제일 수 있으니 소문자/공백 제거 후 재검사
        else:
            candidate = lang_low.replace(" ", "")
            if candidate in lang_aliases:
                chosen_lang = lang_aliases[candidate]
            elif candidate in allowed_languages:
                chosen_lang = candidate

        # 4) 마지막 폴백: 'plain text'로 안전하게 지정
        if not chosen_lang:
            print(f"[INFO] language '{meta.get('language')}' not in allowed list - falling back to 'plain text'")
            chosen_lang = "plain text"
        
        children.append({
            "object": "block",
            "type": "code",
            "code": {
                "rich_text": [
                    {"type": "text", "text": {"content": code_snippet}}
                ],
                "language": chosen_lang
            }
        })

    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": properties_payload,
    }
    if children:
        payload["children"] = children

    # 4) 요청
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
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
