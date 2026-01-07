import streamlit as st
import json
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from PIL import Image 
from fpdf import FPDF 
import time
import os

# ==========================================
# 0. 頁面與全域設定
# ==========================================

# 設定頁面配置 (必須在所有 Streamlit 指令之前)
try:
    icon_image = Image.open("ios_icon.png") 
    st.set_page_config(page_title="消防考試綜合刷題站", page_icon=icon_image, layout="wide")
except:
    st.set_page_config(page_title="消防考試綜合刷題站", page_icon="📝", layout="wide")

# 考試結構定義 (三層架構)
EXAM_STRUCTURE = {
    "消防升官等考": {
        "icon": "👨‍🚒",
        "description": "警正、員級晉高員級",
        "subjects": {
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
                "handwriting_file": "handwriting chinese.json",
                "prefix": "Chi",
                "icon": "📖",
                "has_handwriting": True
            }
        }
    },
    "警大二技": {
        "icon": "👮‍♂️",
        "description": "中央警察大學二年制技術系",
        "subjects": {
            "英文": {
                "file": "cpu_english.json",
                "prefix": "CpuEng",
                "icon": "🔤",
                "has_handwriting": False
            },
            "國文與憲法": {
                "file": "cpu_chi_const.json",
                "prefix": "CpuCC",
                "icon": "📜",
                "has_handwriting": False
            },
            "消防法規": {
                "file": "cpu_fire_law.json",
                "prefix": "CpuLaw",
                "icon": "🚒",
                "has_handwriting": False
            },
            "普通化學": {
                "file": "cpu_chemistry.json",
                "prefix": "CpuChem",
                "icon": "🧪",
                "has_handwriting": False
            }
        }
    },
    "消防設備士": {
        "icon": "🧯",
        "description": "專門職業及技術人員普通考試",
        "subjects": {
            "水與化學系統": {
                "file": "fst_water chemical systems.json",
                "prefix": "WaterChem",
                "icon": "💧",
                "has_handwriting": False
            },
            "火災學概要": {
                "file": "fst_fire science basic.json",
                "prefix": "FireSci",
                "icon": "🔥",
                "has_handwriting": False
            },
            "消防法規概要": {
                "file": "fst_fire law.json",
                "prefix": "FireLaw",
                "icon": "📜",
                "has_handwriting": False
            },
            "警報與避難系統": {
                "file": "fst_alarm evacuationsystems.json",
                "prefix": "Alarm",
                "icon": "🔔",
                "has_handwriting": False
            }
        }
    }
}

# 初始化 Session State
if 'current_exam_type' not in st.session_state:
    st.session_state['current_exam_type'] = None
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
        # st.error(f"連線讀取失敗：{e}") # 除錯用
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
        st.header("🔒 消防考試 - 綜合刷題站")
        try: user_list = list(st.secrets["passwords"].keys())
        except: st.error("找不到 secrets.toml 設定檔"); st.stop()
        
        selected_user = st.selectbox("請選擇登入人員", user_list)
        password_input = st.text_input("請輸入密碼", type="password")
        if st.button("登入"):
            if password_input == st.secrets["passwords"][selected_user]:
                st.session_state["password_correct"] = True
                st.session_state["username"] = selected_user
                st.session_state['current_exam_type'] = None
                st.session_state['current_subject'] = None
                st.rerun()
            else: st.error("❌ 密碼錯誤")
    return False

if not check_password(): st.stop()

# ==========================================
# 3. PDF 功能 & 題目讀取
# ==========================================
def create_pdf(questions, title):
    pdf = FPDF()
    pdf.add_page()
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(current_dir, 'font.ttf') # 請確認目錄下有字型檔

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
# 4. 核心判斷邏輯 (單選 / 多選 / 爭議題)
# ==========================================
def check_answer(user_input, correct_input, q, username, prefix, fav_set, mis_set, mode):
    """
    處理單選、複選、爭議題的對錯判斷
    user_input: 字串 (如 "A" 或 "BCDE")
    correct_input: JSON中的 answer 欄位
    """
    is_correct = False
    
    # 邏輯 A：複選題 (例如 "BCDE") - 長度>1 且不是 "A 或 C"
    if len(correct_input) > 1 and "或" not in correct_input and "/" not in correct_input:
        # 這裡加一個保險，確保兩邊都排序過再比對 (避免 "CB" != "BC" 的情況)
        is_correct = ("".join(sorted(list(user_input))) == "".join(sorted(list(correct_input))))
        
    # 邏輯 B：爭議單選題 (例如 "A 或 C")
    elif "或" in correct_input or "/" in correct_input:
        is_correct = (user_input in correct_input and len(user_input) == 1)
        
    # 邏輯 C：一般單選題
    else:
        is_correct = (user_input == correct_input)

    if is_correct:
        st.success(f"✅ 正確！答案是：{correct_input}")
        # 如果是錯題模式，答對就移除
        if mode == "mis" and q['id'] in mis_set:
            mis_set.discard(q['id'])
            save_user_data(username, prefix, fav_set, mis_set)
            st.rerun()
    else:
        st.error(f"❌ 錯誤，正確答案是：{correct_input}")
        # 答錯加入錯題集
        if q['id'] not in mis_set:
            mis_set.add(q['id'])
            save_user_data(username, prefix, fav_set, mis_set)

# ==========================================
# 5. 模式功能：手寫模式 & 刷題模式
# ==========================================
def run_handwriting_mode(config, username, fav_set):
    st.subheader(f"✍️ {st.session_state['current_subject']} - 手寫練習模式")
    try: hw_questions = load_questions(config['handwriting_file'])
    except: st.error("找不到手寫題庫檔案！"); return

    years = sorted(list(set([q['year'] for q in hw_questions])), reverse=True)
    st.sidebar.markdown("### 篩選年份")
    sel_years = [y for y in years if st.sidebar.checkbox(f"{y} 年", value=True, key=f"hw_year_{y}")]
    
    types = sorted(list(set([q['type'] for q in hw_questions])))
    sel_type = st.sidebar.radio("題型", ["全部"] + types)
    
    pool = [q for q in hw_questions if q['year'] in sel_years]
    if sel_type != "全部": pool = [q for q in pool if q['type'] == sel_type]
    
    st.sidebar.markdown("---")
    st.sidebar.info(f"符合條件：{len(pool)} 題")

    if not pool: st.warning("沒有符合條件的題目"); return

    if 'hw_index' not in st.session_state: st.session_state.hw_index = 0
    if st.session_state.hw_index >= len(pool): st.session_state.hw_index = 0
    q = pool[st.session_state.hw_index]
    
    st.progress((st.session_state.hw_index + 1) / len(pool), text=f"第 {st.session_state.hw_index + 1} / {len(pool)} 題")

    with st.container(border=True):
        c1, c2 = st.columns([0.85, 0.15])
        with c1: st.markdown(f"### [{q['year']}年 {q['type']}] {q['title']}")
        with c2:
            is_fav = q['id'] in fav_set
            if st.button("✅ 已練" if is_fav else "⬜ 未練", key=f"hw_fav_{q['id']}"):
                if is_fav: fav_set.discard(q['id'])
                else: fav_set.add(q['id'])
                # 手寫模式暫存於 Fav 欄位
                save_user_data(username, config['prefix'], fav_set, st.session_state['current_mis'])
                st.rerun()
        st.info(q['prompt'])
        if 'requirements' in q: st.markdown(f"**【作答要求】**\n{q['requirements']}")

    c_in, c_ref = st.columns([1, 1])
    with c_in:
        st.markdown("#### 📝 模擬作答區")
        user_input = st.text_area("練習區", height=400, key=f"ans_{q['id']}")
        st.caption(f"字數：{len(user_input.replace('\n',''))}")
        if st.button("⏱️ 開始 10 分鐘計時"):
            with st.empty():
                for s in range(600, 0, -1):
                    st.write(f"剩餘時間：{s//60:02d}:{s%60:02d}"); time.sleep(1)
                st.write("⏰ 時間到！")
    with c_ref:
        st.markdown("#### 📖 參考範本")
        with st.expander("點擊查看參考擬答"): st.success(q['reference'])

    cp, cn = st.columns([1, 1])
    with cp:
        if st.button("⬅️ 上一題", disabled=(st.session_state.hw_index==0), use_container_width=True):
            st.session_state.hw_index -= 1; st.rerun()
    with cn:
        if st.button("下一題 ➡️", disabled=(st.session_state.hw_index==len(pool)-1), use_container_width=True):
            st.session_state.hw_index += 1; st.rerun()

def run_quiz_mode(config, username, fav_set, mis_set):
    try: all_questions = load_questions(config['file'])
    except FileNotFoundError: st.error(f"❌ 找不到檔案：{config['file']}"); st.stop()

    # 側邊欄設定
    st.sidebar.markdown(f"👤 **{username}**")
    if st.sidebar.button("💾 手動存檔"):
        save_user_data(username, config['prefix'], fav_set, mis_set)
        st.sidebar.success("✅ 已儲存！")
    
    keyword = st.sidebar.text_input("🔍 搜尋關鍵字")
    st.sidebar.markdown("---")

    MODE_NORMAL, MODE_FAV, MODE_MIS = "normal", "fav", "mis"
    if 'view_mode' not in st.session_state: st.session_state.view_mode = MODE_NORMAL
    
    mode_options = [MODE_NORMAL, MODE_FAV, MODE_MIS]
    def mode_label(x):
        if x == MODE_NORMAL: return "一般刷題"
        if x == MODE_FAV: return f"⭐ 收藏 ({len(fav_set)})"
        return f"❌ 錯題 ({len(mis_set)})"

    st.sidebar.radio("模式", mode_options, format_func=mode_label, key="view_mode")
    mode = st.session_state.view_mode
    st.sidebar.markdown("---")

    # 科目與年份篩選
    json_subjects = sorted(list(set([q['subject'] for q in all_questions])))
    selected_json_sub = st.sidebar.radio("子科目", json_subjects) if json_subjects else "無"
    
    # 篩選題目池
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

    # 分類 (Category) 篩選
    cat_counts = {}
    for q in pool: 
        c = q.get('category', '未分類')
        cat_counts[c] = cat_counts.get(c, 0) + 1
    cats = sorted(list(set([q.get('category', '未分類') for q in pool])))
    cats.insert(0, "全部")
    sel_cat = st.sidebar.radio("領域", cats, format_func=lambda x: f"{x} ({cat_counts.get(x,0)})" if x!="全部" else f"全部 ({len(pool)})")

    # 最終篩選
    final_qs = [q for q in pool if (sel_cat == "全部" or q.get('category') == sel_cat)]

    st.title(f"{config['icon']} {selected_json_sub} - {mode_label(mode)}")
    st.caption(f"題目數：{len(final_qs)}")

    # PDF 匯出按鈕
    if final_qs:
        col_dl1, col_dl2 = st.columns([0.7, 0.3])
        with col_dl2:
            if mode == MODE_FAV: p_title, b_label = f"收藏-{username}-{selected_json_sub}", "🖨️ 匯出收藏 (PDF)"
            elif mode == MODE_MIS: p_title, b_label = f"錯題-{username}-{selected_json_sub}", "🖨️ 匯出錯題 (PDF)"
            else: p_title, b_label = f"刷題-{selected_json_sub}", "🖨️ 匯出當前 (PDF)"
            
            if st.button(b_label, use_container_width=True):
                with st.spinner("製作中..."):
                    pdf_data = create_pdf(final_qs, p_title)
                    if pdf_data: st.download_button("📥 下載 PDF", pdf_data, f"{p_title}.pdf", "application/pdf")
                    else: st.error("找不到字型檔 font.ttf")

    st.markdown("---")
    if not final_qs: st.warning("沒有符合條件的題目")

    # --- 題目顯示迴圈 ---
    for q in final_qs:
        q_label = f"{q['year']}#{str(q['id'])[-2:]}"
        with st.container(border=True): # 加上邊框讓題目分明
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
                
                # 自動判斷單選或複選
                # 條件：答案長度 > 1 且不包含 "或" 或 "/"
                is_multiple = len(q['answer']) > 1 and "或" not in q['answer'] and "/" not in q['answer']

                if not is_multiple:
                    # --- 單選模式 (Radio) ---
                    u_ans = st.radio("選項", q['options'], key=f"q_{config['prefix']}_{q['id']}", label_visibility="collapsed", index=None)
                    if u_ans:
                        # 提取字母 A, B, C, D
                        ans_char = u_ans.replace("(","").replace(")","").replace(".","").strip()[0]
                        check_answer(ans_char, q['answer'], q, username, config['prefix'], fav_set, mis_set, mode)
                else:
                    # --- 複選模式 (Multiselect) ---
                    st.info("💡 此題為複選題，需全對才給分")
                    u_ans_list = st.multiselect("請選擇所有正確選項", q['options'], key=f"q_{config['prefix']}_{q['id']}")
                    
                    if st.button("確認送出", key=f"btn_submit_{q['id']}"):
                        if u_ans_list:
                            # 提取所有字母並排序，例如 ["(E)...", "(B)..."] -> "BE"
                            user_chars = "".join(sorted([opt.replace("(","").replace(")","").replace(".","").strip()[0] for opt in u_ans_list]))
                            # 正確答案也做排序
                            correct_chars = "".join(sorted(list(q['answer'])))
                            
                            check_answer(user_chars, correct_chars, q, username, config['prefix'], fav_set, mis_set, mode)
                        else:
                            st.warning("請至少選擇一個選項")

                with st.expander("查看詳解"): st.info(q['explanation'])

# ==========================================
# 6. 主程式導航流程
# ==========================================

# 階段 1: 選擇考試類型 (Exam Type)
if st.session_state['current_exam_type'] is None:
    st.title(f"👋 歡迎回來，{st.session_state['username']}")
    st.subheader("請選擇您的考試類別：")
    st.markdown("---")
    
    cols = st.columns(3)
    for idx, (exam_name, exam_info) in enumerate(EXAM_STRUCTURE.items()):
        with cols[idx]:
            with st.container(border=True):
                st.markdown(f"## {exam_info['icon']} {exam_name}")
                st.caption(exam_info['description'])
                if st.button(f"進入 {exam_name}", key=f"btn_exam_{exam_name}", use_container_width=True):
                    st.session_state['current_exam_type'] = exam_name
                    st.rerun()

# 階段 2: 選擇科目 (Subject)
elif st.session_state['current_subject'] is None:
    curr_exam_name = st.session_state['current_exam_type']
    curr_exam_info = EXAM_STRUCTURE[curr_exam_name]
    
    st.button("⬅️ 回考試首頁", on_click=lambda: st.session_state.update({'current_exam_type': None}))
    st.title(f"{curr_exam_info['icon']} {curr_exam_name} - 科目選擇")
    st.markdown("---")

    subjects = curr_exam_info['subjects']
    cols = st.columns(len(subjects)) if len(subjects) <= 4 else st.columns(4)
    
    for idx, (subj_name, subj_config) in enumerate(subjects.items()):
        col_idx = idx % 4 if len(subjects) > 4 else idx
        with cols[col_idx]:
            with st.container(border=True):
                st.markdown(f"### {subj_config['icon']} {subj_name}")
                if st.button(f"開始練習", key=f"btn_subj_{subj_name}", use_container_width=True):
                    st.session_state['current_subject'] = subj_name
                    st.session_state.view_mode = "normal"
                    st.rerun()

# 階段 3: 進入刷題介面 (Quiz)
else:
    curr_exam_name = st.session_state['current_exam_type']
    curr_subj_name = st.session_state['current_subject']
    config = EXAM_STRUCTURE[curr_exam_name]['subjects'][curr_subj_name]

    # 載入 User Data
    if 'current_fav' not in st.session_state or st.session_state.get('loaded_subject') != curr_subj_name:
        with st.spinner(f"正在載入 {curr_subj_name} 的進度..."):
            f_data, m_data = get_user_data(st.session_state['username'], config['prefix'])
            st.session_state['current_fav'] = f_data
            st.session_state['current_mis'] = m_data
            st.session_state['loaded_subject'] = curr_subj_name

    # 側邊欄 - 返回按鈕
    st.sidebar.title(f"{config['icon']} {curr_subj_name}")
    if st.sidebar.button("⬅️ 回科目選單"):
        st.session_state['current_subject'] = None
        st.rerun()
    
    # 判斷是手寫還是選擇題
    if config.get('has_handwriting', False):
        mode = st.sidebar.radio("練習類型", ["測驗題 (選擇)", "作文/公文 (手寫)"], index=0, key="quiz_type_selector")
        if mode == "作文/公文 (手寫)":
            run_handwriting_mode(config, st.session_state['username'], st.session_state['current_fav'])
        else:
            run_quiz_mode(config, st.session_state['username'], st.session_state['current_fav'], st.session_state['current_mis'])
    else:
        run_quiz_mode(config, st.session_state['username'], st.session_state['current_fav'], st.session_state['current_mis'])