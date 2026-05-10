import FinanceDataReader as fdr
import json, os, re, sys
from datetime import datetime, timedelta

save_folder = r"C:\Users\SON\Desktop\주식프로젝트"
html_file   = os.path.join(save_folder, "ETF_index_Ver3_1.html")
save_path   = os.path.join(save_folder, "prices.json")
KEEP_DAYS   = 35
SERVER_PORT = 9877

my_etfs = [
    '476800','0008S0','0052D0','498410','466940','498400','489030','475720',
    '474220','441680','482730','458760','088980','0086B0','352540','0089D0',
    '0098N0','0097L0','0105E0','329200','481060','0153K0','433970','0025N0','486290'
]

def run_update():
    master_history = {}
    if os.path.exists(save_path):
        with open(save_path, 'r', encoding='utf-8') as f:
            try:
                raw = json.load(f)
                master_history = {d: v for d, v in raw.items()
                                  if re.match(r'^\d{4}-\d{2}-\d{2}$', str(d))}
            except: master_history = {}

    print(f"시세 업데이트 시작 (보관: {len(master_history)}일)")
    success_cnt, fail_list = 0, []

    for code in my_etfs:
        try:
            start_dt = (datetime.now() - timedelta(days=50)).strftime('%Y-%m-%d')
            df = fdr.DataReader(code, start=start_dt)
            if df.empty:
                fail_list.append(code); continue
            for i in range(1, len(df)):
                date_str = df.index[i].strftime('%Y-%m-%d')
                if date_str not in master_history: master_history[date_str] = {}
                master_history[date_str][code] = {
                    "today": int(df['Close'].iloc[i]),
                    "prev":  int(df['Close'].iloc[i-1]),
                    "src":   "Python"
                }
            success_cnt += 1
        except Exception as e:
            fail_list.append(code); print(f"  {code} error: {e}")

    limit_date = (datetime.now() - timedelta(days=KEEP_DAYS)).strftime('%Y-%m-%d')
    sorted_history = dict(sorted({d: v for d, v in master_history.items() if d >= limit_date}.items(), reverse=True))

    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(sorted_history, f, ensure_ascii=False, indent=2)

    html_updated = False
    if os.path.exists(html_file):
        with open(html_file, 'r', encoding='utf-8') as f: html_content = f.read()
        generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_block = (
            f'<!-- \u2605 \uc544\ub798 \ube14\ub85d\uc740 stock.py\uac00 \uc790\ub3d9\uc73c\ub85c \ub36e\uc5b4\uc501\ub2c8\ub2e4. \uc218\ub3d9 \ud3b8\uc9d1 \uae08\uc9c0 -->\n'
            f'<script id="py-prices-block">\n'
            f'// stock.py \uc5c5\ub370\uc774\ud2b8: {generated_at}\n'
            f'window.PYTHON_PRICES_DATA = {json.dumps(sorted_history, ensure_ascii=False)};\n'
            f'</script>'
        )
        pattern = r'<!-- \u2605 \uc544\ub798 \ube14\ub85d\uc740 stock\.py\uac00 \uc790\ub3d9\uc73c\ub85c \ub36e\uc5b4\uc501\ub2c8\ub2e4\. \uc218\ub3d9 \ud3b8\uc9d1 \uae08\uc9c0 -->.*?</script>'
        updated, n = re.subn(pattern, new_block, html_content, flags=re.DOTALL)
        if n > 0:
            with open(html_file, 'w', encoding='utf-8') as f: f.write(updated)
            html_updated = True

    dates = list(sorted_history.keys())
    return {"ok": True, "success": success_cnt, "total": len(my_etfs),
            "fail": fail_list, "newest": dates[0] if dates else 'N/A',
            "oldest": dates[-1] if dates else 'N/A', "days": len(sorted_history),
            "html_updated": html_updated, "time": datetime.now().strftime('%H:%M:%S')}

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
                    self.send_header('Content-Type','application/json; charset=utf-8')
                    self.send_header('Content-Length', len(b)); self.end_headers(); self.wfile.write(b)
                except Exception as e:
                    b = json.dumps({"ok":False,"error":str(e)}).encode()
                    self.send_response(500); self._cors()
                    self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(b)
            elif self.path == '/status':
                self.send_response(200); self._cors()
                self.send_header('Content-Type','application/json'); self.end_headers()
                self.wfile.write(b'{"ok":true}')
            else: self.send_response(404); self.end_headers()
        def _cors(self):
            self.send_header('Access-Control-Allow-Origin','*')
            self.send_header('Access-Control-Allow-Methods','GET,OPTIONS')
        def log_message(self, fmt, *a): print(f"[{datetime.now().strftime('%H:%M:%S')}] {fmt%a}")
    server = HTTPServer(('localhost', SERVER_PORT), H)
    print(f"시세 서버 시작 — http://localhost:{SERVER_PORT}  (Ctrl+C 종료)")
    try: server.serve_forever()
    except KeyboardInterrupt: server.shutdown()

if __name__ == '__main__':
    if '--server' in sys.argv: run_server()
    else:
        r = run_update()
        print(f"\n{'='*50}\n업데이트 완료: {r['success']}/{r['total']} 종목, {r['newest']}\n{'='*50}")
