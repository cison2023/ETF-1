"""
stock_github.py — GitHub Actions 전용 시세 업데이터
- 경로: 스크립트와 동일 폴더의 ETF_index_Ver3_1.html 자동 탐색
- 로컬 PC 경로 불필요

★ GitHub Actions 권장 스케줄 (UTC 기준):
   - cron: '30 9 * * 1-5'  → 한국시간 18:30 (안정적)
   - cron: '0 8 * * 1-5'   → 한국시간 17:00 (이른 경우 재시도)
"""
import FinanceDataReader as fdr
import json, os, re, time
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(BASE_DIR, 'ETF_index_Ver4_1.html')
JSON_FILE = os.path.join(BASE_DIR, 'prices.json')
KEEP_DAYS = 35

# 당일 데이터 미반영 시 재시도 설정
MAX_RETRY       = 3    # 최대 재시도 횟수
RETRY_WAIT_SEC  = 300  # 재시도 대기 (초) — GitHub Actions는 5분 여유 있음

my_etfs = [
    '476800','0008S0','0052D0','498410','466940','498400','489030','475720',
    '474220','441680','482730','458760','088980','0086B0','352540','0089D0',
    '0098N0','0097L0','0105E0','329200','481060','0153K0','433970','0025N0','486290',
    '457480'  # ACE 테슬라밸류체인액티브
]

# ─────────────────────────────────────────────
# 오늘 날짜 데이터 반영 여부 확인
# ─────────────────────────────────────────────
def is_today_in_data(history: dict) -> bool:
    today = datetime.now().strftime('%Y-%m-%d')
    return today in history

# ─────────────────────────────────────────────
# 기존 데이터 로드
# ─────────────────────────────────────────────
master_history = {}
if os.path.exists(JSON_FILE):
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        try:
            raw = json.load(f)
            master_history = {d: v for d, v in raw.items()
                              if re.match(r'^\d{4}-\d{2}-\d{2}$', str(d))}
        except Exception:
            master_history = {}

today_str = datetime.now().strftime('%Y-%m-%d')
is_weekday = datetime.now().weekday() < 5  # 평일 여부

print(f"🚀 시세 업데이트 시작 (기존 보관: {len(master_history)}일)")
print(f"   오늘: {today_str} ({'평일' if is_weekday else '주말'})")

# ─────────────────────────────────────────────
# ETF 시세 수집 함수 (1회)
# ─────────────────────────────────────────────
def fetch_once():
    success_cnt, fail_list = 0, []
    for code in my_etfs:
        try:
            start_dt = (datetime.now() - timedelta(days=50)).strftime('%Y-%m-%d')
            df = fdr.DataReader(code, start=start_dt)
            if df.empty:
                fail_list.append(code)
                continue

            latest_date = df.index[-1].strftime('%Y-%m-%d')
            if is_weekday and latest_date < today_str:
                print(f"  ⏳ {code}: 소스 미반영 (최신={latest_date})")
            else:
                print(f"  ✅ {code} (최신={latest_date})")

            for i in range(1, len(df)):
                date_str = df.index[i].strftime('%Y-%m-%d')
                if date_str not in master_history:
                    master_history[date_str] = {}
                master_history[date_str][code] = {
                    'today': int(df['Close'].iloc[i]),
                    'prev':  int(df['Close'].iloc[i - 1]),
                    'src':   'Python'
                }
            success_cnt += 1
        except Exception as e:
            fail_list.append(code)
            print(f"  ❌ {code}: {e}")
    return success_cnt, fail_list

# ─────────────────────────────────────────────
# 수집 + 재시도 루프
# ─────────────────────────────────────────────
success_cnt, fail_list = 0, []
for attempt in range(1, MAX_RETRY + 1):
    print(f"\n[시도 {attempt}/{MAX_RETRY}]")
    success_cnt, fail_list = fetch_once()

    if is_weekday and not is_today_in_data(master_history):
        if attempt < MAX_RETRY:
            print(f"⏳ 당일({today_str}) 데이터 미반영 → {RETRY_WAIT_SEC}초 대기 후 재시도...")
            time.sleep(RETRY_WAIT_SEC)
        else:
            print(f"⚠️  최대 재시도 초과. 당일 데이터 없이 저장합니다.")
    else:
        if is_weekday and is_today_in_data(master_history):
            print(f"✅ 당일({today_str}) 데이터 반영 확인!")
        break

# ─────────────────────────────────────────────
# 오래된 데이터 정리
# ─────────────────────────────────────────────
limit_date     = (datetime.now() - timedelta(days=KEEP_DAYS)).strftime('%Y-%m-%d')
cleaned        = {d: v for d, v in master_history.items() if d >= limit_date}
sorted_history = dict(sorted(cleaned.items(), reverse=True))

# prices.json 저장
with open(JSON_FILE, 'w', encoding='utf-8') as f:
    json.dump(sorted_history, f, ensure_ascii=False, indent=2)
print(f"\n💾 prices.json 저장 완료")

# ─────────────────────────────────────────────
# HTML 내 PYTHON_PRICES_DATA 블록 교체
# ─────────────────────────────────────────────
if not os.path.exists(HTML_FILE):
    print(f"⚠️  HTML 파일 없음: {HTML_FILE}")
else:
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html_content = f.read()

    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    prices_json  = json.dumps(sorted_history, ensure_ascii=False)
    new_block = (
        f'<!-- ★ 아래 블록은 stock.py가 자동으로 덮어씁니다. 수동 편집 금지 -->\n'
        f'<script id="py-prices-block">\n'
        f'// stock.py 업데이트: {generated_at}\n'
        f'window.PYTHON_PRICES_DATA = {prices_json};\n'
        f'</script>'
    )
    pattern = (r'<!-- ★ 아래 블록은 stock\.py가 자동으로 덮어씁니다\. 수동 편집 금지 -->'
               r'.*?</script>')
    updated, n = re.subn(pattern, new_block, html_content, flags=re.DOTALL)
    if n > 0:
        with open(HTML_FILE, 'w', encoding='utf-8') as f:
            f.write(updated)
        print(f"🌐 HTML 시세 블록 업데이트 완료 → ETF_index_Ver3_1.html")
    else:
        print(f"⚠️  HTML 내 시세 블록 패턴을 찾지 못했습니다")

# ─────────────────────────────────────────────
# 결과 요약
# ─────────────────────────────────────────────
dates     = list(sorted_history.keys())
newest    = dates[0]  if dates else 'N/A'
oldest    = dates[-1] if dates else 'N/A'
today_ok  = is_today_in_data(sorted_history) if is_weekday else True
today_msg = "✅ 당일 반영" if today_ok else "⚠️  당일 미반영 (소스 지연 — 나중에 재실행 권장)"

print(f"\n{'='*55}")
print(f"  ✔  업데이트 완료!")
print(f"  📅 보관기간: {oldest} ~ {newest}  ({len(sorted_history)}일)")
print(f"  ✅ 성공: {success_cnt}개 / 전체: {len(my_etfs)}개 종목")
print(f"  📌 당일시세: {today_msg}")
if fail_list:
    print(f"  ⚠️  실패: {', '.join(fail_list)}")
print(f"{'='*55}")
