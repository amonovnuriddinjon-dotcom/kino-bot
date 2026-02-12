import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
BACKUP_KANAL = os.getenv("BACKUP_KANAL", "")

MOVIES_FILE = "kinolar.json"
USERS_FILE = "foydalanuvchilar.json"

VIDEO, KINO_NOMI, KINO_KODI, KINO_KATEGORIYA, KINO_TAVSIF = range(5)
DELETE_KOD, DELETE_KATEGORIYA, DELETE_QISM = range(5, 8)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class KinoBot:
    def __init__(self):
        self.kinolar = self.load_kinolar()
        self.users = self.load_users()

    def load_kinolar(self):
        if os.path.exists(MOVIES_FILE):
            try:
                with open(MOVIES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data and data.get("items"):
                        logger.info(f"✅ {len(data['items'])} ta kino yuklandi")
                        return data
            except Exception as e:
                logger.error("Kinolar yuklashda xato: %s", e)
        return {"items": {}, "kategoriyalar": {"kino": {}, "serial": {}, "multfilm": {}}}

    def save_kinolar(self):
        try:
            with open(MOVIES_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.kinolar, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error("Kinolar saqlashda xato: %s", e)
            return False

    def load_users(self):
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, 'r', encoding='utf-8') as f:                    return json.load(f)
            except:
                pass
        return {"idlar": [], "soni": 0}

    def save_users(self):
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            return True
        except:
            return False

    def add_user(self, user_id):
        s = str(user_id)
        if s not in self.users["idlar"]:
            self.users["idlar"].append(s)
            self.users["soni"] = len(self.users["idlar"])
            self.save_users()
            return True
        return False

    def add_movie(self, video_id, nomi, public_kod, kategoriya, tavsif, file_type="video", message_id=None):
        item = {
            "nomi": nomi,
            "kodi": int(public_kod),
            "kategoriya": kategoriya,
            "tavsif": tavsif,
            "video_id": video_id,
            "file_type": file_type,
            "message_id": message_id,
            "vaqt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.kinolar["items"][str(message_id)] = item
        cat_map = self.kinolar["kategoriyalar"].setdefault(kategoriya, {})
        cat_map.setdefault(str(public_kod), []).append(str(message_id))
        self.save_kinolar()
        return message_id

    def find_by_public_code(self, public_kod, kategoriya=None):
        result = []
        public_kod = str(public_kod)
        if kategoriya:
            cat = self.kinolar["kategoriyalar"].get(kategoriya, {})
            msg_ids = cat.get(public_kod, [])
            for msg_id in msg_ids:
                item = self.kinolar["items"].get(msg_id)
                if item:
                    result.append(item)
        else:            for cat_name, cat in self.kinolar["kategoriyalar"].items():
                msg_ids = cat.get(public_kod, [])
                for msg_id in msg_ids:
                    item = self.kinolar["items"].get(msg_id)
                    if item:
                        result.append(item)
        return result

    def find_by_name(self, name, kategoriya=None):
        name_lower = name.lower()
        result = []
        for msg_id, item in self.kinolar["items"].items():
            if kategoriya and item["kategoriya"] != kategoriya:
                continue
            if name_lower in item["nomi"].lower():
                result.append(item)
        return result

    def delete_item(self, message_id):
        msg_id_str = str(message_id)
        if msg_id_str not in self.kinolar["items"]:
            return None
        item = self.kinolar["items"].pop(msg_id_str)
        kategoriya = item.get("kategoriya")
        public_kod = str(item.get("kodi"))
        cat = self.kinolar["kategoriyalar"].get(kategoriya, {})
        if public_kod in cat:
            id_list = cat[public_kod]
            if msg_id_str in id_list:
                id_list.remove(msg_id_str)
            if not id_list:
                del cat[public_kod]
        self.save_kinolar()
        return item

    def get_item_by_msgid(self, message_id):
        return self.kinolar["items"].get(str(message_id))

bot = KinoBot()

def main_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 KINO", callback_data='kategoriya_kino')],
        [InlineKeyboardButton("📺 SERIAL", callback_data='kategoriya_serial')],
        [InlineKeyboardButton("🐰 MULTFILM", callback_data='kategoriya_multfilm')],
    ])

def home_button_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 ASOSIY MENYU", callback_data='home_menu')]])
# FOYDALANUVCHI UCHUN
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot.add_user(user.id)
    await update.message.reply_text(f"👋 Assalomu alaykum, <b>{user.full_name}</b>!\n\nKategoriyani tanlang:", reply_markup=main_menu_markup(), parse_mode="HTML")

async def kategoriya_tanlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kategoriya = query.data.split('_')[1]
    context.user_data['kategoriya'] = kategoriya
    await query.edit_message_text(text=f"📂 Kategoriya: <b>{kategoriya.upper()}</b>\n\n🔍 Kodni kiriting yoki nomi bo'yicha qidiring:", parse_mode="HTML")

async def kino_qidirish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    kategoriya = context.user_data.get('kategoriya')
    if not kategoriya:
        await update.message.reply_text("❌ Iltimos, avval kategoriya tanlang.", reply_markup=main_menu_markup())
        return
    try:
        kod = int(text)
        parts = bot.find_by_public_code(kod, kategoriya=kategoriya)
    except ValueError:
        parts = bot.find_by_name(text, kategoriya=kategoriya)
    if not parts:
        await update.message.reply_text("❌ Topilmadi.", reply_markup=home_button_markup())
        return
    if len(parts) == 1:
        item = parts[0]
        caption = f"🎬 <b>{item['nomi']}</b>\n🔢 Kodi: {item['kodi']}\n📂 Kategoriya: {item['kategoriya']}\n📝 {item['tavsif']}"
        if item['file_type'] == 'video':
            await context.bot.send_video(update.effective_chat.id, item['video_id'], caption=caption, parse_mode="HTML", reply_markup=home_button_markup())
        else:
            await context.bot.send_document(update.effective_chat.id, item['video_id'], caption=caption, parse_mode="HTML", reply_markup=home_button_markup())
    else:
        buttons = []
        for item in parts:
            buttons.append([InlineKeyboardButton(f"{item['nomi']} (Kod {item['kodi']})", callback_data=f"play_{item['message_id']}")])
        buttons.append([InlineKeyboardButton("🏠 ASOSIY MENYU", callback_data='home_menu')])
        await update.message.reply_text("📋 Natijalar:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

async def play_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    message_id = query.data.split('_')[1]
    item = bot.get_item_by_msgid(message_id)
    if not item:
        await query.edit_message_text("❌ Kino topilmadi.")
        return
    caption = f"🎬 <b>{item['nomi']}</b>\n\n📝 {item['tavsif']}"    if item['file_type'] == 'video':
        await context.bot.send_video(query.message.chat_id, item['video_id'], caption=caption, parse_mode="HTML", reply_markup=home_button_markup())
    else:
        await context.bot.send_document(query.message.chat_id, item['video_id'], caption=caption, parse_mode="HTML", reply_markup=home_button_markup())

async def home_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("🏠 Asosiy menyu:", reply_markup=main_menu_markup())

# ADMIN
async def admin_addmovie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text("📹 Video yuboring:")
    return VIDEO

async def video_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        video_id = update.message.video.file_id
        ftype = "video"
    elif update.message.document:
        video_id = update.message.document.file_id
        ftype = "document"
    else:
        await update.message.reply_text("❌ Faqat video yoki fayl yuboring.")
        return VIDEO
    context.user_data['video_id'] = video_id
    context.user_data['file_type'] = ftype
    await update.message.reply_text("📝 Nomi:")
    return KINO_NOMI

async def movie_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nomi'] = update.message.text
    await update.message.reply_text("🔢 Kod (raqam):")
    return KINO_KODI

async def movie_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        kod = int(update.message.text)
        context.user_data['public_kod'] = kod
    except:
        await update.message.reply_text("❌ Raqam kiriting:")
        return KINO_KODI
    buttons = [
        [InlineKeyboardButton("🎬 KINO", callback_data='cat_kino')],
        [InlineKeyboardButton("📺 SERIAL", callback_data='cat_serial')],
        [InlineKeyboardButton("🐰 MULTFILM", callback_data='cat_multfilm')],
    ]    await update.message.reply_text("📂 Kategoriya:", reply_markup=InlineKeyboardMarkup(buttons))
    return KINO_KATEGORIYA

async def movie_category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kategoriya = query.data.split('_')[1]
    context.user_data['kategoriya'] = kategoriya
    await query.edit_message_text("📝 Tavsif:")
    return KINO_TAVSIF

async def movie_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tavsif = update.message.text
    video_id = context.user_data['video_id']
    ftype = context.user_data['file_type']
    nomi = context.user_data['nomi']
    public_kod = context.user_data['public_kod']
    kategoriya = context.user_data['kategoriya']
    caption = f"{nomi}|{public_kod}|{kategoriya}|{tavsif}"
    try:
        if ftype == "video":
            msg = await context.bot.send_video(chat_id=f"@{BACKUP_KANAL}", video=video_id, caption=caption)
        else:
            msg = await context.bot.send_document(chat_id=f"@{BACKUP_KANAL}", document=video_id, caption=caption)
        message_id = msg.message_id
    except Exception as e:
        await update.message.reply_text(f"❌ Kanalga yuborishda xato: {e}")
        return ConversationHandler.END
    bot.add_movie(video_id, nomi, public_kod, kategoriya, tavsif, ftype, message_id)
    await update.message.reply_text(f"✅ Qo'shildi! Kod: {public_kod}")
    return ConversationHandler.END

async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("/delete message_id")
        return
    try:
        msg_id = int(context.args[0])
        item = bot.delete_item(msg_id)
        if item:
            await context.bot.delete_message(chat_id=f"@{BACKUP_KANAL}", message_id=msg_id)
            await update.message.reply_text(f"✅ O'chirildi: {item['nomi']}")
        else:
            await update.message.reply_text("❌ Topilmadi.")
    except Exception as e:
        await update.message.reply_text(f"Xato: {e}")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):    total_items = len(bot.kinolar['items'])
    total_users = bot.users.get('soni', 0)
    txt = f"📊 Kinolar: {total_items}\n👥 Foydalanuvchilar: {total_users}"
    await update.message.reply_text(txt)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv_add = ConversationHandler(
        entry_points=[CommandHandler('addmovie', admin_addmovie)],
        states={
            VIDEO: [MessageHandler(filters.VIDEO | filters.Document.ALL, video_received)],
            KINO_NOMI: [MessageHandler(filters.TEXT & ~filters.COMMAND, movie_name)],
            KINO_KODI: [MessageHandler(filters.TEXT & ~filters.COMMAND, movie_code)],
            KINO_KATEGORIYA: [CallbackQueryHandler(movie_category_chosen, pattern='^cat_')],
            KINO_TAVSIF: [MessageHandler(filters.TEXT & ~filters.COMMAND, movie_description)],
        },
        fallbacks=[]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(kategoriya_tanlash, pattern='^kategoriya_'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, kino_qidirish))
    app.add_handler(CallbackQueryHandler(play_item, pattern='^play_'))
    app.add_handler(CallbackQueryHandler(home_menu, pattern='^home_menu$'))
    app.add_handler(conv_add)
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.run_polling()

if __name__ == '__main__':
    main()
