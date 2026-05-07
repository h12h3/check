import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import re
import time

st.set_page_config(page_title="소속 할당량 체크", layout="wide")

st.title("🏢 소속 할당량 체크 시스템")
st.caption("v17.0 | 방장 통합 및 기간 정밀 분석 모드")

# --- 1. 보안 설정 ---
if 'user_cookie' not in st.session_state:
    st.session_state['user_cookie'] = ""

with st.sidebar:
    st.header("🔑 보안")
    st.session_state['user_cookie'] = st.text_input("인스티즈 Cookie", type="password", value=st.session_state['user_cookie'])
    st.info("쿠키를 입력해야 분석이 가능합니다.")

# --- 2. 소속 및 명단 설정 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

st.subheader("📋 소속 정보 및 인원 명단")
num_clubs = st.number_input("관리 소속 개수", 1, 10, value=len(st.session_state['clubs']))

for i in range(num_clubs):
    if i >= len(st.session_state['clubs']):
        st.session_state['clubs'].append({"name": "", "url": "", "m_list": ""})
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.session_state['clubs'][i]['name'] = st.text_input(f"소속 이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'], placeholder="예: 떡잎마을")
        st.session_state['clubs'][i]['url'] = st.text_input(f"목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'])
    with col2:
        example_m = "방장: 맹구\n01470: 수지\n만두찌개: 철수"
        st.session_state['clubs'][i]['m_list'] = st.text_area(f"인원 명단", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'], placeholder=example_m, height=100)

# --- 3. 분석 기간 설정 ---
st.divider()
st.subheader("📅 분석 기간 설정")
col_s1, col_s2 = st.columns(2)
with col_s1:
    s_date = st.date_input("시작 날짜", datetime.date.today() - datetime.timedelta(days=7))
    s_time = st.time_input("시작 시간", datetime.time(0, 0))
with col_s2:
    e_date = st.date_input("종료 날짜", datetime.date.today())
    e_time = st.time_input("종료 시간", datetime.time(23, 59))

start_dt = datetime.datetime.combine(s_date, s_time)
end_dt = datetime.datetime.combine(e_date, e_time)

# --- 4. 분석 엔진 ---
if st.button("🚀 정밀 분석 시작"):
    sel_club_name = st.selectbox("분석 대상 소속", [c['name'] for c in st.session_state['clubs']], label_visibility="collapsed")
    club = next(c for c in st.session_state['clubs'] if c['name'] == sel_club_name)
    
    with st.status("📡 인스티즈 서버 대조 중...", expanded=True) as status:
        try:
            # 명단 파싱 (방장: 맹구 형태를 맹구라는 이름으로 통합)
            member_map = {}
            leader_name = "미정"
            for line in club['m_list'].split('\n'):
                if ':' in line:
                    k, v = line.split(':', 1); k, v = k.strip(), v.strip()
                    if k == "방장": leader_name = v
                    else: member_map[k] = v

            headers = {"Cookie": st.session_state['user_cookie'], "User-Agent": "Mozilla/5.0"}
            res = requests.get(club['url'], headers=headers)
            
            # 목록에서 글 번호 싹 긁어오기
            post_nos = list(dict.fromkeys(re.findall(r'(?:no=|writing/)(\d+)', res.text)))
            st.write(f"📍 목록에서 총 {len(post_nos)}개의 글을 발견했습니다.")
            
            check_results = {leader_name: False}
            for name in member_map.values(): check_results[name] = False

            for p_no in post_nos[:30]: # 최신 30개 분석
                p_url = f"https://www.instiz.net/writing/{p_no}"
                p_res = requests.get(p_url, headers=headers)
                
                # 날짜 추출 (슬래시 대응)
                dt_match = re.search(r'(\d{4}[./]\d{2}[./]\d{2} \d{2}:\d{2}(?::\d{2})?)', p_res.text)
                if not dt_match: continue
                
                raw_dt = dt_match.group(1).replace('/', '.')
                fmt = "%Y.%m.%d %H:%M:%S" if raw_dt.count(':') == 2 else "%Y.%m.%d %H:%M"
                p_dt = datetime.datetime.strptime(raw_dt, fmt)

                if start_dt <= p_dt <= end_dt:
                    if_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={p_no}"
                    if_res = requests.get(if_url, headers=headers)
                    combined = p_res.text + if_res.text
                    
                    matched = False
                    for code, name in member_map.items():
                        if code in combined or f">{name}<" in combined:
                            check_results[name] = True
                            matched = True
                            break
                    if not matched: check_results[leader_name] = True

            status.update(label="분석 완료!", state="complete")
            
            # 최종 결과 표 (깔끔하게 이름만!)
            st.subheader(f"📊 {start_dt.strftime('%m/%d')} ~ {end_dt.strftime('%m/%d')} 결과")
            final_df = pd.DataFrame([{"이름": n, "상태": "✅ 완료" if ok else "❌ 미작성"} for n, ok in check_results.items()])
            st.table(final_df)
            
            # 카톡 공유용
            summary = f"[{start_dt.strftime('%m/%d')}~{end_dt.strftime('%m/%d')} 현황]\n"
            for n, ok in check_results.items():
                summary += f"- {n}: {'✅ 완료' if ok else '❌ 미작성'}\n"
            st.text_area("📋 카톡 공지용 복사", summary, height=150)

        except Exception as e:
            st.error(f"오류: {e}")
