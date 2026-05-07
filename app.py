import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import time

st.set_page_config(page_title="뻘필 분석기 v3.0", layout="wide")

st.title("⏱️ 정밀 뻘필 할당량 분석기")
st.caption("날짜와 시간 범위를 지정하여 정확하게 할당량을 체크합니다.")

# --- 세션 초기화 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

with st.expander("⚙️ 설정 및 멤버 관리"):
    st.session_state['user_cookie'] = st.text_input("내 인스티즈 Cookie", type="password", value=st.session_state.get('user_cookie', ''))
    num_clubs = st.number_input("관리 동아리 수", 1, 10, value=len(st.session_state['clubs']))
    
    updated_clubs = []
    for i in range(num_clubs):
        st.markdown(f"**# {i+1}번 동아리**")
        name = st.text_input(f"이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'] if i < len(st.session_state['clubs']) else "")
        url = st.text_input(f"목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'] if i < len(st.session_state['clubs']) else "")
        m_list = st.text_area(f"명단 (MAIN:방장명 / 식별값:멤버명)", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'] if i < len(st.session_state['clubs']) else "")
        updated_clubs.append({"name": name, "url": url, "m_list": m_list})
    
    if st.button("💾 설정 저장"):
        st.session_state['clubs'] = updated_clubs
        st.success("브라우저에 설정이 저장되었습니다!")

# --- 🔍 분석 실행 섹션 ---
st.divider()
c1, c2 = st.columns(2)
with c1:
    target_date = st.date_input("🗓️ 분석 날짜", datetime.date.today())
with c2:
    start_time = st.time_input("⏰ 시작 시간", datetime.time(0, 0))
    end_time = st.time_input("⏰ 종료 시간", datetime.time(23, 59))

selected_club_idx = st.selectbox("🎯 대상 동아리", range(num_clubs), format_func=lambda x: st.session_state['clubs'][x]['name'])

if st.button("🚀 정밀 분석 시작"):
    club = st.session_state['clubs'][selected_club_idx]
    
    # 분석 범위 설정 (시작~종료 일시)
    start_dt = datetime.datetime.combine(target_date, start_time)
    end_dt = datetime.datetime.combine(target_date, end_time)
    
    with st.spinner(f"{start_dt} ~ {end_dt} 범위의 글을 분석 중..."):
        try:
            # 멤버 파싱
            member_map = {}
            owner_name = "방장"
            for line in club['m_list'].split('\n'):
                if ':' in line:
                    c, n = line.split(':', 1)
                    if c.strip().upper() == 'MAIN': owner_name = n.strip()
                    else: member_map[c.strip()] = n.strip()

            headers = {"Cookie": st.session_state['user_cookie'], "User-Agent": "Mozilla/5.0"}
            res = requests.get(club['url'], headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 인스티즈 리스트에서 글과 날짜 파싱
            posts = soup.select(".listsubject") # 목록 구조에 따라 다를 수 있음
            
            found_members = set()
            owner_wrote = False
            
            progress = st.progress(0)
            valid_posts_count = 0
            
            # 목록의 글들을 하나씩 검사
            for idx, p in enumerate(posts):
                # 글의 날짜/시간 정보를 가져오는 부분 (인스티즈 리스트 구조 반영 필요)
                # 이 예제에서는 각 글의 페이지로 들어가서 정밀 날짜를 확인합니다.
                link = p.find_parent('a')['href']
                post_no = link.split('no=')[-1].split('&')[0]
                post_url = f"https://www.instiz.net/writing/{post_no}"
                
                p_res = requests.get(post_url, headers=headers)
                p_soup = BeautifulSoup(p_res.text, 'html.parser')
                
                # 1. 날짜 판독 (게시글 내 시간 텍스트 찾기)
                # 인스티즈는 보통 '2025.10.15 21:42' 형태
                p_time_text = p_soup.select_one(".writer_date").text if p_soup.select_one(".writer_date") else ""
                try:
                    p_dt = datetime.datetime.strptime(p_time_text, "%Y.%m.%d %H:%M")
                except:
                    continue # 날짜 형식이 안 맞으면 스킵
                
                # 2. 범위 체크 (지정한 시간 안에 있는 글인가?)
                if start_dt <= p_dt <= end_dt:
                    valid_posts_count += 1
                    # 3. 작성자 판독
                    iframe_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={post_no}"
                    if_res = requests.get(iframe_url, headers=headers)
                    
                    matched = False
                    for code in member_map.keys():
                        if code in if_res.text:
                            found_members.add(code)
                            matched = True
                            break
                    if not matched: # 번호표가 없으면 주인이 쓴 글!
                        owner_wrote = True
                
                progress.progress((idx + 1) / len(posts))
                if idx > 20: break # 성능을 위해 최신 20개까지만 체크

            # 결과 리포트
            results = [{"이름": f"{owner_name}(방장)", "상태": "✅ 완료" if owner_wrote else "❌ 미작성"}]
            for c, n in member_map.items():
                results.append({"이름": n, "상태": "✅ 완료" if c in found_members else "❌ 미작성"})
            
            st.success(f"분석 완료! (범위 내 발견된 글: {valid_posts_count}개)")
            st.table(pd.DataFrame(results))

        except Exception as e:
            st.error(f"오류 발생: {e}")
