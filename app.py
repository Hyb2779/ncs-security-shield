import hashlib
import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify, render_template_string
import db
import tg_actions
from panel import panel_bp

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'lutfen-bunu-degistir-guclu-bir-key')

db.init_db()
app.register_blueprint(panel_bp)

def generate_fingerprint(ip, user_agent):
    raw_data = f"{ip}:{user_agent}"
    return hashlib.sha256(raw_data.encode('utf-8')).hexdigest()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Dogrulama</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { font-family: sans-serif; text-align: center; padding: 50px; background: #18222d; color: white; }
        button { padding: 15px 25px; font-size: 18px; background: #2481cc; color: white; border: none; border-radius: 8px; cursor: pointer; }
    </style>
</head>
<body>
    <h2>Gruba Katilim Dogrulamasi</h2>
    <p>Gruba erisim saglamak icin lutfen asagidaki dogrulama butonuna tiklayin.</p>
    <button onclick="verify()">Dogrula ve Katil</button>
    <script>
        function verify() {
            const tg = window.Telegram.WebApp;
            const user = tg.initDataUnsafe.user;
            fetch('api/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: user ? user.id : null })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'banned') {
                    alert('Erisim engellendi: Bu cihaz/ag uzerinden daha once gruptan cikarildiniz.');
                } else {
                    alert('Dogrulama basarili! Gruba yazabilirsiniz.');
                }
                tg.close();
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/verify', methods=['POST'])
def verify_user():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', '')
    user_hash = generate_fingerprint(client_ip, user_agent)

    data = request.json or {}
    telegram_id = data.get('user_id')

    chat_id = db.get_pending_chat(telegram_id) if telegram_id else None

    def _cleanup_welcome_message():
        if telegram_id:
            wm_chat_id, wm_message_id = db.get_and_clear_welcome_message(telegram_id)
            if wm_chat_id and wm_message_id:
                tg_actions.delete_message(wm_chat_id, wm_message_id)

    if db.is_banned(user_hash):
        db.log_event(telegram_id, client_ip, user_agent, user_hash, 'banned')
        if telegram_id:
            tg_actions.kick_user(int(telegram_id), chat_id=chat_id)
        _cleanup_welcome_message()
        return jsonify({'status': 'banned', 'hash': user_hash, 'telegram_id': telegram_id})

    db.log_event(telegram_id, client_ip, user_agent, user_hash, 'success')
    if telegram_id:
        tg_actions.unrestrict_user(int(telegram_id), chat_id=chat_id)
    _cleanup_welcome_message()
    return jsonify({'status': 'success', 'hash': user_hash, 'telegram_id': telegram_id})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
