# === 1-ші блок === #

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.utils import executor
import os
from dotenv import load_dotenv  # ✅ Осы импортты қойдым
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
load_dotenv()  # ✅ .env файлды жүктеді
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
@dp.callback_query_handler(lambda c: c.data == "kanal_add")
async def kanal_add(call: types.CallbackQuery, state: FSMContext):
    if str(call.from_user.id) == ADMIN_ID:
        await call.message.answer("📎 Kanal havolasini yuboring:")
        await state.set_state(KanalFSM.url)
    else:
        await call.answer("⚠️ Sizga ruxsat yo'q!", show_alert=True)

# === Kanal URL === #
@dp.message_handler(state=KanalFSM.url)
async def kanal_url(msg: types.Message, state: FSMContext):
    await state.update_data(url=msg.text)
    await msg.answer("🆔 Kanal ID yuboring:")
    await state.set_state(KanalFSM.kanal_id)

# === Kanal ID === #
@dp.message_handler(state=KanalFSM.kanal_id)
async def kanal_id(msg: types.Message, state: FSMContext):
    await state.update_data(kanal_id=msg.text)
    await msg.answer("⏳ Kanal qancha vaqt majburiy obunada turadi? (masalan: 1m, 1d, null)")
    await state.set_state(KanalFSM.vaqt)

# === Kanal vaqt === #
@dp.message_handler(state=KanalFSM.vaqt)
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
@dp.message_handler(state=KanalFSM.limit)
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

# === 3-ші блок === #

# === Admin paneli === #
@dp.message_handler(lambda m: m.text == "➕ Anime qo‘shish", user_id=ADMINS)
async def add_anime_start(message: types.Message):
    await AdminStates.waiting_for_kino_data.set()
    await message.answer("📝 Anime qo‘shish uchun format:\n`KOD @kanal REKLAMA_ID POST_SONI ANIME_NOMI`\nMasalan: `91 @MyKino 4 12 naruto`", parse_mode="Markdown")

@dp.message_handler(state=AdminStates.waiting_for_kino_data, user_id=ADMINS)
async def add_anime_handler(message: types.Message, state: FSMContext):
    rows = message.text.strip().split("\n")
    successful = 0
    failed = 0
    for row in rows:
        parts = row.strip().split()
        if len(parts) < 5:
            failed += 1
            continue

        code, server_channel, reklama_id, post_count = parts[:4]
        title = " ".join(parts[4:])

        if not (code.isdigit() and reklama_id.isdigit() and post_count.isdigit()):
            failed += 1
            continue

        reklama_id = int(reklama_id)
        post_count = int(post_count)

        await add_kino_code(code, server_channel, reklama_id + 1, post_count, title)

        download_btn = InlineKeyboardMarkup().add(
            InlineKeyboardButton("📥 Yuklab olish", url=f"https://t.me/{BOT_USERNAME}?start={code}")
        )

        try:
            for ch in MAIN_CHANNELS:
                await bot.copy_message(
                    chat_id=ch,
                    from_chat_id=server_channel,
                    message_id=reklama_id,
                    reply_markup=download_btn
                )
            successful += 1
        except:
            failed += 1

    await message.answer(f"✅ Yangi kodlar qo‘shildi:\n\n✅ Muvaffaqiyatli: {successful}\n❌ Xatolik: {failed}")
    await state.finish()

# === Kod statistikasi === #
@dp.message_handler(lambda m: m.text == "📈 Kod statistikasi", user_id=ADMINS)
async def show_stat_code(message: types.Message):
    await message.answer("📥 Kod raqamini yuboring:")
    await AdminStates.waiting_for_stat_code.set()

@dp.message_handler(state=AdminStates.waiting_for_stat_code, user_id=ADMINS)
async def process_stat_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if not code.isdigit():
        await message.answer("❗ Noto'g'ri format. Iltimos, raqam kiriting.")
        await state.finish()
        return

    stat = await get_code_stat(code)
    if not stat:
        await message.answer("❗ Bunday kod statistikasi topilmadi.")
        await state.finish()
        return

    await message.answer(
        f"📊 <b>{code} statistikasi:</b>\n"
        f"🔍 Qidirilgan: <b>{stat['searched']}</b>\n"
        f"👁 Ko‘rilgan: <b>{stat['viewed']}</b>",
        parse_mode="HTML"
    )
    await state.finish()

# === Kodni o'chirish === #
@dp.message_handler(lambda m: m.text == "❌ Kodni o‘chirish", user_id=ADMINS)
async def delete_code_start(message: types.Message):
    await AdminStates.waiting_for_delete_code.set()
    await message.answer("🗑 Qaysi kodni o‘chirmoqchisiz? Kod raqamini yuboring.")

@dp.message_handler(state=AdminStates.waiting_for_delete_code, user_id=ADMINS)
async def delete_code_handler(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if not code.isdigit():
        await message.answer("❗ Noto'g'ri format. Iltimos, raqam kiriting.")
        await state.finish()
        return

    deleted = await delete_kino_code(code)
    if deleted:
        await message.answer(f"✅ Kod {code} o‘chirildi.")
    else:
        await message.answer("❌ Kod topilmadi yoki o‘chirib bo‘lmadi.")
    await state.finish()

# === Kodni tahrirlash === #
@dp.message_handler(lambda m: m.text == "✏️ Kodni tahrirlash", user_id=ADMINS)
async def edit_code_start(message: types.Message):
    await AdminStates.waiting_for_edit_code.set()
    await message.answer("✏️ Qaysi kodni tahrirlashni xohlaysiz? Eski kod raqamini yuboring.")

@dp.message_handler(state=AdminStates.waiting_for_edit_code, user_id=ADMINS)
async def get_old_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if not code.isdigit():
        await message.answer("❗ Noto'g'ri format. Iltimos, raqam kiriting.")
        await state.finish()
        return

    post = await get_kino_by_code(code)
    if not post:
        await message.answer("❌ Bunday kod topilmadi. Qaytadan urinib ko‘ring.")
        await state.finish()
        return

    await state.update_data(old_code=code)
    await message.answer(f"🔎 Kod: {code}\n📌 Nomi: {post['title']}\n\nYangi kod va nomni yuboring (masalan: `92 naruto_uz`):")
    await AdminStates.waiting_for_new_code.set()

@dp.message_handler(state=AdminStates.waiting_for_new_code, user_id=ADMINS)
async def get_new_code(message: types.Message, state: FSMContext):
    data = await state.get_data()
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❗ Noto'g'ri format. Iltimos, yangi kod va nomni kiriting.")
        return

    new_code, new_title = parts[0], " ".join(parts[1:])
    if not new_code.isdigit():
        await message.answer("❗ Noto'g'ri format. Iltimos, yangi kod raqamini kiriting.")
        return

    await state.update_data(new_code=new_code, new_title=new_title)
    await message.answer(f"✅ Kod {data['old_code']} ni {new_code} ga va nomni {new_title} ga almashtirmoqchimisiz?")
    await AdminStates.waiting_for_confirm_edit.set()

@dp.message_handler(state=AdminStates.waiting_for_confirm_edit, user_id=ADMINS)
async def confirm_edit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if message.text.lower() in ("ha", "yes", "ok"):
        await update_anime_code(data['old_code'], data['new_code'], data['new_title'])
        await message.answer("✅ Kod va nom muvaffaqiyatli tahrirlandi.")
    else:
        await message.answer("❌ Tahrirlash bekor edildi.")
    await state.finish()

# === 4-ші блок === #

# === Admin мен пайдаланушы арасындағы хабар алмасу === #
@dp.callback_query_handler(lambda c: c.data.startswith("reply_user:"), user_id=ADMINS)
async def start_admin_reply(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split(":")[1])
    await state.update_data(reply_user_id=user_id)
    await AdminReplyStates.waiting_for_reply_message.set()
    await callback.message.answer("✍️ Endi foydalanuvchiga yubormoqchi bo‘lgan xabaringizni yozing.")
    await callback.answer()

@dp.message_handler(state=AdminReplyStates.waiting_for_reply_message, user_id=ADMINS)
async def send_admin_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("reply_user_id")

    try:
        await bot.send_message(user_id, f"✉️ Admindan javob:\n\n{message.text}")
        await message.answer("✅ Javob foydalanuvchiga yuborildi.")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
    finally:
        await state.finish()

# === Foydalanuvchi bilan chatlashish === #
@dp.message_handler(lambda m: m.text == "✉️ Admin bilan bog‘lanish")
async def contact_admin(message: types.Message):
    await UserStates.waiting_for_admin_message.set()
    await message.answer("✍️ Adminlarga yubormoqchi bo‘lgan xabaringizni yozing.\n\n❌ Bekor qilish uchun '❌ Bekor qilish' tugmasini bosing.")

@dp.message_handler(state=UserStates.waiting_for_admin_message)
async def forward_to_admins(message: types.Message, state: FSMContext):
    await state.finish()
    user = message.from_user

    for admin_id in ADMINS:
        try:
            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("✉️ Javob yozish", callback_data=f"reply_user:{user.id}")
            )

            await bot.send_message(
                admin_id,
                f"📩 <b>Yangi xabar:</b>\n\n"
                f"<b>👤 Foydalanuvchi:</b> {user.full_name} | <code>{user.id}</code>\n"
                f"<b>💬 Xabar:</b> {message.text}",
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Adminga yuborishda xatolik: {e}")

    await message.answer("✅ Xabaringiz yuborildi. Tez orada admin siz bilan bog‘lanadi.")

# === 5-ші блок === #

# === Admin paneli === #
@dp.message_handler(lambda m: m.text == "📢 Habar yuborish", user_id=ADMINS)
async def broadcast_message(message: types.Message):
    await AdminStates.waiting_for_broadcast_data.set()
    await message.answer("📨 Habar yuborish uchun format:\n`@kanal xabar_id`", parse_mode="Markdown")

@dp.message_handler(state=AdminStates.waiting_for_broadcast_data, user_id=ADMINS)
async def process_broadcast(message: types.Message, state: FSMContext):
    await state.finish()
    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("❗ Format noto‘g‘ri. Masalan: `@kanalim 123`")
        return

    channel_username, msg_id = parts
    if not msg_id.isdigit():
        await message.answer("❗ Xabar ID raqam bo‘lishi kerak.")
        return

    msg_id = int(msg_id)
    users = await get_all_user_ids()  # Foydalanuvchilar ro‘yxati

    success = 0
    fail = 0

    for user_id in users:
        try:
            await bot.forward_message(
                chat_id=user_id,
                from_chat_id=channel_username,
                message_id=msg_id
            )
            success += 1
        except Exception as e:
            print(f"Xatolik {user_id} uchun: {e}")
            fail += 1

    await message.answer(f"✅ Yuborildi: {success} ta\n❌ Xatolik: {fail} ta")

# === Qo‘llanma === #
@dp.message_handler(lambda m: m.text == "📘 Qo‘llanma")
async def show_help(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📥 1. Anime qo‘shish", callback_data="help_add"),
        InlineKeyboardButton("📡 2. Kanal yaratish", callback_data="help_channel"),
        InlineKeyboardButton("🆔 3. Reklama ID olish", callback_data="help_id"),
        InlineKeyboardButton("🔁 4. Kod ishlashi", callback_data="help_code"),
        InlineKeyboardButton("❓ 5. Savol-javob", callback_data="help_faq")
    )
    await message.answer("📘 Qanday yordam kerak?", reply_markup=kb)

# === Qo‘llanma sahifalari === #
@dp.callback_query_handler(lambda c: c.data.startswith("help_"))  # ✅ Жақшаны жауып, декораторды дұрыс аяқтадым
async def show_help_page(callback: types.CallbackQuery):
    key = callback.data
    text = HELP_TEXTS.get(key, "❌ Ma'lumot topilmadi.")
    
    # Ortga tugmasi
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("⬅️ Ortga", callback_data="back_help")
    )
    
    try:
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        # Agar matn o'zgartirilmayotgan bo'lsa (masalan, rasmli xabar bo'lsa)
        await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)
        await callback.message.delete()  # Eski xabarni o'chirish
    finally:
        await callback.answer()

# === Ortga tugma === #
@dp.callback_query_handler(lambda c: c.data == "back_help")
async def back_to_qollanma(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📥 1. Anime qo‘shish", callback_data="help_add"),
        InlineKeyboardButton("📡 2. Kanal yaratish", callback_data="help_channel"),
        InlineKeyboardButton("🆔 3. Reklama ID olish", callback_data="help_id"),
        InlineKeyboardButton("🔁 4. Kod ishlashi", callback_data="help_code"),
        InlineKeyboardButton("❓ 5. Savol-javob", callback_data="help_faq")
    )
    
    try:
        await callback.message.edit_text("📘 Qanday yordam kerak?", reply_markup=kb)
    except Exception as e:
        await callback.message.answer("📘 Qanday yordam kerak?", reply_markup=kb)
        await callback.message.delete()
    finally:
        await callback.answer()

    # === 6-шы блок === #

# === Сұрақ-жауап жүйесі === #
class FAQStates(StatesGroup):
    waiting_for_question = State()
    waiting_for_answer = State()

# === FAQ жүйесін басқару === #
@dp.message_handler(lambda m: m.text == "❓ FAQ жүйесін басқару", user_id=ADMINS)
async def manage_faq_start(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ FAQ сұрағын қосу", callback_data="add_faq"),
        InlineKeyboardButton("📋 FAQ тізімін көру", callback_data="list_faq"),
        InlineKeyboardButton("❌ FAQ сұрағын өшіру", callback_data="delete_faq"),
        InlineKeyboardButton("⬅️ Ортаға", callback_data="back_faq")
    )
    await message.answer("📢 FAQ жүйесін басқару:", reply_markup=kb)

# === FAQ сұрағын қосу === #
@dp.callback_query_handler(lambda c: c.data == "add_faq", user_id=ADMINS)
async def add_faq_start(callback: types.CallbackQuery):
    await FAQStates.waiting_for_question.set()
    await callback.message.answer("📝 FAQ сұрағын қосу үшін сұрақты жазыңыз:")
    await callback.answer()

@dp.message_handler(state=FAQStates.waiting_for_question, user_id=ADMINS)
async def add_faq_question(message: types.Message, state: FSMContext):
    await state.update_data(question=message.text.strip())
    await FAQStates.waiting_for_answer.set()
    await message.answer("📝 FAQ жауабын жазыңыз:")
    
@dp.message_handler(state=FAQStates.waiting_for_answer, user_id=ADMINS)
async def add_faq_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    question = data.get("question")
    answer = message.text.strip()
    await add_faq(question, answer)  # add_faq функциясын қосу керек
    await message.answer(f"✅ Сұрақ: {question}\n✅ Жауап: {answer}\nҚосылды.")
    await state.finish()

# === FAQ тізімін көру === #
@dp.callback_query_handler(lambda c: c.data == "list_faq", user_id=ADMINS)
async def list_faq(callback: types.CallbackQuery):
    faqs = await get_all_faqs()  # get_all_faqs функциясын қосу керек
    if not faqs:
        await callback.message.answer("📭 FAQ сұрақтары жоқ.")
        return
    text = "📋 FAQ тізімі:\n"
    for faq in faqs:
        text += f"❓ {faq['question']}\n✅ {faq['answer']}\n\n"
    await callback.message.answer(text)

# === FAQ сұрағын өшіру === #
@dp.callback_query_handler(lambda c: c.data == "delete_faq", user_id=ADMINS)
async def delete_faq_start(callback: types.CallbackQuery):
    faqs = await get_all_faqs()
    if not faqs:
        await callback.message.answer("📭 FAQ сұрақтары жоқ.")
        return
    kb = InlineKeyboardMarkup(row_width=1)
    for faq in faqs:
        kb.add(InlineKeyboardButton(f"❌ {faq['question']}", callback_data=f"del_faq_{faq['id']}"))
    kb.add(InlineKeyboardButton("⬅️ Ортаға", callback_data="back_faq"))
    await callback.message.answer("❌ Қай сұрақты өшіру керек?", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("del_faq_", user_id=ADMINS)
async def delete_faq_confirm(callback: types.CallbackQuery):
    faq_id = c.data.split("_")[2]
    await delete_faq(faq_id)  # delete_faq функциясын қосу керек
    await callback.message.answer("✅ Сұрақ өшірілді.")
    await callback.answer()

# === FAQ жүйесіне сұрақ қою === #
@dp.message_handler()
async def handle_faq(message: types.Message):
    faq = await get_faq_by_question(message.text)
    if faq:
        await message.answer(f"✅ {faq['answer']}")
    else:
        await message.answer("❌ Бұл сұраққа жауап жоқ. Админмен байланысыңыз.")
