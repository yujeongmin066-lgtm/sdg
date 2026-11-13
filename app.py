"""우리 집 물건 찾기 | 실행: streamlit run app.py
GitHub에 app.py와 requirements.txt를 올리고 Streamlit Community Cloud에서 배포.
서버의 SQLite 파일을 사용합니다. Cloud 재배포/재시작 시 데이터가 유실될 수
있으므로 JSON 백업을 받으세요. 가족 코드는 정식 사용자 인증이 아닙니다.
"""
import hashlib
import io
import json
import secrets
import sqlite3
from datetime import datetime

import qrcode
import streamlit as st

st.set_page_config(page_title="우리 집 물건 찾기", page_icon="🔎", layout="centered")
st.markdown("""<style>
.stApp{background:#f5f7fb}
.block-container{max-width:700px;padding-top:1.8rem}
h1,h2,h3{color:#263e64}
.stButton>button{min-height:48px;border-radius:12px}
[data-testid="stForm"]{background:white;border-radius:16px}
</style>""", unsafe_allow_html=True)
CATEGORIES = ["전자기기", "문구", "운동용품", "생활용품", "공구", "기타"]
IMPORTANCE = {1:"1 · 자주 찾는 물건", 2:"2 · 가끔 찾는 물건", 3:"3 · 보관 중인 물건"}

# 1. 데이터 저장: 가족별로 구분하여 SQLite 데이터베이스에 저장합니다.
def db():
    con = sqlite3.connect("family_items.sqlite3", timeout=20)
    con.row_factory = sqlite3.Row
    return con

with db() as con:
    con.execute("""CREATE TABLE IF NOT EXISTS belongings(
        id INTEGER PRIMARY KEY AUTOINCREMENT, family TEXT NOT NULL,
        name TEXT NOT NULL, category TEXT NOT NULL, location TEXT NOT NULL,
        importance INTEGER NOT NULL CHECK(importance BETWEEN 1 AND 3),
        note TEXT NOT NULL, borrower TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL)""")


def load_items(family):
    with db() as con:
        return [dict(row) for row in con.execute(
            "SELECT * FROM belongings WHERE family=? ORDER BY importance, id DESC", (family,))]


def stamp():
    return datetime.now().isoformat(timespec="seconds")

st.title("🔎 우리 집 물건 찾기")
st.caption("충전기 어디 뒀지? 가족의 물건과 보관 장소를 한곳에!")
with st.sidebar:
    st.header("🏠 가족 공간")
    if "suggested" not in st.session_state:
        st.session_state.suggested = secrets.token_urlsafe(12)
    st.caption("처음이라면 아래 코드를 가족끼리 공유하세요.")
    st.code(st.session_state.suggested)
    code = st.text_input("가족 코드 · 8자 이상", type="password")
    st.caption("같은 앱에서 같은 코드를 입력하면 같은 목록을 봅니다. 코드를 아는 누구나 수정할 수 있으니 민감한 정보는 넣지 마세요.")
    if st.button("🔄 최신 목록 불러오기", use_container_width=True):
        st.rerun()
    st.divider()
    st.subheader("📱 QR로 접속")
    url = st.text_input("배포된 앱 주소", placeholder="https://your-app.streamlit.app")
    st.caption("실제 배포 주소를 입력하세요. QR에는 가족 코드가 포함되지 않아요.")
    if url.strip().startswith("https://"):
        image = qrcode.make(url.strip())
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        st.image(buffer.getvalue(), width=190)
        st.download_button("QR 다운로드", buffer.getvalue(), "family_qr.png", "image/png")
    elif url:
        st.warning("https://로 시작하는 주소를 입력하세요.")

if len(code.strip()) < 8:
    st.info("왼쪽 위 메뉴(☰)를 열어 가족 코드를 입력해 주세요.")
    st.markdown("**물건 등록 → 이름·장소 검색 → 사용 중인 가족 확인 → 제자리에 반납**")
    st.stop()
family = hashlib.sha256(code.strip().encode()).hexdigest()
items = load_items(family)
with st.sidebar:
    st.divider()
    backup = [{k:v for k,v in item.items() if k not in ("id", "family")} for item in items]
    st.download_button("💾 물건 목록 백업", json.dumps({"version":1,"items":backup}, ensure_ascii=False, indent=2),
                       "family_items_backup.json", "application/json", use_container_width=True)
    st.caption("Cloud 파일은 영구 저장이 보장되지 않아요. 재배포 전에 백업하세요. 가족의 변경은 새로고침하면 반영돼요.")
    with st.expander("백업 복원 · 기존 목록에 추가"):
        upload = st.file_uploader("이 앱의 JSON 백업", type=["json"])
        if st.button("백업 복원", disabled=upload is None):
            try:
                source = json.loads(upload.getvalue())["items"]
                if not isinstance(source, list) or len(source) > 1000:
                    raise ValueError("최대 1,000개 항목을 복원할 수 있어요.")
                values = []
                for item in source:
                    name = str(item["name"]).strip()
                    location = str(item["location"]).strip()
                    category = item["category"]
                    importance = int(item["importance"])
                    if not name or not location or len(name)>60 or len(location)>100 or category not in CATEGORIES or importance not in IMPORTANCE:
                        raise ValueError("이름, 장소, 분류, 중요도를 확인해 주세요.")
                    values.append((family,name,category,location,importance,str(item.get("note",""))[:160],str(item.get("borrower",""))[:30],stamp()))
                with db() as con:
                    con.executemany("INSERT INTO belongings(family,name,category,location,importance,note,borrower,updated) VALUES(?,?,?,?,?,?,?,?)", values)
                st.rerun()
            except (ValueError, KeyError, TypeError, OverflowError) as error:
                st.error(f"복원 실패: {error}")

left, right = st.columns(2)
left.metric("등록한 물건", f"{len(items)}개")
right.metric("사용 중인 물건", f"{sum(bool(x['borrower']) for x in items)}개")
find_tab, add_tab, about_tab = st.tabs(["🔎 물건 찾기", "➕ 등록", "💡 앱 소개"])

# 2. 입력: 이름, 분류, 위치, 중요도, 메모를 입력받습니다.
with add_tab:
    with st.form("add", clear_on_submit=True):
        name = st.text_input("물건 이름 *", max_chars=60, placeholder="예: 배드민턴 라켓")
        category = st.selectbox("카테고리", CATEGORIES)
        location = st.text_input("보관 장소 *", max_chars=100, placeholder="예: 현관 신발장 맨 아래 칸")
        importance = st.radio("표시 우선순위", [1,2,3], format_func=lambda x: IMPORTANCE[x])
        note = st.text_input("특징 / 메모", max_chars=160, placeholder="예: 파란색 손잡이, 사용 후 제자리에")
        if st.form_submit_button("➕ 물건 등록", use_container_width=True):
            if not name.strip() or not location.strip():
                st.error("물건 이름과 보관 장소는 꼭 입력해 주세요.")
            else:
                with db() as con:
                    con.execute("INSERT INTO belongings(family,name,category,location,importance,note,updated) VALUES(?,?,?,?,?,?,?)",
                                (family,name.strip(),category,location.strip(),importance,note.strip(),stamp()))
                st.rerun()

# 3. 처리: 부분 문자열 검색, 카테고리 필터링, 중요도 정렬을 수행합니다.
with find_tab:
    keyword = st.text_input("물건·장소·메모·사용자 검색", placeholder="예: 라켓, 현관, 파란색")
    a,b = st.columns(2)
    category_filter = a.selectbox("분류", ["전체"]+CATEGORIES)
    state_filter = b.selectbox("상태", ["전체", "보관 중", "사용 중"])
    frequent_only = st.toggle("1순위 물건만 보기")
    query = keyword.strip().casefold()
    found = []
    for item in items:
        text = " ".join([item["name"],item["location"],item["note"],item["borrower"]]).casefold()
        if query and query not in text:
            continue
        if category_filter != "전체" and item["category"] != category_filter:
            continue
        if state_filter == "사용 중" and not item["borrower"]:
            continue
        if state_filter == "보관 중" and item["borrower"]:
            continue
        if frequent_only and item["importance"] != 1:
            continue
        found.append(item)
    st.caption(f"검색 결과 {len(found)}개 · 1순위부터 표시합니다.")
    if not found:
        st.info("조건에 맞는 물건이 없어요. 검색 조건을 바꾸거나 등록 탭에서 추가하세요.")
    # 4. 출력: 검색 결과를 카드 형태로 표시합니다.
    for item in found:
        ident = item["id"]
        with st.container(border=True):
            st.subheader(item["name"])
            st.caption(f"{item['category']} · {IMPORTANCE[item['importance']]}")
            st.write(f"📍 보관 장소: {item['location']}")
            if item["note"]:
                st.write(f"📝 {item['note']}")
            if item["borrower"]:
                st.info(f"🙋 {item['borrower']} 님이 사용 중이에요.")
                if st.button("✅ 제자리에 반납했어요", key=f"return_{ident}", use_container_width=True):
                    with db() as con:
                        con.execute("UPDATE belongings SET borrower='',updated=? WHERE id=? AND family=?", (stamp(),ident,family))
                    st.rerun()
            else:
                with st.expander("🙋 이 물건 사용할게요"):
                    with st.form(f"borrow_{ident}"):
                        borrower = st.text_input("사용하는 가족 이름 / 별명", max_chars=30)
                        if st.form_submit_button("사용 중으로 표시", use_container_width=True):
                            if not borrower.strip():
                                st.error("이름이나 별명을 입력하세요.")
                            else:
                                with db() as con:
                                    con.execute("UPDATE belongings SET borrower=?,updated=? WHERE id=? AND family=?", (borrower.strip(),stamp(),ident,family))
                                st.rerun()
            with st.expander("✏️ 수정 / 삭제"):
                with st.form(f"edit_{ident}"):
                    n = st.text_input("이름", value=item["name"], max_chars=60)
                    c = st.selectbox("분류 수정", CATEGORIES, index=CATEGORIES.index(item["category"]))
                    loc = st.text_input("장소", value=item["location"], max_chars=100)
                    p = st.selectbox("중요도", [1,2,3], index=item["importance"]-1)
                    memo = st.text_input("메모", value=item["note"], max_chars=160)
                    if st.form_submit_button("수정 저장"):
                        if not n.strip() or not loc.strip():
                            st.error("이름과 장소를 모두 입력하세요.")
                        else:
                            with db() as con:
                                con.execute("UPDATE belongings SET name=?,category=?,location=?,importance=?,note=?,updated=? WHERE id=? AND family=?",
                                            (n.strip(),c,loc.strip(),p,memo.strip(),stamp(),ident,family))
                            st.rerun()
                confirm = st.checkbox("이 물건의 기록을 삭제할게요", key=f"confirm_{ident}")
                if st.button("기록 삭제", key=f"delete_{ident}", disabled=not confirm):
                    with db() as con:
                        con.execute("DELETE FROM belongings WHERE id=? AND family=?", (ident,family))
                    st.rerun()

with about_tab:
    st.subheader("정보 수행평가: 앱의 문제 해결 과정")
    st.markdown("""
**문제 발견** — 가족이 공용 물건의 위치를 몰라 찾는 데 시간을 써요.

**해결 방법** — 물건의 보관 장소와 사용 중인 가족을 함께 기록해요.

- **입력:** 물건 이름, 분류, 장소, 중요도, 메모
- **저장:** SQLite 데이터베이스에 가족별 기록 저장
- **처리:** 검색어 포함 여부 판단, 조건 필터링, 중요도 순 정렬
- **출력:** 물건 카드, 보관 장소, 사용 상태, 개수

**사용한 정보 개념:** 변수, 리스트, 딕셔너리, 조건문, 반복문, 함수, 데이터베이스

**QR의 역할:** 배포된 웹 앱 주소를 쉽게 여는 바로가기예요. 물건의 실제 위치를 자동 추적하지는 않아요.

**한계:** 가족이 직접 위치와 사용 상태를 입력해야 해요. 가족 코드는 정식 로그인이 아니며,
동시에 수정하면 마지막 저장 내용이 반영될 수 있어요. 푸시 알림은 없어요.
""")
