-- 혜택존 방문·클릭 집계 — 날짜별 개수만 (개인정보 없음)
CREATE TABLE IF NOT EXISTS daily (
  day   TEXT    NOT NULL,   -- 한국 날짜 YYYY-MM-DD
  page  TEXT    NOT NULL,   -- main | hotdeal
  type  TEXT    NOT NULL,   -- visit | card | toc | source | share | home | buy | filter | sort | more | cat | search
  label TEXT    NOT NULL,   -- 무엇을 눌렀는지 (브랜드명, 카테고리 등)
  n     INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, page, type, label)
);

-- 쿠팡 검색 결과 임시 저장 (검색어 → 결과 JSON, 만료 시각). 방문자 정보는 없음
CREATE TABLE IF NOT EXISTS search_cache (
  q    TEXT    PRIMARY KEY,   -- 검색어 (소문자·공백 정리) 또는 '__cooldown__'
  body TEXT    NOT NULL,
  exp  INTEGER NOT NULL       -- 만료 (유닉스 초)
);
