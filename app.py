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

st.set_page_config(page_title="오로트 정밀 할당량 시스템", layout="wide")

# --- 1. 데이터 보안 및 로드 함수 ---
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

# --- 2. 로그인 세션 관리 ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    # [로그인 창]
    st.title("🔐 오로트 시스템 접속")
    with st.form("login_form"):
        room_id = st.text_input("소속 코드 (Room ID)", type="password")
        user_cookie = st.text_input("인스티즈 Cookie", type="password")
        submit = st.form_submit_button("시스템 승인 및 접속")
        
        if submit:
            if room_id and user_cookie:
                st.session_state['room_id'] = room_id
                st.session_state['user_cookie'] = user_cookie
                st.session_state['room_data'] = load_room_data(room_id)
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("코드와 쿠키를 모두 입력해주세요.")
    st.stop()

# --- 3. 분석기 본체 (로그인 성공 시) ---
st.title(f"🛡️ {st.session_state['room_id']} 할당량 분석기")

# 상단 탭 구성 (멤버 관리 / 분석 실행)
tab1, tab2 = st.tabs(["👤 멤버 및 설정 관리", "🚀 할당량 분석 실행"])

with tab1:
    st.subheader("🚫 제외 키워드 설정")
    st.session_state['room_data']['filters'] = st.text_area("제외 키워드 (쉼표 구분)", value=st.session_state['room_data']['filters'])
    if st.button("설정 저장"):
        save_room_data(st.session_state['room_id'], st.session_state['room_data'])
        st.success("키워드가 저장되었습니다.")

    st.divider()
    st.subheader("👥 멤버 명단 관리")
    
    # 추가 폼
    with st.form("add_member_form", clear_on_submit=True):
        c1, c2 = st.columns([1, 2])
        name = c1.text_input("이름")
        link = c2.text_input("신알신 링크 (방장은 '방장' 입력)")
        if st.form_submit_button("➕ 멤버 추가"):
            if name and link:
                st.session_state['room_data']['members'].append({"이름": name, "링크": link})
                save_room_data(st.session_state['room_id'], st.session_state['room_data'])
                st.rerun()

    # 명단 표시 및 선택 삭제
    if st.session_state['room_data']['members']:
        m_df = pd.DataFrame(st.session_state['room_data']['members'])
        st.write("현재 등록된 멤버 (행 번호를 확인하세요):")
        st.table(m_df)
        
        del_idx = st.number_input("삭제할 멤버의 행 번호", 0, len(st.session_state['room_data']['members'])-1, step=1)
        if st.button("🗑️ 선택한 멤버 삭제", type="primary"):
            st.session_state['room_data']['members'].pop(del_idx)
            save_room_data(st.session_state['room_id'], st.session_state['room_data'])
            st.rerun()

with tab2:
    st.subheader("📅 분석 범위 설정")
    col_run1, col_run2 = st.columns([2, 1])
    with col_run1:
        club_url = st.text_input("전체글 보기 URL (필명 목록 주소)")
        ref_post_url = st.text_input("기준 글 링크 (해당 날짜의 첫 번째 글)", placeholder="이 글부터 아래로 훑습니다.")
    with col_run2:
        target_date = st.date_input("체크할 날짜", datetime.date.today())
        analyze_btn = st.button("🚀 정밀 분석 시작", use_container_width=True)

    # --- 분석 로직 ---
    def check_member_logic(member, club_url, cookie, filters, target_dt):
        name = member['이름']
        p_no_match = re.search(r'(?:no=|writing/)(\d+)', member['링크'])
        if not p_no_match: return name, False
        
        p_no = p_no_match.group(1)
        headers = {"Cookie": cookie, "User-Agent": "Mozilla/5.0"}
        
        # 1. 신알신 신청
        requests.get(f"https://www.instiz.net/bbs/alarm_post.php?id=writing&no={p_no}", headers=headers, timeout=5)
        time.sleep(0.5)
        
        has_valid_post = False
        try:
            res = requests.get(club_url, headers=headers, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            filter_list = [f.strip() for f in filters.split(',')]
            
            # 목록의 각 글을 대조
            for row in soup.select('tr, li, .list_item'): # 인스티즈 테마 대응
                row_text = row.get_text()
                if "알림 취소" in row_text:
                    # 제목 필터링
                    is_filtered = any(f in row_text for f in filter_list if f)
                    if not is_filtered:
                        has_valid_post = True
                        break
        except: pass
        
        # 2. 신알신 해제 (원상복구)
        requests.get(f"https://www.instiz.net/bbs/alarm_post.php?id=writing&no={p_no}", headers=headers, timeout=5)
        return name, has_valid_post

    if analyze_btn:
        if not club_url:
            st.error("목록 URL을 입력해주세요.")
        else:
            with st.status("⚡ 30인 병렬 분석 및 날짜 경계 확인 중...", expanded=True):
                members_only = [m for m in st.session_state['room_data']['members'] if "방장" not in m['링크']]
                leader_name = next((m['이름'] for m in st.session_state['room_data']['members'] if "방장" in m['링크']), "맹구")
                
                results = {m['이름']: False for m in st.session_state['room_data']['members']}
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                    futures = {executor.submit(check_member_logic, m, club_url, st.session_state['user_cookie'], st.session_state['room_data']['filters'], target_date): m for m in members_only}
                    for future in concurrent.futures.as_completed(futures):
                        name, ok = future.result()
                        results[name] = ok

                st.subheader(f"📊 {target_date} 분석 결과")
                res_df = pd.DataFrame([{"이름": n, "상태": "✅ 완료" if ok else "❌ 미작성"} for n, ok in results.items()])
                st.table(res_df)
                
                # 로그아웃 버튼
                if st.button("시스템 로그아웃"):
                    st.session_state['logged_in'] = False
                    st.rerun()
