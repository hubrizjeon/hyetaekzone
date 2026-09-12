-- 혜택존 회원·포인트 (D1: hyetaekzone-members). 방문 집계(hyetaekzone-stats)와 따로 둡니다.
-- 개인정보: 카카오 회원번호·닉네임, 현금 교환 신청 시 예금주·은행·계좌번호(암호화 저장).
CREATE TABLE IF NOT EXISTS members (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  kakao_id   TEXT    NOT NULL UNIQUE,
  nick       TEXT,
  sub_id     TEXT    UNIQUE,            -- 쿠팡 링크 이름표 (hzm00001)
  created    INTEGER NOT NULL,          -- 유닉스 초
  last_login INTEGER,
  is_admin   INTEGER NOT NULL DEFAULT 0,
  status     TEXT    NOT NULL DEFAULT 'ok',   -- ok | blocked
  memo       TEXT,                       -- 관리자 메모
  terms_ver  TEXT,                       -- 동의한 포인트 이용약관 버전
  terms_at   INTEGER
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
  commission   INTEGER NOT NULL DEFAULT 0,  -- 우리가 받는 쿠팡 수수료 (원)
  share        REAL    NOT NULL,        -- 수수료 중 회원에게 주는 비율 (주문이 처음 잡힐 때 설정값으로 고정)
  confirm_on   TEXT    NOT NULL,        -- 적립 확정일 YYYY-MM-DD (구매한 달의 다음 달 25일)
  confirmed_at INTEGER,                 -- 확정 처리한 시각
  points       INTEGER,                 -- 확정 때 고정한 포인트
  created_at   INTEGER,                 -- 우리 DB에 처음 잡힌 시각 (회원 알림용)
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
-- 포인트 움직임 (주문 적립 외): cashout 현금 교환(−) · refund 교환 반려 복구(+) · adjust 관리자 조정(±) · expire 소멸(−)
CREATE TABLE IF NOT EXISTS points_log (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  member_id INTEGER NOT NULL,
  kind      TEXT    NOT NULL,
  amount    INTEGER NOT NULL,
  memo      TEXT,
  admin     TEXT,
  at        INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS points_member ON points_log(member_id);
-- 현금 교환 신청. 계좌 정보는 AES-GCM 암호화(PII_KEY), 화면에는 뒤 4자리만
CREATE TABLE IF NOT EXISTS cashouts (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  member_id    INTEGER NOT NULL,
  nick         TEXT,                    -- 신청 당시 닉네임 (탈퇴 후에도 지급 기록 보관용)
  amount       INTEGER NOT NULL,        -- 교환 포인트
  tax          INTEGER NOT NULL DEFAULT 0,   -- 원천징수세액
  net          INTEGER,                 -- 실제 입금액 (amount − tax)
  bank         TEXT    NOT NULL,
  acct_mask    TEXT    NOT NULL,        -- ****1234
  pii          TEXT,                    -- 암호화된 {예금주, 은행, 계좌번호}. 반려 즉시·지급 5년 뒤 삭제
  status       TEXT    NOT NULL,        -- requested | paid | rejected
  reason       TEXT,
  requested_at INTEGER NOT NULL,
  done_at      INTEGER,
  admin        TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS cashouts_one_pending ON cashouts(member_id) WHERE status = 'requested';
CREATE TABLE IF NOT EXISTS settings (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  at     INTEGER NOT NULL,
  admin  TEXT    NOT NULL,
  action TEXT    NOT NULL,
  target TEXT,
  detail TEXT
);
CREATE TABLE IF NOT EXISTS sync_log (
  at   INTEGER PRIMARY KEY,
  ok   INTEGER NOT NULL,
  note TEXT
);
