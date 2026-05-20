"""
stock_github.py — GitHub Actions 전용 시세 업데이터
- 경로: 스크립트와 동일 폴더의 ETF_index_Ver4_1.html 자동 탐색
- RAW 거래내역 173건 내장 HTML과 함께 사용

★ GitHub Actions 권장 스케줄 (UTC 기준):
   - cron: '30 6 * * 1-5'  → 한국시간 15:30 (장 마감 직후)
   - cron: '0 9 * * 1-5'   → 한국시간 18:00 (가장 안정적)
"""
import FinanceDataReader as fdr
import json, os, re, time
from datetime import datetime, timedelta

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(BASE_DIR, 'ETF_index_Ver4_1.html')
JSON_FILE = os.path.join(BASE_DIR, 'prices.json')
KEEP_DAYS = 35

MAX_RETRY      = 3
RETRY_WAIT_SEC = 300

# ★ RAW 173건 기준 전체 31개 종목 코드
my_etfs = [
    # 기존 26개
    '476800', '0008S0', '0052D0', '498410', '466940', '498400',
    '489030', '475720', '474220', '441680', '482730', '458760',
    '088980', '0086B0', '352540', '0089D0', '0098N0', '0097L0',
    '0105E0', '329200', '481060', '0153K0', '433970', '0025N0',
    '486290', '457480',
    # ★ 신규 5개 (173건 추가분)
    '472150',  # TIGER 배당커버드콜액티브
    '0047R0',  # RISE 팔란티어고정테크100
    '261070',  # TIGER 코스닥150바이오테크
    '381170',  # TIGER 미국테크TOP10 INDXX
    '488770',  # KODEX 머니마켓액티브
]

def is_today_in_data(history: dict) -> bool:
    today = datetime.now().strftime('%Y-%m-%d')
    return today in history

# 기존 데이터 로드
master_history = {}
if os.path.exists(JSON_FILE):
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        try:
            raw = json.load(f)
            master_history = {d: v for d, v in raw.items()
                              if re.match(r'^\d{4}-\d{2}-\d{2}$', str(d))}
        except Exception:
            master_history = {}

today_str  = datetime.now().strftime('%Y-%m-%d')
is_weekday = datetime.now().weekday() < 5

print(f"🚀 시세 업데이트 시작 (기존: {len(master_history)}일, 종목: {len(my_etfs)}개)")
print(f"   오늘: {today_str} ({'평일' if is_weekday else '주말'})")

def fetch_once():
    success_cnt, fail_list = 0, []
    for code in my_etfs:
        try:
            start_dt = (datetime.now() - timedelta(days=50)).strftime('%Y-%m-%d')
            df = fdr.DataReader(code, start=start_dt)
            if df.empty:
                fail_list.append(code); continue
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

success_cnt, fail_list = 0, []
for attempt in range(1, MAX_RETRY + 1):
    print(f"\n[시도 {attempt}/{MAX_RETRY}]")
    success_cnt, fail_list = fetch_once()
    if is_weekday and not is_today_in_data(master_history):
        if attempt < MAX_RETRY:
            print(f"⏳ 당일({today_str}) 미반영 → {RETRY_WAIT_SEC}초 대기 후 재시도...")
            time.sleep(RETRY_WAIT_SEC)
        else:
            print(f"⚠️  최대 재시도 초과.")
    else:
        if is_weekday and is_today_in_data(master_history):
            print(f"✅ 당일({today_str}) 데이터 반영 확인!")
        break

# 오래된 데이터 정리
limit_date     = (datetime.now() - timedelta(days=KEEP_DAYS)).strftime('%Y-%m-%d')
sorted_history = dict(sorted(
    {d: v for d, v in master_history.items() if d >= limit_date}.items(),
    reverse=True
))

# prices.json 저장
with open(JSON_FILE, 'w', encoding='utf-8') as f:
    json.dump(sorted_history, f, ensure_ascii=False, indent=2)
print(f"\n💾 prices.json 저장 완료")

# HTML 시세 블록 교체 (RAW 거래내역은 건드리지 않음)
if not os.path.exists(HTML_FILE):
    print(f"⚠️  HTML 파일 없음: {HTML_FILE}")
else:
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html_content = f.read()
    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_block = (
        f'<!-- ★ 아래 블록은 stock.py가 자동으로 덮어씁니다. 수동 편집 금지 -->\n'
        f'<script id="py-prices-block">\n'
        f'// stock.py 업데이트: {generated_at}\n'
        f'window.PYTHON_PRICES_DATA = {json.dumps(sorted_history, ensure_ascii=False)};\n'
        f'</script>'
    )
    pattern = (r'<!-- ★ 아래 블록은 stock\.py가 자동으로 덮어씁니다\. 수동 편집 금지 -->'
               r'.*?</script>')
    updated, n = re.subn(pattern, new_block, html_content, flags=re.DOTALL)
    if n > 0:
        with open(HTML_FILE, 'w', encoding='utf-8') as f:
            f.write(updated)
        print(f"🌐 HTML 시세 블록 업데이트 완료 → ETF_index_Ver4_1.html")
        print(f"   ※ RAW 거래내역 173건은 그대로 유지됩니다")
    else:
        print(f"⚠️  HTML 내 시세 블록 패턴을 찾지 못했습니다")

dates    = list(sorted_history.keys())
newest   = dates[0] if dates else 'N/A'
oldest   = dates[-1] if dates else 'N/A'
today_ok = is_today_in_data(sorted_history) if is_weekday else True

print(f"\n{'='*55}")
print(f"  ✔  업데이트 완료!")
print(f"  📅 보관기간: {oldest} ~ {newest}  ({len(sorted_history)}일)")
print(f"  ✅ 성공: {success_cnt}개 / 전체: {len(my_etfs)}개 종목")
print(f"  📌 당일시세: {'✅ 당일 반영' if today_ok else '⚠️  당일 미반영'}")
if fail_list:
    print(f"  ⚠️  실패: {', '.join(fail_list)}")
print(f"{'='*55}")
