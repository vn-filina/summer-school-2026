import streamlit as strl
import requests
import uuid
from datetime import datetime

BACKEND_URL = "http://127.0.0.1:8000"

strl.set_page_config(page_title="Глина — Запись", page_icon="🏺", layout="centered")

if "token" not in strl.session_state:
    strl.session_state.token = None
if "user_name" not in strl.session_state:
    strl.session_state.user_name = None


def logout():
    strl.session_state.token = None
    strl.session_state.user_name = None


# ================= ЭКРАН ВХОДА =================
if not strl.session_state.token:
    strl.title("🏺 Добро пожаловать в «Глину»")
    strl.markdown("Пожалуйста, войдите или зарегистрируйтесь по номеру телефона.")

    with strl.form("auth_form"):
        phone = strl.text_input("Телефон (+79991234567)")
        name = strl.text_input("Имя (только для новой регистрации)", placeholder="Иван")
        code = strl.text_input("Код из SMS (введите 1234 для теста)", type="password")

        col1, col2 = strl.columns(2)
        submit_btn = col1.form_submit_button("Войти / Зарегистрироваться")

        if submit_btn:
            if not phone.startswith("+7") and not phone.startswith("8"):
                strl.error("Формат телефона должен быть +79991234567")
            else:
                payload = {"phone": phone, "code": code, "name": name}
                res = requests.post(f"{BACKEND_URL}/auth/verify-code", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    strl.session_state.token = data["access_token"]
                    strl.session_state.user_name = data["user_name"]
                    strl.rerun()
                else:
                    strl.error(res.json().get("detail", "Ошибка входа"))

# ================= ГЛАВНЫЙ ЭКРАН =================
else:
    col1, col2 = strl.columns([0.8, 0.2])
    col1.title(f"Привет, {strl.session_state.user_name}! 👋")
    col2.button("Выйти", on_click=logout)

    headers = {"Authorization": f"Bearer {strl.session_state.token}"}

    tab1, tab2 = strl.tabs(["📅 Расписание", "🎫 Мои записи"])

    with tab1:
        strl.header("Доступные мастер-классы (на 7 дней)")
        try:
            slots = requests.get(f"{BACKEND_URL}/slots").json()
            if not slots:
                strl.info("Пока нет доступных занятий.")

            for slot in slots:
                with strl.container(border=True):
                    dt = datetime.fromisoformat(slot["start_time"].replace("Z", "+00:00"))

                    strl.subheader(f"{slot['program_name']} ({dt.strftime('%d.%m.%Y в %H:%M')})")
                    strl.markdown(
                        f"**Мастер:** {slot['master_name']} | **Мест:** {slot['available_places']} из {slot['total_places']}")

                    if slot["status"] == "club_cancelled":
                        strl.error(f"Отменено мастерской. Причина: {slot.get('cancellation_reason', 'Форс-мажор')}")
                    else:
                        # Убрали st.form, теперь чекбокс работает динамически
                        needs_rental = strl.checkbox("Нужен прокат (фартук + инструменты) + 300 руб.",
                                                     key=f"rent_{slot['id']}")

                        # ДИНАМИЧЕСКИЙ РАСЧЕТ ЦЕНЫ (FR-006)
                        final_price = slot.get("base_price", 1500) + (300 if needs_rental else 0)
                        strl.markdown(f"**💰 Итого к оплате:** `{final_price} руб.`")

                        is_disabled = slot["available_places"] <= 0
                        btn_label = "Мест нет" if is_disabled else "Записаться"

                        # Обычная кнопка вместо form_submit_button
                        if strl.button(btn_label, key=f"book_{slot['id']}", disabled=is_disabled,
                                       use_container_width=True):
                            book_headers = {**headers, "Idempotency-Key": str(uuid.uuid4())}
                            payload = {"slot_id": slot["id"], "needs_rental": needs_rental}

                            res = requests.post(f"{BACKEND_URL}/bookings", json=payload, headers=book_headers)
                            if res.status_code == 200:
                                strl.success("Вы успешно записались! Можете проверить в разделе «Мои записи».")
                            else:
                                err_msg = res.json().get("detail", "Неизвестная ошибка")
                                strl.error(f"Не удалось записаться: {err_msg}")
        except Exception as e:
            strl.error(f"Не удалось загрузить расписание: {e}")

    with tab2:
        strl.header("История бронирований")
        try:
            my_bookings = requests.get(f"{BACKEND_URL}/bookings/me", headers=headers).json()
            if not my_bookings:
                strl.info("У вас пока нет записей.")

            for b in my_bookings:
                with strl.container(border=True):
                    slot = b.get("slot", {})
                    prog_name = slot.get("program_name", "Неизвестная программа")
                    master = slot.get("master_name", "Неизвестный мастер")

                    if "start_time" in slot:
                        dt = datetime.fromisoformat(slot["start_time"].replace("Z", "+00:00"))
                        time_str = dt.strftime('%d.%m.%Y в %H:%M')
                    else:
                        time_str = "Время неизвестно"

                    strl.subheader(f"{prog_name} ({time_str})")
                    strl.markdown(f"**Мастер:** {master}")

                    # Проверяем статус слота (FR-009) и статус самой брони (FR-007, FR-008)
                    is_club_cancelled = slot.get("status") == "club_cancelled"

                    if is_club_cancelled:
                        nice_status = "⚫ Отменено клубом"
                        strl.error(
                            "Занятие отменено организатором (форс-мажор). Повторная запись невозможна. Оплата подлежит возврату в полном объеме.")
                    elif b['status'] == 'cancelled':
                        nice_status = "⚪ Отменено"
                        strl.success(
                            "Ранняя отмена (более 3 часов до старта). Место успешно освобождено, предоплата подлежит возврату.")
                    elif b['status'] == 'late_cancelled':
                        nice_status = "🔴 Отменено (поздняя)"
                        strl.warning(
                            "Поздняя отмена (менее 3 часов до старта). Место не освобождается, возврат средств не предусмотрен.")
                    else:
                        nice_status = "🟢 Активна"

                    strl.markdown(f"**Статус:** {nice_status} | **К оплате:** `{b['final_price']} руб.`")

                    # Кнопку отмены показываем только если бронь активна И клуб не отменил занятие
                    if b["status"] == "active" and not is_club_cancelled:
                        if strl.button("Отменить запись", key=f"cancel_{b['id']}"):
                            res = requests.post(f"{BACKEND_URL}/bookings/{b['id']}/cancel", headers=headers)
                            if res.status_code == 200:
                                strl.rerun()  # Мгновенно обновляем UI, чтобы клиент увидел новый статус
                            else:
                                strl.error(res.json().get('detail'))
        except Exception as e:
            strl.error(f"Не удалось загрузить историю: {e}")