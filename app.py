import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import re
import concurrent.futures

st.set_page_config(page_title="소속 할당량 체크", layout="wide")

st.title("🛡️ 소속 할당량 최종 분석 (v19.0)")
st.caption("신알신 버튼 및 관리자 지문 추적 시스템")

# --- 1. 보안 및 세션 설정 ---
if 'user_cookie' not in st.session_state:
    st.session_state['user_cookie'] = ""

with st.sidebar:
    st.header("🔑 보안")
    st.session_state['user_cookie'] = st.text_input("인스티즈 Cookie", type="password", value=st.session_state['user_cookie'])
    st.info("로그인 쿠키를 입력해야 관리자 권한으로 지문을 읽을 수 있습니다.")

# --- 2. 소속 설정 ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "m_list": ""}]

st.subheader("📋 소속 정보 및 인원 명단")
num_clubs = st.number_input("소속 개수", 1, 5, value=len(st.session_state['clubs']))

for i in range(num_clubs):
    col1, col2 = st.columns([1, 2])
    with col1:
        st.session_state['clubs'][i]['name'] = st.text_input(f"소속 이름", key=f"n{i}", value=st.session_state['clubs'][i]['name'])
        st.session_state['clubs'][i]['url'] = st.text_input(f"전체글 목록 URL", key=f"u{i}", value=st.session_state['clubs'][i]['url'])
    with col2:
        st.session_state['clubs'][i]['m_list'] = st.text_area(f"명단 (방장: 이름 / 식별값: 이름)", key=f"m{i}", value=st.session_state['clubs'][i]['m_list'], placeholder="방장: 맹구\n01470: 수지\n만두찌개: 철수")

# --- 3. 분석 기간 설정 ---
st.divider()
st.subheader("📅 분석 기간 설정")
c1, c2 = st.columns(2)
with c1:
    start_dt = st.datetime_input("날짜 체크 시작 일시", value=datetime.datetime.now() - datetime.timedelta(days=7))
with c2:
    end_dt = st.datetime_input("날짜 체크 끝 일시", value=datetime.datetime.now())

# --- 4. 분석 엔진 ---
def trace_fingerprint(p_no, headers, member_map, leader_name, start, end):
    try:
        p_url = f"https://www.instiz.net/writing/{p_no}"
        res = requests.get(p_url, headers=headers, timeout=5)
        
        # 날짜 체크
        dt_match = re.search(r'(\d{4}[./]\d{2}[./]\d{2} \d{2}:\d{2}(?::\d{2})?)', res.text)
        if not dt_match: return None
        p_dt = datetime.datetime.strptime(dt_match.group(1).replace('/', '.'), 
               "%Y.%m.%d %H:%M:%S" if dt_match.group(1).count(':') == 2 else "%Y.%m.%d %H:%M")

        if start <= p_dt <= end:
            # 수지님 지문 찾기 (페이지 내 모든 텍스트 + 모든 링크 주소 확인)
            # 신알신 버튼이나 신고/관리 링크에 숨은 번호까지 싹 긁어옵니다.
            soup = BeautifulSoup(res.text, 'html.parser')
            all_html = res.text + "".join([str(a) for a in soup.find_all('a', href=True)])
            
            for code, name in member_map.items():
                # 식별값(01470 등)이 소스코드나 링크 주소 어딘가에 박혀있는지 확인
                if code in all_html:
                    return {"name": name, "date": p_dt}
            
            # 기간 내 글인데 멤버 식별자가 없다면 방장(맹구)으로 판정
            return {"name": leader_name, "date": p_dt}
    except:
        return None

if st.button("🚀 정밀 할당량 분석 시작"):
    club = st.session_state['clubs'][0]
    with st.status("📡 지문 추적 중...", expanded=True) as status:
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
        post_nos = list(dict.fromkeys(re.findall(r'(?:no=|writing/)(\d+)', res.text)))
        
        # 결과 저장
        names = [leader_name] + list(member_map.values())
        results = {name: False for name in names if name != "미정"}

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(trace_fingerprint, p_no, headers, member_map, leader_name, start_dt, end_dt) for p_no in post_nos[:30]]
            for f in concurrent.futures.as_completed(futures):
                data = f.result()
                if data: results[data['name']] = True

        status.update(label="분석 완료!", state="complete")
        
        # 결과 출력 (이름만 깔끔하게!)
        st.subheader(f"📊 {start_dt.strftime('%m/%d')} ~ {end_dt.strftime('%m/%d')} 결과")
        final_df = pd.DataFrame([{"이름": n, "상태": "✅ 완료" if ok else "❌ 미작성"} for n, ok in results.items()])
        st.table(final_df)
        
        summary = f"[{start_dt.strftime('%m/%d')}~{end_dt.strftime('%m/%d')} 현황]\n"
        for n, ok in results.items():
            summary += f"- {n}: {'✅ 완료' if ok else '❌ 미작성'}\n"
        st.text_area("카톡 공지용 복사", summary, height=150)
