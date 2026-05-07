import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import re
import concurrent.futures

st.set_page_config(page_title="소속 할당량 체크기", layout="wide")

st.title("🛡️ 소속 할당량 정밀 분석기 (최종판)")
st.caption("v15.0 | 이름 기반 깔끔한 출력 & 주간/기간 체크 & 광속 분석")

# --- 1. 보안 설정 ---
if 'user_cookie' not in st.session_state:
    st.session_state['user_cookie'] = ""

with st.sidebar:
    st.header("🔑 보안 설정")
    st.session_state['user_cookie'] = st.text_input("인스티즈 Cookie 입력", type="password", value=st.session_state['user_cookie'])
    st.info("쿠키를 넣어야 분석이 가능합니다.")

# --- 2. 소속 및 명단 설정 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

st.subheader("📋 소속 및 인원 관리")
num_clubs = st.number_input("관리 소속 개수", 1, 10, value=len(st.session_state['clubs']))

for i in range(num_clubs):
    if i >= len(st.session_state['clubs']):
        st.session_state['clubs'].append({"name": "", "url": "", "m_list": ""})
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.session_state['clubs'][i]['name'] = st.text_input(f"소속 #{i+1} 이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'], placeholder="예: 떡잎마을")
        st.session_state['clubs'][i]['url'] = st.text_input(f"소속 목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'])
    with col2:
        example_m = "방장: 맹구\n01470: 수지\n만두찌개: 철수"
        st.session_state['clubs'][i]['m_list'] = st.text_area(f"인원 명단 (방장: 이름 / 식별값: 이름)", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'], placeholder=example_m, height=100)

# --- 3. 분석 범위 설정 ---
st.divider()
st.subheader("📅 분석 기간 설정 (주간/자유)")
c1, c2 = st.columns(2)
with c1:
    start_dt = st.datetime_input("날짜 체크 시작 일시", value=datetime.datetime.now() - datetime.timedelta(days=7))
with c2:
    end_dt = st.datetime_input("날짜 체크 끝 일시", value=datetime.datetime.now())

sel_club_name = st.selectbox("분석 대상 소속 선택", [c['name'] if c['name'] else f"소속 #{i+1}" for i, c in enumerate(st.session_state['clubs'])])
club = next((c for c in st.session_state['clubs'] if c['name'] == sel_club_name or (not c['name'] and sel_club_name.endswith(f"#{st.session_state['clubs'].index(c)+1}"))), st.session_state['clubs'][0])

# --- 4. 분석 핵심 로직 ---
def analyze_single_post(p_no, headers, member_map, leader_name):
    """글 하나를 분석하여 작성자를 반환하는 함수"""
    try:
        p_url = f"https://www.instiz.net/writing/{p_no}"
        p_res = requests.get(p_url, headers=headers, timeout=5)
        
        # 날짜 추출
        dt_match = re.search(r'(\d{4}[./]\d{2}[./]\d{2} \d{2}:\d{2}(?::\d{2})?)', p_res.text)
        if not dt_match: return None
        
        p_dt = datetime.datetime.strptime(dt_match.group(1).replace('/', '.'), 
               "%Y.%m.%d %H:%M:%S" if dt_match.group(1).count(':') == 2 else "%Y.%m.%d %H:%M")
        
        if start_dt <= p_dt <= end_dt:
            # 수지님 같은 멤버를 찾기 위한 정밀 탐색 (iframe 포함)
            if_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={p_no}"
            if_res = requests.get(if_url, headers=headers, timeout=3)
            combined_src = p_res.text + if_res.text
            
            for code, name in member_map.items():
                # multiwriter=01470 형태를 정확히 추적
                if f"multiwriter={code}" in combined_src or f"'{code}'" in combined_src or f'"{code}"' in combined_src:
                    return {"name": name, "date": p_dt}
            
            # 범위 내 글인데 멤버 식별자가 없으면 방장 글로 간주
            return {"name": leader_name, "date": p_dt}
    except:
        pass
    return None

if st.button("🚀 광속 할당량 분석 시작"):
    if not st.session_state['user_cookie']:
        st.error("보안 설정을 위해 쿠키를 먼저 입력해주세요!")
    else:
        with st.status("📡 소속 데이터를 정밀 분석 중입니다...", expanded=True) as status:
            # 명단 파싱
            member_map = {}
            leader_name = "방장명없음"
            for line in club['m_list'].split('\n'):
                if ':' in line:
                    k, v = line.split(':', 1)
                    k, v = k.strip(), v.strip()
                    if k == "방장": leader_name = v
                    else: member_map[k] = v

            headers = {"Cookie": st.session_state['user_cookie'], "User-Agent": "Mozilla/5.0"}
            res = requests.get(club['url'], headers=headers)
            post_nos = list(dict.fromkeys(re.findall(r'(?:no=|writing/)(\d+)', res.text)))
            
            # 결과 저장 (이름: 완료여부)
            check_results = {leader_name: False}
            for name in member_map.values():
                check_results[name] = False

            # 병렬 처리로 속도 업그레이드
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(analyze_single_post, p_no, headers, member_map, leader_name) for p_no in post_nos[:40]]
                for future in concurrent.futures.as_completed(futures):
                    res_data = future.result()
                    if res_data:
                        check_results[res_data['name']] = True

            status.update(label="분석 완료!", state="complete")
            
            # 결과 테이블 출력
            st.subheader(f"📊 {sel_club_name} 할당량 현황")
            final_df = pd.DataFrame([{"이름": name, "상태": "✅ 완료" if ok else "❌ 미작성"} for name, ok in check_results.items()])
            st.table(final_df)
            
            # 카톡용 텍스트
            summary = f"[{start_dt.strftime('%m/%d')}~{end_dt.strftime('%m/%d')} {sel_club_name} 현황]\n"
            for name, ok in check_results.items():
                summary += f"- {name}: {'✅ 완료' if ok else '❌ 미작성'}\n"
            st.text_area("📋 카톡 공지용 복사", summary, height=150)
