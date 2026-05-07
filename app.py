import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import time

st.set_page_config(page_title="뻘필 분석기", layout="wide")

st.title("📱 뻘필 할당량 분석기 (집주인 모드)")
st.caption("작성자: 로하 | 번호표가 없으면 '주인'으로 인식합니다.")

# --- ⚙️ 설정 섹션 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

with st.expander("⚙️ 설정 및 멤버 관리 (필독!)"):
    st.session_state['user_cookie'] = st.text_input("내 인스티즈 Cookie", type="password", value=st.session_state.get('user_cookie', ''))
    
    st.info("💡 멤버 명단 작성 팁:\n1. 집주인은 'MAIN:이름'으로 적으세요.\n2. 나머지는 '식별값:이름'으로 적으세요.")
    
    num_clubs = st.number_input("관리 동아리 수", 1, 10, value=len(st.session_state['clubs']))
    
    updated_clubs = []
    for i in range(num_clubs):
        st.markdown(f"**# {i+1}번 동아리**")
        name = st.text_input(f"이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'] if i < len(st.session_state['clubs']) else "")
        url = st.text_input(f"목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'] if i < len(st.session_state['clubs']) else "")
        m_list = st.text_area(f"멤버 명단", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'] if i < len(st.session_state['clubs']) else "", placeholder="MAIN:로하\n01470:수지\n만두찌개:철수")
        updated_clubs.append({"name": name, "url": url, "m_list": m_list})
    
    if st.button("💾 모든 설정 저장"):
        st.session_state['clubs'] = updated_clubs
        st.success("설정이 저장되었습니다!")

# --- 🔍 분석 실행 섹션 ---
st.divider()
col1, col2 = st.columns(2)
with col1:
    target_date = st.date_input("🗓️ 분석 날짜 선택", datetime.date.today())
with col2:
    selected_club_idx = st.selectbox("🎯 대상 동아리 선택", range(num_clubs), format_func=lambda x: st.session_state['clubs'][x]['name'] if st.session_state['clubs'][x]['name'] else f"동아리 #{x+1}")

if st.button("🚀 할당량 체크 시작"):
    club = st.session_state['clubs'][selected_club_idx]
    if not st.session_state.get('user_cookie') or not club['url'] or not club['m_list']:
        st.error("설정에서 모든 정보를 입력해주세요!")
    else:
        with st.spinner("분석 중..."):
            try:
                # 1. 명단 분류 (주인 vs 세입자)
                owner_name = "주인"
                member_map = {}
                for line in club['m_list'].split('\n'):
                    if ':' in line:
                        code, name = line.split(':', 1)
                        if code.strip().upper() == 'MAIN':
                            owner_name = name.strip()
                        else:
                            member_map[code.strip()] = name.strip()

                # 2. 데이터 수집
                headers = {"Cookie": st.session_state['user_cookie'], "User-Agent": "Mozilla/5.0"}
                res = requests.get(club['url'], headers=headers)
                soup = BeautifulSoup(res.text, 'html.parser')
                post_links = soup.select("a[href*='no=']")
                
                found_codes = set()
                owner_post_count = 0
                
                progress_bar = st.progress(0)
                for idx, link in enumerate(post_links):
                    post_no = link['href'].split('no=')[-1].split('&')[0]
                    iframe_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={post_no}"
                    iframe_res = requests.get(iframe_url, headers=headers)
                    
                    # 판독 시작
                    is_member_post = False
                    for code in member_map.keys():
                        if code in iframe_res.text:
                            found_codes.add(code)
                            is_member_post = True
                            break
                    
                    # 어떤 번호표도 없다면? 주인 글로 간주!
                    if not is_member_post:
                        owner_post_count += 1
                    
                    progress_bar.progress((idx + 1) / len(post_links))
                    time.sleep(0.05)

                # 3. 결과 출력
                results = []
                # 주인 결과
                results.append({"이름": f"{owner_name}(주인)", "상태": "✅ 완료" if owner_post_count > 0 else "❌ 미작성"})
                # 멤버 결과
                for code, name in member_map.items():
                    status = "✅ 완료" if code in found_codes else "❌ 미작성"
                    results.append({"이름": name, "상태": status})
                
                st.subheader("📊 분석 결과")
                st.table(pd.DataFrame(results))
                
            except Exception as e:
                st.error(f"오류: {e}")
