import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import re

st.set_page_config(page_title="소속 할당량 체크", layout="wide")

st.title("🏢 소속 할당량 정밀 분석기")
st.caption("v21.0 | 방장 이름 통합 & 자유 기간 설정 & 지문 정밀 추적")

# --- 1. 보안 설정 (쿠키) ---
if 'user_cookie' not in st.session_state:
    st.session_state['user_cookie'] = ""

with st.sidebar:
    st.header("🔑 보안")
    st.session_state['user_cookie'] = st.text_input("인스티즈 Cookie", type="password", value=st.session_state['user_cookie'])
    st.info("쿠키를 입력해야 분석이 작동합니다.")

# --- 2. 소속 정보 입력 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

st.subheader("📋 소속 및 인원 설정")
num_clubs = st.number_input("소속 개수", 1, 5, value=len(st.session_state['clubs']))

for i in range(num_clubs):
    if i >= len(st.session_state['clubs']):
        st.session_state['clubs'].append({"name": "", "url": "", "m_list": ""})
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.session_state['clubs'][i]['name'] = st.text_input(f"소속 이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'], placeholder="예: 떡잎마을방범대")
        st.session_state['clubs'][i]['url'] = st.text_input(f"전체글 목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'], placeholder="전체글 보기 주소")
    with col2:
        example_m = "방장: 맹구\n01470: 수지\n만두찌개: 철수"
        st.session_state['clubs'][i]['m_list'] = st.text_area(f"인원 명단 (방장: 이름 / 식별값: 이름)", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'], placeholder=example_m, height=100)

# --- 3. 분석 기간 설정 (시작/끝 날짜+시간) ---
st.divider()
st.subheader("📅 분석 기간 설정")
col_s1, col_s2 = st.columns(2)
with col_s1:
    s_date = st.date_input("날짜 체크 시작일", datetime.date.today() - datetime.timedelta(days=7))
    s_time = st.time_input("시작 시간", datetime.time(0, 0))
with col_s2:
    e_date = st.date_input("날짜 체크 종료일", datetime.date.today())
    e_time = st.time_input("종료 시간", datetime.time(23, 59))

start_dt = datetime.datetime.combine(s_date, s_time)
end_dt = datetime.datetime.combine(e_date, e_time)

# --- 4. 분석 엔진 ---
if st.button("🚀 정밀 할당량 분석 시작"):
    club = st.session_state['clubs'][0] # 첫 번째 소속 우선 분석
    
    if not st.session_state['user_cookie']:
        st.error("보안 설정을 위해 쿠키를 먼저 입력해주세요!")
    else:
        with st.status("📡 지문 추적 및 데이터 대조 중...", expanded=True) as status:
            try:
                # 명단 파싱
                member_map = {}
                leader_name = "미정"
                for line in club['m_list'].split('\n'):
                    if ':' in line:
                        k, v = line.split(':', 1); k, v = k.strip(), v.strip()
                        if k == "방장": leader_name = v
                        else: member_map[k] = v

                headers = {"Cookie": st.session_state['user_cookie'], "User-Agent": "Mozilla/5.0"}
                res = requests.get(club['url'], headers=headers)
                
                # 목록에서 모든 글 번호 싹 긁어오기
                post_nos = list(dict.fromkeys(re.findall(r'(?:no=|writing/)(\d+)', res.text)))
                
                # 결과 저장용 (중복 없이 맹구, 수지, 철수 이름만!)
                check_results = {leader_name: False}
                for name in member_map.values():
                    check_results[name] = False

                for p_no in post_nos[:30]:
                    p_url = f"https://www.instiz.net/writing/{p_no}"
                    p_res = requests.get(p_url, headers=headers)
                    
                    # 글 내부에서 정밀 날짜 추출 (2025/10/15 21:42:50 형태 대응)
                    dt_match = re.search(r'(\d{4}[./]\d{2}[./]\d{2} \d{2}:\d{2}(?::\d{2})?)', p_res.text)
                    if not dt_match: continue
                    
                    raw_dt = dt_match.group(1).replace('/', '.')
                    fmt = "%Y.%m.%d %H:%M:%S" if raw_dt.count(':') == 2 else "%Y.%m.%d %H:%M"
                    p_dt = datetime.datetime.strptime(raw_dt, fmt)

                    # 지정한 기간 내의 글인지 확인
                    if start_dt <= p_dt <= end_dt:
                        if_url = f"https://www.instiz.net/iframe_writing.htm?id=writing&no={p_no}"
                        if_res = requests.get(if_url, headers=headers)
                        combined_src = p_res.text + if_res.text
                        
                        matched_member = False
                        for code, name in member_map.items():
                            # 수지님의 식별값(01470)이 소스코드 어딘가에라도 있는지 정밀 수색
                            if code in combined_src or f"'{code}'" in combined_src or f'"{code}"' in combined_src:
                                check_results[name] = True
                                matched_member = True
                                break
                        
                        # 기간 내 글인데 멤버의 식별자가 없다면? -> 방장(맹구) 글로 확정!
                        if not matched_member and leader_name != "미정":
                            check_results[leader_name] = True

                status.update(label="분석 완료!", state="complete")
                
                # --- 결과 출력 ---
                st.subheader(f"📊 할당량 현황 ({start_dt.strftime('%m/%d')} ~ {end_dt.strftime('%m/%d')})")
                # 결과 테이블 (이름만 깔끔하게!)
                final_df = pd.DataFrame([{"이름": n, "상태": "✅ 완료" if ok else "❌ 미작성"} for n, ok in check_results.items() if n != "미정"])
                st.table(final_df)
                
                summary = f"[{start_dt.strftime('%m/%d')}~{end_dt.strftime('%m/%d')} 현황]\n"
                for n, ok in check_results.items():
                    if n != "미정":
                        summary += f"- {n}: {'✅ 완료' if ok else '❌ 미작성'}\n"
                st.text_area("📋 카톡 공지용 복사", summary, height=150)

            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")
