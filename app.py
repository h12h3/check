import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import time
import re

st.set_page_config(page_title="소속 할당량 체크기", layout="wide")

st.title("📊 소속 할당량 최종 확인")
st.caption("v9.0 | 지정된 날짜에 누가 글을 썼는지 1초 만에 확인합니다.")

# --- 세션 상태 초기화 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

with st.sidebar:
    st.header("🔑 보안 설정")
    user_cookie = st.text_input("인스티즈 Cookie 입력", type="password", value=st.session_state.get('user_cookie', ''))
    if st.button("보안 설정 저장"):
        st.session_state['user_cookie'] = user_cookie
        st.success("쿠키가 저장되었습니다.")

# --- 소속 설정 ---
st.subheader("📋 관리 소속 설정")
num_clubs = st.number_input("소속 개수", 1, 10, value=len(st.session_state['clubs']))

for i in range(num_clubs):
    if i >= len(st.session_state['clubs']):
        st.session_state['clubs'].append({"name": "", "url": "", "m_list": ""})
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.session_state['clubs'][i]['name'] = st.text_input(f"소속 #{i+1} 이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'])
        st.session_state['clubs'][i]['url'] = st.text_input(f"목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'])
    with col2:
        st.session_state['clubs'][i]['m_list'] = st.text_area(f"멤버 명단", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'], placeholder="방장: 맹구\n01470: 수지\n만두찌개: 철수")

if st.button("💾 설정 정보 저장"):
    st.success("모든 설정이 브라우저에 저장되었습니다.")

# --- 분석 실행 ---
st.divider()
st.subheader("🔍 할당량 분석 실행")
c1, c2 = st.columns(2)
with c1:
    target_date = st.date_input("체크할 날짜", datetime.date.today())
with c2:
    start_t = st.time_input("시작 시간", datetime.time(0, 0))
    end_t = st.time_input("종료 시간", datetime.time(23, 59))

# 소속 선택
club_options = [c['name'] if c['name'] else f"소속 #{i+1}" for i, c in enumerate(st.session_state['clubs'])]
sel_name = st.selectbox("체크할 소속 선택", club_options)
sel_idx = club_options.index(sel_name)
club = st.session_state['clubs'][sel_idx]

if st.button("🚀 할당량 체크 시작"):
    start_dt = datetime.datetime.combine(target_date, start_t)
    end_dt = datetime.datetime.combine(target_date, end_t)
    
    with st.status("📡 인스티즈 서버 대조 중...", expanded=True) as status:
        try:
            # 1. 명단 파싱
            member_map = {}
            owner_name = "방장"
            for line in club['m_list'].split('\n'):
                if ':' in line:
                    code, name = line.split(':', 1)
                    code, name = code.strip(), name.strip()
                    if code == "방장": owner_name = name
                    else: member_map[code] = name

            headers = {
                "Cookie": st.session_state.get('user_cookie', ''),
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
            
            # 2. 목록 가져오기
            res = requests.get(club['url'], headers=headers)
            post_nos = list(dict.fromkeys(re.findall(r'(?:no=|writing/)(\d+)', res.text)))
            
            found_members = set() # 글을 쓴 멤버들
            owner_wrote = False # 방장이 글을 썼는지 여부
            
            # 3. 각 글 정밀 분석
            for p_no in post_nos[:20]: # 최신 20개 분석
                p_url = f"https://www.instiz.net/writing/{p_no}"
                p_res = requests.get(p_url, headers=headers)
                
                # 날짜 추출
                dt_match = re.search(r'(\d{4}[./]\d{2}[./]\d{2} \d{2}:\d{2}(?::\d{2})?)', p_res.text)
                if not dt_match: continue
                
                raw_dt = dt_match.group(1).replace('/', '.')
                fmt = "%Y.%m.%d %H:%M:%S" if raw_dt.count(':') == 2 else "%Y.%m.%d %H:%M"
                p_dt = datetime.datetime.strptime(raw_dt, fmt)

                # 날짜가 범위 안일 때만 작성자 확인
                if start_dt <= p_dt <= end_dt:
                    # iframe(지문 영역) 데이터 가져오기
                    if_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={p_no}"
                    if_res = requests.get(if_url, headers=headers)
                    combined_text = p_res.text + if_res.text # 본문과 지문 영역 합쳐서 수색
                    
                    is_member_post = False
                    for code in member_map.keys():
                        if code in combined_text:
                            found_members.add(code)
                            is_member_post = True
                            break
                    
                    # 지정된 시간 내 글인데 멤버 식별값이 없다면? -> 방장 글!
                    if not is_member_post:
                        owner_wrote = True

            status.update(label="분석 완료!", state="complete")
            
            # 4. 최종 결과 테이블
            st.subheader(f"📊 {target_date} 최종 결과")
            
            final_results = []
            # 방장 결과
            final_results.append({"소속": sel_name, "이름": f"{owner_name}(방장)", "상태": "✅ 작성 완료" if owner_wrote else "❌ 미작성"})
            # 멤버 결과
            for code, name in member_map.items():
                status_text = "✅ 작성 완료" if code in found_members else "❌ 미작성"
                final_results.append({"소속": sel_name, "이름": name, "상태": status_text})
            
            st.table(pd.DataFrame(final_results))
            
            # 카톡 공유용
            summary = f"[{target_date} {sel_name} 할당량 현황]\n"
            for r in final_results:
                summary += f" - {r['이름']}: {r['상태']}\n"
            st.text_area("📋 결과 복사 (카톡용)", summary, height=150)

        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")
