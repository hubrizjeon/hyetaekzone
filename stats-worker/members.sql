-- 혜택존 회원·포인트 (D1: hyetaekzone-members). 방문 집계(hyetaekzone-stats)와 따로 둡니다.
-- 저장하는 개인정보: 카카오 회원번호, 닉네임뿐. 탈퇴하면 회원·주문 기록을 지웁니다.
CREATE TABLE IF NOT EXISTS members (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  kakao_id   TEXT    NOT NULL UNIQUE,
  nick       TEXT,
  sub_id     TEXT    UNIQUE,            -- 쿠팡 링크 이름표 (hzm00001)
  created    INTEGER NOT NULL,          -- 유닉스 초
  last_login INTEGER
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT    PRIMARY KEY,       -- 로그인 토큰의 SHA-256 (토큰 자체는 저장 안 함)
  member_id  INTEGER NOT NULL,
  exp        INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_member ON sessions(member_id);
-- 쿠팡 주문 리포트에서 회원 이름표(hzm…)가 붙은 줄만 옮겨 둡니다
CREATE TABLE IF NOT EXISTS orders (
  order_id     TEXT    NOT NULL,
  product_id   TEXT    NOT NULL,
  sub_id       TEXT    NOT NULL,
  day          TEXT    NOT NULL,        -- 구매일 YYYYMMDD
  name         TEXT,
  qty          INTEGER,
  gmv          INTEGER NOT NULL,        -- 구매금액 (원)
  confirm_on   TEXT    NOT NULL,        -- 적립 확정일 YYYY-MM-DD (구매한 달의 다음 달 25일)
  confirmed_at INTEGER,                 -- 확정 처리한 시각
  points       INTEGER,                 -- 확정 때 고정한 포인트
  PRIMARY KEY (order_id, product_id)
);
CREATE INDEX IF NOT EXISTS orders_sub ON orders(sub_id);
CREATE TABLE IF NOT EXISTS cancels (
  order_id   TEXT    NOT NULL,
  product_id TEXT    NOT NULL,
  day        TEXT    NOT NULL,
  gmv        INTEGER NOT NULL,          -- 취소·반품 금액 (양수)
  PRIMARY KEY (order_id, product_id, day)
);
CREATE TABLE IF NOT EXISTS sync_log (
  at   INTEGER PRIMARY KEY,
  ok   INTEGER NOT NULL,
  note TEXT
);
