import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import time

st.set_page_config(page_title="뻘필 분석기 v4.0", layout="wide")

st.title("⏱️ 정밀 뻘필 할당량 분석기")
st.caption("v4.0: 에러 방지 및 시간 정밀 체크 기능 탑재")

# --- 세션 초기화 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

with st.expander("⚙️ 설정 및 멤버 관리"):
    st.session_state['user_cookie'] = st.text_input("내 인스티즈 Cookie", type="password", value=st.session_state.get('user_cookie', ''))
    num_clubs = st.number_input("관리 동아리 수", 1, 10, value=len(st.session_state['clubs']))
    
    updated_clubs = []
    for i in range(num_clubs):
        if i >= len(st.session_state['clubs']):
            st.session_state['clubs'].append({"name": "", "url": "", "m_list": ""})
            
        st.markdown(f"**# {i+1}번 동아리**")
        name = st.text_input(f"이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'])
        url = st.text_input(f"목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'])
        m_list = st.text_area(f"명단 (MAIN:방장명 / 식별값:멤버명)", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'])
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

selected_club_idx = st.selectbox("🎯 대상 동아리", range(num_clubs), format_func=lambda x: st.session_state['clubs'][x]['name'] if st.session_state['clubs'][x]['name'] else f"동아리 #{x+1}")

if st.button("🚀 정밀 분석 시작"):
    club = st.session_state['clubs'][selected_club_idx]
    start_dt = datetime.datetime.combine(target_date, start_time)
    end_dt = datetime.datetime.combine(target_date, end_time)
    
    with st.status("🔍 데이터 수집 및 분석 중...", expanded=True) as status:
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
            
            # 모든 글 링크 수집 (에러 방지용 안전 선택기)
            all_links = soup.find_all('a', href=True)
            post_links = [l['href'] for l in all_links if 'no=' in l['href']]
            # 중복 제거
            post_links = list(dict.fromkeys(post_links))
            
            found_members = set()
            owner_wrote = False
            valid_posts_count = 0
            
            for idx, link in enumerate(post_links[:20]): # 최신 20개만
                try:
                    post_no = link.split('no=')[-1].split('&')[0]
                    p_url = f"https://www.instiz.net/writing/{post_no}"
                    p_res = requests.get(p_url, headers=headers)
                    p_soup = BeautifulSoup(p_res.text, 'html.parser')
                    
                    # 날짜 추출 (클래스명이 다를 경우를 대비해 여러 후보군 체크)
                    date_element = p_soup.select_one(".writer_date") or p_soup.select_one(".min_date")
                    if not date_element: continue
                    
                    p_dt = datetime.datetime.strptime(date_element.text.strip(), "%Y.%m.%d %H:%M")
                    
                    # 범위 체크
                    if start_dt <= p_dt <= end_dt:
                        valid_posts_count += 1
                        iframe_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={post_no}"
                        if_res = requests.get(iframe_url, headers=headers)
                        
                        matched = False
                        for code, name in member_map.items():
                            if code in if_res.text:
                                found_members.add(code)
                                matched = True
                                break
                        if not matched: owner_wrote = True
                        st.write(f"✅ {p_dt} 글 분석 완료")
                except:
                    continue # 한 글에서 에러나도 다음으로!

            status.update(label="분석 완료!", state="complete")
            
            # 결과 리포트
            results = [{"이름": f"{owner_name}(방장)", "상태": "✅ 완료" if owner_wrote else "❌ 미작성"}]
            for c, n in member_map.items():
                results.append({"이름": n, "상태": "✅ 완료" if c in found_members else "❌ 미작성"})
            
            st.table(pd.DataFrame(results))
            st.info(f"범위 내에서 총 {valid_posts_count}개의 글을 확인했습니다.")

        except Exception as e:
            st.error(f"🚨 중대한 오류 발생: {e}")
