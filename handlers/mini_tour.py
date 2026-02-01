from aiogram import Router, types
from places import PLACES
from locales import LOCALES
from state import user_mini_tour_active, user_languages, user_seen_places
import math
import time

router = Router()

user_selected_map = {}

# ----------------------------------------
# Формула Гаверсина
# ----------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ----------------------------------------
# Кнопки выбора карты (inline)
# ----------------------------------------
def get_map_buttons(user_id: int, lang: str):
    buttons = LOCALES[lang]["buttons"]
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=buttons["yandex"],
                    callback_data=f"mini_map:yandex:{user_id}"
                ),
                types.InlineKeyboardButton(
                    text=buttons["google"],
                    callback_data=f"mini_map:google:{user_id}"
                )
            ]
        ]
    )


# ----------------------------------------
# Запуск мини-тура
# ----------------------------------------
@router.callback_query(lambda c: c.data == "mini_tour")
async def mini_tour_start(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, "ru")

    # Активируем мини-тур
    user_mini_tour_active[user_id] = True

    # Сообщение
    await callback.message.answer(LOCALES[lang]["mini_tour_start"])

    # Клавиатура запроса геолокации
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(
            text=LOCALES[lang]["buttons"]["send_location"],
            request_location=True
        )]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await callback.message.answer(
        LOCALES[lang]["buttons"]["send_location"],
        reply_markup=kb
    )

    await callback.answer()


# ----------------------------------------
# Обработка геолокации (мини-тур)
# ----------------------------------------
async def mini_tour_location(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")

    u_lat = message.location.latitude
    u_lon = message.location.longitude

    # Сортировка мест по расстоянию
    sorted_places = sorted(
        PLACES.items(),
        key=lambda x: haversine(u_lat, u_lon, x[1]["lat"], x[1]["lon"])
    )

    # Сохраняем данные маршрута
    user_selected_map[user_id] = {
        "coords": [(u_lat, u_lon)] + [(p["lat"], p["lon"]) for _, p in sorted_places],
        "names": [p["name"][lang] for _, p in sorted_places],
        "lang": lang
    }

    # --- Сброс просмотренных достопримечательностей через час ---
    now = time.time()
    user_seen_places.setdefault(user_id, {})
    lang_data = user_seen_places[user_id].get(lang)
    if not lang_data or now - lang_data.get("timestamp", 0) > 3600:
        user_seen_places[user_id][lang] = {"seen": set(), "timestamp": now}

    # --- Формируем список с нумерацией ---
    places_text = "\n".join(
        f"📍{i + 1}. {name}" for i, name in enumerate(user_selected_map[user_id]["names"])
    )

    # Сообщение о готовности маршрута
    await message.answer(
        LOCALES[lang]["mini_tour_ready"].format(count=len(sorted_places))
    )

    # Кнопка "В главное меню" после списка достопримечательностей
    back_kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=LOCALES[lang]["buttons"]["back_menu"])]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    # Отправляем список достопримечательностей с кнопкой "В главное меню"
    await message.answer(places_text, reply_markup=back_kb)

    # Отправляем inline-кнопки карт отдельно
    await message.answer(
        LOCALES[lang]["choose_map"],
        reply_markup=get_map_buttons(user_id, lang)
    )


# ----------------------------------------
# Выбор карты (мини-тур)
# ----------------------------------------
@router.callback_query(lambda c: c.data.startswith("mini_map:"))
async def mini_tour_map(callback: types.CallbackQuery):
    _, map_type, user_id_str = callback.data.split(":")
    user_id = int(user_id_str)

    data = user_selected_map.get(user_id)
    if not data:
        await callback.answer("Ошибка: маршрут не найден.", show_alert=True)
        return

    coords = data["coords"]
    lang = data["lang"]

    # Формируем ссылку
    if map_type == "yandex":
        link = "https://yandex.ru/maps/?rtext=" + "~".join(f"{lat},{lon}" for lat, lon in coords)
    else:
        link = "https://www.google.com/maps/dir/" + "/".join(f"{lat},{lon}" for lat, lon in coords)

    await callback.message.answer(link)
    await callback.answer(f"Открыть маршрут в {map_type.capitalize()}")


# ----------------------------------------
# Завершение мини-тура кнопкой "В главное меню"
# ----------------------------------------
@router.message(lambda m: m.text in (LOCALES[lang]["buttons"]["back_menu"] for lang in LOCALES))
async def mini_tour_finish(message: types.Message):
    user_id = message.from_user.id
    user_mini_tour_active[user_id] = False

    lang = user_languages.get(user_id, "ru")
    # Убираем клавиатуру и возвращаем меню
    await message.answer(
        text=LOCALES[lang]["welcome"],
        reply_markup=types.ReplyKeyboardRemove()
    )
