"""
Family Tree Editor - Secure Web Application
Візуалізація: Custom SVG Renderer (Orthogonal).
Функціонал: Read-Only Mode, Visual Linking, File Management, Cloud Sync & Logging.
Безпека: st.secrets + Session Management.
Мова: Українська.
"""

import streamlit as st
import streamlit_authenticator as stauth
import os
import base64
import re
import datetime
from st_click_detector import click_detector

# Імпорт локальних модулів
from data_manager import DataManager
from layout_engine import LayoutEngine
from svg_renderer import SVGRenderer
from relationship_calculator import RelationshipCalculator
from utils.security_utils import check_session_timeout, brute_force_protection
from utils.persistence_service import PersistenceService

# --- КОНФІГУРАЦІЯ СТОРІНКИ ---
st.set_page_config(
    page_title="Редактор Сімейного Дерева",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 1. ЛОГІКА ДАНИХ ТА СИНХРОНІЗАЦІЯ ---
@st.cache_resource
def get_persistence_service():
    """Створює сервіс синхронізації один раз."""
    return PersistenceService()

@st.cache_resource
def get_data_manager():
    # 1. Пробуємо синхронізувати з хмари при холодному старті
    ps = get_persistence_service()
    if not os.path.exists("family_tree_data"):
        # Якщо папки немає локально, пробуємо стягнути з Drive
        ps.download_latest_backup()

    # 2. Ініціалізуємо DataManager
    dm = DataManager()
    data_dir = "family_tree_data"
    data_file = os.path.join(data_dir, "family.tree")

    if not os.path.exists(data_dir): os.makedirs(data_dir)
    if os.path.exists(data_file): dm.load_project(data_file)
    else:
        dm.project_file_path = os.path.abspath(data_file)
        dm.project_directory = os.path.dirname(dm.project_file_path)
    return dm

def perform_backup(manual=False):
    """Виконує бекап з перевіркою часу."""
    BACKUP_INTERVAL_MIN = 10
    now = datetime.datetime.now()
    last_backup = st.session_state.get('last_backup_time')

    should_backup = False

    if manual:
        should_backup = True
    elif last_backup is None:
        should_backup = True
    else:
        diff = (now - last_backup).total_seconds() / 60
        if diff > BACKUP_INTERVAL_MIN:
            should_backup = True

    if should_backup:
        ps = get_persistence_service()

        # Явна перевірка для ручного режиму
        if manual and (not ps.is_enabled):
            st.sidebar.error(f"Налаштування хмари неповні: {ps.status}")
            return

        if ps.is_enabled:
            with st.spinner("💾 Створення бекапу на Google Drive..."):
                if ps.upload_backup():
                    st.session_state['last_backup_time'] = now
                    if manual:
                        # ВИПРАВЛЕНО: icon="cloud" -> icon="☁️"
                        st.toast("✅ Бекап успішно створено!", icon="☁️")
                    else:
                        print(f"Auto-backup created at {now}")
                else:
                    if manual: st.sidebar.error("Помилка завантаження (див. консоль).")
    elif manual:
        st.sidebar.info(f"Бекап вже був створений нещодавно (чекайте {BACKUP_INTERVAL_MIN} хв або перезавантажте).")

def save_state(dm):
    """Зберігає локально і тригерить авто-бекап."""
    dm.save_project()
    # Автоматичний бекап
    perform_backup(manual=False)
    st.cache_resource.clear()
    st.rerun()

# --- ДОПОМІЖНІ ФУНКЦІЇ ---
def show_pdf(file_path):
    try:
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Не вдалося відкрити PDF: {e}")

# --- CALLBACKS ---
def on_person_selected():
    selected_label = st.session_state.person_selector
    if selected_label and selected_label != "-- Оберіть --":
        options_map = st.session_state.get('options_map', {})
        new_id = options_map.get(selected_label)
        if new_id:
            st.session_state.selected_person_id = new_id

def on_center_view():
    st.session_state.view_root_id = st.session_state.selected_person_id

def start_linking_mode(mode, role=None):
    st.session_state.linking_mode = mode
    st.session_state.linking_role = role
    st.session_state.linking_source_id = st.session_state.selected_person_id
    st.rerun()

def cancel_linking_mode():
    st.session_state.linking_mode = None
    st.session_state.linking_role = None
    st.session_state.linking_source_id = None
    st.rerun()

# --- 2. ВІЗУАЛІЗАЦІЯ (SVG) ---
def render_graph(dm: DataManager, selected_pid: str):
    if not dm.graph.nodes():
        st.info("Дерево порожнє. Додайте людей через меню зліва.")
        return None

    global_root = "1"
    if not dm.graph.has_node(global_root):
        global_root = list(dm.graph.nodes())[0] if dm.graph.nodes() else None

    custom_root = st.session_state.get('view_root_id')
    layout_root = custom_root if (custom_root and dm.graph.has_node(custom_root)) else global_root

    layout_engine = LayoutEngine()
    focus_id = selected_pid if selected_pid else layout_root

    positions = layout_engine.calculate_layout(dm.graph, layout_root)

    if not positions:
        st.error("Не вдалося розрахувати макет дерева.")
        return None

    renderer = SVGRenderer(dm.graph, positions, focus_id)
    svg_content = renderer.generate_svg()

    is_linking = st.session_state.get('linking_mode') is not None
    if is_linking:
        svg_content = re.sub(r"id='([^']+)'", r"id='LINK_\1'", svg_content)
        click_key = "graph_linking_mode"
    else:
        click_key = "graph_view_mode"

    clicked_id_raw = click_detector(svg_content, key=click_key)

    if clicked_id_raw and is_linking and clicked_id_raw.startswith("LINK_"):
        return clicked_id_raw.replace("LINK_", "")

    return clicked_id_raw

# --- 3. UI КОМПОНЕНТИ ---
def render_sidebar(dm: DataManager, authenticator):
    user_name = st.session_state.get('name', 'Користувач')
    st.sidebar.title(f"👤 {user_name}")
    authenticator.logout('🚪 Вийти', 'sidebar')

    st.sidebar.markdown("---")
    edit_mode = st.sidebar.toggle("🛠️ Режим редагування", value=False, key="edit_mode_toggle")

    # КНОПКА БЕКАПУ
    if edit_mode:
        col_backup, col_last = st.sidebar.columns([1, 2])
        if col_backup.button("☁️"):
            # Примусове скидання кешу, якщо треба
            # st.cache_resource.clear()
            perform_backup(manual=True)

        last_time = st.session_state.get('last_backup_time')
        if last_time:
            time_str = last_time.strftime("%H:%M")
            col_last.caption(f"Останній: {time_str}")
        else:
            col_last.caption("Бекапів не було")

    with st.sidebar.expander("ℹ️ Легенда кольорів", expanded=False):
        st.markdown("""
        <div style="font-size: 12px;">
        <span style="color:#FFD700; font-size:16px;">■</span> <b>Жовтий</b>: Вибрана людина<br>
        <span style="color:#87CEEB; font-size:16px;">■</span> <b>Блакитний</b>: Предки<br>
        <span style="color:#98FB98; font-size:16px;">■</span> <b>Зелений</b>: Нащадки<br>
        <span style="color:#FFB6C1; font-size:16px;">■</span> <b>Рожевий</b>: Партнери<br>
        <span style="color:#DDA0DD; font-size:16px;">■</span> <b>Фіолетовий</b>: Брати/Сестри
        </div>
        """, unsafe_allow_html=True)

    st.sidebar.markdown("---")

    people = dm.get_all_people()
    if people:
        options_map = {f"{label} (ID: {pid})": pid for pid, label in people}
        st.session_state.options_map = options_map
        sorted_labels = sorted(options_map.keys())

        current_index = 0
        current_pid = st.session_state.get('selected_person_id')

        if current_pid:
            for idx, label in enumerate(sorted_labels):
                if options_map[label] == current_pid:
                    current_index = idx + 1
                    break

        st.sidebar.selectbox(
            "🔍 Знайти / Редагувати",
            ["-- Оберіть --"] + sorted_labels,
            index=current_index,
            key="person_selector",
            on_change=on_person_selected
        )

        st.sidebar.button("🎯 Центрувати дерево на вибраному", on_click=on_center_view)

    if edit_mode:
        st.sidebar.markdown("---")
        with st.sidebar.form("add_person_form"):
            st.write("➕ **Додати нову людину**")
            new_name = st.text_input("Введіть ПІБ")
            if st.form_submit_button("Додати"):
                if new_name:
                    new_id = dm.add_person(new_name)
                    st.session_state.selected_person_id = new_id
                    save_state(dm)

        if not people and st.sidebar.button("🛠 Тестові дані"):
            dm.create_test_data(); save_state(dm)

    # ЛОГИ АКТИВНОСТІ
    with st.sidebar.expander("📜 Історія змін", expanded=False):
        logs = dm.logger.get_recent_logs(10)
        if not logs:
            st.write("Історія порожня.")
        else:
            for timestamp, user, action, details in logs:
                st.markdown(f"**{action}** ({user})")
                st.caption(f"{details} | {timestamp}")
                st.markdown("---")

    return edit_mode

def render_main_area(dm: DataManager, is_editing: bool):
    selected_pid = st.session_state.get('selected_person_id')
    linking_mode = st.session_state.get('linking_mode')

    if linking_mode:
        role_text = st.session_state.get('linking_role', '')
        if role_text == 'father': role_str = "БАТЬКА"
        elif role_text == 'mother': role_str = "МАТІР"
        elif linking_mode == 'partner': role_str = "ПАРТНЕРА"
        elif linking_mode == 'child': role_str = "ДИТИНУ"
        else: role_str = "РОДИЧА"

        st.warning(f"🔗 **ОБЕРІТЬ {role_str} НА ГРАФІ НИЖЧЕ** (або натисніть 'Скасувати')")
        if st.button("❌ Скасувати"):
            cancel_linking_mode()

    st.subheader("📊 Генеалогічне Дерево")

    clicked_node_id = render_graph(dm, selected_pid)

    if clicked_node_id:
        if linking_mode:
            source = st.session_state.linking_source_id
            target = clicked_node_id

            if source == target:
                st.toast("❌ Не можна поєднати людину з собою!", icon="⚠️")
            else:
                try:
                    if linking_mode == 'parent':
                        role = st.session_state.linking_role
                        dm.add_parent(source, target, role)
                    elif linking_mode == 'partner':
                        dm.add_partner(source, target)
                    elif linking_mode == 'child':
                        dm.add_child(source, target)

                    st.success("Зв'язок створено!")
                    cancel_linking_mode()
                    save_state(dm)
                except Exception as e:
                    st.error(f"Помилка: {e}")

        elif clicked_node_id != selected_pid:
            st.session_state.selected_person_id = clicked_node_id
            st.rerun()

    st.markdown("---")

    if selected_pid and dm.graph.has_node(selected_pid):
        render_edit_panel(dm, selected_pid, is_editing)
    else:
        if not linking_mode:
            st.info("👈 Клікніть на людину в дереві або оберіть зі списку.")

def render_edit_panel(dm: DataManager, pid: str, is_editing: bool):
    data = dm.get_person_data(pid)

    root_id = st.session_state.get('view_root_id')
    if not root_id or not dm.graph.has_node(root_id):
        root_id = "1" if dm.graph.has_node("1") else pid

    rel_calc = RelationshipCalculator(dm.graph)
    _, rel_name = rel_calc.get_relationship_type(root_id, pid)
    root_name = dm.graph.nodes[root_id].get('label', 'Центр') if dm.graph.has_node(root_id) else "..."

    st.markdown(f"""
    <div style="padding: 15px; background-color: #262730; border-radius: 10px; border-left: 5px solid #FFD700; margin-bottom: 20px;">
        <h2 style="margin:0; padding:0;">✏️ {data.get('label')}</h2>
        <p style="margin:5px 0 0 0; color: #aaa;">
            Відносно <b>{root_name}</b>: <span style="color: #FFD700; font-weight: bold;">{rel_name}</span>
        </p>
    </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs(["📝 Інфо", "🔗 Зв'язки", "📎 Документи", "🗑️ Видалення"])

    # 1. ІНФО
    with tabs[0]:
        c1, c2 = st.columns(2)
        if is_editing:
            with c1:
                name = st.text_input("ПІБ", data.get('label', ''), key="edit_name")
                dob = st.text_input("Д.Н.", data.get('date_of_birth', ''), key="edit_dob")
            with c2:
                dod = st.text_input("Д.С.", data.get('date_of_death', ''), key="edit_dod")
            notes = st.text_area("Нотатки", data.get('notes', ''), key="edit_notes")
            if st.button("Зберегти зміни", type="primary"):
                dm.update_person(pid, name=name, birth_date=dob)
                dm.graph.nodes[pid]['date_of_death'] = dod
                dm.save_notes(pid, notes)
                save_state(dm)
        else:
            with c1:
                st.write(f"**ПІБ:** {data.get('label', '—')}")
                st.write(f"**Дата народження:** {data.get('date_of_birth', '—')}")
            with c2:
                st.write(f"**Дата смерті:** {data.get('date_of_death', '—')}")
            st.divider()
            st.write("**Нотатки:**")
            st.write(data.get('notes', '—'))

    # 2. ЗВ'ЯЗКИ
    with tabs[1]:
        all_p = dm.get_all_people()
        opts = {f"{l} ({i})": i for i, l in all_p if i != pid}

        parents = dm.get_parents(pid)
        partners = dm.get_partners(pid)
        children = dm.get_children(pid)

        st.write("#### 👨‍👩‍👧‍👦 Родина")
        if parents[0]: st.write(f"👴 **Батько:** {dm.graph.nodes[parents[0]]['label']}")
        if parents[1]: st.write(f"👵 **Мати:** {dm.graph.nodes[parents[1]]['label']}")
        if partners: st.write(f"❤️ **Партнери:** {', '.join([dm.graph.nodes[p]['label'] for p in partners])}")
        if children: st.write(f"👶 **Діти:** {', '.join([dm.graph.nodes[c]['label'] for c in children])}")

        if is_editing:
            st.divider()
            st.write("#### ➕ Змінити зв'язки")

            # --- БАТЬКИ ---
            st.markdown("##### Батьки")
            col1, col2 = st.columns([2, 1])
            with col1:
                p_sel = st.selectbox("Оберіть зі списку", ["--"]+list(opts.keys()), key="p_parent_sel")
                role_dict = {"Батько": "father", "Мати": "mother"}
                role_ua = st.radio("Роль", ["Батько", "Мати"], horizontal=True, key="p_role_sel")
                if st.button("Додати", key="btn_add_parent_list"):
                    if p_sel != "--":
                        dm.add_parent(pid, opts[p_sel], role_dict[role_ua])
                        save_state(dm)
            with col2:
                st.write("")
                st.write("")
                if st.button("🎯 Обрати на графі", key="btn_link_parent"):
                    start_linking_mode('parent', role_dict[role_ua])

            st.markdown("---")
            # --- ПАРТНЕРИ ---
            st.markdown("##### Партнери")
            col1, col2 = st.columns([2, 1])
            with col1:
                pt_sel = st.selectbox("Оберіть зі списку", ["--"]+list(opts.keys()), key="p_partner_sel")
                if st.button("Додати", key="btn_add_partner_list"):
                    if pt_sel != "--":
                        dm.add_partner(pid, opts[pt_sel])
                        save_state(dm)
            with col2:
                st.write("")
                if st.button("🎯 Обрати на графі", key="btn_link_partner"):
                    start_linking_mode('partner')

            st.markdown("---")
            # --- ДІТИ ---
            st.markdown("##### Діти")
            col1, col2 = st.columns([2, 1])
            with col1:
                ch_sel = st.selectbox("Оберіть зі списку", ["--"]+list(opts.keys()), key="p_child_sel")
                if st.button("Додати", key="btn_add_child_list"):
                    if ch_sel != "--":
                        dm.add_child(pid, opts[ch_sel])
                        save_state(dm)
            with col2:
                st.write("")
                if st.button("🎯 Обрати на графі", key="btn_link_child"):
                    start_linking_mode('child')

    # 3. ДОКУМЕНТИ
    with tabs[2]:
        st.write("📂 **Файли та зображення**")

        if is_editing:
            if 'uploader_key' not in st.session_state:
                st.session_state.uploader_key = 0

            up_tab1, up_tab2 = st.tabs(["📤 Завантажити файл", "📸 Зробити фото"])

            with up_tab1:
                uploaded_file = st.file_uploader(
                    "Виберіть документ",
                    key=f"file_upl_{st.session_state.uploader_key}"
                )
                if uploaded_file is not None:
                    if st.button("Завантажити", key="btn_upl_file"):
                        if dm.save_document_file(pid, uploaded_file):
                            st.session_state.uploader_key += 1
                            save_state(dm)
                            st.success("Файл збережено!")

            with up_tab2:
                camera_file = st.camera_input(
                    "Зробіть фото документа",
                    key=f"cam_upl_{st.session_state.uploader_key}"
                )
                if camera_file is not None:
                    import datetime
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    camera_file.name = f"scan_{ts}.jpg"

                    if st.button("Зберегти фото", key="btn_upl_cam"):
                        if dm.save_document_file(pid, camera_file):
                            st.session_state.uploader_key += 1
                            save_state(dm)
                            st.success("Фото збережено!")

            st.divider()

        docs = dm.get_person_documents(pid)
        if not docs:
            st.info("Немає документів.")
        else:
            for doc in docs:
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.write(f"📄 **{doc['filename']}**")
                    if doc['type'] == 'image':
                        # ВИПРАВЛЕНО: 'auto' замість 'stretch' для st.image
                        st.image(doc['path'], caption=doc['filename'], width=None)
                    elif doc['filename'].lower().endswith('.pdf'):
                        with st.expander("👁️ Переглянути PDF"):
                            show_pdf(doc['path'])
                with c2:
                    with open(doc['path'], "rb") as f:
                        st.download_button("⬇️ Скачати", f, file_name=doc['filename'], key=f"dl_{doc['filename']}")
                    if is_editing:
                        if st.button("🗑️ Видалити", key=f"del_{doc['filename']}"):
                            dm.delete_document_file(pid, doc['filename'])
                            save_state(dm)
                st.divider()

    # 4. ВИДАЛЕННЯ
    with tabs[3]:
        if is_editing:
            st.warning("Будьте обережні. Ця дія незворотна.")
            if st.button("🗑️ Видалити людину назавжди", type="secondary"):
                dm.delete_person(pid)
                st.session_state.selected_person_id = None
                if st.session_state.view_root_id == pid:
                    st.session_state.view_root_id = None
                save_state(dm)
        else:
            st.info("Видалення доступне тільки в режимі редагування.")

# --- 4. ГОЛОВНИЙ ЗАПУСК ---
def main():
    try:
        def safe_convert(obj):
            if isinstance(obj, list): return [safe_convert(x) for x in obj]
            if hasattr(obj, "items"): return {k: safe_convert(v) for k, v in obj.items()}
            return obj

        if 'credentials' not in st.session_state:
            st.session_state['credentials'] = safe_convert(st.secrets['credentials'])

        credentials = st.session_state['credentials']
        cookie_params = st.secrets['cookie']

    except Exception as e:
        st.error(f"❌ Помилка ініціалізації: {e}")
        st.stop()

    authenticator = stauth.Authenticate(
        credentials,
        cookie_params['name'],
        cookie_params['key'],
        cookie_params['expiry_days']
    )

    if check_session_timeout(authenticator): return

    try:
        authenticator.login(location='main')
    except Exception as e:
        st.error(f"Помилка входу: {e}")

    if st.session_state.get("authentication_status"):
        if 'selected_person_id' not in st.session_state:
            st.session_state.selected_person_id = None
        if 'view_root_id' not in st.session_state:
            st.session_state.view_root_id = None
        if 'linking_mode' not in st.session_state:
            st.session_state.linking_mode = None

        dm = get_data_manager()
        is_editing = render_sidebar(dm, authenticator)
        render_main_area(dm, is_editing)

    elif st.session_state.get("authentication_status") is False:
        st.error('❌ Невірний логін або пароль')
        brute_force_protection()

    elif st.session_state.get("authentication_status") is None:
        st.warning('🔐 Будь ласка, введіть логін та пароль')

if __name__ == "__main__":
    main()