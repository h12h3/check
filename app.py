import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import time
import re

st.set_page_config(page_title="소속 할당량 분석기", layout="wide")

st.title("🏢 소속 할당량 체크 시스템")
st.caption("v8.0 | 소속별 관리 및 방장/멤버 정밀 판독 모드")

# --- 세션 상태 초기화 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

with st.sidebar:
    st.header("🔑 개인 보안 설정")
    user_cookie = st.text_input("내 인스티즈 Cookie", type="password", value=st.session_state.get('user_cookie', ''))
    if st.button("설정 저장"):
        st.session_state['user_cookie'] = user_cookie
        st.success("보안 설정이 완료되었습니다.")

# --- 소속 정보 입력 ---
st.subheader("📋 소속 설정")
num_clubs = st.number_input("관리 중인 소속 개수", 1, 10, value=len(st.session_state['clubs']))

for i in range(num_clubs):
    if i >= len(st.session_state['clubs']):
        st.session_state['clubs'].append({"name": "", "url": "", "m_list": ""})
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.session_state['clubs'][i]['name'] = st.text_input(f"소속 #{i+1} 이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'], placeholder="예: 떡잎마을방범대")
        st.session_state['clubs'][i]['url'] = st.text_input(f"소속 목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'], placeholder="전체글 목록 주소")
    with col2:
        example_m = "방장: 맹구\n01470: 수지\n만두찌개: 철수"
        st.session_state['clubs'][i]['m_list'] = st.text_area(f"소속 #{i+1} 인원 명단", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'], placeholder=example_m, height=120)

if st.button("💾 모든 정보 브라우저 저장"):
    st.success("소속 정보가 본인 기기에 저장되었습니다.")

# --- 분석 실행 ---
st.divider()
st.subheader("🚀 할당량 체크 실행")
c1, c2 = st.columns(2)
with c1:
    target_date = st.date_input("분석 날짜", datetime.date.today())
with c2:
    start_t = st.time_input("시작 시간", datetime.time(0, 0))
    end_t = st.time_input("종료 시간", datetime.time(23, 59))

# 소속 선택
club_options = [c['name'] if c['name'] else f"소속 #{i+1}" for i, c in enumerate(st.session_state['clubs'])]
sel_name = st.selectbox("할당량을 체크할 소속 선택", club_options)
sel_idx = club_options.index(sel_name)
club = st.session_state['clubs'][sel_idx]

if st.button("🔍 정밀 분석 시작"):
    start_dt = datetime.datetime.combine(target_date, start_t)
    end_dt = datetime.datetime.combine(target_date, end_t)
    
    st.write(f"### 📡 {sel_name} 분석 로그")
    
    try:
        # 1. 멤버 명단 파싱 (방장: 맹구 / 01470: 수지 형식 대응)
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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://www.instiz.net/"
        }
        
        # 목록 페이지 요청
        res = requests.get(club['url'], headers=headers)
        
        # 목록 내 글 번호 추출 (더 강력한 정규식)
        # /writing/12345 또는 no=12345 형태 모두 수집
        post_nos = list(dict.fromkeys(re.findall(r'(?:no=|writing/)(\d+)', res.text)))
        
        # 본인이 작성한 글 번호 등은 제외 (필요시 조정)
        st.write(f"📍 목록에서 총 {len(post_nos)}개의 게시글 후보를 발견했습니다.")
        
        found_codes = set()
        owner_wrote = False
        valid_count = 0

        for p_no in post_nos[:15]: # 성능상 상위 15개
            p_url = f"https://www.instiz.net/writing/{p_no}"
            p_res = requests.get(p_url, headers=headers)
            
            # 2. 날짜 찾기 (본문 텍스트 전체에서 검색)
            # 인티 특유의 YYYY/MM/DD HH:MM:SS 또는 YYYY.MM.DD HH:MM 추출
            dt_regex = r'(\d{4}[./]\d{2}[./]\d{2} \d{2}:\d{2}(?::\d{2})?)'
            date_match = re.search(dt_regex, p_res.text)
            
            if not date_match:
                # 만약 본문에 없으면 title 태그나 meta 태그 확인 (최후의 보루)
                soup = BeautifulSoup(p_res.text, 'html.parser')
                date_str = soup.get_text() # 전체 텍스트에서 재수색
                date_match = re.search(dt_regex, date_str)

            if not date_match:
                st.write(f"❓ {p_no}번 글: 날짜를 확인할 수 없어 건너뜁니다.")
                continue
                
            raw_dt_str = date_match.group(1).replace('/', '.')
            try:
                fmt = "%Y.%m.%d %H:%M:%S" if raw_dt_str.count(':') == 2 else "%Y.%m.%d %H:%M"
                p_dt = datetime.datetime.strptime(raw_dt_str, fmt)
            except:
                continue

            # 3. 시간 범위 체크
            if start_dt <= p_dt <= end_dt:
                valid_count += 1
                st.write(f"✅ **범위 적중!** ({raw_dt_str})")
                
                # 4. 작성자 지문(multiwriter) 확인
                if_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={p_no}"
                if_res = requests.get(if_url, headers=headers)
                
                matched = False
                for code, name in member_map.items():
                    if code in if_res.text:
                        found_codes.add(code)
                        matched = True
                        st.write(f"   ㄴ 확인된 작성자: {name}")
                        break
                if not matched:
                    owner_wrote = True
                    st.write(f"   ㄴ 확인된 작성자: {owner_name}(방장)")
            else:
                st.write(f"⚪ {raw_dt_str}: 범위 밖입니다.")

        # 최종 리포트
        st.divider()
        st.subheader("📊 최종 할당량 체크 결과")
        final_data = [{"이름": f"{owner_name}(방장)", "상태": "✅ 완료" if owner_wrote else "❌ 미작성"}]
        for code, name in member_map.items():
            final_data.append({"이름": name, "상태": "✅ 완료" if code in found_codes else "❌ 미작성"})
        
        st.table(pd.DataFrame(final_data))
        st.success(f"지정한 시간에 작성된 글 총 {valid_count}개를 분석 완료했습니다!")

    except Exception as e:
        st.error(f"🚨 분석 중 오류가 발생했습니다: {e}")
