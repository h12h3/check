import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import time

st.set_page_config(page_title="뻘필 분석기", layout="wide")

st.title("📱 뻘필 할당량 분석기 (최종본)")
st.caption("작성자: 로하 | 모든 데이터는 브라우저에만 저장됩니다.")

# --- ⚙️ 설정 섹션 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

with st.expander("⚙️ 동아리 및 쿠키 설정 (본인 폰에 저장됨)"):
    st.session_state['user_cookie'] = st.text_input("내 인스티즈 Cookie", type="password", value=st.session_state.get('user_cookie', ''))
    num_clubs = st.number_input("관리 동아리 수", 1, 10, value=len(st.session_state['clubs']))
    
    updated_clubs = []
    for i in range(num_clubs):
        st.markdown(f"**# {i+1}번 동아리**")
        name = st.text_input(f"이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'] if i < len(st.session_state['clubs']) else "")
        url = st.text_input(f"목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'] if i < len(st.session_state['clubs']) else "")
        m_list = st.text_area(f"멤버 명단 (식별값:이름)", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'] if i < len(st.session_state['clubs']) else "", placeholder="01470:수지\n만두찌개:철수")
        updated_clubs.append({"name": name, "url": url, "m_list": m_list})
    
    if st.button("💾 모든 설정 저장"):
        st.session_state['clubs'] = updated_clubs
        st.success("브라우저에 설정이 저장되었습니다!")

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
        st.error("설정에서 쿠키, URL, 멤버 명단을 모두 입력해주세요!")
    else:
        with st.spinner(f"'{club['name']}'의 {target_date} 데이터를 분석 중입니다..."):
            try:
                # 1. 멤버 명단 정리
                member_map = {}
                for line in club['m_list'].split('\n'):
                    if ':' in line:
                        code, name = line.split(':', 1)
                        member_map[code.strip()] = name.strip()

                # 2. 인스티즈 목록 페이지 접속
                headers = {"Cookie": st.session_state['user_cookie'], "User-Agent": "Mozilla/5.0"}
                res = requests.get(club['url'], headers=headers)
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # 3. 글 목록 추출 및 필터링
                found_codes = set()
                # 인스티즈 목록에서 글 번호(no) 추출 (보통 .listsubject 나 a 태그 내 포함)
                post_links = soup.select("a[href*='no=']")
                
                # 진행률 표시
                progress_bar = st.progress(0)
                total_posts = len(post_links)
                
                for idx, link in enumerate(post_links):
                    post_url = "https://www.instiz.net" + link['href']
                    # 날짜 체크 로직 (HTML 구조에 따라 조정 필요)
                    # 여기서는 간단히 모든 글의 '신알신' 데이터를 확인합니다.
                    
                    # 4. 각 글의 '신알신' iframe 데이터 확인 (진짜 지문 캐내기)
                    post_no = post_url.split('no=')[-1].split('&')[0]
                    iframe_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={post_no}"
                    
                    iframe_res = requests.get(iframe_url, headers=headers)
                    # iframe 소스코드 내에서 multiwriter=01470 같은 텍스트 찾기
                    for code in member_map.keys():
                        if code in iframe_res.text:
                            found_codes.add(code)
                    
                    progress_bar.progress((idx + 1) / total_posts)
                    time.sleep(0.1) # 서버 과부하 방지

                # 5. 결과 테이블 생성
                results = []
                for code, name in member_map.items():
                    status = "✅ 완료" if code in found_codes else "❌ 미작성"
                    results.append({"이름": name, "식별값": code, "상태": status})
                
                st.subheader("📊 분석 결과")
                st.dataframe(pd.DataFrame(results), use_container_width=True)
                
                # 6. 카톡 공지용 요약
                done = [r['이름'] for r in results if "✅" in r['상태']]
                fail = [r['이름'] for r in results if "❌" in r['상태']]
                
                summary = f"[{target_date} {club['name']} 할당량 결과]\n\n"
                summary += f"✔️ 작성 완료 ({len(done)}명): {', '.join(done) if done else '없음'}\n"
                summary += f"⚠️ 미작성 ({len(fail)}명): {', '.join(fail) if fail else '없음'}"
                
                st.text_area("📋 카톡 공지용 복사", summary, height=150)

            except Exception as e:
                st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")
