# utils/security_utils.py
import time
import streamlit as st
from streamlit_authenticator import Authenticate

SESSION_TIMEOUT_MINUTES = 43200


def check_session_timeout(authenticator: Authenticate):
    """
    Перевіряє час останньої активності. Якщо пройшло більше 30 хв — робить логаут.
    """
    if st.session_state.get("authentication_status"):
        last_activity = st.session_state.get('last_activity_time', time.time())
        current_time = time.time()

        # Перевірка тайм-ауту
        if (current_time - last_activity) > (SESSION_TIMEOUT_MINUTES * 60):
            authenticator.logout('main')
            st.warning("⏳ Сесія завершена через неактивність. Будь ласка, увійдіть знову.")
            st.session_state['last_activity_time'] = current_time  # скидання
            return True

        # Оновлення часу активності
        st.session_state['last_activity_time'] = current_time
    return False


def brute_force_protection():
    """
    Додає штучну затримку, якщо статус авторизації False (помилка входу).
    """
    if st.session_state.get("authentication_status") is False:
        time.sleep(2)  # Затримка 2 секунди при неправильному паролі