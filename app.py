import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import re
import time
import json
import os
import concurrent.futures

st.set_page_config(page_title="오로트 소속 관리 시스템", layout="wide")

# --- 1. 데이터 저장 및 로드 로직 ---
def get_db_path(room_id):
    return f"room_{room_id}.json"

def load_room_data(room_id):
    path = get_db_path(room_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"members": [], "filters": "카데판, 게임판, 산책판"}

def save_room_data(room_id, data):
    path = get_db_path(room_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- 2. 사이드바: 접속 및 로그인 ---
with st.sidebar:
    st.header("🔐 시크릿 룸 접속")
    room_id = st.text_input("소속 코드 (Room ID)", type="password", help="데이터를 저장하고 불러올 열쇠입니다.")
    user_cookie = st.text_input("인스티즈 Cookie", type="password", help="서버에 저장되지 않으며 세션 종료 시 휘발됩니다.")
    
    if room_id:
        if 'current_room' not in st.session_state or st.session_state['current_room'] != room_id:
            st.session_state['room_data'] = load_room_data(room_id)
            st.session_state['current_room'] = room_id
        st.success(f"'{room_id}' 방 접속 중")
    else:
        st.warning("소속 코드를 입력해주세요.")

# --- 3. 메인 화면: 멤버 및 필터 설정 ---
st.title("🛡️ 오로트(Orot) 할당량 관리 시스템")

if 'room_data' in st.session_state:
    with st.expander("⚙️ 멤버 및 필터링 설정", expanded=not st.session_state['room_data']['members']):
        st.subheader("🚫 제외 키워드 설정")
        st.session_state['room_data']['filters'] = st.text_area("제목에 포함되면 제외할 키워드 (쉼표 구분)", value=st.session_state['room_data']['filters'])
        
        st.divider()
        st.subheader("👤 멤버 추가/삭제")
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1: new_name = st.text_input("이름", key="new_name")
        with c2: new_url = st.text_input("신알신 링크 (방장은 '방장' 입력)", key="new_url")
        with c3: 
            st.write("")
            if st.button("추가", use_container_width=True):
                if new_name and new_url:
                    st.session_state['room_data']['members'].append({"이름": new_name, "링크": new_url})
                    save_room_data(room_id, st.session_state['room_data'])
                    st.rerun()

        if st.session_state['room_data']['members']:
            m_df = pd.DataFrame(st.session_state['room_data']['members'])
            st.table(m_df)
            del_idx = st.number_input("삭제할 행 번호", 0, len(st.session_state['room_data']['members'])-1, step=1)
            if st.button("🗑️ 선택 멤버 삭제", type="primary"):
                st.session_state['room_data']['members'].pop(del_idx)
                save_room_data(room_id, st.session_state['room_data'])
                st.rerun()

    # --- 4. 분석 실행 섹션 ---
    st.divider()
    col_run1, col_run2 = st.columns([2, 1])
    with col_run1:
        club_url = st.text_input("필명 전체글 보기 URL")
    with col_run2:
        target_date = st.date_input("체크 날짜", datetime.date.today())

    # 분석 엔진
    def check_member_logic(member, club_url, cookie, filters):
        name = member['이름']
        p_no_match = re.search(r'(?:no=|writing/)(\d+)', member['링크'])
        if not p_no_match: return name, False
        
        p_no = p_no_match.group(1)
        headers = {"Cookie": cookie, "User-Agent": "Mozilla/5.0"}
        
        # 신청 (Toggle ON)
        requests.get(f"https://www.instiz.net/bbs/alarm_post.php?id=writing&no={p_no}", headers=headers, timeout=5)
        time.sleep(0.5)
        
        has_done = False
        try:
            res = requests.get(club_url, headers=headers, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            filter_list = [f.strip() for f in filters.split(',')]
            
            for row in soup.select('tr, li, div'):
                text = row.get_text()
                if "알림 취소" in text:
                    # 필터링 대조
                    if not any(f in text for f in filter_list if f):
                        has_done = True
                        break
        except: pass
        
        # 해제 (Toggle OFF)
        requests.get(f"https://www.instiz.net/bbs/alarm_post.php?id=writing&no={p_no}", headers=headers, timeout=5)
        return name, has_done

    if st.button("🚀 30인 병렬 필터링 분석 시작", use_container_width=True):
        if not user_cookie or not club_url:
            st.error("사이드바에 쿠키를 입력하고 목록 URL을 확인해주세요.")
        else:
            with st.status("⚡ 라이트닝 엔진 가동 중... (약 20초 소요)", expanded=True):
                members_only = [m for m in st.session_state['room_data']['members'] if "방장" not in m['링크']]
                leader_name = next((m['이름'] for m in st.session_state['room_data']['members'] if "방장" in m['링크']), "맹구")
                
                results = {m['이름']: False for m in st.session_state['room_data']['members']}
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                    futures = {executor.submit(check_member_logic, m, club_url, user_cookie, st.session_state['room_data']['filters']): m for m in members_only}
                    for future in concurrent.futures.as_completed(futures):
                        name, ok = future.result()
                        results[name] = ok

                # 결과 요약
                st.subheader(f"📊 {target_date} 할당량 현황")
                res_df = pd.DataFrame([{"이름": n, "상태": "✅ 완료" if ok else "❌ 미작성"} for n, ok in results.items()])
                st.table(res_df)
                
                summary = f"[{target_date.strftime('%m/%d')} 현황]\n"
                for n, ok in results.items():
                    summary += f"- {n}: {'✅ 완료' if ok else '❌ 미작성'}\n"
                st.text_area("📋 카톡 공지용 복사", summary, height=150)
else:
    st.info("👈 사이드바에서 소속 코드(Room ID)를 입력하여 접속해주세요.")
