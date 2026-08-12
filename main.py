import os
import json
import asyncio
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)

# .env faylidan muhit o'zgaruvchilarini yuklash
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://vy489320-png.github.io/MEATBOX.UZ/")
ADMIN_ID = os.getenv("ADMIN_ID", "8593408047")

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE" or ":" not in BOT_TOKEN:
    logging.error("\n⚠️ DIQQAT: Railway (yoki .env) parametrlarida BOT_TOKEN topilmadi yoki noto'g'ri!")

# Telegram Bot va Dispatcher obyektlarini yaratish
try:
    from aiogram.client.default import DefaultBotProperties
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
except Exception as e:
    logging.error(f"Bot obyektini yaratishda xatolik: {e}")
    bot = None

dp = Dispatcher(storage=MemoryStorage())

# =====================================================================
# MAHSULOTLAR MA'LUMOTLAR BAZASI (SETLAR)
# =====================================================================
PRODUCTS = {
    "set_1": {
        "name": "🥩 Premium Steak Set",
        "description": "Eng saralab olingan Mramor mol go'shti (T-Bone 1kg, Ribeye 1kg, Tenderloin 0.5kg) + maxsus marinad va ziravorlar to'plami.",
        "price": 450000,
        "price_formatted": "450 000 so'm"
    },
    "set_2": {
        "name": "🔥 BBQ Grill Box",
        "description": "Katta kompaniya va piknik uchun ideal! Marinadlangan qovurg'alar (2kg), kabob uchun go'sht (2kg), nemis sosiskalari (1kg).",
        "price": 380000,
        "price_formatted": "380 000 so'm"
    },
    "set_3": {
        "name": "👨‍👩‍👧‍👦 Family Meat Box",
        "description": "Oila uchun haftalik yangi va halol go'shtlar (Mol go'shti lahza 2kg, Qo'y go'shti me'yori 2kg, Qiymasi 1kg).",
        "price": 520000,
        "price_formatted": "520 000 so'm"
    },
    "set_4": {
        "name": "🍔 Burger & Steak Combo",
        "description": "Uyda eng mazali burger va steyklar tayyorlang! Ribeye steyk (1kg), Burger kotletlari (8 dona), maxsus sous.",
        "price": 320000,
        "price_formatted": "320 000 so'm"
    }
}

user_carts = {}

class OrderState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_location = State()
    confirm_order = State()

def get_main_keyboard():
    kb = [
        [KeyboardButton(text="🛍 Menyu va Buyurtma (Mini App)", web_app=WebAppInfo(url=WEB_APP_URL))],
        [KeyboardButton(text="🥩 Mahsulotlar (Setlar)"), KeyboardButton(text="🛒 Savat")],
        [KeyboardButton(text="📍 Biz haqimizda"), KeyboardButton(text="📞 Aloqa")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_phone_keyboard():
    kb = [
        [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)],
        [KeyboardButton(text="❌ Bekor qilish")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_location_keyboard():
    kb = [
        [KeyboardButton(text="📍 Geolokatsiyani yuborish", request_location=True)],
        [KeyboardButton(text="❌ Bekor qilish")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_product_inline_keyboard(product_id):
    kb = [
        [InlineKeyboardButton(text="🛒 Savatga qo'shish", callback_data=f"add_cart:{product_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_cart_inline_keyboard():
    kb = [
        [InlineKeyboardButton(text="🚖 Buyurtma berish", callback_data="checkout")],
        [InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear_cart")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_confirm_inline_keyboard():
    kb = [
        [InlineKeyboardButton(text="✅ Buyurtmani tasdiqlash", callback_data="confirm_order")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_order")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_name = message.from_user.first_name or "Mijoz"
    welcome_text = (
        f"Xush kelibsiz, <b>{user_name}</b>!\n\n"
        f"🥩 <b>MEATBOX.UZ</b> — Premium sifatli va yangi go'sht do'konining rasmiy telegram botiga xush kelibsiz!\n\n"
        f"📱 Endi siz <b>'🛍 Menyu va Buyurtma (Mini App)'</b> tugmasini bosish orqali zamonaviy interaktiv katalogdan foydalanishingiz mumkin!\n\n"
        f"👇 Kerakli bo'limni tanlang:"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

# =====================================================================
# WEB APP (MINI APP) DATA HANDLER
# =====================================================================
@dp.message(F.web_app_data)
async def handle_web_app_data(message: Message):
    """Mini App (index.html) dan sendData orqali kelgan buyurtma ma'lumotlarini qabul qilish"""
    raw_data = message.web_app_data.data
    
    try:
        data = json.loads(raw_data)
    except Exception as e:
        logging.error(f"JSON parsing error: {e}")
        await message.answer("❌ Buyurtma ma'lumotlarini o'qishda xatolik yuz berdi.")
        return

    items = data.get("items", [])
    total_price = data.get("total_price", 0)
    total_count = data.get("total_count", 0)
    comment = data.get("comment", "Izoh yo'q")
    customer = data.get("customer", {})

    cust_name = customer.get("name", message.from_user.full_name)
    cust_phone = customer.get("phone", "Ko'rsatilmadi")
    cust_address = customer.get("address", "Olib ketish")

    if not items:
        await message.answer("🛒 Savat bo'sh bo'lgani uchun buyurtma qabul qilinmadi.")
        return

    # Geolokatsiya koordinatalarini bossa ochiladigan havola (link) ga aylantirish
    import re
    formatted_address = cust_address
    lat_coord, lon_coord = None, None
    coords = re.findall(r"[-+]?\d+\.\d+", cust_address)
    
    if len(coords) >= 2:
        lat_coord, lon_coord = coords[0], coords[1]
        maps_link = f"https://maps.google.com/maps?q={lat_coord},{lon_coord}"
        formatted_address = f'<a href="{maps_link}">📍 Xaritada ko\'rish ({lat_coord}, {lon_coord}) 🗺</a>'
    elif cust_address.startswith("http://") or cust_address.startswith("https://"):
        formatted_address = f'<a href="{cust_address}">📍 Manzil havolasi (Xaritada ochish) 🗺</a>'

    receipt = (
        f"🎉 <b>BUYURTMANGIZ QABUL QILINDI! (Mini App)</b>\n\n"
        f"🆔 Buyurtma ID: <b>#MB-WA-{message.from_user.id}</b>\n"
        f"👤 Mijoz: <b>{cust_name}</b>\n"
        f"📱 Telefon: <code>{cust_phone}</code>\n"
        f"📍 Manzil: {formatted_address}\n"
        f"📅 Sana: <code>{data.get('date', 'Hozir')}</code>\n\n"
        f"📋 <b>BUYURTMA TARKIBI:</b>\n"
    )

    for idx, item in enumerate(items, 1):
        item_total_formatted = f"{item['total']:,}".replace(",", " ")
        receipt += f"{idx}. <b>{item['name']}</b>\n   └ {item['count']} dona x {item['price']:,} = <b>{item_total_formatted} so'm</b>\n".replace(",", " ")

    total_formatted = f"{total_price:,}".replace(",", " ")
    receipt += (
        f"\n💳 <b>Jami to'lov:</b> <code>{total_formatted} so'm</code>\n"
        f"📦 Jami dona: <b>{total_count} ta</b>\n"
        f"📝 <b>Izoh:</b> <i>{comment}</i>\n\n"
        f"⚡️ Operatorimiz tez orada siz bilan bog'lanadi.\n"
        f"MEATBOX.UZ ni tanlaganingiz uchun rahmat! 🥩"
    )

    await message.answer(receipt, reply_markup=get_main_keyboard())

    # Native Location pin yuborish
    if lat_coord and lon_coord:
        try:
            await message.answer_location(latitude=float(lat_coord), longitude=float(lon_coord))
        except Exception as err:
            logging.error(f"User location yuborishda xatolik: {err}")

    if ADMIN_ID and ADMIN_ID.isdigit():
        admin_text = (
            f"🔔 <b>YANGI MINI APP BUYURTMA!</b>\n\n"
            f"👤 <b>Mijoz:</b> {cust_name} (@{message.from_user.username or 'yo_q'})\n"
            f"📱 <b>Tel:</b> {cust_phone}\n"
            f"📍 <b>Manzil:</b> {formatted_address}\n"
            f"🆔 <b>Mijoz ID:</b> <code>{message.from_user.id}</code>\n\n"
            f"📋 <b>Tarkib:</b>\n"
        )
        for item in items:
            admin_text += f"• {item['name']} - {item['count']} dona ({item['total']:,} so'm)\n".replace(",", " ")
        
        admin_text += f"\n💳 <b>Jami summasi:</b> <code>{total_formatted} so'm</code>\n"
        admin_text += f"📝 <b>Izoh:</b> {comment}"
        
        try:
            await bot.send_message(chat_id=int(ADMIN_ID), text=admin_text)
            if lat_coord and lon_coord:
                await bot.send_location(chat_id=int(ADMIN_ID), latitude=float(lat_coord), longitude=float(lon_coord))
        except Exception as err:
            logging.error(f"Adminga xabar yuborishda xatolik: {err}")

@dp.message(F.text == "❌ Bekor qilish")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Amaliyot bekor qilindi. Asosiy menyu:", reply_markup=get_main_keyboard())

@dp.message(F.text.startswith("🥩 Mahsulotlar"))
async def show_products(message: Message):
    await message.answer("🥩 <b>MEATBOX.UZ Premium Setlar ro'yxati:</b>")
    for prod_id, prod in PRODUCTS.items():
        caption = (
            f"<b>{prod['name']}</b>\n\n"
            f"📝 <b>Tavsif:</b> {prod['description']}\n\n"
            f"💰 <b>Narxi:</b> <code>{prod['price_formatted']}</code>"
        )
        await message.answer(caption, reply_markup=get_product_inline_keyboard(prod_id))

@dp.callback_query(F.data.startswith("add_cart:"))
async def add_to_cart_callback(callback: CallbackQuery):
    product_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    if product_id not in PRODUCTS:
        await callback.answer("Mahsulot topilmadi!", show_alert=True)
        return
    if user_id not in user_carts:
        user_carts[user_id] = {}
    user_carts[user_id][product_id] = user_carts[user_id].get(product_id, 0) + 1
    await callback.answer(f"✅ {PRODUCTS[product_id]['name']} savatga qo'shildi!", show_alert=False)

@dp.message(F.text == "🛒 Savat")
async def show_cart(message: Message):
    user_id = message.from_user.id
    cart = user_carts.get(user_id, {})
    if not cart or sum(cart.values()) == 0:
        await message.answer("🛒 Savatingiz bo'sh.", reply_markup=get_main_keyboard())
        return
    cart_text = "🛒 <b>Sizning savatingiz:</b>\n\n"
    total_price = 0
    item_num = 1
    for prod_id, count in cart.items():
        if count > 0 and prod_id in PRODUCTS:
            prod = PRODUCTS[prod_id]
            item_total = prod["price"] * count
            total_price += item_total
            cart_text += f"{item_num}. <b>{prod['name']}</b>\n   └ {count} dona x {prod['price_formatted']} = <b>{item_total:,} so'm</b>\n\n".replace(",", " ")
            item_num += 1
    cart_text += f"💳 <b>Jami to'lov:</b> <code>{total_price:,} so'm</code>".replace(",", " ")
    await message.answer(cart_text, reply_markup=get_cart_inline_keyboard())

@dp.callback_query(F.data == "clear_cart")
async def clear_cart_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_carts[user_id] = {}
    await callback.answer("🗑 Savat tozalandi!")
    await callback.message.edit_text("🛒 Savatingiz bo'shatildi.")

@dp.callback_query(F.data == "checkout")
async def start_checkout(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    cart = user_carts.get(user_id, {})
    if not cart or sum(cart.values()) == 0:
        await callback.answer("Savatingiz bo'sh!", show_alert=True)
        return
    await callback.answer()
    await state.set_state(OrderState.waiting_for_phone)
    await callback.message.answer("📱 Telefon raqamingizni yuboring:", reply_markup=get_phone_keyboard())

@dp.message(OrderState.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text
    await state.update_data(phone=phone)
    await state.set_state(OrderState.waiting_for_location)
    await message.answer("📍 Manzilingizni yuboring:", reply_markup=get_location_keyboard())

@dp.message(OrderState.waiting_for_location)
async def process_location(message: Message, state: FSMContext):
    location_info = f"https://maps.google.com/maps?q={message.location.latitude},{message.location.longitude}" if message.location else message.text
    await state.update_data(location=location_info)
    await state.set_state(OrderState.confirm_order)
    data = await state.get_data()
    cart = user_carts.get(message.from_user.id, {})
    order_summary = f"📋 <b>BUYURTMA:</b>\n\n📞 Tel: {data['phone']}\n📍 Manzil: {data['location']}\n"
    await message.answer(order_summary, reply_markup=get_confirm_inline_keyboard())

@dp.callback_query(F.data == "confirm_order", OrderState.confirm_order)
async def confirm_order_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    phone = data.get("phone", "Ko'rsatilmadi")
    location_info = data.get("location", "Ko'rsatilmadi")

    user_carts[user_id] = {}
    await state.clear()
    await callback.answer("Buyurtmangiz qabul qilindi!")
    await callback.message.edit_text("🎉 Buyurtmangiz muvaffaqiyatli qabul qilindi!")
    await callback.message.answer("Asosiy menyu:", reply_markup=get_main_keyboard())

    # Adminga Telegram orqali yuborish (8593408047)
    admin_id_to_use = ADMIN_ID or "8593408047"
    if admin_id_to_use and str(admin_id_to_use).isdigit():
        admin_text = (
            f"🔔 <b>YANGI BOT BUYURTMA!</b>\n\n"
            f"👤 <b>Mijoz:</b> {callback.from_user.full_name} (@{callback.from_user.username or 'username_yoq'})\n"
            f"📱 <b>Tel:</b> <code>{phone}</code>\n"
            f"📍 <b>Manzil:</b> {location_info}\n"
            f"🆔 <b>Mijoz ID:</b> <code>{user_id}</code>\n"
        )
        try:
            await bot.send_message(chat_id=int(admin_id_to_use), text=admin_text)
        except Exception as err:
            logging.error(f"Adminga xabar yuborishda xatolik: {err}")

@dp.message(F.text == "📍 Biz haqimizda")
async def show_about(message: Message):
    about_text = (
        "🥩 <b>MEATBOX.UZ — Premium Go'sht Do'koni</b>\n\n"
        "✨ 100% Halol va Yangi go'shtlar!\n\n"
        "📍 <b>Do'kon manzili:</b> https://t.me/xasanqassob/367\n"
        "📱 <b>Call-markaz:</b> +998 (95) 113-53-53\n"
        "⏰ <b>Ish vaqti:</b> Har kuni 09:00 dan 21:00 gacha"
    )
    await message.answer(about_text, reply_markup=get_main_keyboard())

@dp.message(F.text == "📞 Aloqa")
async def show_contact(message: Message):
    await message.answer("📞 <b>MEATBOX.UZ bilan bog'lanish:</b>\n\n📱 <b>Call-markaz:</b> +998 (95) 113-53-53\n💬 <b>Telegram Admin:</b> @meatbox_admin", reply_markup=get_main_keyboard())

from aiohttp import web

async def handle_healthcheck(request):
    return web.Response(text="MEATBOX.UZ Telegram Bot is active and running 24/7 🚀")

async def start_web_server():
    port = int(os.getenv("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", handle_healthcheck)
    app.router.add_get("/health", handle_healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"🌐 Railway HTTP Healthcheck server listening on port {port}")

async def main():
    if not bot:
        return
    print("🚀 MEATBOX.UZ Telegram boti va 24/7 server ishga tushirilmoqda...")
    
    try:
        asyncio.create_task(start_web_server())
    except Exception as e:
        logging.error(f"HTTP healthcheck server xatosi: {e}")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
