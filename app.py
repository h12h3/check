import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import re

st.set_page_config(page_title="소속 체크기", layout="wide")

st.title("📊 할당량 최종 분석")
st.caption("v11.0 | 이름만 깔끔하게! 중복 없이 정확하게 체크합니다.")

# --- 세션 초기화 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

with st.sidebar:
    st.header("🔑 보안 설정")
    user_cookie = st.text_input("인스티즈 Cookie", type="password", value=st.session_state.get('user_cookie', ''))
    if st.button("저장"):
        st.session_state['user_cookie'] = user_cookie
        st.success("완료!")

# --- 소속 설정 ---
st.subheader("📋 소속 및 인원 관리")
num_clubs = st.number_input("소속 개수", 1, 10, value=len(st.session_state['clubs']))

for i in range(num_clubs):
    if i >= len(st.session_state['clubs']):
        st.session_state['clubs'].append({"name": "", "url": "", "m_list": ""})
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.session_state['clubs'][i]['name'] = st.text_input(f"소속 이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'])
        st.session_state['clubs'][i]['url'] = st.text_input(f"목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'])
    with col2:
        example_m = "방장: 맹구\n01470: 수지\n만두찌개: 철수"
        st.session_state['clubs'][i]['m_list'] = st.text_area(f"인원 명단 (식별값: 이름)", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'], placeholder=example_m)

# --- 분석 실행 ---
st.divider()
c1, c2 = st.columns(2)
with c1:
    target_date = st.date_input("분석 날짜", datetime.date.today())
with c2:
    start_t = st.time_input("시작", datetime.time(0, 0))
    end_t = st.time_input("종료", datetime.time(23, 59))

club_options = [c['name'] if c['name'] else f"소속 #{i+1}" for i, c in enumerate(st.session_state['clubs'])]
sel_name = st.selectbox("소속 선택", club_options)
club = st.session_state['clubs'][club_options.index(sel_name)]

if st.button("🚀 할당량 분석 시작"):
    start_dt = datetime.datetime.combine(target_date, start_t)
    end_dt = datetime.datetime.combine(target_date, end_t)
    
    with st.spinner("분석 중입니다..."):
        try:
            # 1. 명단 정리 (중복 제거)
            member_map = {}
            leader_key = "방장"
            leader_name = ""
            
            for line in club['m_list'].split('\n'):
                if ':' in line:
                    k, v = line.split(':', 1)
                    k, v = k.strip(), v.strip()
                    if k == "방장": leader_name = v
                    else: member_map[k] = v

            # 2. 인스티즈 데이터 수집
            headers = {"Cookie": st.session_state.get('user_cookie', ''), "User-Agent": "Mozilla/5.0"}
            res = requests.get(club['url'], headers=headers)
            post_nos = list(dict.fromkeys(re.findall(r'(?:no=|writing/)(\d+)', res.text)))
            
            check_results = {leader_name: False} # 방장 기본값
            for name in member_map.values():
                check_results[name] = False # 멤버 기본값

            # 3. 글 하나씩 열어서 판독
            for p_no in post_nos[:15]:
                p_url = f"https://www.instiz.net/writing/{p_no}"
                p_res = requests.get(p_url, headers=headers)
                
                # 날짜 체크
                dt_match = re.search(r'(\d{4}[./]\d{2}[./]\d{2} \d{2}:\d{2}(?::\d{2})?)', p_res.text)
                if not dt_match: continue
                p_dt = datetime.datetime.strptime(dt_match.group(1).replace('/', '.'), 
                       "%Y.%m.%d %H:%M:%S" if dt_match.group(1).count(':') == 2 else "%Y.%m.%d %H:%M")

                if start_dt <= p_dt <= end_dt:
                    if_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={p_no}"
                    if_res = requests.get(if_url, headers=headers)
                    combined_src = p_res.text + if_res.text # 본문+지문 합치기
                    
                    matched = False
                    for code, name in member_map.items():
                        if code in combined_src:
                            check_results[name] = True
                            matched = True
                            break
                    
                    if not matched: # 누구의 번호표도 없다면 방장 글!
                        check_results[leader_name] = True

            # 4. 결과 출력
            st.subheader(f"📊 {target_date} 분석 결과")
            final_df = pd.DataFrame([{"이름": name, "상태": "✅ 완료" if ok else "❌ 미작성"} for name, ok in check_results.items()])
            st.table(final_df)
            
            # 카톡용 요약
            summary = f"[{target_date} 현황]\n"
            for name, ok in check_results.items():
                summary += f"- {name}: {'✅ 완료' if ok else '❌ 미작성'}\n"
            st.text_area("📋 카톡 복사용", summary)

        except Exception as e:
            st.error(f"오류: {e}")
