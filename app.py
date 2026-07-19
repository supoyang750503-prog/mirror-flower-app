import streamlit as st
from PIL import Image, ImageEnhance, ImageOps
import json
import os
import re
from datetime import datetime
import base64
from io import BytesIO

# 設定頁面配置
st.set_page_config(page_title="鏡花水月隨筆", page_icon="🌸", layout="wide")

# --- 路徑定義 (嚴格指向專案根目錄 ROOT) ---
# 使用 os.getcwd() 確保所有路徑相對於執行 streamlit run 的根目錄
BASE_DIR = os.getcwd() 
LOG_FILE = os.path.join(BASE_DIR, "plants_log.json")
DATA_IMAGES_DIR = os.path.join(BASE_DIR, "data_images")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads") # 保留以相容舊資料，但新圖將存入 data_images

if not os.path.exists(DATA_IMAGES_DIR):
    os.makedirs(DATA_IMAGES_DIR)
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# --- 資料處理函數 ---
def load_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
            # 確保格式統一
            for log in logs:
                if "image_path" in log and "image_paths" not in log:
                    log["image_paths"] = [log["image_path"]]
                    del log["image_path"]
            return logs
    return []

def save_logs(logs):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=4)

# --- 影像路徑解析 (搜尋根目錄下的 data_images/) ---
def resolve_images(entry):
    """
    從根目錄的 data_images/ 搜尋匹配植物名稱的所有檔案。
    """
    if not os.path.exists(DATA_IMAGES_DIR):
        return []
        
    raw_name = entry.get("name", "")
    plant_name_clean = raw_name.strip().lower()
    
    if not plant_name_clean:
        return []
    
    keywords = [k.strip().lower() for k in re.split(r'[()\[\]{}\-_]', plant_name_clean) if k.strip()]
    
    matched_files = []
    for f in os.listdir(DATA_IMAGES_DIR):
        if f.lower().endswith(('.png', '.jpg', '.jpeg')):
            f_name_clean = os.path.splitext(f)[0].lower()
            if plant_name_clean in f_name_clean or any(kw in f_name_clean for kw in keywords):
                matched_files.append(os.path.join(DATA_IMAGES_DIR, f))
    
    matched_files.sort()
    return matched_files

# --- 初始化 Session State ---
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

if 'logs' not in st.session_state:
    st.session_state.logs = load_logs()

if 'editing_index' not in st.session_state:
    st.session_state.editing_index = None

if 'plant_name' not in st.session_state:
    st.session_state.plant_name = ""
if 'photo_date' not in st.session_state:
    st.session_state.photo_date = datetime.now().date()
if 'notes' not in st.session_state:
    st.session_state.notes = ""
if 'filter_style' not in st.session_state:
    st.session_state.filter_style = "原圖"
if 'uploader_id' not in st.session_state:
    st.session_state.uploader_id = 0
if 'error_msg' not in st.session_state:
    st.session_state.error_msg = None

if 'expanded_logs' not in st.session_state:
    st.session_state.expanded_logs = {}

# --- Callback 函式 ---
def reset_form():
    st.session_state.plant_name = ""
    st.session_state.photo_date = datetime.now().date()
    st.session_state.notes = ""
    st.session_state.filter_style = "原圖"
    st.session_state.editing_index = None
    st.session_state.error_msg = None
    st.session_state.uploader_id += 1

def start_edit(index):
    entry = st.session_state.logs[index]
    st.session_state.editing_index = index
    st.session_state.plant_name = entry["name"]
    st.session_state.photo_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
    st.session_state.notes = entry["notes"]
    st.session_state.filter_style = entry["style"]
    st.session_state.error_msg = None

def delete_entry(index):
    st.session_state.logs.pop(index)
    save_logs(st.session_state.logs)
    st.toast("已刪除該筆紀錄")
    if st.session_state.editing_index == index:
        reset_form()

def submit_form():
    plant_name = st.session_state.plant_name
    uploader_key = f"uploaded_files_{st.session_state.uploader_id}"
    uploaded_files = st.session_state.get(uploader_key)

    is_editing = st.session_state.editing_index is not None
    if not plant_name:
        st.session_state.error_msg = "請輸入植物名稱。"
        return
    if not is_editing and not uploaded_files:
        st.session_state.error_msg = "請上傳至少一張照片。"
        return

    saved_paths = []
    # 如果是編輯且沒有上傳新圖，保留原路徑；否則儲存新圖至 data_images/
    if is_editing and not uploaded_files:
        saved_paths = st.session_state.logs[st.session_state.editing_index].get("image_paths", [])
    else:
        if uploaded_files:
            for idx, uploaded_file in enumerate(uploaded_files):
                file_ext = os.path.splitext(uploaded_file.name)[1]
                # 自動命名：植物名稱_1.jpg, 植物名稱_2.jpg ...
                filename = f"{plant_name}_{idx+1}{file_ext}"
                save_path = os.path.join(DATA_IMAGES_DIR, filename)
                
                with open(save_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # 儲存相對根目錄的路徑
                saved_paths.append(save_path)

    log_entry = {
        "name": plant_name,
        "date": str(st.session_state.photo_date),
        "notes": st.session_state.notes,
        "style": st.session_state.filter_style,
        "image_paths": saved_paths
    }

    if is_editing:
        st.session_state.logs[st.session_state.editing_index] = log_entry
        st.toast("紀錄已更新！")
    else:
        st.session_state.logs.append(log_entry)
        st.toast("日誌已成功儲存！")

    # 1. 寫入本地 JSON 檔案
    save_logs(st.session_state.logs)
    
    # 2. 重置表單狀態
    reset_form()
    
    # 3. 強制重新載入頁面以更新 UI
    st.rerun()

def toggle_expand(index):
    st.session_state.expanded_logs[index] = not st.session_state.expanded_logs.get(index, False)

# --- 影像處理函數 ---
def apply_filter(image, style):
    if style == "原圖":
        return image
    img = image.convert("RGB")
    r, g, b = img.split()
    if style == "清晨冷調":
        b = b.point(lambda i: i * 1.2)
        r = r.point(lambda i: i * 0.9)
        img = Image.merge("RGB", (r, g, b))
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(0.8)
        return img
    elif style == "暖陽金黃":
        r = r.point(lambda i: i * 1.2)
        g = g.point(lambda i: i * 1.1)
        img = Image.merge("RGB", (r, g, b))
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.1)
        return img
    return image

def get_image_base64(image):
    buffered = BytesIO()
    image.convert("RGB").save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

def render_photo_card(image, caption=None):
    """用於頂部預覽，保持 contain 模式以完整顯示圖片"""
    img_base64 = get_image_base64(image)
    html_code = f"""
    <div style="
        width: 100%; 
        height: 300px; 
        border-radius: 12px; 
        overflow: hidden; 
        box-shadow: 0 8px 20px rgba(0,0,0,0.3); 
        margin-bottom: 10px;
        background-color: #1a1a1a;
        display: flex;
        justify-content: center;
        align-items: center;
    ">
        <img src="data:image/jpeg;base64,{img_base64}" style="
            max-width: 100%; 
            max-height: 100%; 
            object-fit: contain;
        ">
    </div>
    """
    if caption:
        html_code += f'<p style="text-align: center; font-size: 0.8rem; color: #666; margin-top: -5px;">{caption}</p>'
    st.markdown(html_code, unsafe_allow_html=True)

def render_expanded_image(image):
    """用於展開後的網格，強制統一邊界且保持原圖比例 (Contain)"""
    img_base64 = get_image_base64(image)
    html_code = f"""
    <div style="
        height: 280px; 
        width: 100%; 
        background-color: rgba(255,255,255,0.03); 
        border-radius: 12px; 
        border: 1px solid rgba(255,255,255,0.1); 
        padding: 8px; 
        display: flex; 
        align-items: center; 
        justify-content: center;
        box-sizing: border-box;
    ">
        <img src="data:image/jpeg;base64,{img_base64}" style="
            object-fit: contain; 
            max-height: 100%; 
            max-width: 100%;
        ">
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)

# --- UI 介面設計 ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    [data-testid="stSidebar"] { background-color: #0E1117 !important; }
    .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown span { color: white !important; }
    
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #a855f7 0%, #3b82f6 100%) !important;
        color: white !important;
        border: none !important;
        font-weight: bold !important;
        transition: all 0.3s ease;
        width: 100%;
    }
    div.stButton > button:first-child:hover {
        opacity: 0.9;
        transform: scale(1.02);
        box-shadow: 0 0 15px rgba(168, 85, 247, 0.4);
    }

    .history-section div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(22, 24, 30, 0.9) !important;
        border: 1px solid rgba(138, 43, 226, 0.25) !important;
        border-radius: 12px !important;
        padding: 15px !important;
        margin-bottom: 15px !important;
        transition: all 0.3s ease;
    }
    .history-section div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: rgba(138, 43, 226, 0.6) !important;
        box-shadow: 0 0 20px rgba(138, 43, 226, 0.15) !important;
    }

    .purple-tag {
        background: linear-gradient(45deg, #6a11cb 0%, #2575fc 100%);
        color: white !important;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: bold;
        display: inline-block;
        margin-bottom: 8px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }

    .stats-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        color: #eee;
    }
    .stats-value {
        color: #a855f7;
        font-weight: bold;
        font-family: 'Courier New', monospace;
        font-size: 1.1rem;
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center; font-family: \"Georgia\", serif; color: white !important;'>🌸 鏡花水月隨筆 🌙</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #aaa !important; font-style: italic;'>於光影交錯間，記錄植物的低語與時光的流轉</p>", unsafe_allow_html=True)

# --- 左側欄 (Sidebar) ---
with st.sidebar:
    if st.session_state.is_admin:
        is_editing = st.session_state.editing_index is not None
        st.header("📝 編輯紀錄" if is_editing else "📝 新增紀錄")
        if st.session_state.error_msg:
            st.error(st.session_state.error_msg)
        st.text_input("植物名稱", key="plant_name", placeholder="例如：龜背竹、白蘭花")
        st.date_input("拍照日期", key="photo_date")
        st.text_area("觀察筆記", key="notes", placeholder="記錄光影特色、花期或心情...")
        uploaded_files = st.file_uploader(
            "上傳照片", type=["jpg", "jpeg", "png"], accept_multiple_files=True, 
            key=f"uploaded_files_{st.session_state.uploader_id}"
        )
        st.selectbox("選擇照片風格", ["原圖", "清晨冷調", "暖陽金黃"], key="filter_style")
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            submit_label = "🔄 重塑光影" if is_editing else "📷 鐫刻光影"
            st.button(submit_label, type="primary", on_click=submit_form)
        with col_btn2:
            if is_editing:
                st.button("取消編輯", on_click=reset_form)
    else:
        st.info("🌸 您目前以訪客身分瀏覽，僅可查看紀錄。")

# --- 右側主畫面 ---
col1, col2 = st.columns([1, 1])
with col1:
    with st.container(border=True):
        st.subheader("🖼️ 預覽")
        if st.session_state.is_admin:
            uploader_key = f"uploaded_files_{st.session_state.uploader_id}"
            uploaded_files = st.session_state.get(uploader_key)
            if uploaded_files:
                cols = st.columns(3)
                for idx, uploaded_file in enumerate(uploaded_files):
                    with cols[idx % 3]:
                        image = Image.open(uploaded_file)
                        image = ImageOps.exif_transpose(image)
                        processed_image = apply_filter(image, st.session_state.filter_style)
                        render_photo_card(processed_image, caption=f"照片 {idx+1}")
            else:
                st.info("請在左側欄上傳照片以查看預覽")
        else:
            st.info("管理員登入後可在此查看上傳預覽")

with col2:
    with st.container(border=True):
        st.subheader("✍️ 內容預覽")
        if st.session_state.is_admin and st.session_state.plant_name:
            st.markdown(f"### {st.session_state.plant_name}")
            st.markdown(f"📅 **日期：** {st.session_state.photo_date}")
            st.markdown(f"📝 **筆記：**")
            note_content = st.session_state.notes if st.session_state.notes else '尚未填寫筆記'
            st.markdown(f'<div style="white-space: pre-wrap;">{note_content}</div>', unsafe_allow_html=True)
        elif not st.session_state.is_admin:
            st.write("訪客模式：僅可查看下方歷史紀錄")
        else:
            st.write("等待輸入植物名稱...")

st.divider()

# --- 核心佈局重構：主內容與統計面板 ---
main_col, side_col = st.columns([3, 1])

with main_col:
    st.subheader("⏳ 流金歲月")
    all_logs = st.session_state.logs
    if not all_logs:
        st.write("目前還沒有紀錄，快去拍拍植物吧！")
    else:
        sorted_logs = sorted(enumerate(all_logs), key=lambda x: x[1]['date'], reverse=True)
        st.markdown('<div class="history-section">', unsafe_allow_html=True)
        for idx, entry in sorted_logs:
            with st.container(border=True):
                is_expanded = st.session_state.expanded_logs.get(idx, False)
                
                # 嚴格從 data_images/ 搜尋影像
                final_paths = resolve_images(entry)
                
                if not is_expanded:
                    # --- 摺疊預覽模式 (水平佈局) ---
                    col_thumb, col_info, col_action = st.columns([1, 4, 1])
                    
                    with col_thumb:
                        if final_paths:
                            try:
                                img = Image.open(final_paths[0])
                                img = ImageOps.exif_transpose(img)
                                img = ImageOps.fit(img, (120, 120), Image.Resampling.LANCZOS)
                                filtered_img = apply_filter(img, entry['style'])
                                st.image(filtered_img, use_container_width=True)
                            except Exception:
                                st.warning("圖片讀取失敗")
                        else:
                            st.warning("無照片")

                    with col_info:
                        st.markdown(f"**{entry['date']} · {entry['name']}**")
                        st.markdown(f'<span class="purple-tag">{entry["style"]}</span>', unsafe_allow_html=True)
                        # 提取第一行作為摘要
                        summary = entry["notes"].split('\n')[0] if entry["notes"] else "尚未記錄筆記"
                        st.markdown(f"<div style='color: #aaa; font-size: 0.9rem; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;'>{summary}</div>", unsafe_allow_html=True)
                        
                        if st.session_state.is_admin:
                            btn_col1, btn_col2 = st.columns(2)
                            with btn_col1:
                                st.button("編輯", key=f"edit_{idx}", on_click=start_edit, args=(idx,))
                            with btn_col2:
                                st.button("刪除", key=f"del_{idx}", type="secondary", on_click=delete_entry, args=(idx,))
                    
                    with col_action:
                        st.markdown(f"<div style='text-align: right; color: #aaa; font-size: 0.8rem; margin-bottom: 5px;'>🖼️ {len(final_paths)}</div>", unsafe_allow_html=True)
                        st.button("展開 >", key=f"exp_{idx}", on_click=toggle_expand, args=(idx,))
                
                else:
                    # --- 展開詳細模式 (影像在上，筆記在下) ---
                    st.markdown(f"### 🌸 {entry['name']}")
                    st.markdown(f"📅 **記錄日期：** {entry['date']} | 🎨 **影像風格：** {entry['style']}")
                    
                    # 1. 照片顯示：優先渲染在上方
                    if final_paths:
                        st.markdown("<br>", unsafe_allow_html=True)
                        img_cols = st.columns(3)
                        for p_idx, img_path in enumerate(final_paths):
                            with img_cols[p_idx % 3]:
                                try:
                                    img = Image.open(img_path)
                                    img = ImageOps.exif_transpose(img)
                                    filtered_img = apply_filter(img, entry['style'])
                                    render_expanded_image(filtered_img)
                                except Exception:
                                    st.warning(f"照片 {p_idx+1} 遺失或損毀")
                    else:
                        st.warning("此紀錄無可用照片")
                    
                    # 2. 筆記內容：渲染在影像下方
                    st.markdown("---")
                    st.markdown("**📝 完整筆記：**")
                    full_note = entry["notes"] if entry["notes"] else "（尚未記錄筆記）"
                    st.markdown(f'<div style="font-style: italic; color: #eee; font-size: 1rem; line-height: 1.6; white-space: pre-line; background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px;">{full_note}</div>', unsafe_allow_html=True)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.button("收起 📁", key=f"coll_{idx}", on_click=toggle_expand, args=(idx,))

        st.markdown('</div>', unsafe_allow_html=True)

with side_col:
    with st.container(border=True):
        st.subheader("📊 我的花草紀錄")
        total_logs = len(all_logs)
        total_photos = sum(len(resolve_images(log)) for log in all_logs)
        unique_plants = len(set(log["name"] for log in all_logs))
        
        if all_logs:
            dates = [datetime.strptime(log["date"], "%Y-%m-%d") for log in all_logs]
            days_diff = (max(dates) - min(dates)).days + 1
        else:
            days_diff = 0

        stats_data = [
            ("總紀錄數", f"{total_logs} 筆"),
            ("匹配照片", f"{total_photos} 張"),
            ("記錄天數", f"{days_diff} 天"),
            ("植物種類", f"{unique_plants} 種"),
        ]
        
        for label, value in stats_data:
            st.markdown(f"""
                <div class="stats-row">
                    <span>{label}</span>
                    <span class="stats-value">{value}</span>
                </div>
            """, unsafe_allow_html=True)

# --- 頁面最下方：管理員登入入口 ---
st.markdown("<br><br>", unsafe_allow_html=True)
with st.expander("🔐 管理員入口"):
    if not st.session_state.is_admin:
        admin_pwd = st.text_input("請輸入管理員密碼", type="password")
        if st.button("登入"):
            if admin_pwd == "750325":
                st.session_state.is_admin = True
                st.rerun()
            else:
                st.error("密密碼錯誤，請重新輸入。")
    else:
        st.write("目前身分：**管理員**")
        if st.button("登出"):
            st.session_state.is_admin = False
            reset_form()
            st.rerun()
