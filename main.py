here# === 1-ші блок === #

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.utils import executor
import os
from keep_alive import keep_alive
from database import (  # database.py файлдан функцияларды импорттаймыз
    init_db,
    add_user,
    get_user_count,
    add_kino_code,
    get_kino_by_code,
    get_all_codes,
    delete_kino_code,
    get_code_stat,
    increment_stat,
    get_all_user_ids,
    update_anime_code
)

# === YUKLAMALAR === #
load_dotenv()
keep_alive()

API_TOKEN = os.getenv("API_TOKEN")
CHANNELS = os.getenv("CHANNEL_USERNAMES").split(",")
MAIN_CHANNELS = os.getenv("MAIN_CHANNELS").split(",")
BOT_USERNAME = os.getenv("BOT_USERNAME")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# === OBUNA TEKSHIRISH FUNKSIYALARI === #
async def get_unsubscribed_channels(user_id):
    unsubscribed = []
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(channel.strip(), user_id)
            if member.status not in ["member", "administrator", "creator"]:
                unsubscribed.append(channel)
        except Exception as e:
            print(f"❗ Obuna tekshirishda xatolik: {channel} -> {e}")
            unsubscribed.append(channel)
    return unsubscribed

# === /start HANDLER – to‘liq versiya (statistika bilan) === #
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await add_user(message.from_user.id)
    args = message.get_args()

    if args and args.isdigit():
        code = args
        await increment_stat(code, "init")
        await increment_stat(code, "searched")

        unsubscribed = await get_unsubscribed_channels(message.from_user.id)
        if unsubscribed:
            markup = await make_subscribe_markup(code)
            await message.answer(
                "❗ Kino olishdan oldin quyidagi kanal(lar)ga obuna bo‘ling:",
                reply_markup=markup
            )
        else:
            await send_reklama_post(message.from_user.id, code)
            await increment_stat(code, "searched")
        return

    # === Oddiy /start === #
    if message.from_user.id in ADMINS:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("➕ Anime qo‘shish")
        kb.add("📊 Statistika", "📈 Kod statistikasi")
        kb.add("❌ Kodni o‘chirish", "📄 Kodlar ro‘yxati")
        kb.add("✏️ Kodni tahrirlash", "📤 Post qilish")
        kb.add("📢 Habar yuborish", "📘 Qo‘llanma")
        kb.add("➕ Admin qo‘shish", "📦 Bazani olish")
        kb.add("📥 User qo‘shish")
        await message.answer("👮‍♂️ Admin panel:", reply_markup=kb)
    else:
        kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        kb.add(
            KeyboardButton("🎞 Barcha animelar"),
            KeyboardButton("✉️ Admin bilan bog‘lanish")
        )
        await message.answer("🎬 Botga xush kelibsiz!\nKod kiriting:", reply_markup=kb)

# === TEKSHIRUV CALLBACK – faqat obuna bo‘lmaganlar uchun === #
@dp.callback_query_handler(lambda c: c.data.startswith("checksub:"))  # Bu yerda 100 qatardan oshib ketsa, keyingi blokka o'tiladi

# === 2-ші блок === #

# === Kanallar komandasi === #
@dp.message_handler(commands=['kanallar'])
async def kanallar_handler(message: types.Message):
    if str(message.from_user.id) == ADMIN_ID:
        await message.answer("📌 Kanal menyusi:", reply_markup=kanal_menu())
    else:
        await message.answer("⚠️ Sizga ruxsat yo'q!")

# === Kanal menyusi === #
def kanal_menu():
    menu = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="kanal_add")],
        [InlineKeyboardButton(text="📋 Kanal ro'yxati", callback_data="kanal_list")],
        [InlineKeyboardButton(text="❌ Kanal o'chirish", callback_data="kanal_delete")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="kanal_back")],
    ])
    return menu

# === Kanal qo'shish === #
@dp.callback_query(lambda c: c.data == "kanal_add")
async def kanal_add(call: types.CallbackQuery, state: FSMContext):
    if str(call.from_user.id) == ADMIN_ID:
        await call.message.answer("📎 Kanal havolasini yuboring:")
        await state.set_state(KanalFSM.url)
    else:
        await call.answer("⚠️ Sizga ruxsat yo'q!", show_alert=True)

# === Kanal URL === #
@dp.message(KanalFSM.url)
async def kanal_url(msg: types.Message, state: FSMContext):
    await state.update_data(url=msg.text)
    await msg.answer("🆔 Kanal ID yuboring:")
    await state.set_state(KanalFSM.kanal_id)

# === Kanal ID === #
@dp.message(KanalFSM.kanal_id)
async def kanal_id(msg: types.Message, state: FSMContext):
    await state.update_data(kanal_id=msg.text)
    await msg.answer("⏳ Kanal qancha vaqt majburiy obunada turadi? (masalan: 1m, 1d, null)")
    await state.set_state(KanalFSM.vaqt)

# === Kanal vaqt === #
@dp.message(KanalFSM.vaqt)
async def kanal_vaqt(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    vaqt_input = msg.text.strip()
    if vaqt_input == "null":
        vaqt = None
    else:
        try:
            if vaqt_input.endswith("m"):
                vaqt = int(vaqt_input[:-1]) * 60  # minutlarni sekuntaga aylantirish
            elif vaqt_input.endswith("d"):
                vaqt = int(vaqt_input[:-1]) * 86400  # kunlarni sekuntaga aylantirish
            else:
                await msg.answer("❗ Noto'g'ri format. Iltimos, 'm' yoki 'd' bilan vaqtni belgilang.")
                return
        except:
            await msg.answer("❗ Noto'g'ri format. Iltimos, raqam va 'm' yoki 'd' bilan vaqtni belgilang.")
            return
    await state.update_data(vaqt=vaqt)
    await msg.answer("👥 Kanalga qancha odam tirkalishi kerak? (masalan: 10)")
    await state.set_state(KanalFSM.limit)

# === Kanal limit === #
@dp.message(KanalFSM.limit)
async def kanal_limit(msg: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        data.update({
            "limit": int(msg.text),
            "created_at": time.time(),
            "end_time": (datetime.now() + timedelta(seconds=data['vaqt'])) if data['vaqt'] else None,
            "members": []
        })
        kanal_id = data["kanal_id"]
        kanallar[kanal_id] = data
        save_kanallar(kanallar)
        
        await msg.answer(
            f"✅ Kanal qo'shildi!\n"
            f"URL: {data['url']}\n"
            f"ID: {data['kanal_id']}\n"
            f"Vaqt: {format_vaqt(data['vaqt'])}\n"
            f"Limit: {data['limit']} odam"
        )
    except ValueError:
        await msg.answer("⚠️ Iltimos, raqam kiriting!")
    finally:
        await state.clear()

# === Kanal list === #
@dp.callback_query(lambda c: c.data == "kanal_list")
async def kanal_list(call: types.CallbackQuery):
    if not kanallar:
        await call.message.answer("📭 Hech qanday kanal yo'q.")
    else:
        text = "📋 Majburiy obunadagi kanallar:\n"
        for i, (k_id, data) in enumerate(kanallar.items(), 1):
            text += f"{i}. {data['url']} (ID: {k_id}) - {data['limit']} odam, {format_vaqt(data['vaqt'])} vaqt\n"
        await call.message.answer(text)

# === Kanal delete === #
@dp.callback_query(lambda c: c.data == "kanal_delete")
async def kanal_delete(call: types.CallbackQuery):
    if not kanallar:
        await call.message.answer("📭 Hech qanday kanal yo'q.")
        return
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"❌ {data['url']} ni ochirish", callback_data=f"del_{k_id}")]
        for k_id, data in kanallar.items()
    ])
    markup.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="kanal_back")])
    await call.message.answer("❌ Qaysi kanalni ochirmoqchisiz?", reply_markup=markup)

# === Kanal back === #
@dp.callback_query(lambda c: c.data == "kanal_back")
async def kanal_back(call: types.CallbackQuery):
    await call.message.answer("🔙 Orqaga qaytdingiz.", reply_markup=kanal_menu())

# === Kod statistikasi === #
@dp.message_handler(lambda m: m.text == "📈 Kod statistikasi")
async def ask_stat_code(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("📥 Kod raqamini yuboring:")
    await AdminStates.waiting_for_stat_code.set()

# === Kod statistikasi === #
@dp.message_handler(state=AdminStates.waiting_for_stat_code)
async def show_code_stat(message: types.Message, state: FSMContext):
    await state.finish()
    code = message.text.strip()
    if not code:
        await message.answer("❗ Kod yuboring.")
        return
    stat = await get_code_stat(code)
    if not stat:
        await message.answer("❗ Bunday kod statistikasi topilmadi.")
        return

    await message.answer(
        f"📊 <b>{code} statistikasi:</b>\n"
        f"🔍 Qidirilgan: <b>{stat['searched']}</b>\n"
        f"👁 Ko‘rilgan: <b>{stat['viewed']}</b>",
        parse_mode="HTML"
  )
