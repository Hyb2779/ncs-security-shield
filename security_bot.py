import os
from dotenv import load_dotenv
load_dotenv()
import db
import moderation
import tg_actions
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, ChatMemberHandler, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
BOT_USERNAME = "AntoniusGuard_bot"
WEBAPP_URL = "https://www.nunuexpress.com/tg-verify-antonius/"

async def on_member_status_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    old_is_member = getattr(result.old_chat_member, 'is_member', False)
    new_is_member = getattr(result.new_chat_member, 'is_member', False)
    # ChatMemberBanned/Left gibi tiplerde is_member alani hic olmayabilir,
    # bu durumlarda status'e gore manuel karar veriyoruz.
    if new_status in ('kicked', 'banned', 'left'):
        new_is_member = False
    elif new_status in ('member', 'administrator', 'creator') and not hasattr(result.new_chat_member, 'is_member'):
        new_is_member = True
    user = result.new_chat_member.user
    chat_id = update.effective_chat.id

    # Yeni katilan uye (is_member False->True gecisi ile yakalanir, status string'i
    # guvenilir degil cunku mute'lu kullanici RESTRICTED durumunda kalabilir)
    if (not old_is_member) and new_is_member and new_status != "creator":
        await context.bot.restrict_chat_member(
            chat_id=chat_id, user_id=user.id,
            permissions=ChatPermissions(can_send_messages=False)
        )
        verify_link = f"https://t.me/{BOT_USERNAME}?start=verify_{chat_id}"
        keyboard = [[InlineKeyboardButton("Dogrulamayi Baslat (Botla ozel sohbet)", url=verify_link)]]
        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=f"Hos geldin [{user.first_name}](tg://user?id={user.id})!\n\nSpam korumasi sebebiyle mesaj izniniz kisitlandi. Dogrulamayi tamamlamak icin asagidaki butona tiklayip botla ozel sohbeti baslatin.",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        db.save_welcome_message(user.id, chat_id, sent.message_id)

    # Kullanici gruptan banlandi/atildi: hash'ini kalici banli listesine ekle
    if new_status in ["kicked", "banned"] and old_status not in ["kicked", "banned"]:
        user_hash = db.latest_hash_for_telegram_id(user.id)
        if user_hash:
            db.ban_hash(user_hash, reason=f'grup bani: telegram_id={user.id}')
            print(f"[BAN KAYDI] {user.id} banlandi, hash kaydedildi: {user_hash[:16]}...")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    if args and args[0].startswith("verify_"):
        chat_id = args[0].replace("verify_", "", 1)
        db.save_pending_chat(user.id, chat_id)
        keyboard = [[InlineKeyboardButton("Dogrula ve Katil", web_app=WebAppInfo(url=WEBAPP_URL))]]
        await update.message.reply_text(
            "Gruba erisim icin lutfen asagidaki butona tiklayarak cihaz dogrulamasini tamamlayin.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text("Merhaba! Bu bot grup guvenlik dogrulamasi icin kullanilir.")

async def on_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        return
    user = update.effective_user
    if not user or user.is_bot:
        return

    banned_word = moderation.find_banned_word(message.text)
    if not banned_word:
        return

    # Mesaji sil
    try:
        await context.bot.delete_message(chat_id=chat.id, message_id=message.message_id)
    except Exception as e:
        print(f"[MODERASYON] Mesaj silinemedi: {e}")

    db.add_violation(user.id, chat.id, banned_word, message.text)
    violation_count = db.get_violation_count(user.id, chat.id)

    if violation_count >= 2:
        # Ikinci ihlal: banla
        await context.bot.ban_chat_member(chat_id=chat.id, user_id=user.id)
        user_hash = db.latest_hash_for_telegram_id(user.id)
        if user_hash:
            db.ban_hash(user_hash, reason=f'kufur/spam filtresi 2. ihlal: telegram_id={user.id}')
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"[{user.first_name}](tg://user?id={user.id}) uygunsuz icerik nedeniyle gruptan banlandi.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        print(f"[MODERASYON] {user.id} 2. ihlal sonrasi banlandi. Kelime: {banned_word}")
    else:
        # Ilk ihlal: uyar
        try:
            warn_msg = await context.bot.send_message(
                chat_id=chat.id,
                text=f"[{user.first_name}](tg://user?id={user.id}) uygunsuz dil kullandiniz, mesajiniz silindi. Tekrari halinde banlanacaksiniz.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        print(f"[MODERASYON] {user.id} 1. ihlal, uyarildi. Kelime: {banned_word}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(ChatMemberHandler(on_member_status_change, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, on_group_message))
    print("Guvenlik botu dinlemede...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
