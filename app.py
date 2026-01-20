import streamlit as st
from PIL import Image, ImageDraw
import numpy as np
from streamlit_drawable_canvas import st_canvas
from io import BytesIO

# --- 1. 頁面設定 ---
st.set_page_config(page_title="三段式去背工具 (修復版)", layout="wide")
st.title("🎨 Vibe Coding: 三段式去背 (紅框挖除 / 藍框保留 / 青筆修補)")

# --- 初始化記憶體 ---
if "layer_magenta" not in st.session_state: st.session_state["layer_magenta"] = None
if "layer_blue" not in st.session_state: st.session_state["layer_blue"] = None
if "layer_cyan" not in st.session_state: st.session_state["layer_cyan"] = None

if "last_file_key" not in st.session_state: st.session_state["last_file_key"] = None
if "processed_image" not in st.session_state: st.session_state["processed_image"] = None

# --- 2. 上傳圖片 ---
uploaded_file = st.file_uploader("請上傳圖片 (JPG/PNG)", type=["png", "jpg", "jpeg"])

if uploaded_file:
    # 換圖偵測與重置
    current_file_key = f"{uploaded_file.name}_{uploaded_file.size}"
    if st.session_state["last_file_key"] != current_file_key:
        st.session_state["layer_magenta"] = None
        st.session_state["layer_blue"] = None
        st.session_state["layer_cyan"] = None
        st.session_state["processed_image"] = None
        st.session_state["last_file_key"] = current_file_key
        st.rerun()

    original_image = Image.open(uploaded_file).convert("RGBA")
    orig_w, orig_h = original_image.size

    # --- 縮圖處理 ---
    display_width = 800
    if orig_w > display_width:
        scale_factor = orig_w / display_width
        display_height = int(orig_h / scale_factor)
        display_image = original_image.resize((display_width, display_height))
    else:
        scale_factor = 1.0
        display_height = orig_h
        display_image = original_image
    
    base_bg = display_image.convert("RGB")

    # --- 3. 介面佈局 ---
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. 操作區")
        
        tool_mode = st.radio("選擇步驟：", 
            ("1️⃣ 洋紅框 (挖除)", "2️⃣ 藍色框 (保留)", "3️⃣ 青色筆 (細修)"), 
            horizontal=True
        )

        # === 動態背景生成器 ===
        current_bg = base_bg.copy()
        bg_draw = ImageDraw.Draw(current_bg, "RGBA")

        # 輔助函數：將圖層「烤」在背景上
        def bake_layer(json_data, color_fill, color_outline):
            if json_data and "objects" in json_data:
                for obj in json_data["objects"]:
                    if obj["type"] == "rect":
                        left, top = obj["left"], obj["top"]
                        width = obj["width"] * obj["scaleX"]
                        height = obj["height"] * obj["scaleY"]
                        bg_draw.rectangle(
                            [left, top, left + width, top + height],
                            fill=color_fill, 
                            outline=color_outline, 
                            width=2
                        )

        # 依據步驟決定背景顯示
        if tool_mode == "1️⃣ 洋紅框 (挖除)":
            drawing_mode = "rect"
            stroke_color = "rgba(255, 0, 255, 1.0)"
            fill_color = "rgba(255, 0, 255, 0.3)"
            active_layer_key = "layer_magenta"
            
        elif tool_mode == "2️⃣ 藍色框 (保留)":
            # 顯示上一層的洋紅框
            bake_layer(
                st.session_state["layer_magenta"], 
                (255, 0, 255, 80), 
                (255, 0, 255, 255)
            )
            drawing_mode = "rect"
            stroke_color = "rgba(0, 80, 255, 1.0)"
            fill_color = "rgba(0, 80, 255, 0.3)"
            active_layer_key = "layer_blue"

        else: # 3️⃣ 青色筆 (細修)
            # 顯示洋紅框 + 藍色框
            bake_layer(
                st.session_state["layer_magenta"], 
                (255, 0, 255, 80), 
                (255, 0, 255, 255)
            )
            bake_layer(
                st.session_state["layer_blue"], 
                (0, 80, 255, 80), 
                (0, 80, 255, 255)
            )
            drawing_mode = "freedraw"
            stroke_color = "rgba(0, 255, 255, 1.0)"
            fill_color = "rgba(0, 255, 255, 0.0)"
            active_layer_key = "layer_cyan"

        # 建立畫布
        canvas_result = st_canvas(
            fill_color=fill_color,
            stroke_width=2 if drawing_mode == "rect" else st.slider("筆刷粗細", 1, 50, 20),
            stroke_color=stroke_color,
            background_image=current_bg,
            update_streamlit=True,
            height=display_height,
            width=display_width,
            drawing_mode=drawing_mode,
            initial_drawing=st.session_state[active_layer_key],
            key=f"canvas_{active_layer_key}_{current_file_key}",
        )

        if canvas_result.json_data is not None:
            st.session_state[active_layer_key] = canvas_result.json_data

        run_btn = st.button("✂️ 全部畫好，執行去背！", type="primary", use_container_width=True)

    with col2:
        st.subheader("2. 結果預覽")

        if st.session_state["processed_image"] is not None:
            st.image(st.session_state["processed_image"], caption="去背結果", use_column_width=True)
            buf = BytesIO()
            st.session_state["processed_image"].save(buf, format="PNG")
            byte_im = buf.getvalue()
            st.download_button("📥 下載成品 PNG", byte_im, "result.png", "image/png", type="primary")

        if run_btn:
            try:
                st.info("🔄 三層運算合成中...")
                
                img_array = np.array(original_image)
                img_array.setflags(write=1)
                
                scale_x = orig_w / display_width
                scale_y = orig_h / display_height

                # 1. 洋紅框 (挖除)
                if st.session_state["layer_magenta"]:
                    for obj in st.session_state["layer_magenta"]["objects"]:
                        if obj["type"] == "rect":
                            x = int(obj["left"] * scale_x)
                            y = int(obj["top"] * scale_y)
                            w = int(obj["width"] * obj["scaleX"] * scale_x)
                            h = int(obj["height"] * obj["scaleY"] * scale_y)
                            img_array[y:y+h, x:x+w, 3] = 0

                # 2. 藍色框 (保留)
                if st.session_state["layer_blue"]:
                    for obj in st.session_state["layer_blue"]["objects"]:
                        if obj["type"] == "rect":
                            x = int(obj["left"] * scale_x)
                            y = int(obj["top"] * scale_y)
                            w = int(obj["width"] * obj["scaleX"] * scale_x)
                            h = int(obj["height"] * obj["scaleY"] * scale_y)
                            img_array[y:y+h, x:x+w, 3] = 255

                # 3. 青色筆 (細修 - 使用當前畫布資料)
                if tool_mode == "3️⃣ 青色筆 (細修)" and canvas_result.image_data is not None:
                    mask_data = canvas_result.image_data
                    mask_img = Image.fromarray(mask_data.astype('uint8'), mode="RGBA")
                    mask_img = mask_img.resize((orig_w, orig_h), resample=Image.NEAREST)
                    mask_arr = np.array(mask_img)
                    
                    is_pen = mask_arr[:, :, 1] > 0
                    img_array[is_pen, 3] = 255
                elif st.session_state["layer_cyan"] is not None:
                    # 如果使用者不在青筆模式按執行，我們給個小提醒，但還是盡量跑
                    st.warning("⚠️ 提醒：為了獲得最佳效果，建議切換到「步驟3」再按執行按鈕")

                final_image = Image.fromarray(img_array)
                st.session_state["processed_image"] = final_image
                st.success("✅ 三層處理完成！")
                st.rerun()

            except Exception as e:
                st.error(f"錯誤：{e}")
