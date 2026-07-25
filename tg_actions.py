import os
import requests
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '8825440586:AAESDwIvheKmWYlq5lWTBSH-04ZedF9_gRU')
DEFAULT_GROUP_CHAT_ID = os.environ.get('TG_GROUP_CHAT_ID', '')

API_BASE = f'https://api.telegram.org/bot{BOT_TOKEN}'

def unrestrict_user(user_id, chat_id=None):
    cid = chat_id or DEFAULT_GROUP_CHAT_ID
    if not cid:
        return False, 'chat_id belirtilmedi ve TG_GROUP_CHAT_ID tanimli degil'
    try:
        r = requests.post(f'{API_BASE}/restrictChatMember', json={
            'chat_id': cid, 'user_id': user_id,
            'permissions': {'can_send_messages': True}
        }, timeout=10)
        d = r.json()
        return d.get('ok', False), d
    except Exception as e:
        return False, str(e)

def kick_user(user_id, chat_id=None):
    cid = chat_id or DEFAULT_GROUP_CHAT_ID
    if not cid:
        return False, 'chat_id belirtilmedi ve TG_GROUP_CHAT_ID tanimli degil'
    try:
        r = requests.post(f'{API_BASE}/banChatMember', json={
            'chat_id': cid, 'user_id': user_id
        }, timeout=10)
        d = r.json()
        return d.get('ok', False), d
    except Exception as e:
        return False, str(e)

def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    payload = {'chat_id': chat_id, 'text': text}
    if reply_markup:
        payload['reply_markup'] = reply_markup
    if parse_mode:
        payload['parse_mode'] = parse_mode
    try:
        r = requests.post(f'{API_BASE}/sendMessage', json=payload, timeout=10)
        d = r.json()
        return d.get('ok', False), d
    except Exception as e:
        return False, str(e)

def delete_message(chat_id, message_id):
    try:
        r = requests.post(f'{API_BASE}/deleteMessage', json={
            'chat_id': chat_id, 'message_id': message_id
        }, timeout=10)
        d = r.json()
        return d.get('ok', False), d
    except Exception as e:
        return False, str(e)
