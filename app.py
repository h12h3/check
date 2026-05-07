import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import re

st.set_page_config(page_title="소속 할당량 체크", layout="wide")

st.title("🛡️ 소속 할당량 정밀 분석기 (v22.0)")
st.caption("신알신 링크에서 지문을 추출하여 수지님을 끝까지 추적합니다.")

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

st.subheader("📋 소속 정보 및 인원 명단")
num_clubs = st.number_input("소속 개수", 1, 5, value=len(st.session_state['clubs']))

for i in range(num_clubs):
    col1, col2 = st.columns([1, 2])
    with col1:
        st.session_state['clubs'][i]['name'] = st.text_input(f"소속 이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'], placeholder="예: 떡잎마을")
        st.session_state['clubs'][i]['url'] = st.text_input(f"전체글 보기 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'])
    with col2:
        example_m = "방장: 맹구\n[신알신링크]: 수지\n만두찌개: 철수"
        st.session_state['clubs'][i]['m_list'] = st.text_area(f"명단", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'], placeholder=example_m, height=120)

# --- 3. 분석 기간 설정 (시작/끝 날짜+시간) ---
st.divider()
st.subheader("📅 분석 기간 설정")
col_s1, col_s2 = st.columns(2)
with col_s1:
    start_dt = st.datetime_input("날짜 체크 시작 일시", value=datetime.datetime.now() - datetime.timedelta(days=7))
with col_s2:
    end_dt = st.datetime_input("날짜 체크 끝 일시", value=datetime.datetime.now())

# --- 4. 분석 엔진 ---
if st.button("🚀 정밀 할당량 분석 시작"):
    club = st.session_state['clubs'][0]
    if not st.session_state['user_cookie']:
        st.error("보안 설정을 위해 쿠키를 먼저 입력해주세요!")
    else:
        with st.status("📡 지문 정밀 수색 중...", expanded=True) as status:
            try:
                # 명단 파싱 및 링크에서 ID 추출
                member_map = {}
                leader_name = "미정"
                for line in club['m_list'].split('\n'):
                    if ':' in line:
                        k, v = line.split(':', 1); k, v = k.strip(), v.strip()
                        if k == "방장": 
                            leader_name = v
                        else:
                            # 만약 k가 링크라면 숫자만 추출 (예: multiwriter=01470 -> 01470)
                            id_match = re.search(r'multiwriter=(\d+)', k)
                            real_id = id_match.group(1) if id_match else k
                            member_map[real_id] = v

                headers = {"Cookie": st.session_state['user_cookie'], "User-Agent": "Mozilla/5.0"}
                res = requests.get(club['url'], headers=headers)
                post_nos = list(dict.fromkeys(re.findall(r'(?:no=|writing/)(\d+)', res.text)))
                
                # 결과 초기화 (이름만!)
                check_results = {leader_name: False}
                for name in member_map.values():
                    check_results[name] = False

                for p_no in post_nos[:30]:
                    p_url = f"https://www.instiz.net/writing/{p_no}"
                    p_res = requests.get(p_url, headers=headers)
                    
                    dt_match = re.search(r'(\d{4}[./]\d{2}[./]\d{2} \d{2}:\d{2}(?::\d{2})?)', p_res.text)
                    if not dt_match: continue
                    
                    p_dt = datetime.datetime.strptime(dt_match.group(1).replace('/', '.'), 
                           "%Y.%m.%d %H:%M:%S" if dt_match.group(1).count(':') == 2 else "%Y.%m.%d %H:%M")

                    if start_dt <= p_dt <= end_dt:
                        if_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={p_no}"
                        if_res = requests.get(if_url, headers=headers)
                        combined_src = p_res.text + if_res.text
                        
                        matched = False
                        for code, name in member_map.items():
                            if code in combined_src:
                                check_results[name] = True
                                matched = True
                                break
                        
                        if not matched and leader_name != "미정":
                            check_results[leader_name] = True

                status.update(label="분석 완료!", state="complete")
                
                # --- 결과 출력 ---
                st.subheader(f"📊 최종 분석 결과")
                final_df = pd.DataFrame([{"이름": n, "상태": "✅ 완료" if ok else "❌ 미작성"} for n, ok in check_results.items() if n != "미정"])
                st.table(final_df)
                
                summary = f"[{start_dt.strftime('%m/%d')}~{end_dt.strftime('%m/%d')} 현황]\n"
                for n, ok in check_results.items():
                    if n != "미정": summary += f"- {n}: {'✅ 완료' if ok else '❌ 미작성'}\n"
                st.text_area("📋 카톡 공지용 복사", summary, height=150)

            except Exception as e:
                st.error(f"오류: {e}")
