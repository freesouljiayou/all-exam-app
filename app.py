import streamlit as st
import json
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from PIL import Image 
from fpdf import FPDF 
import time

# ==========================================
# 0. 全域設定
# ==========================================
EXAM_CONFIG = {
    "刑法與消防法規": {
        "file": "questions criminal andfire law.json",
        "prefix": "Law",
        "icon": "🚒",
        "has_handwriting": False
    },
    "法學知識與英文": {
        "file": "questions law and english.json",
        "prefix": "Eng",
        "icon": "⚖️",
        "has_handwriting": False
    },
    "國文": {
        "file": "questions chinese.json",
        "handwriting_file": "handwriting chinese.json", # 手寫題庫檔
        "prefix": "Chi",
        "icon": "📖",
        "has_handwriting": True # 開啟手寫模式
    }
}

try:
    icon_image = Image.open("ios_icon.png") 
    st.set_page_config(page_title="消防升等考綜合刷題站", page_icon=icon_image, layout="wide")
except:
    st.set_page_config(page_title="消防升等考綜合刷題站", page_icon="📝", layout="wide")

if 'current_subject' not in st.session_state:
    st.session_state['current_subject'] = None 

# ==========================================
# 1. Google Sheets 資料庫功能
# ==========================================
def get_user_data(username, prefix):
    col_fav = f"Fav_{prefix}"
    col_mis = f"Mis_{prefix}"
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl=0)
        if df.empty: df = pd.DataFrame(columns=['Username'])
        
        expected_cols = ['Username', col_fav, col_mis]
        for col in expected_cols:
            if col not in df.columns: df[col] = None 

        user_row = df[df['Username'] == username]
        if not user_row.empty:
            fav_str = str(user_row.iloc[0][col_fav])
            mis_str = str(user_row.iloc[0][col_mis])
            fav_set = set(json.loads(fav_str)) if fav_str and fav_str not in ['nan', 'None'] else set()
            mis_set = set(json.loads(mis_str)) if mis_str and mis_str not in ['nan', 'None'] else set()
            return fav_set, mis_set
        else:
            return set(), set()
    except Exception as e:
        st.error(f"連線讀取失敗：{e}")
        return set(), set()

def save_user_data(username, prefix, fav_set, mis_set):
    col_fav = f"Fav_{prefix}"
    col_mis = f"Mis_{prefix}"
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl=0)
        
        fav_json = json.dumps(list(fav_set))
        mis_json = json.dumps(list(mis_set))
        
        if col_fav not in df.columns: df[col_fav] = None
        if col_mis not in df.columns: df[col_mis] = None

        if username in df['Username'].values:
            df.loc[df['Username'] == username, col_fav] = fav_json
            df.loc[df['Username'] == username, col_mis] = mis_json
        else:
            new_data = {'Username': username, col_fav: fav_json, col_mis: mis_json}
            for col in df.columns:
                if col not in new_data: new_data[col] = None
            new_row = pd.DataFrame([new_data])
            df = pd.concat([df, new_row], ignore_index=True)
            
        conn.update(data=df)
    except Exception as e:
        st.warning(f"自動存檔失敗：{e}")

# ==========================================
# 2. 登入驗證
# ==========================================
def check_password():
    if st.session_state.get("password_correct", False): return True
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.header("🔒 消防升等考 - 綜合刷題站")
        try: user_list = list(st.secrets["passwords"].keys())
        except: st.error("找不到 secrets.toml"); st.stop()
        
        selected_user = st.selectbox("請選擇登入人員", user_list)
        password_input = st.text_input("請輸入密碼", type="password")
        if st.button("登入"):
            if password_input == st.secrets["passwords"][selected_user]:
                st.session_state["password_correct"] = True
                st.session_state["username"] = selected_user
                st.rerun()
            else: st.error("❌ 密碼錯誤")
    return False

if not check_password(): st.stop()

# ==========================================
# 3. PDF 功能 (增加自動抓路徑)
# ==========================================
import os
def create_pdf(questions, title):
    pdf = FPDF()
    pdf.add_page()
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(current_dir, 'font.ttf')

    try:
        pdf.add_font('ChineseFont', '', font_path)
        pdf.set_font('ChineseFont', '', 12)
    except:
        return None

    pdf.set_font_size(16)
    pdf.cell(0, 10, title, ln=True, align='C')
    pdf.ln(5)
    pdf.set_font_size(11)
    
    for idx, q in enumerate(questions):
        if pdf.get_y() > 250: pdf.add_page()
        q_year = q.get('year', '')
        q_id = str(q.get('id', ''))
        q_content = q.get('question', '')
        pdf.multi_cell(0, 7, f"{idx + 1}. [{q_year}#{q_id[-2:]}] {q_content}")
        pdf.ln(1)
        for opt in q.get('options', []):
            pdf.set_x(15)
            pdf.multi_cell(0, 7, opt)
        pdf.ln(1)
        pdf.set_x(15)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 7, f"👉 正解: ({q.get('answer', '')})", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
    return bytes(pdf.output())

@st.cache_data
def load_questions(filename):
    with open(filename, 'r', encoding='utf-8') as f: return json.load(f)

# ==========================================
# 4. 手寫題模式邏輯 (新功能)
# ==========================================
def run_handwriting_mode(config, username, fav_set):
    st.subheader(f"✍️ {st.session_state['current_subject']} - 手寫練習模式")
    
    try:
        hw_questions = load_questions(config['handwriting_file'])
    except:
        st.error("找不到手寫題庫檔案！")
        return

    # 側邊欄篩選
    years = sorted(list(set([q['year'] for q in hw_questions])), reverse=True)
    sel_years = [y for y in years if st.sidebar.checkbox(f"{y} 年", value=True, key=f"hw_year_{y}")]
    
    types = sorted(list(set([q['type'] for q in hw_questions])))
    sel_type = st.sidebar.radio("題型", ["全部"] + types)
    
    # 篩選題目
    pool = [q for q in hw_questions if q['year'] in sel_years]
    if sel_type != "全部":
        pool = [q for q in pool if q['type'] == sel_type]
    
    st.sidebar.markdown("---")
    st.sidebar.info(f"符合條件：{len(pool)} 題")

    if not pool:
        st.warning("沒有符合條件的題目")
        return

    # 主畫面 - 使用 Tabs 來切換題目，避免頁面太長
    # 但為了刷題感，我們用 index 切換
    if 'hw_index' not in st.session_state: st.session_state.hw_index = 0
    
    # 確保 index 不會超標
    if st.session_state.hw_index >= len(pool): st.session_state.hw_index = 0
    
    q = pool[st.session_state.hw_index]
    
    # 進度條
    progress = (st.session_state.hw_index + 1) / len(pool)
    st.progress(progress, text=f"第 {st.session_state.hw_index + 1} / {len(pool)} 題")

    # 題目卡片
    with st.container(border=True):
        col_info, col_fav = st.columns([0.85, 0.15])
        with col_info:
            st.markdown(f"### [{q['year']}年 {q['type']}] {q['title']}")
        with col_fav:
            is_fav = q['id'] in fav_set
            if st.button("✅ 已練習" if is_fav else "⬜ 未練習", key=f"hw_fav_{q['id']}"):
                if is_fav: fav_set.discard(q['id'])
                else: fav_set.add(q['id'])
                save_user_data(username, config['prefix'], fav_set, st.session_state['current_mis'])
                st.rerun()

        st.info(q['prompt'])
        if 'requirements' in q:
            st.markdown(f"**【作答要求】**\n{q['requirements']}")

    # 作答區 (兩欄配置)
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.markdown("#### 📝 模擬作答區")
        user_input = st.text_area("請在此輸入你的擬答 (僅供練習，不會存檔)", height=400, key=f"ans_{q['id']}")
        word_count = len(user_input.replace("\n", "").replace(" ", ""))
        st.caption(f"目前字數：{word_count} 字")
        
        # 倒數計時器
        st.markdown("---")
        if st.button("⏱️ 開始 10 分鐘計時"):
            with st.empty():
                for seconds in range(600, 0, -1):
                    st.write(f"剩餘時間：{seconds // 60:02d}:{seconds % 60:02d}")
                    time.sleep(1)
                st.write("⏰ 時間到！")

    with c2:
        st.markdown("#### 📖 參考範本")
        with st.expander("點擊查看參考擬答 / 寫作指引", expanded=False):
            st.success(q['reference'])

    # 換題按鈕
    c_prev, c_next = st.columns([1, 1])
    with c_prev:
        if st.button("⬅️ 上一題", disabled=(st.session_state.hw_index == 0), use_container_width=True):
            st.session_state.hw_index -= 1
            st.rerun()
    with c_next:
        if st.button("下一題 ➡️", disabled=(st.session_state.hw_index == len(pool)-1), use_container_width=True):
            st.session_state.hw_index += 1
            st.rerun()

# ==========================================
# 5. 選擇題模式邏輯 (原本的邏輯封裝)
# ==========================================
def run_quiz_mode(config, username, fav_set, mis_set):
    try: all_questions = load_questions(config['file'])
    except FileNotFoundError: st.error(f"❌ 找不到檔案：{config['file']}"); st.stop()

    # Sidebar
    st.sidebar.markdown(f"👤 **{username}**")
    if st.sidebar.button("💾 雲端存檔"):
        save_user_data(username, config['prefix'], fav_set, mis_set)
        st.sidebar.success("✅ 已儲存！")

    keyword = st.sidebar.text_input("🔍 搜尋關鍵字")
    st.sidebar.markdown("---")

    MODE_NORMAL, MODE_FAV, MODE_MIS = "normal", "fav", "mis"
    def format_mode(opt):
        if opt == MODE_NORMAL: return "一般刷題"
        if opt == MODE_FAV: return f"⭐ 收藏 ({len(fav_set)})"
        if opt == MODE_MIS: return f"❌ 錯題 ({len(mis_set)})"
        return opt

    # 1. 初始化狀態 (如果沒有設定過，預設為一般刷題)
    if 'view_mode' not in st.session_state: 
        st.session_state.view_mode = MODE_NORMAL

    mode_options = [MODE_NORMAL, MODE_FAV, MODE_MIS]

    # 2. 直接使用 key="view_mode"
    # Streamlit 會自動把這個 widget 的選擇結果，同步到 st.session_state.view_mode
    # 我們不需要設定 index，也不用手動寫 mode = ...
    st.sidebar.radio(
        "模式", 
        mode_options, 
        format_func=format_mode, 
        key="view_mode" 
    )
    
    # 3. 取得目前的模式 (直接從 session_state 拿)
    mode = st.session_state.view_mode
    st.sidebar.markdown("---")

    json_subjects = list(set([q['subject'] for q in all_questions]))
    selected_json_sub = st.sidebar.radio("子科目", json_subjects) if json_subjects else "無"
    sub_questions = [q for q in all_questions if q['subject'] == selected_json_sub]
    years = sorted(list(set([q['year'] for q in sub_questions])), reverse=True)
    sel_years = [y for y in years if st.sidebar.checkbox(f"{y} 年", value=True)]

    pool = []
    for q in all_questions:
        if q['subject'] != selected_json_sub: continue
        if q['year'] not in sel_years: continue
        if keyword and keyword not in q['question']: continue
        if mode == MODE_FAV and q['id'] not in fav_set: continue
        if mode == MODE_MIS and q['id'] not in mis_set: continue
        pool.append(q)

    cat_counts = {}
    for q in pool: c = q.get('category', '未分類'); cat_counts[c] = cat_counts.get(c, 0) + 1
    cats = sorted(list(set([q.get('category', '未分類') for q in sub_questions]))); cats.insert(0, "全部")
    sel_cat = st.sidebar.radio("領域", cats, format_func=lambda x: f"{x} ({cat_counts.get(x,0)})" if x!="全部" else f"全部 ({len(pool)})")

    sel_sub_cat = "全部"
    if sel_cat != "全部":
        sub_pool_temp = [q for q in pool if q.get('category') == sel_cat]
        sub_counts = {}
        for q in sub_pool_temp: sc = q.get('sub_category', '未分類'); sub_counts[sc] = sub_counts.get(sc, 0) + 1
        base_sub_cats = sorted(list(set([q.get('sub_category','未分類') for q in sub_questions if q.get('category')==sel_cat])))
        base_sub_cats.insert(0, "全部")
        sel_sub_cat = st.sidebar.radio("細項", base_sub_cats, format_func=lambda x: f"{x} ({sub_counts.get(x,0)})" if x!="全部" else f"全部 ({len(sub_pool_temp)})")

    final_qs = [q for q in pool if (sel_cat == "全部" or q.get('category') == sel_cat) and (sel_sub_cat == "全部" or q.get('sub_category') == sel_sub_cat)]

    st.title(f"{config['icon']} {selected_json_sub} - {format_mode(mode)}")
    st.caption(f"題目數：{len(final_qs)}")

    if final_qs:
        col_dl1, col_dl2 = st.columns([0.7, 0.3])
        with col_dl2:
            if mode == MODE_FAV: p_title, b_label = f"【收藏】{username}-{selected_json_sub}", "🖨️ 匯出收藏 (PDF)"
            elif mode == MODE_MIS: p_title, b_label = f"【錯題】{username}-{selected_json_sub}", "🖨️ 匯出錯題 (PDF)"
            else: p_title, b_label = f"【刷題】{selected_json_sub}", "🖨️ 匯出當前 (PDF)"
            if st.button(b_label, use_container_width=True):
                with st.spinner("製作中..."):
                    pdf_data = create_pdf(final_qs, p_title)
                    if pdf_data: st.download_button("📥 下載 PDF", pdf_data, f"{p_title}.pdf", "application/pdf")
                    else: st.error("找不到字型檔 font.ttf")

    st.markdown("---")
    if not final_qs:
        st.warning("沒有符合條件的題目")

    for q in final_qs:
        q_label = f"{q['year']}#{str(q['id'])[-2:]}"
        with st.container():
            c1, c2 = st.columns([0.08, 0.92])
            with c1:
                is_fav = q['id'] in fav_set
                if st.button("⭐" if is_fav else "☆", key=f"fav_{config['prefix']}_{q['id']}"):
                    if is_fav: fav_set.discard(q['id'])
                    else: fav_set.add(q['id'])
                    save_user_data(username, config['prefix'], fav_set, mis_set)
                    st.rerun()
            with c2:
                st.markdown(f"### **[{q_label}]** {q['question']}")
                u_ans = st.radio("選項", q['options'], key=f"q_{config['prefix']}_{q['id']}", label_visibility="collapsed", index=None)
                if u_ans:
                    ans_char = u_ans.replace("(","").replace(")","").replace(".","").strip()[0]
                    if ans_char == q['answer']:
                        st.success("✅ 正確！")
                        if mode == MODE_MIS and q['id'] in mis_set:
                            mis_set.discard(q['id'])
                            save_user_data(username, config['prefix'], fav_set, mis_set)
                            st.rerun()
                    else:
                        st.error(f"❌ 錯誤，答案是 {q['answer']}")
                        if q['id'] not in mis_set:
                            mis_set.add(q['id'])
                            save_user_data(username, config['prefix'], fav_set, mis_set)
                    with st.expander("查看詳解"): st.info(q['explanation'])
        st.markdown("---")

# ==========================================
# 6. 主程式流程 (大腦)
# ==========================================
if st.session_state['current_subject'] is None:
    # --- 大廳 (選單) ---
    st.title(f"👋 歡迎回來，{st.session_state['username']}")
    st.subheader("請選擇今天要練習的科目：")
    st.markdown("---")
    cols = st.columns(len(EXAM_CONFIG))
    for idx, (subject_name, config) in enumerate(EXAM_CONFIG.items()):
        with cols[idx]:
            st.info(f"### {config['icon']} {subject_name}")
            if st.button(f"進入 {subject_name}", key=f"btn_{config['prefix']}", use_container_width=True):
                st.session_state['current_subject'] = subject_name
                # 確保這一行是這樣寫，讓它重置為一般模式
                st.session_state.view_mode = "normal" 
                st.rerun()
else:
    # --- 進入特定科目 ---
    current_subj_name = st.session_state['current_subject']
    current_config = EXAM_CONFIG[current_subj_name]
    
    # 載入 User Data
    if 'current_fav' not in st.session_state or st.session_state.get('loaded_subject') != current_subj_name:
        with st.spinner(f"正在載入 {current_subj_name} 的進度..."):
            f_data, m_data = get_user_data(st.session_state['username'], current_config['prefix'])
            st.session_state['current_fav'] = f_data
            st.session_state['current_mis'] = m_data
            st.session_state['loaded_subject'] = current_subj_name

    # 側邊欄 - 返回按鈕
    st.sidebar.title(f"{current_config['icon']} {current_subj_name}")
    if st.sidebar.button("🏠 返回主選單"):
        st.session_state['current_subject'] = None
        st.rerun()
    
    # 決定要跑哪種模式 (手寫 vs 選擇)
    if current_config.get('has_handwriting', False):
        # 顯示模式切換器 (放在側邊欄頂部)
        mode = st.sidebar.radio("練習類型", ["測驗題 (選擇)", "作文/公文 (手寫)"], index=0)
        
        if mode == "作文/公文 (手寫)":
            run_handwriting_mode(current_config, st.session_state['username'], st.session_state['current_fav'])
        else:
            run_quiz_mode(current_config, st.session_state['username'], st.session_state['current_fav'], st.session_state['current_mis'])
    else:
        # 沒有手寫題的科目，直接跑選擇題模式
        run_quiz_mode(current_config, st.session_state['username'], st.session_state['current_fav'], st.session_state['current_mis'])