"""노트 마크다운 조립/해체 — 순수 문자열 함수 모음.

TS 원본: src/app/api/chat/route.ts:153-186 (조립), src/lib/github.ts:128-131 (추출)

★ 왜 별도 파일인가:
  TS에서는 라우트 핸들러 한가운데에 템플릿 문자열이 박혀 있었다.
  외부 호출이 전혀 없는 순수 함수라, 떼어내면 테스트가 제일 쉬운 부분이 된다.
  (tests/test_markdown.py — 네트워크 없이 돈다)

여기 있는 형식은 **옵시디언 볼트의 파일 형식**이다. 바꾸면 기존 노트와 어긋나므로
`extract_summary` 가 옛 노트를 못 읽게 된다 → 재색인 시 조용히 스킵된다.
"""

import re
from datetime import date

# TS 대응: chat/route.ts:8
URL_PATTERN = re.compile(r"https?://[^\s]+")

# 파일명에 남길 문자: 영문/숫자/한글/공백. 나머지는 버린다.
# TS 대응: chat/route.ts:157
_FILENAME_ALLOWED = re.compile(r"[^a-zA-Z0-9가-힣\s]")
_WHITESPACE = re.compile(r"\s+")

# "## 요약" 섹션의 본문만. 다음 "## " 를 만나면 멈춘다.
# TS 대응: github.ts:129
_SUMMARY_SECTION = re.compile(r"##\s*요약\s*\n(.*?)(?=\n##\s|$)", re.DOTALL)

# 파일명 길이 상한. 경로 전체가 너무 길어지면 GitHub API 가 거부한다.
FILENAME_MAX = 50


def current_date_str() -> str:
    """오늘 날짜를 "2026-09-02" 형태로.

    ★ 이 형식이 세 군데에 묶여 있다. 한 곳에서 만들어야 어긋나지 않는다.
        build_filename  파일명 접두사
        build_note      프론트매터의 date:
        github._DATE_PREFIX  목록에서 접두사를 다시 벗겨내는 정규식
    """
    return date.today().isoformat()


def extract_url(text: str) -> str:
    """본문에서 첫 URL. 없으면 빈 문자열.

    노트의 `type: link | text` 와 `source:` 프론트매터를 정하는 데 쓴다.
    """
    match = URL_PATTERN.search(text)
    return match.group(0) if match else ""


def build_filename(title: str, date_str: str) -> str:
    """제목 → "2026-09-02-제목-슬러그" (확장자 없음).

    TS 대응: chat/route.ts:156-159

    ★ 날짜 접두사를 붙이는 이유: 같은 제목의 노트가 다른 날 또 들어와도 충돌하지 않고,
      파일 목록이 시간순으로 정렬된다. list_notes() 는 이 접두사를 다시 벗겨낸다.
    """
    slug = _FILENAME_ALLOWED.sub("", title)
    slug = _WHITESPACE.sub("-", slug.strip())[:FILENAME_MAX]
    return f"{date_str}-{slug}"


def build_note(
    *,
    title: str,
    summary: str,
    tags: list[str],
    category: str,
    date_str: str,
    original: str,
    related: list[str],
) -> str:
    """옵시디언 노트 .md 본문 조립.

    TS 대응: chat/route.ts:167-186

    구조:
        --- 프론트매터 ---   옵시디언이 읽는 메타데이터
        # 제목
        ## 요약              ← ★ 재색인(sync)이 이 섹션만 다시 읽어 임베딩한다
        ## 원본              사용자가 보낸 원문 그대로
        ## 태그
        ## 관련 노트          [[링크]] — 있을 때만
    """
    source_url = extract_url(original)
    tag_list = ", ".join(f'"{t}"' for t in tags)
    tag_line = " ".join(f"#{t}" for t in tags)

    related_section = ""
    if related:
        links = "\n".join(f"- [[{name}]]" for name in related)
        related_section = f"\n## 관련 노트\n{links}\n"

    return f"""---
title: "{title}"
date: {date_str}
tags: [{tag_list}]
category: {category}
type: {"link" if source_url else "text"}
source: "{source_url}"
---

# {title}

## 요약
{summary}

## 원본
{original}

## 태그
{tag_line}
{related_section}"""


def extract_summary(markdown: str) -> str:
    """저장된 .md 에서 "## 요약" 섹션 본문만 꺼낸다. 없으면 빈 문자열.

    TS 대응: github.ts:128-131

    ★ 재색인(sync)이 Gemini 를 다시 부르지 않는 이유가 이 함수다.
      요약은 이미 노트 안에 적혀 있으므로 읽어 쓰면 된다 — API 비용 0.
      단, "## 요약" 이 없는 옛 형식 노트는 빈 문자열이 나온다 → sync 에서 skip 처리.
    """
    match = _SUMMARY_SECTION.search(markdown)
    return match.group(1).strip() if match else ""
