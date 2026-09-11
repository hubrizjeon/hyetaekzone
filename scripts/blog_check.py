#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""블로그 원고 품질 검사 — 허수빈님 요청 기준 (2026-09-11)

  python3 scripts/blog_check.py blog/20260911.html

기준
  1. 본문 공백 제외 2,000자 이상 (검색 포털 노출)
  2. 사진 4~5장, 서로 다른 사진, 이전 원고에 쓴 사진 재사용 금지
  3. 이전 원고와 겹치는 문장 금지 — 같은 문장이나 80% 이상 비슷한 문장이 있으면 실패
     (해시태그·출처·안내 문구가 담긴 맨 아래 작은 글씨 칸은 비교에서 제외)
통과하면 종료코드 0, 하나라도 실패하면 1.
"""
import sys, re, html, glob, os, difflib

MIN_CHARS, MIN_PHOTOS, MAX_PHOTOS, SIM = 2000, 4, 5, 0.80

def body(path):
    s = open(path, encoding="utf-8").read()
    a = s.find('<div id="post">'); b = s.find('<script>', a)
    post = s[a:b if b > 0 else len(s)]
    # 맨 아래 작은 글씨 칸(해시태그·출처·안내)은 제외
    post = re.sub(r'<p style="font-size:13px;color:#aaa[^"]*">.*?</p>', '', post, flags=re.S)
    return post

def text(post):
    t = re.sub(r'<(br|/p|/li|/h\d|/div)[^>]*>', '\n', post)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', t))
    return t

def sentences(t):
    out = []
    for line in t.split('\n'):
        for s in re.split(r'(?<=[.!?])\s+', line.strip()):
            s = re.sub(r'\s+', ' ', s).strip()
            if len(s.replace(' ', '')) >= 15 and not re.fullmatch(r'\S*https?://\S+', s):
                out.append(s)   # 링크 주소 줄은 문장이 아니므로 제외
    return out

def photos(post):
    return re.findall(r'<img[^>]+src="([^"]+)"', post)

def main(target):
    tb = body(target); tt = text(tb)
    chars = len(re.sub(r'\s', '', tt))
    imgs = photos(tb)
    others = sorted(p for p in glob.glob(os.path.join(os.path.dirname(target), '2*.html'))
                    if os.path.abspath(p) != os.path.abspath(target))
    ok = True
    print(f"■ {target}")
    r = chars >= MIN_CHARS; ok &= r
    print(f"  {'✅' if r else '❌'} 글자 수: 공백 제외 {chars:,}자 (기준 {MIN_CHARS:,}자↑)")
    r = MIN_PHOTOS <= len(imgs) <= MAX_PHOTOS and len(set(imgs)) == len(imgs); ok &= r
    print(f"  {'✅' if r else '❌'} 사진: {len(imgs)}장 · 서로 다른 사진 {len(set(imgs))}장 (기준 {MIN_PHOTOS}~{MAX_PHOTOS}장)")
    used = set()
    for p in others: used |= set(photos(body(p)))
    reused = [i for i in imgs if i in used]
    r = not reused; ok &= r
    print(f"  {'✅' if r else '❌'} 사진 재사용: {len(reused)}장" + ("".join(f"\n       - {x.split('/')[-1]}" for x in reused)))
    prior = []
    for p in others: prior += [(os.path.basename(p), s) for s in sentences(text(body(p)))]
    dups = []
    for s in sentences(tt):
        for name, q in prior:
            ratio = difflib.SequenceMatcher(None, s, q).ratio()
            if ratio >= SIM:
                dups.append((ratio, s, name, q)); break
    r = not dups; ok &= r
    print(f"  {'✅' if r else '❌'} 이전 원고와 겹치는 문장: {len(dups)}개 (비교 대상 {len(others)}편)")
    for ratio, s, name, q in dups[:10]:
        print(f"       - {int(ratio*100)}% · {s[:48]}…  ↔ {name}")
    print(f"  {'🟢 통과' if ok else '🔴 불합격'}")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
