import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile

# 1. Bot sozlamalari
BOT_TOKEN = "8812228075:AAHYhRLzjGiwWCFgIgZm6d-EZ-Lijj7K4n0"
ADMIN_ID = 7871609676  # 👈 SHU YERGA O'ZINGIZNING TELEGRAM ID RAQAMINGIZNI YOZING!

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Admin reklama yuborish rejimini tekshirish uchun vaqtinchalik o'zgaruvchi
admin_state = {}

# --- 2. MA'LUMOTLAR BAZASI BILAN ISHLASH (SQLITE) ---
conn = sqlite3.connect("users.db")
cursor = conn.cursor()
cursor.execute("""
               CREATE TABLE IF NOT EXISTS users
               (
                   user_id
                   INTEGER
                   PRIMARY
                   KEY,
                   username
                   TEXT,
                   balance
                   INTEGER
                   DEFAULT
                   0,
                   invited_by
                   INTEGER
               )
               """)
conn.commit()


# --- 3. /START MENYUSI (REFERAL HAVOLANI TEKSHIRISH BILAN) ---
@dp.message(CommandStart())
async def start_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Foydalanuvchi"

    # Start komandasi argumentini tekshiramiz (/start r_123456)
    args = message.text.split()
    invited_by = None

    if len(args) > 1 and args[1].startswith("r_"):
        try:
            invited_by = int(args[1].replace("r_", ""))
        except ValueError:
            invited_by = None

    # Bazada foydalanuvchi bor-yo'qligini tekshiramiz
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if user is None:
        if invited_by and invited_by != user_id:
            cursor.execute("UPDATE users SET balance = balance + 1 WHERE user_id = ?", (invited_by,))
            conn.commit()
            try:
                await bot.send_message(
                    chat_id=invited_by,
                    text=f"🎉 Tabriklaymiz! Do'stingiz botga kirdi va hisobingizga **+1 ball** qo'shildi!",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        cursor.execute("INSERT INTO users (user_id, username, invited_by) VALUES (?, ?, ?)",
                       (user_id, username, invited_by))
        conn.commit()

    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="🔥 Eng sara (Top) o'yinlar", callback_data="top_oyinlar"))
    builder.add(types.InlineKeyboardButton(text="📂 O'yinlar Kategoriyasi", callback_data="janrlar"))
    builder.add(types.InlineKeyboardButton(text="🔗 Pul ishlash (Partnerka)", callback_data="partnerka"))
    builder.adjust(1)

    await message.answer(
        f"🕹 Assalomu alaykum, {message.from_user.full_name}!\n\n"
        "🤖 **Torrent Games** botiga xush kelibsiz!\n"
        "Quyidagi bo'limlardan birini tanlang yoki o'yin nomini srazu yozib yuboring:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


# --- 4. YASHIRIN ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"))
        builder.add(types.InlineKeyboardButton(text="📢 Reklama yuborish", callback_data="admin_send_ad"))
        builder.adjust(1)

        await message.answer("👑 **Xush kelibsiz, Admin!**\nBotni boshqarish uchun quyidagi tugmalardan foydalaning:",
                             reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        # Oddiy foydalanuvchilarga bu komanda haqida bildirmaymiz
        pass


@dp.callback_query(lambda call: call.data.startswith("admin_"))
async def admin_callbacks(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Siz admin emassiz!", show_alert=True)
        return

    if call.data == "admin_stats":
        # Bazadan jami foydalanuvchilar sonini olamiz
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        await call.message.answer(f"📊 **Bot Statistikasi:**\n\nJami foydalanuvchilar: **{total_users} ta**",
                                  parse_mode="Markdown")
        await call.answer()

    elif call.data == "admin_send_ad":
        admin_state[call.from_user.id] = "waiting_for_ad"
        await call.message.answer(
            "📝 **Reklama postini yuboring.**\nBu matn, rasm yoki video bo'lishi mumkin. Bot uni barcha foydalanuvchilarga tarqatadi.")
        await call.answer()


# --- 5. PARTNERKA (REFERAL) OYNASI ---
@dp.callback_query(lambda call: call.data == "partnerka")
async def partnerka_menu(call: types.CallbackQuery):
    user_id = call.from_user.id

    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    balance = res[0] if res else 0

    bot_info = await bot.get_me()
    referal_link = f"https://t.me/{bot_info.username}?start=r_{user_id}"

    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="⬅️ Ortga qaytish", callback_data="back_to_start"))

    matn = (
        "🤝 **Partnyorlik dasturi (Partnerka)**\n\n"
        f"💰 Sizning balansingiz: **{balance} ball**\n\n"
        "📢 Botga do'stlaringizni taklif qiling va har bir faol foydalanuvchi uchun **1 ball** qo'lga kiriting!\n\n"
        f"🔗 Sizning referal havolangiz:\n`{referal_link}`\n\n"
        "☝️ Havolani nusxalash uchun ustiga bosing va do'stlaringizga tarqating!"
    )

    await call.message.edit_text(matn, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await call.answer()


# --- 6. KATEGORIYALAR (JANRLAR) OYNASI ---
@dp.callback_query(lambda call: call.data == "janrlar")
async def janrlar_menu(call: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="🏎 Poyga (Racing)", callback_data="cat_racing"))
    builder.add(types.InlineKeyboardButton(text="💥 Shuter (Shooter)", callback_data="cat_shooter"))
    builder.add(types.InlineKeyboardButton(text="🗺 Sarguzasht (Adventure)", callback_data="cat_adventure"))
    builder.add(types.InlineKeyboardButton(text="🌍 Ochiq dunyo (Open World)", callback_data="open_world"))
    builder.add(types.InlineKeyboardButton(text="⬅️ Ortga qaytish", callback_data="back_to_start"))
    builder.adjust(1)

    await call.message.edit_text("📂 **O'yinlar kategoriyasini tanlang:**", reply_markup=builder.as_markup(),
                                 parse_mode="Markdown")
    await call.answer()


# --- 7. KATEGORIYALAR ICHIDAGI O'YINLAR ---
@dp.callback_query(lambda call: call.data == "cat_racing")
async def cat_racing_books(call: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="🏎 NFS: Underground 2", callback_data="download_nfs"))
    builder.add(types.InlineKeyboardButton(text="🏎 Forza Horizon 5", callback_data="download_forza"))
    builder.add(types.InlineKeyboardButton(text="🏎 NFS: Most Wanted", callback_data="download_most_wanted"))
    builder.add(types.InlineKeyboardButton(text="🏎 Flatout2", callback_data="download_flatout2"))
    builder.add(types.InlineKeyboardButton(text="🏎 f12014", callback_data="download_formula1_2014"))
    builder.add(types.InlineKeyboardButton(text="🏎 Hard_truck2", callback_data="download_hard_truck2"))
    builder.add(types.InlineKeyboardButton(text="🏎 American_Truck", callback_data="download_american-truck-simulator"))
    builder.add(types.InlineKeyboardButton(text="⬅️ Janrlarga qaytish", callback_data="janrlar"))
    builder.adjust(1)
    await call.message.edit_text("🏎 **Poyga janridagi eng sara o'yinlar:**", reply_markup=builder.as_markup())
    await call.answer()


@dp.callback_query(lambda call: call.data == "cat_shooter")
async def cat_shooter_books(call: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="💥 Counter-Strike 1.6", callback_data="download_cs"))
    builder.add(types.InlineKeyboardButton(text="💥 Half_life_2", callback_data="download_half_life2"))
    builder.add(types.InlineKeyboardButton(text="💥 Left_4_dead2", callback_data="download_left_4_dead2"))
    builder.add(types.InlineKeyboardButton(text="⬅️ Janrlarga qaytish", callback_data="janrlar"))
    builder.adjust(1)
    await call.message.edit_text("💥 **Shuter janridagi eng sara o'yinlar:**", reply_markup=builder.as_markup())
    await call.answer()


@dp.callback_query(lambda call: call.data == "cat_adventure")
async def cat_adventure_books(call: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="🧱 Minecraft", callback_data="download_mc"))
    builder.add(types.InlineKeyboardButton(text="⬅️ Janrlarga qaytish", callback_data="janrlar"))
    builder.adjust(1)
    await call.message.edit_text("🗺 **Sarguzasht janridagi eng sara o'yinlar:**", reply_markup=builder.as_markup())
    await call.answer()


@dp.callback_query(lambda call: call.data == "open_world")
async def open_world_info(call: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="🏎 Forza Horizon 5", callback_data="download_forza"))
    builder.add(types.InlineKeyboardButton(text="🏙 Grand Theft Auto 5", callback_data="download_gta5"))
    builder.add(types.InlineKeyboardButton(text="⬅️ Janrlarga qaytish", callback_data="janrlar"))
    builder.adjust(1)
    await call.message.edit_text("🌍 **Ochiq dunyo (Open World) janridagi o'yinlar:**", reply_markup=builder.as_markup(),
                                 parse_mode="Markdown")
    await call.answer()


# --- 8. TOP O'YINLAR RO'YXATI ---
@dp.callback_query(lambda call: call.data == "top_oyinlar")
async def top_oyinlar_info(call: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="🏎 NFS: Underground 2", callback_data="download_nfs"))
    builder.add(types.InlineKeyboardButton(text="🏎 Forza Horizon 5", callback_data="download_forza"))
    builder.add(types.InlineKeyboardButton(text="🧱 Minecraft ", callback_data="download_mc"))
    builder.add(types.InlineKeyboardButton(text="💥 Counter-Strike 1.6", callback_data="download_cs"))
    builder.add(types.InlineKeyboardButton(text="🏎 NFS: Most Wanted", callback_data="download_most_wanted"))
    builder.add(types.InlineKeyboardButton(text="🏙 Grand Theft Auto 5", callback_data="download_gta5"))
    builder.add(types.InlineKeyboardButton(text="⬅️ Ortga qaytish", callback_data="back_to_start"))
    builder.adjust(1)
    await call.message.edit_text("🔥 **Eng ko'p yuklab olingan sara o'yinlar ro'yxati:**",
                                 reply_markup=builder.as_markup(), parse_mode="Markdown")
    await call.answer()


# --- 9. ORTGA QAYTISH FUNKSIYASI ---
@dp.callback_query(lambda call: call.data == "back_to_start")
async def back_start(call: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="🔥 Eng sara (Top) o'yinlar", callback_data="top_oyinlar"))
    builder.add(types.InlineKeyboardButton(text="📂 O'yinlar Kategoriyasi", callback_data="janrlar"))
    builder.add(types.InlineKeyboardButton(text="🔗 Pul ishlash (Partnerka)", callback_data="partnerka"))
    builder.adjust(1)
    await call.message.edit_text(
        f"🕹 Assalomu alaykum, {call.from_user.full_name}!\n\n🤖 **Torrent Games** botiga xush kelibsiz!\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=builder.as_markup(), parse_mode="Markdown")
    await call.answer()


# --- 10. RASMLI MA'LUMOT OYNALARI ---
@dp.callback_query(lambda call: call.data == "download_nfs")
async def send_nfs(call: types.CallbackQuery):
    await call.message.delete()
    btn = InlineKeyboardBuilder().add(
        types.InlineKeyboardButton(text="📥 Torrent faylni yuklab olish", callback_data="file_nfs"))
    caption = "🏎 **Need for Speed: Underground 2**\n\nHajmi: 2 GB\nRAM: 256 MB 🚀\n\n👇 Yuklash uchun bosing:"
    try:
        await call.message.answer_photo(photo=FSInputFile("FSInputFile/nfs2w.jpg"), caption=caption,
                                        reply_markup=btn.as_markup(), parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, reply_markup=btn.as_markup(), parse_mode="Markdown")
    await call.answer()


@dp.callback_query(lambda call: call.data == "download_gta5")
async def send_gta5(call: types.CallbackQuery):
    await call.message.delete()
    btn = InlineKeyboardBuilder().add(
        types.InlineKeyboardButton(text="📥 Torrent faylni yuklab olish", callback_data="file_gta5"))
    caption = "🏙 **Grand Theft Auto 5**\n\nHajmi: 110 GB\nRAM: 6 GB 🚀\n\n👇 Yuklash uchun bosing:"
    try:
        await call.message.answer_photo(photo=FSInputFile("FSInputFile/gta5w.jpg"), caption=caption,
                                        reply_markup=btn.as_markup(), parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, reply_markup=btn.as_markup(), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(lambda call: call.data == "download_flatout2")
async def send_flatout2(call: types.CallbackQuery):
    await call.message.delete()
    btn = InlineKeyboardBuilder().add(
        types.InlineKeyboardButton(text="📥 Torrent faylni yuklab olish", callback_data="file_flatout2"))
    caption = "🏙 **FlatOut 2**\n\nHajmi: 3 GB\nRAM: 2 GB 🚀\n\n👇 Yuklash uchun bosing:"
    try:
        await call.message.answer_photo(photo=FSInputFile("FSInputFile/flatout2w.jpg"), caption=caption,
                                        reply_markup=btn.as_markup(), parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, reply_markup=btn.as_markup(), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(lambda call: call.data == "download_formula1_2014")
async def send_formula1_2014(call: types.CallbackQuery):
    await call.message.delete()
    btn = InlineKeyboardBuilder().add(
        types.InlineKeyboardButton(text="📥 Torrent faylni yuklab olish", callback_data="file_formula1_2014"))
    caption = " **Formula 1 2014**\n\nHajmi: 3.5 GB\nRAM: 4 GB 🚀\n\n👇 Yuklash uchun bosing:"
    try:
        await call.message.answer_photo(photo=FSInputFile("FSInputFile/f1w.jpg"), caption=caption,
                                        reply_markup=btn.as_markup(), parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, reply_markup=btn.as_markup(), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(lambda call: call.data == "download_hard_truck2")
async def send_hard_truck2(call: types.CallbackQuery):
    await call.message.delete()
    btn = InlineKeyboardBuilder().add(
        types.InlineKeyboardButton(text="📥 Torrent faylni yuklab olish", callback_data="file_hard_truck2"))
    caption = " **Hard Truck 2**\n\nHajmi: 350 MB\nRAM: 2 GB 🚀\n\n👇 Yuklash uchun bosing:"
    try:
        await call.message.answer_photo(photo=FSInputFile("FSInputFile/hardw.jpg"), caption=caption,
                                        reply_markup=btn.as_markup(), parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, reply_markup=btn.as_markup(), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(lambda call: call.data == "download_american-truck-simulator")
async def send_americantruck(call: types.CallbackQuery):
    await call.message.delete()
    btn = InlineKeyboardBuilder().add(
        types.InlineKeyboardButton(text="📥 Torrent faylni yuklab olish", callback_data="file_americantruck"))
    caption = " **American Truck 2**\n\nHajmi: 24 GB\nRAM: 4 GB 🚀\n\n👇 Yuklash uchun bosing:"
    try:
        await call.message.answer_photo(photo=FSInputFile("FSInputFile/americanw.jpg"), caption=caption,
                                        reply_markup=btn.as_markup(), parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, reply_markup=btn.as_markup(), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(lambda call: call.data == "download_half_life2")
async def send_half_life2(call: types.CallbackQuery):
    await call.message.delete()
    btn = InlineKeyboardBuilder().add(
        types.InlineKeyboardButton(text="📥 Torrent faylni yuklab olish", callback_data="file_half_life2"))
    caption = " **Half Life 2**\n\nHajmi: 5 GB\nRAM: 4 GB 🚀\n\n👇 Yuklash uchun bosing:"
    try:
        await call.message.answer_photo(photo=FSInputFile("FSInputFile/halfw.jpg"), caption=caption,
                                        reply_markup=btn.as_markup(), parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, reply_markup=btn.as_markup(), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(lambda call: call.data == "download_left_4_dead2")
async def send_left_4_dead2(call: types.CallbackQuery):
    await call.message.delete()
    btn = InlineKeyboardBuilder().add(
        types.InlineKeyboardButton(text="📥 Torrent faylni yuklab olish", callback_data="file_left_4_dead2"))
    caption = " **Left 4 Dead 2**\n\nHajmi: 17 GB\nRAM: 4 GB 🚀\n\n👇 Yuklash uchun bosing:"
    try:
        await call.message.answer_photo(photo=FSInputFile("FSInputFile/left2w.jpg"), caption=caption,
                                        reply_markup=btn.as_markup(), parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, reply_markup=btn.as_markup(), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(lambda call: call.data == "download_forza")
async def send_forza(call: types.CallbackQuery):
    await call.message.delete()
    btn = InlineKeyboardBuilder().add(
        types.InlineKeyboardButton(text="📥 Torrent faylni yuklab olish", callback_data="file_forza"))
    caption = "🏎 **Forza Horizon 5**\n\nHajmi: 145 GB\nRAM: 12 GB 🚀\n\n👇 Yuklash uchun bosing:"
    try:
        await call.message.answer_photo(photo=FSInputFile("FSInputFile/forza5w.jpg"), caption=caption,
                                        reply_markup=btn.as_markup(), parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, reply_markup=btn.as_markup(), parse_mode="Markdown")
    await call.answer()


@dp.callback_query(lambda call: call.data == "download_most_wanted")
async def send_most_wanted(call: types.CallbackQuery):
    await call.message.delete()
    btn = InlineKeyboardBuilder().add(
        types.InlineKeyboardButton(text="📥 Torrent faylni yuklab olish", callback_data="file_most_wanted"))
    caption = "🏎 **NFS: Most Wanted**\n\nHajmi: 3.5 GB\nRAM: 4 GB 🚀\n\n👇 Yuklash uchun bosing:"
    try:
        await call.message.answer_photo(photo=FSInputFile("FSInputFile/mostw.jpg"), caption=caption,
                                        reply_markup=btn.as_markup(), parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, reply_markup=btn.as_markup(), parse_mode="Markdown")
    await call.answer()


@dp.callback_query(lambda call: call.data == "download_mc")
async def send_mc(call: types.CallbackQuery):
    await call.message.delete()
    btn = InlineKeyboardBuilder().add(
        types.InlineKeyboardButton(text="📥 Torrent faylni yuklab olish", callback_data="file_mc"))
    caption = "🧱 **Minecraft**\n\nHajmi: 1 GB\nRAM: 2-4 GB 🚀\n\n👇 Yuklash uchun bosing:"
    try:
        await call.message.answer_photo(photo=FSInputFile("FSInputFile/minecraftw.jpg"), caption=caption,
                                        reply_markup=btn.as_markup(), parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, reply_markup=btn.as_markup(), parse_mode="Markdown")
    await call.answer()


@dp.callback_query(lambda call: call.data == "download_cs")
async def send_cs(call: types.CallbackQuery):
    await call.message.delete()
    btn = InlineKeyboardBuilder().add(
        types.InlineKeyboardButton(text="📥 Torrent faylni yuklab olish", callback_data="file_cs"))
    caption = "💥 **Counter-Strike 1.6**\n\nHajmi: 500 MB\nRAM: 512 MB 🚀\n\n👇 Yuklash uchun bosing:"
    try:
        await call.message.answer_photo(photo=FSInputFile("FSInputFile/cs16ww.jpg"), caption=caption,
                                        reply_markup=btn.as_markup(), parse_mode="Markdown")
    except Exception:
        await call.message.answer(caption, reply_markup=btn.as_markup(), parse_mode="Markdown")
    await call.answer()


# --- 11. TORRENT FAYLLARINI YUBORISH ---
@dp.callback_query(lambda call: call.data == "file_nfs")
async def file_nfs(call: types.CallbackQuery):
    await call.message.answer("⏳ NFS torrent yuklanmoqda...")
    try:
        await call.message.answer_document(document=FSInputFile("FSInputFile/nfs2.torrent"), caption="🏎 NFS 2 Torrent")
    except Exception:
        await call.message.answer("❌ NFS torrent fayli topilmadi.")
    await call.answer()

@dp.callback_query(lambda call: call.data == "file_flatout2")
async def file_flatout2(call: types.CallbackQuery):
    await call.message.answer("⏳ FlatOut2 torrent yuklanmoqda...")
    try:
        await call.message.answer_document(document=FSInputFile("FSInputFile/flatout2.torrent"), caption="FlatOut2 Torrent")
    except Exception:
        await call.message.answer("❌ FlatOut2 torrent fayli topilmadi.")
    await call.answer()

@dp.callback_query(lambda call: call.data == "file_hard_truck2")
async def file_hard_truck2(call: types.CallbackQuery):
    await call.message.answer("⏳ Hard Truck2  torrent yuklanmoqda...")
    try:
        await call.message.answer_document(document=FSInputFile("FSInputFile/hard_truck2.torrent"), caption=" Torrent")
    except Exception:
        await call.message.answer("❌ Hard truck 2 torrent fayli topilmadi.")
    await call.answer()

@dp.callback_query(lambda call: call.data == "file_formula1_2014")
async def file_formula1_2014(call: types.CallbackQuery):
    await call.message.answer("⏳ Formula 1 torrent yuklanmoqda...")
    try:
        await call.message.answer_document(document=FSInputFile("FSInputFile/f12014.torrent"), caption="🏎 Formula 1 Torrent")
    except Exception:
        await call.message.answer("❌ Formula 12014 torrent fayli topilmadi.")
    await call.answer()

@dp.callback_query(lambda call: call.data == "file_americantruck")
async def file_americantruck(call: types.CallbackQuery):
    await call.message.answer("⏳ American Truck 2 torrent yuklanmoqda...")
    try:
        await call.message.answer_document(document=FSInputFile("FSInputFile/Factor.torrent"), caption="American Truck Torrent")
    except Exception:
        await call.message.answer("❌ American Truck 2 torrent fayli topilmadi.")
    await call.answer()

@dp.callback_query(lambda call: call.data == "file_half_life2")
async def file_half_life2(call: types.CallbackQuery):
    await call.message.answer("⏳ Half LIfe 2 torrent yuklanmoqda...")
    try:
        await call.message.answer_document(document=FSInputFile("FSInputFile/half_life2.torrent"), caption="Half Life2 Torrent")
    except Exception:
        await call.message.answer("❌ Half Life 2 torrent fayli topilmadi.")
    await call.answer()

@dp.callback_query(lambda call: call.data == "file_left_4_dead2")
async def file_left_4_dead2(call: types.CallbackQuery):
    await call.message.answer("⏳ Left 4 Dead 2 torrent yuklanmoqda...")
    try:
        await call.message.answer_document(document=FSInputFile("FSInputFile/ledt42.torrent"), caption="Left 4 Dead 2 Torrent")
    except Exception:
        await call.message.answer("❌ Left 4 Dead 2 torrent fayli topilmadi.")
    await call.answer()

@dp.callback_query(lambda call: call.data == "file_gta5")
async def file_gta5(call: types.CallbackQuery):
    await call.message.answer("⏳ GTA 5 torrent yuklanmoqda...")
    try:
        await call.message.answer_document(document=FSInputFile("FSInputFile/gta5.torrent"), caption="🏙 GTA 5 Torrent")
    except Exception:
        await call.message.answer("❌ GTA 5 torrent fayli topilmadi.")
    await call.answer()


@dp.callback_query(lambda call: call.data == "file_mc")
async def file_mc(call: types.CallbackQuery):
    await call.message.answer("⏳ Minecraft torrent yuklanmoqda...")
    try:
        await call.message.answer_document(document=FSInputFile("FSInputFile/minecraft.torrent"),
                                           caption="🧱 Minecraft Torrent")
    except Exception:
        await call.message.answer("❌ Minecraft torrent fayli topilmadi.")
    await call.answer()


@dp.callback_query(lambda call: call.data == "file_forza")
async def file_forza(call: types.CallbackQuery):
    await call.message.answer("⏳ Forza Horizon 5 torrent yuklanmoqda...")
    try:
        await call.message.answer_document(document=FSInputFile("FSInputFile/forza5.torrent"),
                                           caption="🏎 Forza Horizon 5 Torrent")
    except Exception:
        await call.message.answer("❌ Forza Horizon 5 torrent fayli topilmadi.")
    await call.answer()


@dp.callback_query(lambda call: call.data == "file_most_wanted")
async def file_most_wanted(call: types.CallbackQuery):
    await call.message.answer("⏳ NFS: Most Wanted torrent yuklanmoqda...")
    try:
        await call.message.answer_document(document=FSInputFile("FSInputFile/nfsmost.torrent"),
                                           caption="🏎 NFS: Most Wanted Torrent")
    except Exception:
        await call.message.answer("❌ NFS: Most Wanted torrent fayli topilmadi.")
    await call.answer()


@dp.callback_query(lambda call: call.data == "file_cs")
async def file_cs(call: types.CallbackQuery):
    await call.message.answer("⏳ CS 1.6 torrent yuklanmoqda...")
    try:
        await call.message.answer_document(document=FSInputFile("FSInputFile/cs16.torrent"), caption="💥 CS 1.6 Torrent")
    except Exception:
        await call.message.answer("❌ CS 1.6 torrent fayli topilmadi.")
    await call.answer()


# --- 12. REKLAMA TARQATISH VA TEZKOR QIDIRUV (MATNLARNI ILISH) ---
@dp.message()
async def handle_all_messages(message: types.Message):
    user_id = message.from_user.id
    user_text = message.text.lower() if message.text else ""

    # ADMIN REKLAMA TARQATAYOTGAN BO'LSA
    if user_id == ADMIN_ID and admin_state.get(user_id) == "waiting_for_ad":
        # Holatni srazu tozalaymiz
        admin_state.pop(user_id, None)

        await message.answer("⏳ Reklama barcha foydalanuvchilarga tarqatilmoqda, kuting...")

        # Bazadan hamma foydalanuvchilarni ID raqamini olamiz
        cursor.execute("SELECT user_id FROM users")
        all_users = cursor.fetchall()

        success = 0
        failed = 0

        for u in all_users:
            target_id = u[0]
            try:
                # Xabarni barchaga aynan qanday formatda bo'lsa shunday nusxalab yuboramiz (Rasm, matn, video farqi yo'q)
                await message.copy_to(chat_id=target_id)
                success += 1
                await asyncio.sleep(0.05)  # Telegram bloklab qo'ymasligi uchun kichik pauza
            except Exception:
                failed += 1

        await message.answer(
            f"📢 **Reklama tarqatish yakunlandi!**\n\n✅ Muvaffaqiyatli: {success} ta\n❌ Yetib bormadi (botni bloklaganlar): {failed} ta")
        return

    # ODDIY FOYDALANUVCHILAR UCHUN QIDIRUV TIZIMI
    if "most" in user_text or "wanted" in user_text:
        btn = InlineKeyboardBuilder().add(
            types.InlineKeyboardButton(text="📥 Torrent yuklash", callback_data="file_most_wanted"))
        await message.answer_photo(photo=FSInputFile("FSInputFile/mostw.jpg"), caption="🏎 NFS: Most Wanted topildi!",
                                   reply_markup=btn.as_markup())
    elif "underground" in user_text or "nfs 2" in user_text or (user_text == "nfs"):
        btn = InlineKeyboardBuilder().add(
            types.InlineKeyboardButton(text="📥 Torrent yuklash", callback_data="file_nfs"))
        await message.answer_photo(photo=FSInputFile("FSInputFile/nfs2w.jpg"), caption="🏎 NFS 2 topildi!",
                                   reply_markup=btn.as_markup())
    elif "minecraft" in user_text or "maynkraft" in user_text:
        btn = InlineKeyboardBuilder().add(types.InlineKeyboardButton(text="📥 Torrent yuklash", callback_data="file_mc"))
        await message.answer_photo(photo=FSInputFile("FSInputFile/minecraftw.jpg"), caption="🧱 Minecraft topildi!",
                                   reply_markup=btn.as_markup())
    elif "cs" in user_text or "counter" in user_text:
        btn = InlineKeyboardBuilder().add(types.InlineKeyboardButton(text="📥 Torrent yuklash", callback_data="file_cs"))
        await message.answer_photo(photo=FSInputFile("FSInputFile/cs16ww.jpg"), caption="💥 CS 1.6 topildi!",
                                   reply_markup=btn.as_markup())
    elif "forza" in user_text or "horizon" in user_text:
        btn = InlineKeyboardBuilder().add(
            types.InlineKeyboardButton(text="📥 Torrent yuklash", callback_data="file_forza"))
        await message.answer_photo(photo=FSInputFile("FSInputFile/forza5w.jpg"), caption="🏎 Forza Horizon 5 topildi!",
                                   reply_markup=btn.as_markup())
    elif "gta" in user_text or "gta5" in user_text:
        btn = InlineKeyboardBuilder().add(
            types.InlineKeyboardButton(text="📥 Torrent yuklash", callback_data="file_gta5"))
        await message.answer_photo(photo=FSInputFile("FSInputFile/gta5w.jpg"), caption="🏙 GTA 5 topildi!",
                                   reply_markup=btn.as_markup())
    elif "hard_truck2" in user_text or "hard_truck2" in user_text:
        btn = InlineKeyboardBuilder().add(
            types.InlineKeyboardButton(text="📥 Torrent yuklash", callback_data="file_hard_truck2"))
        await message.answer_photo(photo=FSInputFile("FSInputFile/hardw.jpg"), caption="Hard Truck 2 topildi!",
                                   reply_markup=btn.as_markup())
    elif "flatout2" in user_text or "out2" in user_text:
        btn = InlineKeyboardBuilder().add(
            types.InlineKeyboardButton(text="📥 Torrent yuklash", callback_data="file_flatout2"))
        await message.answer_photo(photo=FSInputFile("FSInputFile/flatout2w.jpg"), caption="FlatOut2 topildi!",
                                   reply_markup=btn.as_markup())
    elif "f1" in user_text or "formula 2014" in user_text:
        btn = InlineKeyboardBuilder().add(
            types.InlineKeyboardButton(text="📥 Torrent yuklash", callback_data="file_formula1_2014"))
        await message.answer_photo(photo=FSInputFile("FSInputFile/f1w.jpg"), caption="Formula 1 2014 topildi!",
                                   reply_markup=btn.as_markup())
    elif "americantruck" in user_text or "american" in user_text:
        btn = InlineKeyboardBuilder().add(
            types.InlineKeyboardButton(text="📥 Torrent yuklash", callback_data="file_american_truck2"))
        await message.answer_photo(photo=FSInputFile("FSInputFile/americanw.jpg"), caption="American Truck 2 topildi!",
                                   reply_markup=btn.as_markup())
    elif "half_life2" in user_text or "half_life" in user_text:
        btn = InlineKeyboardBuilder().add(
            types.InlineKeyboardButton(text="📥 Torrent yuklash", callback_data="file_half_life2"))
        await message.answer_photo(photo=FSInputFile("FSInputFile/halfw.jpg"), caption="Half Life 2 topildi!",
                                   reply_markup=btn.as_markup())
    elif "left_4_dead2" in user_text or "left_4_dead2" in user_text:
        btn = InlineKeyboardBuilder().add(
            types.InlineKeyboardButton(text="📥 Torrent yuklash", callback_data="file_left_4_dead2"))
        await message.answer_photo(photo=FSInputFile("FSInputFile/left2w.jpg"), caption="Left 4 Dead 2 topildi!",
                                   reply_markup=btn.as_markup())
    else:
        await message.reply(
            f"🔍 '{message.text}' bo'yicha hech narsa topilmadi.\nSinab ko'ring: NFS, CS, Minecraft, Forza, Most Wanted, GTA5")


# --- 13. BOTNI ISHGA TUSHIRISH ---
async def main():
    print("Baza, Partnerka va Admin Panelli professional bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())