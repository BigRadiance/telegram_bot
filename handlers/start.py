from aiogram import Router, types, F
from aiogram.filters import Command
from locales import LOCALES
from places import PLACES
from handlers.mini_tour import mini_tour_location
from state import (
    user_languages,
    user_mini_tour_active,
    user_seen_places,
    user_selected_map,
    user_selected_place,
    user_showing_places
)

import time

import asyncio

router = Router()

# ----------------------------
# /start -> выбор языка
# ----------------------------
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="🇷🇺 RU", callback_data="lang_ru"),
                types.InlineKeyboardButton(text="🇧🇾 BE", callback_data="lang_be"),
                types.InlineKeyboardButton(text="🇬🇧 EN", callback_data="lang_en")
            ]
        ]
    )

    await message.answer(
        LOCALES["ru"]["choose_language"],
        reply_markup=keyboard
    )


# ----------------------------
# Выбор языка
# ----------------------------
@router.callback_query(lambda c: c.data.startswith("lang_"))
async def choose_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang

    try:
        await callback.message.delete()
    except:
        pass

    await callback.message.answer(LOCALES[lang]["welcome"])
    await send_menu(callback.message, lang)
    await callback.answer()


# ----------------------------
# Отправка главного меню
# ----------------------------
async def send_menu(message: types.Message, lang: str):
    buttons = LOCALES[lang]["buttons"]

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=buttons["places"], callback_data="places")],
            #[types.InlineKeyboardButton(text=buttons["routes"], callback_data="routes")],
            [types.InlineKeyboardButton(text=buttons["mini_tour"], callback_data="mini_tour")],
            [types.InlineKeyboardButton(text=buttons["about"], callback_data="about")]
        ]
    )

    await message.answer(LOCALES[lang]["menu"], reply_markup=keyboard)



# ----------------------------
# О боте
# ----------------------------
@router.callback_query(lambda c: c.data == "about")
async def about_bot(callback: types.CallbackQuery):
    lang = user_languages.get(callback.from_user.id, "ru")
    buttons = LOCALES[lang]["buttons"]

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=buttons["back_menu"], callback_data="open_menu_edit")]
        ]
    )

    await callback.message.edit_text(LOCALES[lang]["about"], reply_markup=keyboard)
    await callback.answer()


# ----------------------------
# Вернуться в меню
# ----------------------------
@router.callback_query(lambda c: c.data == "open_menu_edit")
async def return_to_menu(callback: types.CallbackQuery):
    lang = user_languages.get(callback.from_user.id, "ru")
    buttons = LOCALES[lang]["buttons"]

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=buttons["places"], callback_data="places")],
            [types.InlineKeyboardButton(text=buttons["mini_tour"], callback_data="mini_tour")],
            [types.InlineKeyboardButton(text=buttons["about"], callback_data="about")]
        ]
    )

    await callback.message.edit_text(LOCALES[lang]["menu"], reply_markup=keyboard)
    await callback.answer()


# ============================================================
#                       ДОСТОПРИМЕЧАТЕЛЬНОСТИ
# ============================================================

# Кнопка "Поехали туда"
def get_go_button(place_id, lang):
    text = LOCALES[lang]["buttons"]["go"]
    return types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text=text, callback_data=f"go:{place_id}")]]
    )


# Кнопки карт после "Поехали"
def get_maps_buttons(place_id, lang):
    buttons = LOCALES[lang]["buttons"]
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text=buttons["yandex"], callback_data=f"map:yandex:{place_id}"),
                types.InlineKeyboardButton(text=buttons["google"], callback_data=f"map:google:{place_id}")
            ]
        ]
    )



# ----------------------------
# Нажатие — "ДОСТОПРИМЕЧАТЕЛЬНОСТИ"
# ----------------------------
@router.callback_query(lambda c: c.data == "places")
async def show_places(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, "ru")

    user_showing_places[user_id] = True

    # Кнопка "Назад"
    back_kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(
            text=LOCALES[lang]["buttons"]["back_menu"]
        )]],
        resize_keyboard=True
    )

    await callback.message.answer(
        LOCALES[lang]["places_start"],
        reply_markup=back_kb
    )

    # 1) Отправляем начало
    # Инициализация просмотренных мест
    now = time.time()

    user_seen_places.setdefault(user_id, {})
    lang_data = user_seen_places[user_id].get(lang)

    # если первый раз или прошёл час — сбрасываем
    if not lang_data or now - lang_data["timestamp"] > 3600:
        user_seen_places[user_id][lang] = {
            "seen": set(),
            "timestamp": now
        }

    for place_id, place in PLACES.items():
        if not user_showing_places.get(user_id):
            break

        if place_id in user_seen_places[user_id][lang]["seen"]:
            continue

        caption = place["name"][lang]
        full_text = place["description"][lang]
        photos = place.get("photos", [])

        # 1 Фото (caption = только название)
        if photos:
            media = [
                types.InputMediaPhoto(
                    media=types.FSInputFile(photo),
                    caption=caption if i == 0 else None
                )
                for i, photo in enumerate(photos)
            ]
            await callback.message.answer_media_group(media)
        else:
            await callback.message.answer(caption)

        # 2 Готовим текст кусками
        MAX_LEN = 4096
        text_parts = [
            full_text[i:i + MAX_LEN]
            for i in range(0, len(full_text), MAX_LEN)
        ]

        # 3 Отправляем текст, кнопку вешаем на ПОСЛЕДНИЙ кусок
        for idx, part in enumerate(text_parts):
            if not user_showing_places.get(user_id):
                break

            if idx == len(text_parts) - 1:
                await callback.message.answer(
                    part,
                    reply_markup=get_go_button(place_id, lang)
                )
            else:
                await callback.message.answer(part)

        user_seen_places[user_id][lang]["seen"].add(place_id)


        await asyncio.sleep(5)

    user_showing_places[user_id] = False



@router.message(F.text)
async def back_button_handler(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")

    if message.text != LOCALES[lang]["buttons"]["back_menu"]:
        return

    user_showing_places[user_id] = False

    # Убираем клавиатуру
    await message.answer(
        text=LOCALES[lang]["welcome"],
        reply_markup=types.ReplyKeyboardRemove()
    )

    await send_menu(message, lang)











# ----------------------------
# Нажатие — "Поехали туда"
# ----------------------------
@router.callback_query(lambda c: c.data.startswith("go:"))
async def go_to_place(callback: types.CallbackQuery):
    place_id = callback.data.split(":")[1]
    lang = user_languages.get(callback.from_user.id, "ru")

    await callback.message.edit_reply_markup(
        reply_markup=get_maps_buttons(place_id, lang)
    )

    await callback.answer()


# ----------------------------
# Пользователь выбрал карту
# ----------------------------
@router.callback_query(lambda c: c.data.startswith("map:"))
async def map_selected(callback: types.CallbackQuery):
    _, map_type, place_id = callback.data.split(":")

    user_selected_map[callback.from_user.id] = map_type
    user_selected_place[callback.from_user.id] = place_id

    lang = user_languages.get(callback.from_user.id, "ru")

    # Кнопка отправки геолокации
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=LOCALES[lang]["buttons"]["send_location"], request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await callback.message.answer(LOCALES[lang]["buttons"]["send_location"], reply_markup=kb)
    await callback.answer()


@router.message(F.location)
async def unified_location_handler(message: types.Message):
    user_id = message.from_user.id

    # Если включён мини-тур → передаём в mini_tour
    if user_mini_tour_active.get(user_id):
        return await mini_tour_location(message)

    # Если выбран обычный маршрут
    if user_id in user_selected_place:
        return await build_route(message)

    # Иначе просто ошибка
    await message.answer("Ошибка: вы не выбрали ни мини-тур, ни достопримечательность.")

# -----------------------------
# Обычный маршрут
# -----------------------------
async def build_route(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")

    place_id = user_selected_place.get(user_id)
    map_type = user_selected_map.get(user_id)

    if not place_id or not map_type:
        await message.answer("Ошибка: вы не выбрали точку назначения.")
        return

    place = PLACES[place_id]

    u_lat = message.location.latitude
    u_lon = message.location.longitude

    p_lat = place["lat"]
    p_lon = place["lon"]

    yandex = f"https://yandex.ru/maps/?rtext={u_lat},{u_lon}~{p_lat},{p_lon}"
    google = f"https://www.google.com/maps/dir/?api=1&origin={u_lat},{u_lon}&destination={p_lat},{p_lon}"

    link = yandex if map_type == "yandex" else google

    await message.answer(LOCALES[lang]["route_ready"], reply_markup=types.ReplyKeyboardRemove())
    await message.answer(link)



