import streamlit as st
import datetime
import pandas as pd

# 페이지 설정 (모바일 최적화)
st.set_page_config(page_title="뻘필 분석기", layout="centered")

st.title("📱 뻘필 할당량 분석기")
st.caption("작성자: 관리자 전용 / 데이터는 본인 브라우저에만 저장됩니다.")

# --- 1. 설정 저장 및 불러오기 (로컬 스토리지 시뮬레이션) ---
if 'clubs' not in st.session_state:
    st.session_state['clubs'] = [{"name": "", "url": "", "members": ""}]

with st.expander("⚙️ 동아리 및 쿠키 설정 (저장됨)"):
    user_cookie = st.text_input("내 인스티즈 쿠키", type="password")
    
    st.subheader("👥 관리 동아리 리스트 (최대 10개)")
    num_clubs = st.number_input("동아리 수", 1, 10, value=len(st.session_state['clubs']))
    
    # 동아리 수만큼 입력칸 생성
    updated_clubs = []
    for i in range(num_clubs):
        st.markdown(f"**# {i+1}번 동아리**")
        c_name = st.text_input(f"이름", key=f"n{i}")
        c_url = st.text_input(f"목록 URL", key=f"u{i}")
        c_mems = st.text_area(f"멤버 명단 (번호:이름)", key=f"m{i}", placeholder="01470:수지\n만두찌개:철수")
        updated_clubs.append({"name": c_name, "url": c_url, "members": c_mems})
    
    if st.button("설정 저장"):
        st.session_state['clubs'] = updated_clubs
        st.success("브라우저에 설정이 저장되었습니다!")

# --- 2. 분석 실행 섹션 ---
st.divider()
target_date = st.date_input("🗓️ 분석할 날짜", datetime.date.today())
club_names = [c['name'] if c['name'] else f"동아리 {i+1}" for i, c in enumerate(st.session_state['clubs'])]
selected_club = st.selectbox("🎯 대상 동아리 선택", club_names)

if st.button("🚀 할당량 체크 시작"):
    with st.spinner("데이터를 분석 중입니다..."):
        # 실제 인스티즈 서버와 통신하여 작성자를 가려내는 로직이 실행될 자리입니다.
        # 로하님이 주신 multiwriter 번호를 대조하게 됩니다.
        
        st.success(f"{target_date} 분석이 완료되었습니다!")
        
        # 가상의 결과 데이터 (디자인 예시)
        results = [
            {"이름": "수지(01470)", "상태": "✅ 완료", "시간": "14:05"},
            {"이름": "철수(만두찌개)", "상태": "❌ 미작성", "시간": "-"}
        ]
        st.table(pd.DataFrame(results))
        
        # 카톡 복사용 텍스트
        copy_text = f"[{target_date} {selected_club} 결과]\n"
        for r in results:
            copy_text += f"{r['이름']} : {r['상태']}\n"
        st.text_area("카톡 공지용 복사", copy_text)
