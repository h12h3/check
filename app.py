import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import re

st.set_page_config(page_title="소속 체크 시스템", layout="wide")

st.title("🛡️ 소속 할당량 최종 분석기")
st.caption("v12.0 | 주간 단위 체크 지원 & 방장/멤버 정밀 판독")

# --- 1. 보안 설정 (쿠키) ---
if 'user_cookie' not in st.session_state:
    st.session_state['user_cookie'] = ""

with st.sidebar:
    st.header("🔑 보안 설정")
    st.session_state['user_cookie'] = st.text_input("인스티즈 Cookie", type="password", value=st.session_state['user_cookie'])
    st.info("쿠키는 브라우저를 닫으면 초기화됩니다.")

# --- 2. 소속 설정 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

st.subheader("📋 소속 및 명단 관리")
num_clubs = st.number_input("소속 개수", 1, 10, value=len(st.session_state['clubs']))

for i in range(num_clubs):
    if i >= len(st.session_state['clubs']):
        st.session_state['clubs'].append({"name": "", "url": "", "m_list": ""})
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.session_state['clubs'][i]['name'] = st.text_input(f"소속 이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'], placeholder="예: 떡잎마을")
        st.session_state['clubs'][i]['url'] = st.text_input(f"목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'])
    with col2:
        st.session_state['clubs'][i]['m_list'] = st.text_area(f"명단 (방장: 이름 / 식별값: 이름)", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'], placeholder="방장: 맹구\n01470: 수지\n만두찌개: 철수")

# --- 3. 분석 범위 설정 (주간/자유 범위) ---
st.divider()
st.subheader("📅 분석 범위 설정")
c1, c2 = st.columns(2)
with c1:
    start_dt = st.datetime_input("날짜 체크 시작 일시", value=datetime.datetime.now() - datetime.timedelta(days=7))
with c2:
    end_dt = st.datetime_input("날짜 체크 끝 일시", value=datetime.datetime.now())

sel_club_name = st.selectbox("분석 대상 소속 선택", [c['name'] if c['name'] else f"소속 #{i+1}" for i, c in enumerate(st.session_state['clubs'])])
club_idx = [c['name'] for c in st.session_state['clubs']].index(sel_club_name if sel_club_name in [c['name'] for c in st.session_state['clubs']] else "")
club = st.session_state['clubs'][club_idx]

# --- 4. 분석 엔진 ---
if st.button("🚀 할당량 분석 시작"):
    if not st.session_state['user_cookie']:
        st.error("쿠키를 먼저 입력해주세요!")
    else:
        with st.spinner("데이터를 정밀 분석 중입니다..."):
            try:
                # 명단 정리
                member_map = {}
                leader_name = "맹구"
                for line in club['m_list'].split('\n'):
                    if ':' in line:
                        k, v = line.split(':', 1)
                        k, v = k.strip(), v.strip()
                        if k == "방장": leader_name = v
                        else: member_map[k] = v

                headers = {"Cookie": st.session_state['user_cookie'], "User-Agent": "Mozilla/5.0"}
                res = requests.get(club['url'], headers=headers)
                post_nos = list(dict.fromkeys(re.findall(r'(?:no=|writing/)(\d+)', res.text)))
                
                # 결과 저장 딕셔너리
                final_status = {leader_name: False}
                for name in member_map.values():
                    final_status[name] = False

                # 글 분석
                for p_no in post_nos[:30]: # 범위가 넓을 수 있으니 상위 30개 검사
                    p_url = f"https://www.instiz.net/writing/{p_no}"
                    p_res = requests.get(p_url, headers=headers)
                    
                    # 날짜 추출
                    dt_match = re.search(r'(\d{4}[./]\d{2}[./]\d{2} \d{2}:\d{2}(?::\d{2})?)', p_res.text)
                    if not dt_match: continue
                    p_dt = datetime.datetime.strptime(dt_match.group(1).replace('/', '.'), 
                           "%Y.%m.%d %H:%M:%S" if dt_match.group(1).count(':') == 2 else "%Y.%m.%d %H:%M")

                    # 범위 내의 글인지 확인
                    if start_dt <= p_dt <= end_dt:
                        iframe_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={p_no}"
                        if_res = requests.get(iframe_url, headers=headers)
                        combined_src = p_res.text + if_res.text
                        
                        matched = False
                        for code, name in member_map.items():
                            if code in combined_src:
                                final_status[name] = True
                                matched = True
                                break
                        
                        if not matched: # 누구의 지문도 없다면 방장 글
                            final_status[leader_name] = True

                # --- 결과 출력 ---
                st.subheader(f"📊 분석 결과 ({start_dt.strftime('%m/%d')} ~ {end_dt.strftime('%m/%d')})")
                res_df = pd.DataFrame([{"이름": name, "상태": "✅ 완료" if ok else "❌ 미작성"} for name, ok in final_status.items()])
                st.table(res_df)
                
                summary = f"[{start_dt.strftime('%m/%d')}~{end_dt.strftime('%m/%d')} 현황]\n"
                for name, ok in final_status.items():
                    summary += f"- {name}: {'✅ 완료' if ok else '❌ 미작성'}\n"
                st.text_area("카톡 공지용 복사", summary, height=150)

            except Exception as e:
                st.error(f"오류: {e}")
