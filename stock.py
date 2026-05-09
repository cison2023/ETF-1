import FinanceDataReader as fdr
import json, os, re
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# 1. 설정
# ─────────────────────────────────────────────
save_folder = r"C:\Users\SON\Desktop\주식프로젝트"
html_file   = os.path.join(save_folder, "ETF_index_Ver3_1.html")   # ★ HTML 직접 수정
save_path   = os.path.join(save_folder, "prices.json")              # 백업용 JSON
KEEP_DAYS   = 35   # prices.json 보관 기간 (최근 1개월)

my_etfs = [
    '476800','0008S0','0052D0','498410','466940','498400','489030','475720',
    '474220','441680','482730','458760','088980','0086B0','352540','0089D0',
    '0098N0','0097L0','0105E0','329200','481060','0153K0','433970','0025N0','486290'
]

# ─────────────────────────────────────────────
# 2. 기존 데이터 불러오기
# ─────────────────────────────────────────────
master_history = {}
if os.path.exists(save_path):
    with open(save_path, 'r', encoding='utf-8') as f:
        try:
            raw = json.load(f)
            # 날짜 형식(YYYY-MM-DD) 키만 보존 (구버전 잔재 제거)
            master_history = {d: v for d, v in raw.items()
                              if re.match(r'^\d{4}-\d{2}-\d{2}$', str(d))}
        except:
            master_history = {}

# ─────────────────────────────────────────────
# 3. 최근 10거래일 시세 수집
# ─────────────────────────────────────────────
print(f"🚀 시세 업데이트 시작 (현재 보관: {len(master_history)}일)")
success_cnt, fail_list = 0, []

for code in my_etfs:
    try:
        # 최근 35거래일(약 1개월) 데이터 수집
        start_dt = (datetime.now() - timedelta(days=50)).strftime('%Y-%m-%d')
        df = fdr.DataReader(code, start=start_dt)
        if df.empty:
            fail_list.append(code); continue
        for i in range(1, len(df)):
            date_str = df.index[i].strftime('%Y-%m-%d')
            today_p  = int(df['Close'].iloc[i])
            prev_p   = int(df['Close'].iloc[i - 1])
            if date_str not in master_history:
                master_history[date_str] = {}
            master_history[date_str][code] = {"today": today_p, "prev": prev_p, "src": "Python"}
        success_cnt += 1
    except Exception as e:
        fail_list.append(code)
        print(f"  ❌ {code} 에러: {e}")

# ─────────────────────────────────────────────
# 4. 35일 초과 데이터 정리 + 정렬
# ─────────────────────────────────────────────
limit_date     = (datetime.now() - timedelta(days=KEEP_DAYS)).strftime('%Y-%m-%d')
cleaned        = {d: v for d, v in master_history.items() if d >= limit_date}
deleted        = len(master_history) - len(cleaned)
sorted_history = dict(sorted(cleaned.items(), reverse=True))

# ─────────────────────────────────────────────
# 5-A. prices.json 저장 (백업)
# ─────────────────────────────────────────────
with open(save_path, 'w', encoding='utf-8') as f:
    json.dump(sorted_history, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────
# 5-B. ★ HTML 파일 내부의 시세 블록 직접 교체
#       fetch/외부파일 없이 file:// 환경에서 완전 동작
# ─────────────────────────────────────────────
html_updated = False
if os.path.exists(html_file):
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    generated_at  = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    prices_json   = json.dumps(sorted_history, ensure_ascii=False)
    new_block = (
        f'<!-- ★ 아래 블록은 stock.py가 자동으로 덮어씁니다. 수동 편집 금지 -->\n'
        f'<script id="py-prices-block">\n'
        f'// stock.py 업데이트: {generated_at}\n'
        f'window.PYTHON_PRICES_DATA = {prices_json};\n'
        f'</script>'
    )

    # 기존 블록을 정규식으로 찾아 교체
    pattern = r'<!-- ★ 아래 블록은 stock\.py가 자동으로 덮어씁니다\. 수동 편집 금지 -->.*?</script>'
    updated, n = re.subn(pattern, new_block, html_content, flags=re.DOTALL)

    if n > 0:
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(updated)
        html_updated = True
    else:
        print("  ⚠️  HTML 내 시세 블록을 찾지 못했습니다. HTML 파일 경로를 확인하세요.")
else:
    print(f"  ⚠️  HTML 파일 없음: {html_file}")
    print(f"      html_file 경로를 실제 HTML 위치로 수정하세요.")

# ─────────────────────────────────────────────
# 6. 결과 출력
# ─────────────────────────────────────────────
dates  = list(sorted_history.keys())
newest = dates[0]  if dates else 'N/A'
oldest = dates[-1] if dates else 'N/A'

print("\n" + "=" * 55)
print(f"  ✔  업데이트 완료!")
print(f"  📅 보관기간: {oldest} ~ {newest}  ({len(sorted_history)}일)")
print(f"  ✅ 성공: {success_cnt}개 / 전체: {len(my_etfs)}개 종목")
if fail_list:
    print(f"  ⚠️  실패: {', '.join(fail_list)}")
if deleted > 0:
    print(f"  🗑  35일 초과 {deleted}일치 정리됨 (최근 1개월 유지)")
print(f"  💾 prices.json  저장됨")
if html_updated:
    print(f"  🌐 HTML 시세 자동 반영 완료 → 브라우저에서 F5 (새로고침) 하세요!")
print("=" * 55)
