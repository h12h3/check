import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import re

st.set_page_config(page_title="소속 할당량 관리", layout="wide")

st.title("🛡️ 소속 할당량 정밀 분석기")
st.caption("v13.0 | 맹구 중복 해결 & 수지 닉네임 교차 검증 모드")

# --- 1. 보안 설정 ---
if 'user_cookie' not in st.session_state:
    st.session_state['user_cookie'] = ""

with st.sidebar:
    st.header("🔑 보안")
    st.session_state['user_cookie'] = st.text_input("인스티즈 Cookie", type="password", value=st.session_state['user_cookie'])
    st.info("쿠키를 넣어야 분석이 가능합니다.")

# --- 2. 소속 설정 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

st.subheader("📋 소속 및 인원 설정")
num_clubs = st.number_input("소속 개수", 1, 10, value=len(st.session_state['clubs']))

for i in range(num_clubs):
    if i >= len(st.session_state['clubs']):
        st.session_state['clubs'].append({"name": "", "url": "", "m_list": ""})
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.session_state['clubs'][i]['name'] = st.text_input(f"소속 이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'])
        st.session_state['clubs'][i]['url'] = st.text_input(f"목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'])
    with col2:
        st.session_state['clubs'][i]['m_list'] = st.text_area(f"명단 (방장: 이름 / 식별값: 이름)", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'], placeholder="방장: 맹구\n01470: 수지\n만두찌개: 철수")

# --- 3. 기간 설정 ---
st.divider()
st.subheader("📅 분석 기간 설정")
c1, c2 = st.columns(2)
with c1:
    start_dt = st.datetime_input("시작 일시", value=datetime.datetime.now() - datetime.timedelta(days=7))
with c2:
    end_dt = st.datetime_input("끝 일시", value=datetime.datetime.now())

club_list = [c['name'] if c['name'] else f"소속 #{i+1}" for i, c in enumerate(st.session_state['clubs'])]
sel_club_name = st.selectbox("체크할 소속 선택", club_list)
club_idx = club_list.index(sel_name if 'sel_name' in locals() else sel_club_name)
club = st.session_state['clubs'][club_idx]

# --- 4. 분석 실행 ---
if st.button("🚀 할당량 분석 시작"):
    if not st.session_state['user_cookie']:
        st.error("쿠키를 먼저 넣어주세요!")
    else:
        with st.status("📡 데이터 정밀 수색 중...", expanded=True) as status:
            try:
                # 명단 정리 (중복 제거 및 방장 고정)
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
                
                # 결과 초기화 (이름만 표시)
                check_results = {leader_name: False}
                for name in member_map.values():
                    check_results[name] = False

                for p_no in post_nos[:50]: # 기간이 길 수 있으니 50개까지 확인
                    p_url = f"https://www.instiz.net/writing/{p_no}"
                    p_res = requests.get(p_url, headers=headers)
                    
                    dt_match = re.search(r'(\d{4}[./]\d{2}[./]\d{2} \d{2}:\d{2}(?::\d{2})?)', p_res.text)
                    if not dt_match: continue
                    p_dt = datetime.datetime.strptime(dt_match.group(1).replace('/', '.'), 
                           "%Y.%m.%d %H:%M:%S" if dt_match.group(1).count(':') == 2 else "%Y.%m.%d %H:%M")

                    # 기간 체크
                    if start_dt <= p_dt <= end_dt:
                        if_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={p_no}"
                        if_res = requests.get(if_url, headers=headers)
                        combined_src = p_res.text + if_res.text
                        
                        matched = False
                        # 1단계: 식별값(번호표)으로 수색
                        for code, name in member_map.items():
                            if code in combined_src:
                                check_results[name] = True
                                matched = True
                                break
                        
                        # 2단계: 닉네임으로 직접 수색 (수지님 검거용)
                        if not matched:
                            for name in member_map.values():
                                if f">{name}<" in p_res.text or f"'{name}'" in p_res.text:
                                    check_results[name] = True
                                    matched = True
                                    break
                        
                        # 3단계: 아무도 아니면 방장 글
                        if not matched:
                            check_results[leader_name] = True

                status.update(label="분석 완료!", state="complete")
                
                # 결과 출력
                st.subheader(f"📊 최종 결과 리포트")
                res_df = pd.DataFrame([{"이름": name, "상태": "✅ 완료" if ok else "❌ 미작성"} for name, ok in check_results.items()])
                st.table(res_df)
                
                summary = f"[{start_dt.strftime('%m/%d')}~{end_dt.strftime('%m/%d')} 현황]\n"
                for name, ok in check_results.items():
                    summary += f"- {name}: {'✅ 완료' if ok else '❌ 미작성'}\n"
                st.text_area("📋 카톡 공지용 복사", summary, height=150)

            except Exception as e:
                st.error(f"오류: {e}")
