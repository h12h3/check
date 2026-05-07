import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import time
import re

st.set_page_config(page_title="뻘필 분석기 v5.0", layout="wide")

st.title("🕵️ 뻘필 분석기 (현장 생중계 버전)")
st.info("분석 버튼을 누른 후, 아래 '분석 로그'에 뜨는 내용을 유심히 봐주세요!")

# --- 세션 초기화 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

with st.sidebar:
    st.header("⚙️ 설정")
    user_cookie = st.text_input("내 인스티즈 Cookie", type="password", value=st.session_state.get('user_cookie', ''))
    if st.button("설정 저장"):
        st.session_state['user_cookie'] = user_cookie
        st.success("저장 완료!")

# --- 동아리 설정 ---
num_clubs = st.number_input("관리 동아리 수", 1, 10, value=len(st.session_state['clubs']))
for i in range(num_clubs):
    if i >= len(st.session_state['clubs']):
        st.session_state['clubs'].append({"name": "", "url": "", "m_list": ""})
    col1, col2 = st.columns(2)
    with col1:
        st.session_state['clubs'][i]['name'] = st.text_input(f"동아리 #{i+1} 이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'])
        st.session_state['clubs'][i]['url'] = st.text_input(f"목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'])
    with col2:
        st.session_state['clubs'][i]['m_list'] = st.text_area(f"명단 (식별값:이름)", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'], placeholder="MAIN:방장\n01470:수지")

# --- 분석 실행 ---
st.divider()
c1, c2 = st.columns(2)
with c1:
    target_date = st.date_input("🗓️ 분석 날짜", datetime.date.today())
with c2:
    start_t = st.time_input("⏰ 시작 시간", datetime.time(0, 0))
    end_t = st.time_input("⏰ 종료 시간", datetime.time(23, 59))

if st.button("🚀 분석 및 생중계 시작"):
    club = st.session_state['clubs'][st.selectbox("대상", range(num_clubs), format_func=lambda x: st.session_state['clubs'][x]['name'], label_visibility="collapsed")]
    start_dt = datetime.datetime.combine(target_date, start_t)
    end_dt = datetime.datetime.combine(target_date, end_t)
    
    st.write(f"### 📡 분석 로그 ({start_dt} ~ {end_dt})")
    
    try:
        # 멤버 파싱
        member_map = {}
        owner_name = "방장"
        for line in club['m_list'].split('\n'):
            if ':' in line:
                c, n = line.split(':', 1)
                if c.strip().upper() == 'MAIN': owner_name = n.strip()
                else: member_map[c.strip()] = n.strip()

        headers = {"Cookie": st.session_state.get('user_cookie', ''), "User-Agent": "Mozilla/5.0"}
        res = requests.get(club['url'], headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 1. 모든 게시글 번호 추출
        all_links = [l['href'] for l in soup.find_all('a', href=True) if 'no=' in l['href']]
        post_nos = list(dict.fromkeys([re.findall(r'no=(\d+)', l)[0] for l in all_links if re.findall(r'no=(\d+)', l)]))
        
        st.write(f"📍 목록에서 총 {len(post_nos)}개의 글 번호를 찾았습니다.")
        
        found_members = set()
        owner_wrote = False
        valid_count = 0

        for p_no in post_nos[:15]: # 상위 15개만 정밀 분석
            p_url = f"https://www.instiz.net/writing/{p_no}"
            p_res = requests.get(p_url, headers=headers)
            p_soup = BeautifulSoup(p_res.text, 'html.parser')
            
            # 날짜 텍스트 추출 시도
            raw_date = p_soup.find(string=re.compile(r'\d{2,4}\.\d{1,2}\.\d{1,2} \d{1,2}:\d{1,2}'))
            if not raw_date:
                st.write(f"❓ {p_no}번 글: 날짜를 찾을 수 없음")
                continue
                
            date_str = raw_date.strip()
            # 2025.1.1 -> 2025.01.01 형태 보정 (필요시)
            try:
                # 다양한 날짜 형식 지원 (25.10.15 vs 2025.10.15)
                fmt = "%Y.%m.%d %H:%M" if len(date_str.split('.')[0]) == 4 else "%y.%m.%d %H:%M"
                p_dt = datetime.datetime.strptime(date_str, fmt)
            except:
                st.write(f"❌ {p_no}번 글: 날짜 해석 실패 ({date_str})")
                continue

            # 범위 체크
            if start_dt <= p_dt <= end_dt:
                valid_count += 1
                st.write(f"✅ **적중!** {p_no}번 글 ({date_str}) - 분석 중...")
                
                # 식별값 확인
                if_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={p_no}"
                if_res = requests.get(if_url, headers=headers)
                
                matched = False
                for code, name in member_map.items():
                    if code in if_res.text:
                        found_members.add(code)
                        matched = True
                        st.write(f"   ㄴ 작성자 확인: {name}({code})")
                        break
                if not matched:
                    owner_wrote = True
                    st.write(f"   ㄴ 작성자 확인: {owner_name}(방장/지문없음)")
            else:
                st.write(f"⚪ {p_no}번 글 ({date_str}): 시간 범위 밖")

        # 결과 리포트
        st.divider()
        st.subheader("📊 최종 분석 결과")
        res_list = [{"이름": f"{owner_name}(방장)", "상태": "✅ 완료" if owner_wrote else "❌ 미작성"}]
        for c, n in member_map.items():
            res_list.append({"이름": n, "상태": "✅ 완료" if c in found_members else "❌ 미작성"})
        st.table(pd.DataFrame(res_list))
        st.success(f"범위 내 총 {valid_count}개의 글을 분석했습니다.")

    except Exception as e:
        st.error(f"🚨 에러 발생: {e}")
