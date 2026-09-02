"""마크다운 조립/해체 — 외부 호출이 전혀 없는 순수 함수."""

from app.core import markdown


def test_build_filename_strips_symbols_and_joins_with_dash():
    name = markdown.build_filename("React 서버 컴포넌트! (RSC)", "2026-09-02")
    assert name == "2026-09-02-React-서버-컴포넌트-RSC"


def test_build_filename_truncates_long_titles():
    name = markdown.build_filename("가" * 200, "2026-09-02")
    # 날짜 접두사(11자)를 뺀 나머지가 상한을 넘지 않아야 한다
    assert len(name) == len("2026-09-02-") + markdown.FILENAME_MAX


def test_build_note_marks_link_type_when_url_present():
    note = markdown.build_note(
        title="제목",
        summary="요약문",
        tags=["a", "b"],
        category="articles",
        date_str="2026-09-02",
        original="참고 https://example.com/x 링크",
        related=[],
    )
    assert "type: link" in note
    assert 'source: "https://example.com/x"' in note
    assert "## 관련 노트" not in note  # related 가 비면 섹션 자체가 없어야 한다


def test_build_note_includes_related_links():
    note = markdown.build_note(
        title="제목",
        summary="요약문",
        tags=[],
        category="concepts",
        date_str="2026-09-02",
        original="URL 없는 메모",
        related=["노트A", "노트B"],
    )
    assert "type: text" in note
    assert "- [[노트A]]" in note and "- [[노트B]]" in note


def test_extract_summary_roundtrips_with_build_note():
    """★ 이 왕복이 깨지면 재색인이 조용히 전부 스킵된다.

    build_note 형식을 바꿀 때 이 테스트가 먼저 알려준다.
    """
    summary = "핵심만 적은 요약.\n두 번째 줄."
    note = markdown.build_note(
        title="제목",
        summary=summary,
        tags=["t"],
        category="concepts",
        date_str="2026-09-02",
        original="원문",
        related=["다른노트"],
    )
    assert markdown.extract_summary(note) == summary


def test_extract_summary_returns_empty_for_old_format():
    assert markdown.extract_summary("# 제목\n본문만 있는 옛 노트") == ""
