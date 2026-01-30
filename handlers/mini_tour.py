from aiogram import Router, types
from places import PLACES
from locales import LOCALES
from state import user_mini_tour_active
import math

router = Router()

# Хранилище языков и временных данных
user_languages = {}
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
# Кнопки выбора карты
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
# ФУНКЦИЯ обработки геолокации
# Вызывается из start.py → unified_location_handler()
# ----------------------------------------
async def mini_tour_location(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")

    u_lat = message.location.latitude
    u_lon = message.location.longitude

    # Сортировка мест
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

    # Отправляем список мест
    places_text = "\n".join(user_selected_map[user_id]["names"])

    await message.answer(
        LOCALES[lang]["mini_tour_ready"].format(count=len(sorted_places))
    )

    await message.answer(
        LOCALES[lang].get("choose_map", "Выберите карту:"),
        reply_markup=types.ReplyKeyboardRemove()
    )

    await message.answer(
        places_text,
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
        link = "https://yandex.ru/maps/?rtext=" + "~".join(
            f"{lat},{lon}" for lat, lon in coords
        )
    else:
        link = "https://www.google.com/maps/dir/" + "/".join(
            f"{lat},{lon}" for lat, lon in coords
        )

    await callback.message.answer(link)
    await callback.answer(f"Открыть маршрут в {map_type.capitalize()}")

    # Завершаем мини-тур
    user_mini_tour_active[user_id] = False
