import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import time
import re

st.set_page_config(page_title="뻘필 분석기 v7.0", layout="wide")

st.title("🕵️ 뻘필 할당량 분석기")
st.caption("v7.0: 소속 관리 모드 & 띄어쓰기 완벽 지원")

# --- 세션 초기화 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

with st.sidebar:
    st.header("⚙️ 기본 설정")
    user_cookie = st.text_input("내 인스티즈 Cookie", type="password", value=st.session_state.get('user_cookie', ''))
    if st.button("설정 저장"):
        st.session_state['user_cookie'] = user_cookie
        st.success("저장 완료!")

# --- 소속 설정 ---
st.subheader("🏢 소속 및 인원 관리")
num_clubs = st.number_input("관리 중인 소속 개수", 1, 10, value=len(st.session_state['clubs']))

for i in range(num_clubs):
    if i >= len(st.session_state['clubs']):
        st.session_state['clubs'].append({"name": "", "url": "", "m_list": ""})
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.session_state['clubs'][i]['name'] = st.text_input(f"소속 #{i+1} 이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'], placeholder="예: 떡잎마을방범대")
        st.session_state['clubs'][i]['url'] = st.text_input(f"소속 목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'], placeholder="전체글 보기 주소")
    with col2:
        example_m = "방장: 맹구\n01470: 수지\n만두찌개: 철수"
        st.session_state['clubs'][i]['m_list'] = st.text_area(f"멤버 명단 (식별값: 이름)", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'], placeholder=example_m, height=120)

if st.button("💾 모든 소속 정보 저장"):
    st.success("브라우저에 소속 정보가 저장되었습니다!")

# --- 분석 실행 ---
st.divider()
st.subheader("🚀 할당량 체크")
c1, c2 = st.columns(2)
with c1:
    target_date = st.date_input("🗓️ 분석 날짜", datetime.date.today())
with c2:
    start_t = st.time_input("⏰ 시작 시간", datetime.time(0, 0))
    end_t = st.time_input("⏰ 종료 시간", datetime.time(23, 59))

# 소속 선택
club_options = [c['name'] if c['name'] else f"소속 #{i+1}" for i, c in enumerate(st.session_state['clubs'])]
sel_name = st.selectbox("분석할 소속 선택", club_options)
sel_idx = club_options.index(sel_name)
club = st.session_state['clubs'][sel_idx]

if st.button("📊 정밀 분석 시작"):
    start_dt = datetime.datetime.combine(target_date, start_t)
    end_dt = datetime.datetime.combine(target_date, end_t)
    
    st.write(f"### 📡 실시간 분석 로그")
    
    try:
        # 멤버 파싱 (방장: 맹구 형태 및 띄어쓰기 지원)
        member_map = {}
        owner_name = "방장"
        for line in club['m_list'].split('\n'):
            if ':' in line:
                c, n = line.split(':', 1)
                c, n = c.strip(), n.strip()
                if c == '방장': owner_name = n
                else: member_map[c] = n

        headers = {"Cookie": st.session_state.get('user_cookie', ''), "User-Agent": "Mozilla/5.0"}
        res = requests.get(club['url'], headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 게시글 번호 추출
        post_nos = list(dict.fromkeys(re.findall(r'no=(\d+)', res.text)))
        st.write(f"📍 목록에서 총 {len(post_nos)}개의 글 번호를 찾았습니다.")
        
        found_members = set()
        owner_wrote = False
        valid_count = 0

        for p_no in post_nos[:20]:
            p_url = f"https://www.instiz.net/writing/{p_no}"
            p_res = requests.get(p_url, headers=headers)
            
            # 날짜 정밀 수색 (본문 전체에서 정규식으로 찾기)
            # 2025/10/15 21:42:50 또는 2025.10.15 21:42 등 모든 형태 대응
            date_match = re.search(r'(\d{4}[./]\d{2}[./]\d{2} \d{2}:\d{2}(?::\d{2})?)', p_res.text)
            
            if not date_match:
                st.write(f"❓ {p_no}번 글: 날짜 형식을 찾을 수 없음")
                continue
                
            date_str = date_match.group(1).replace('/', '.') # 형식을 점(.)으로 통일
            try:
                # 초 단위가 있으면 포함해서 해석, 없으면 분까지만 해석
                fmt = "%Y.%m.%d %H:%M:%S" if date_str.count(':') == 2 else "%Y.%m.%d %H:%M"
                p_dt = datetime.datetime.strptime(date_str, fmt)
            except:
                st.write(f"❌ {p_no}번 글: 날짜 해석 실패 ({date_str})")
                continue

            if start_dt <= p_dt <= end_dt:
                valid_count += 1
                st.write(f"✅ **적중!** {p_no}번 글 ({date_str})")
                
                if_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={p_no}"
                if_res = requests.get(if_url, headers=headers)
                
                matched = False
                for code, name in member_map.items():
                    if code in if_res.text:
                        found_members.add(code)
                        matched = True
                        st.write(f"   ㄴ 작성자: {name}({code})")
                        break
                if not matched:
                    owner_wrote = True
                    st.write(f"   ㄴ 작성자: {owner_name}(방장)")
            else:
                st.write(f"⚪ {p_no}번 글 ({date_str}): 범위 밖")

        # 결과
        st.divider()
        res_list = [{"이름": f"{owner_name}(방장)", "상태": "✅ 완료" if owner_wrote else "❌ 미작성"}]
        for c, n in member_map.items():
            res_list.append({"이름": n, "상태": "✅ 완료" if c in found_members else "❌ 미작성"})
        st.table(pd.DataFrame(res_list))
        st.success(f"분석 완료! 범위 내 글 {valid_count}개 발견")

    except Exception as e:
        st.error(f"🚨 에러: {e}")
