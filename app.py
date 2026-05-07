import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import re

st.set_page_config(page_title="소속 할당량 체크기", layout="wide")

st.title("⚡ 소속 할당량 번개 체크")
st.caption("v10.0 | 소속 관리 및 작성자 정밀 판독 (속도 개선판)")

# --- 세션 초기화 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

with st.sidebar:
    st.header("🔑 보안 설정")
    user_cookie = st.text_input("인스티즈 Cookie", type="password", value=st.session_state.get('user_cookie', ''))
    if st.button("보안 설정 저장"):
        st.session_state['user_cookie'] = user_cookie
        st.success("쿠키 저장 완료!")

# --- 소속 설정 ---
st.subheader("📋 소속 설정")
num_clubs = st.number_input("관리 소속 개수", 1, 10, value=len(st.session_state['clubs']))

for i in range(num_clubs):
    if i >= len(st.session_state['clubs']):
        st.session_state['clubs'].append({"name": "", "url": "", "m_list": ""})
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.session_state['clubs'][i]['name'] = st.text_input(f"소속 #{i+1}", key=f"n{i}", value=st.session_state['clubs'][i]['name'], placeholder="예: 떡잎마을방범대")
        st.session_state['clubs'][i]['url'] = st.text_input(f"목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'])
    with col2:
        example_m = "방장: 맹구\n01470: 수지\n만두찌개: 철수"
        st.session_state['clubs'][i]['m_list'] = st.text_area(f"인원 명단", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'], placeholder=example_m, height=120)

if st.button("💾 설정 정보 브라우저 저장"):
    st.success("저장되었습니다.")

# --- 분석 실행 ---
st.divider()
c1, c2 = st.columns(2)
with c1:
    target_date = st.date_input("체크 날짜", datetime.date.today())
with c2:
    start_t = st.time_input("시작 시간", datetime.time(0, 0))
    end_t = st.time_input("종료 시간", datetime.time(23, 59))

club_options = [c['name'] if c['name'] else f"소속 #{i+1}" for i, c in enumerate(st.session_state['clubs'])]
sel_name = st.selectbox("소속 선택", club_options)
club = st.session_state['clubs'][club_options.index(sel_name)]

if st.button("🚀 번개 분석 시작"):
    start_dt = datetime.datetime.combine(target_date, start_t)
    end_dt = datetime.datetime.combine(target_date, end_t)
    
    with st.spinner("🚀 광속 분석 중..."):
        try:
            # 1. 명단 파싱
            member_map = {}
            owner_name = "맹구"
            for line in club['m_list'].split('\n'):
                if ':' in line:
                    k, v = line.split(':', 1)
                    k, v = k.strip(), v.strip()
                    if k == "방장": owner_name = v
                    else: member_map[k] = v

            # 2. 통신 세션 생성 (속도 향상 핵심)
            session = requests.Session()
            session.headers.update({
                "Cookie": st.session_state.get('user_cookie', ''),
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            
            res = session.get(club['url'], timeout=5)
            post_nos = list(dict.fromkeys(re.findall(r'(?:no=|writing/)(\d+)', res.text)))
            
            found_members = set()
            owner_wrote = False
            
            # 3. 최신 글 10개만 타이트하게 분석
            for p_no in post_nos[:10]:
                p_url = f"https://www.instiz.net/writing/{p_no}"
                p_res = session.get(p_url, timeout=3)
                
                dt_match = re.search(r'(\d{4}[./]\d{2}[./]\d{2} \d{2}:\d{2}(?::\d{2})?)', p_res.text)
                if not dt_match: continue
                
                p_dt = datetime.datetime.strptime(dt_match.group(1).replace('/', '.'), 
                       "%Y.%m.%d %H:%M:%S" if dt_match.group(1).count(':') == 2 else "%Y.%m.%d %H:%M")

                if start_dt <= p_dt <= end_dt:
                    # 작성자 지문 수색 (iframe을 따로 열지 않고 본문 소스에서 바로 검색)
                    matched = False
                    for code in member_map.keys():
                        # multiwriter=번호 또는 onclick 등 모든 패턴 수색
                        if code in p_res.text:
                            found_members.add(code)
                            matched = True
                            break
                    if not matched:
                        # 본문에 멤버 지문이 없으면 iframe 한 번 더 확인 (수지님 구조 대응)
                        if_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={p_no}"
                        if_res = session.get(if_url, timeout=2)
                        for code in member_map.keys():
                            if code in if_res.text:
                                found_members.add(code)
                                matched = True
                                break
                        if not matched: owner_wrote = True

            # 4. 결과 출력 (군더더기 없이!)
            st.subheader(f"📊 {sel_name} 결과 리포트")
            final_res = [{"이름": f"{owner_name}(방장)", "상태": "✅ 완료" if owner_wrote else "❌ 미작성"}]
            for code, name in member_map.items():
                final_res.append({"이름": name, "상태": "✅ 완료" if code in found_members else "❌ 미작성"})
            
            st.table(pd.DataFrame(final_res))
            
            summary = f"[{target_date} {sel_name} 현황]\n"
            for r in final_res:
                summary += f" - {r['이름']}: {r['상태']}\n"
            st.text_area("📋 카톡 복사용", summary)

        except Exception as e:
            st.error(f"🚨 오류 발생: {e}")
