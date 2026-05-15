import FinanceDataReader as fdr
import json, os, re, sys, time
from datetime import datetime, timedelta

save_folder = r"C:\Users\SON\Desktop\주식프로젝트"
html_file   = os.path.join(save_folder, "ETF_index_Ver3_1.html")
save_path   = os.path.join(save_folder, "prices.json")
KEEP_DAYS   = 35
SERVER_PORT = 9877

# ──────────────────────────────────────────────
#  장 마감 후 데이터 반영 시간 설정
#  KRX 마감(15:30) 후 데이터 소스 업데이트까지
#  보통 16:30~18:00 소요 → 18:00 이후 안정적
# ──────────────────────────────────────────────
MARKET_CLOSE_HOUR   = 15   # 장 마감 시각 (시)
MARKET_CLOSE_MINUTE = 30   # 장 마감 시각 (분)
DATA_READY_HOUR     = 18   # 데이터 안정 반영 시각 (시)
MAX_RETRY           = 3    # 당일 데이터 미반영 시 최대 재시도 횟수
RETRY_WAIT_SEC      = 300  # 재시도 대기 시간 (초, 기본 5분)

my_etfs = [
    '476800','0008S0','0052D0','498410','466940','498400','489030','475720',
    '474220','441680','482730','458760','088980','0086B0','352540','0089D0',
    '0098N0','0097L0','0105E0','329200','481060','0153K0','433970','0025N0','486290'
]

# ──────────────────────────────────────────────
#  현재 시각이 데이터 수집에 적절한지 확인
# ──────────────────────────────────────────────
def check_timing():
    now  = datetime.now()
    # 주말 체크
    if now.weekday() >= 5:
        return "weekend"
    now_min = now.hour * 60 + now.minute
    close_min = MARKET_CLOSE_HOUR * 60 + MARKET_CLOSE_MINUTE
    ready_min = DATA_READY_HOUR * 60
    if now_min < close_min:
        return "before_close"   # 장 중
    elif now_min < ready_min:
        return "too_early"      # 마감 직후, 아직 소스 업데이트 전
    else:
        return "ok"             # 18:00 이후 안정

# ──────────────────────────────────────────────
#  오늘 날짜 데이터가 수집됐는지 확인
# ──────────────────────────────────────────────
def is_today_in_data(history: dict) -> bool:
    today = datetime.now().strftime('%Y-%m-%d')
    return today in history

# ──────────────────────────────────────────────
#  실제 업데이트 로직 (1회 실행)
# ──────────────────────────────────────────────
def _do_fetch(master_history: dict):
    success_cnt, fail_list = 0, []
    today_str = datetime.now().strftime('%Y-%m-%d')

    for code in my_etfs:
        try:
            start_dt = (datetime.now() - timedelta(days=50)).strftime('%Y-%m-%d')
            df = fdr.DataReader(code, start=start_dt)
            if df.empty:
                fail_list.append(code)
                continue

            latest_date = df.index[-1].strftime('%Y-%m-%d')
            if latest_date < today_str:
                print(f"  ⏳ {code}: 소스 미반영 (최신={latest_date}, 오늘={today_str})")

            for i in range(1, len(df)):
                date_str = df.index[i].strftime('%Y-%m-%d')
                if date_str not in master_history:
                    master_history[date_str] = {}
                master_history[date_str][code] = {
                    "today": int(df['Close'].iloc[i]),
                    "prev":  int(df['Close'].iloc[i - 1]),
                    "src":   "Python"
                }
            success_cnt += 1
        except Exception as e:
            fail_list.append(code)
            print(f"  {code} error: {e}")

    return success_cnt, fail_list

# ──────────────────────────────────────────────
#  메인 업데이트 (재시도 포함)
# ──────────────────────────────────────────────
def run_update():
    # ── 기존 데이터 로드 ──
    master_history = {}
    if os.path.exists(save_path):
        with open(save_path, 'r', encoding='utf-8') as f:
            try:
                raw = json.load(f)
                master_history = {d: v for d, v in raw.items()
                                  if re.match(r'^\d{4}-\d{2}-\d{2}$', str(d))}
            except:
                master_history = {}

    timing = check_timing()
    today  = datetime.now().strftime('%Y-%m-%d')
    now_time = datetime.now().strftime('%H:%M')

    # 장 중 / 너무 이른 경우 경고 출력 (실행은 계속)
    if timing == "before_close":
        print(f"⚠️  현재 {now_time} — 아직 장 중입니다. 당일 종가 미확정.")
    elif timing == "too_early":
        print(f"⚠️  현재 {now_time} — 마감(15:30) 직후라 데이터 소스 업데이트 중.")
        print(f"   18:00 이후 실행을 권장합니다. (재시도 최대 {MAX_RETRY}회)")
    elif timing == "weekend":
        print(f"⚠️  주말입니다. 가장 최근 거래일 데이터를 수집합니다.")

    print(f"시세 업데이트 시작 (보관: {len(master_history)}일)")

    # ── 수집 + 재시도 루프 ──
    success_cnt, fail_list = 0, []
    for attempt in range(1, MAX_RETRY + 1):
        print(f"\n  [시도 {attempt}/{MAX_RETRY}]")
        success_cnt, fail_list = _do_fetch(master_history)

        # 당일(평일)이면 오늘 데이터 반영 여부 확인
        is_weekday = datetime.now().weekday() < 5
        today_in   = is_today_in_data(master_history)

        if timing == "ok" and is_weekday and not today_in:
            if attempt < MAX_RETRY:
                print(f"  ⏳ 당일({today}) 데이터 미반영 → {RETRY_WAIT_SEC}초 후 재시도...")
                time.sleep(RETRY_WAIT_SEC)
            else:
                print(f"  ⚠️  최대 재시도 초과. 당일 데이터 없이 저장합니다.")
        else:
            if today_in:
                print(f"  ✅ 당일({today}) 데이터 반영 확인!")
            break

    # ── 오래된 데이터 정리 ──
    limit_date     = (datetime.now() - timedelta(days=KEEP_DAYS)).strftime('%Y-%m-%d')
    sorted_history = dict(sorted(
        {d: v for d, v in master_history.items() if d >= limit_date}.items(),
        reverse=True
    ))

    # ── prices.json 저장 ──
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(sorted_history, f, ensure_ascii=False, indent=2)

    # ── HTML 블록 교체 ──
    html_updated = False
    if os.path.exists(html_file):
        with open(html_file, 'r', encoding='utf-8') as f:
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
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(updated)
            html_updated = True

    dates = list(sorted_history.keys())
    today_reflected = is_today_in_data(sorted_history)

    return {
        "ok":            True,
        "success":       success_cnt,
        "total":         len(my_etfs),
        "fail":          fail_list,
        "newest":        dates[0] if dates else 'N/A',
        "oldest":        dates[-1] if dates else 'N/A',
        "days":          len(sorted_history),
        "html_updated":  html_updated,
        "today_ok":      today_reflected,       # ★ 당일 데이터 반영 여부
        "timing_warn":   timing,                # ★ 타이밍 경고 코드
        "time":          datetime.now().strftime('%H:%M:%S')
    }

# ──────────────────────────────────────────────
#  HTTP 서버 모드
# ──────────────────────────────────────────────
def run_server():
    from http.server import HTTPServer, BaseHTTPRequestHandler
    class H(BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            self.send_response(200); self._cors(); self.end_headers()
        def do_GET(self):
            if self.path.startswith('/update'):
                try:
                    r = run_update()
                    b = json.dumps(r, ensure_ascii=False).encode('utf-8')
                    self.send_response(200); self._cors()
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Content-Length', len(b))
                    self.end_headers(); self.wfile.write(b)
                except Exception as e:
                    b = json.dumps({"ok": False, "error": str(e)}).encode()
                    self.send_response(500); self._cors()
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers(); self.wfile.write(b)
            elif self.path == '/status':
                self.send_response(200); self._cors()
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            else:
                self.send_response(404); self.end_headers()
        def _cors(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET,OPTIONS')
        def log_message(self, fmt, *a):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {fmt % a}")

    server = HTTPServer(('localhost', SERVER_PORT), H)
    print(f"시세 서버 시작 — http://localhost:{SERVER_PORT}  (Ctrl+C 종료)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()

# ──────────────────────────────────────────────
if __name__ == '__main__':
    if '--server' in sys.argv:
        run_server()
    else:
        r = run_update()
        today_msg = "✅ 당일 반영" if r.get('today_ok') else "⚠️  당일 미반영(소스 지연)"
        print(f"\n{'='*55}")
        print(f"  업데이트 완료: {r['success']}/{r['total']} 종목")
        print(f"  최신날짜: {r['newest']}  ({today_msg})")
        print(f"  보관기간: {r['oldest']} ~ {r['newest']}  ({r['days']}일)")
        if r['fail']:
            print(f"  실패종목: {', '.join(r['fail'])}")
        print(f"{'='*55}")
