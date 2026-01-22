"""
Family Tree Editor - Secure Web Application
Візуалізація: Custom SVG Renderer (Orthogonal).
Функціонал: Multi-tenancy, Visual Linking, Cloud Sync & Logging.
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
def get_data_manager(username: str):
    """
    Створює інстанс DataManager. 
    Тут ТІЛЬКИ створення об'єкта, без виклику st.* елементів.
    """
    dm = DataManager(username)
    return dm

def perform_backup(manual=False):
    """Виконує бекап з перевіркою часу."""
    BACKUP_INTERVAL_MIN = 60
    now = datetime.datetime.now()
    last_backup = st.session_state.get('last_backup_time')
    
    should_backup = False
    if manual:
        should_backup = True
    elif last_backup is not None:
        diff = (now - last_backup).total_seconds() / 60
        if diff > BACKUP_INTERVAL_MIN:
            should_backup = True
            
    if should_backup:
        ps = get_persistence_service()
        if ps.is_enabled:
            if manual:
                with st.spinner("💾 Синхронізація з Google Drive..."):
                    if ps.upload_backup():
                        st.session_state['last_backup_time'] = now
                        st.toast("✅ Бекап створено!", icon="☁️")
                    else:
                        st.sidebar.error("Помилка завантаження.")
            else:
                if ps.upload_backup():
                    st.session_state['last_backup_time'] = now
    elif manual:
        st.sidebar.info(f"Бекап нещодавно створено.")

def save_state(dm):
    """Зберігає проект і пробує зробити авто-бекап."""
    dm.save_project()
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
        st.error("Помилка макета.")
        return None

    renderer = SVGRenderer(dm.graph, positions, focus_id)
    svg_content = renderer.generate_svg()
    
    is_linking = st.session_state.get('linking_mode') is not None
    if is_linking:
        svg_content = re.sub(r"id='([^']+)'", r"id='LINK_\1'", svg_content)
        click_key = f"graph_link_{focus_id}"
    else:
        click_key = f"graph_view_{focus_id}"

    return click_detector(svg_content, key=click_key)

# --- 3. UI КОМПОНЕНТИ ---
def render_sidebar(dm: DataManager, authenticator):
    user_name = st.session_state.get('name', 'Користувач')
    st.sidebar.title(f"👤 {user_name}")
    authenticator.logout('🚪 Вийти', 'sidebar')
    
    st.sidebar.markdown("---")
    edit_mode = st.sidebar.toggle("🛠️ Режим редагування", value=False, key="edit_mode_toggle")
    
    if edit_mode:
        col_backup, col_last = st.sidebar.columns([1, 2])
        if col_backup.button("☁️"):
            perform_backup(manual=True)
        
        last_time = st.session_state.get('last_backup_time')
        if last_time:
            col_last.caption(f"Бекап: {last_time.strftime('%H:%M')}")

    with st.sidebar.expander("ℹ️ Легенда кольорів"):
        st.markdown("""
        <div style="font-size: 12px;">
        <span style="color:#FFD700;">■</span> <b>Жовтий</b>: Вибраний<br>
        <span style="color:#87CEEB;">■</span> <b>Блакитний</b>: Предки<br>
        <span style="color:#98FB98;">■</span> <b>Зелений</b>: Нащадки<br>
        <span style="color:#FFB6C1;">■</span> <b>Рожевий</b>: Партнери<br>
        <span style="color:#DDA0DD;">■</span> <b>Фіолетовий</b>: Брат/Сестра
        </div>
        """, unsafe_allow_html=True)

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

        st.sidebar.selectbox("🔍 Знайти / Редагувати", ["-- Оберіть --"] + sorted_labels, 
                             index=current_index, key="person_selector", on_change=on_person_selected)
        st.sidebar.button("🎯 Центрувати дерево", on_click=on_center_view)

    if edit_mode:
        with st.sidebar.form("add_person_form"):
            st.write("➕ **Нова людина**")
            new_name = st.text_input("ПІБ")
            if st.form_submit_button("Додати"):
                if new_name:
                    new_id = dm.add_person(new_name)
                    st.session_state.selected_person_id = new_id
                    save_state(dm)
                    
        if st.sidebar.button("🔄 Force Restore"):
             ps = get_persistence_service()
             with st.spinner("Завантаження..."):
                 if ps.download_latest_backup():
                     st.success("Готово")
                     st.rerun()

    with st.sidebar.expander("📜 Історія змін"):
        logs = dm.logger.get_recent_logs(5)
        for log in logs:
            st.caption(f"{log[0]} | {log[2]}")
            
    return edit_mode

def render_main_area(dm: DataManager, is_editing: bool):
    selected_pid = st.session_state.get('selected_person_id')
    linking_mode = st.session_state.get('linking_mode')
    
    if linking_mode:
        st.warning(f"🔗 **ОБЕРІТЬ РОДИЧА НА ГРАФІ**")
        if st.button("❌ Скасувати"): cancel_linking_mode()

    st.subheader("📊 Генеалогічне Дерево")
    clicked_node_id = render_graph(dm, selected_pid)

    if clicked_node_id:
        if linking_mode:
            source = st.session_state.linking_source_id
            if source != clicked_node_id:
                try:
                    if linking_mode == 'parent': dm.add_parent(source, clicked_node_id, st.session_state.linking_role)
                    elif linking_mode == 'partner': dm.add_partner(source, clicked_node_id)
                    elif linking_mode == 'child': dm.add_child(source, clicked_node_id)
                    st.success("Зв'язок створено!")
                    cancel_linking_mode()
                    save_state(dm)
                except Exception as e: st.error(f"Помилка: {e}")
            else: st.toast("❌ Самого з собою не можна!")
        elif clicked_node_id != selected_pid:
            st.session_state.selected_person_id = clicked_node_id
            st.rerun()

    st.markdown("---")
    if selected_pid and dm.graph.has_node(selected_pid):
        render_edit_panel(dm, selected_pid, is_editing)

def render_edit_panel(dm: DataManager, pid: str, is_editing: bool):
    data = dm.get_person_data(pid)
    root_id = st.session_state.get('view_root_id') or "1"
    rel_calc = RelationshipCalculator(dm.graph)
    _, rel_name = rel_calc.get_relationship_type(root_id, pid)
    
    st.markdown(f"""
    <div style="padding:10px; background:#262730; border-radius:10px; border-left:5px solid #FFD700;">
        <h3>✏️ {data.get('label')}</h3>
        <p>Зв'язок: <b>{rel_name}</b></p>
    </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs(["📝 Інфо", "🔗 Зв'язки", "📎 Документи", "🗑️ Видалення"])

    with tabs[0]:
        if is_editing:
            name = st.text_input("ПІБ", data.get('label', ''), key="en")
            dob = st.text_input("Д.Н.", data.get('date_of_birth', ''), key="eb")
            dod = st.text_input("Д.С.", data.get('date_of_death', ''), key="ed")
            notes = st.text_area("Нотатки", data.get('notes', ''), key="eo")
            if st.button("Зберегти", type="primary"):
                dm.update_person(pid, name=name, birth_date=dob)
                dm.graph.nodes[pid]['date_of_death'] = dod
                dm.save_notes(pid, notes)
                save_state(dm)
        else:
            st.write(f"**Д.Н.:** {data.get('date_of_birth', '—')} | **Д.С.:** {data.get('date_of_death', '—')}")
            st.write(data.get('notes', '—'))

    with tabs[1]:
        parents = dm.get_parents(pid)
        if parents[0]: st.write(f"👴 Батько: {dm.graph.nodes[parents[0]]['label']}")
        if parents[1]: st.write(f"👵 Мати: {dm.graph.nodes[parents[1]]['label']}")
        if is_editing:
            st.button("🎯 Обрати батька на графі", on_click=start_linking_mode, args=('parent', 'father'))
            st.button("🎯 Обрати матір на графі", on_click=start_linking_mode, args=('parent', 'mother'))
            st.button("💑 Додати партнера на графі", on_click=start_linking_mode, args=('partner',))

    with tabs[2]:
        if is_editing:
            if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
            u_file = st.file_uploader("Додати файл", key=f"f_{st.session_state.uploader_key}")
            if u_file and st.button("Завантажити"):
                if dm.save_document_file(pid, u_file):
                    st.session_state.uploader_key += 1
                    save_state(dm)
        
        for doc in dm.get_person_documents(pid):
            col_a, col_b = st.columns([4, 1])
            col_a.write(doc['filename'])
            if doc['type'] == 'image': st.image(doc['path'], width=300)
            with open(doc['path'], "rb") as f:
                col_b.download_button("⬇️", f, file_name=doc['filename'], key=f"dl_{doc['filename']}")

    with tabs[3]:
        if is_editing and st.button("🗑️ Видалити назавжди"):
            dm.delete_person(pid)
            st.session_state.selected_person_id = None
            save_state(dm)

# --- 4. ГОЛОВНИЙ ЗАПУСК ---
def main():
    try:
        def safe_convert(obj):
            if hasattr(obj, "items"): return {k: safe_convert(v) for k, v in obj.items()}
            return obj
        if 'credentials' not in st.session_state:
            st.session_state['credentials'] = safe_convert(st.secrets['credentials'])
        cookie_params = st.secrets['cookie']
    except Exception as e:
        st.error(f"Помилка конфігурації: {e}")
        st.stop()

    authenticator = stauth.Authenticate(st.session_state['credentials'], cookie_params['name'], cookie_params['key'], cookie_params['expiry_days'])
    if check_session_timeout(authenticator): return

    authenticator.login(location='main')

    if st.session_state.get("authentication_status"):
        if 'last_backup_time' not in st.session_state:
            st.session_state['last_backup_time'] = datetime.datetime.now()
        
        username = st.session_state.get('username')
        
        # --- ЛОГІКА ВІДНОВЛЕННЯ (ПОЗА КЕШЕМ) ---
        user_dir = os.path.join("family_tree_data", username)
        ps = get_persistence_service()
        if ps.is_enabled and not os.path.exists(user_dir):
            with st.status("☁️ Завантаження даних з хмари...") as status:
                if ps.download_latest_backup():
                    status.update(label="✅ Дані відновлено!", state="complete")
                    st.rerun()
                else:
                    status.update(label="❌ Бекапів не знайдено", state="error")

        dm = get_data_manager(username)
        is_editing = render_sidebar(dm, authenticator)
        render_main_area(dm, is_editing)
    elif st.session_state.get("authentication_status") is False:
        st.error('❌ Невірний логін')
        brute_force_protection()

if __name__ == "__main__":
    main()
