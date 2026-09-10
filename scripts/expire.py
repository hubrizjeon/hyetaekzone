#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""기간 지난 혜택 자동 정리 — 매일 00:05 (GitHub Actions) 에 돈다.

카드 뱃지의 날짜를 읽어 종료일이 오늘(한국 날짜)보다 앞선 혜택 카드를 내린다.
- 날짜를 분명히 읽을 수 있는 카드만 판단한다 ("상시", "추석 전", "9월 중순" 같은 건 그대로 둔다)
- 핫딜(PARTNERS 블록)은 건드리지 않는다
- 새 혜택을 넣지는 않는다 (그건 야간 갱신의 일). 그래서 푸터의 '콘텐츠 최종 갱신' 날짜도 바꾸지 않는다

  python3 scripts/expire.py                    정리
  python3 scripts/expire.py --check            무엇을 내릴지만 출력
  python3 scripts/expire.py --check --today 2026-09-14   날짜를 바꿔 점검
"""
import argparse, calendar, datetime, html, os, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
P_START, P_END = "<!-- PARTNERS:START", "<!-- PARTNERS:END -->"
EMPTY = '<p class="hz-empty" style="font-size:17px;color:var(--mut);margin:4px 0 14px">새 소식을 준비하고 있어요. 곧 채워집니다.</p>'


def _d(y, m, d):
    try:
        return datetime.date(int(y), int(m), int(d))
    except ValueError:
        return None


def end_date(badge, today):
    """뱃지 글자에서 종료일을 읽는다. 여러 개면 가장 늦은 날(예: 발급 ~11.30 · 사용 ~12.31 → 12.31)."""
    b = html.unescape(re.sub(r"<[^>]+>", "", badge))
    yr = re.search(r"(20\d{2})", b)
    year = int(yr.group(1)) if yr else today.year
    ends = []
    for m in re.finditer(r"(\d{4})\.(\d{1,2})\.(\d{1,2})\s*~\s*(?:(\d{4})\.)?(\d{1,2})\.(\d{1,2})", b):
        ends.append(_d(m.group(4) or m.group(1), m.group(5), m.group(6)))          # 2026.9.10 ~ 9.16
    for m in re.finditer(r"~\s*(\d{4})\.(\d{1,2})\.(\d{1,2})", b):
        ends.append(_d(m.group(1), m.group(2), m.group(3)))                        # ~2026.9.30
    for m in re.finditer(r"~\s*(\d{1,2})[./](\d{1,2})(?![./]?\d)", b):
        ends.append(_d(year, m.group(1), m.group(2)))                              # ~12/31, ~ 9.16
    for m in re.finditer(r"(\d{4})-(\d{2})-(\d{2})\s*~\s*(?:(\d{4})-)?(\d{2})-(\d{2})", b):
        ends.append(_d(m.group(4) or m.group(1), m.group(5), m.group(6)))          # 2026-09-01 ~ 09-23
    for m in re.finditer(r"(\d{4})년\s*(\d{1,2})월\s*한\s*달", b):
        y, mo = int(m.group(1)), int(m.group(2))
        ends.append(_d(y, mo, calendar.monthrange(y, mo)[1]))                      # 2026년 9월 한 달
    ends = [e for e in ends if e]
    return max(ends) if ends else None


def card_spans(src):
    """혜택 카드(<div class="card …">…</div>)의 [시작, 끝) — 핫딜 블록 안은 제외"""
    ps, pe = src.find(P_START), src.find(P_END)
    spans = []
    for m in re.finditer(r'<div class="card(?:\s[^"]*)?">', src):
        s = m.start()
        if ps != -1 and ps <= s <= pe:
            continue
        depth = 0
        for t in re.finditer(r"<div\b|</div>", src[s:]):
            depth += -1 if t.group() == "</div>" else 1
            if depth == 0:
                spans.append((s, s + t.end()))
                break
    return spans


def run(src, today):
    removed, kept_unknown = [], 0
    for s, e in reversed(card_spans(src)):
        block = src[s:e]
        badge = re.search(r'<span class="badge[^"]*">(.*?)</span>', block, re.S)
        end = end_date(badge.group(1), today) if badge else None
        if end is None:
            kept_unknown += 1
            continue
        if end < today:
            where = re.search(r'<span class="where">(.*?)</span>', block, re.S)
            what = re.search(r'<div class="what">(.*?)</div>', block, re.S)
            removed.append((re.sub(r"<[^>]+>", "", where.group(1)) if where else "?",
                            re.sub(r"<[^>]+>", "", what.group(1))[:30] if what else "", end))
            s0 = src.rfind("\n", 0, s) + 1
            e0 = src.find("\n", e) + 1 or e
            if src[s0:s].strip() == "" and src[e:e0].strip() == "":
                s, e = s0, e0
            src = src[:s] + src[e:]
    # 카드가 하나도 안 남은 혜택 섹션에는 안내 한 줄
    for m in reversed(list(re.finditer(r'<section id="(\w+)"[^>]*>.*?</section>', src, re.S))):
        if m.group(1) == "hotdeal":
            continue
        body = m.group(0)
        if 'class="card' not in body and "hz-empty" not in body:
            at = m.start() + body.rfind("</section>")
            src = src[:at] + "  " + EMPTY + "\n  " + src[at:]
    return src, removed[::-1], kept_unknown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--today", help="YYYY-MM-DD (점검용)")
    a = ap.parse_args()
    today = (datetime.date.fromisoformat(a.today) if a.today
             else datetime.datetime.now(KST).date())
    old = INDEX.read_text(encoding="utf-8")
    new, removed, unknown = run(old, today)

    # 검증 — 핫딜 블록 그대로, div 짝, 섹션 수 그대로
    blk = lambda t: t[t.find(P_START):t.find(P_END)] if P_START in t else ""
    bal = lambda t: len(re.findall(r"<div\b", t)) - t.count("</div>")
    problems = []
    if blk(old) != blk(new):
        problems.append("핫딜 블록이 바뀜")
    if bal(old) != bal(new):
        problems.append("div 짝이 맞지 않음")
    if old.count("<section") != new.count("<section"):
        problems.append("섹션 수가 바뀜")
    if problems:
        print("❌ 검증 실패 — 파일을 바꾸지 않았습니다:", "; ".join(problems))
        return 1

    print(f"기준일 {today} · 내린 카드 {len(removed)}개 · 날짜를 읽을 수 없어 둔 카드 {unknown}개")
    for w, t, e in removed:
        print(f"  - {w} · {t} (종료 {e})")
    if a.check or not removed:
        if a.check:
            print("(--check: 파일은 바꾸지 않았습니다)")
        return 0
    tmp = INDEX.with_suffix(".html.tmp")
    tmp.write_text(new, encoding="utf-8")
    os.replace(tmp, INDEX)
    print("저장: index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
