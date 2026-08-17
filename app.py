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
    <title>NCS Koruma</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, system-ui, sans-serif;
            text-align: center;
            padding: 40px 24px;
            margin: 0;
            background: radial-gradient(circle at 50% 20%, #1a0a2e 0%, #0a0612 60%, #05030a 100%);
            color: #fff;
            min-height: 100vh;
        }
        .logo { width: 140px; height: 140px; border-radius: 50%; margin-bottom: 18px; box-shadow: 0 0 40px rgba(180, 90, 255, 0.45); }
        .badge {
            display: inline-block;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 0.12em;
            color: #d9b8ff;
            background: rgba(157, 78, 221, 0.18);
            border: 1px solid rgba(157, 78, 221, 0.45);
            padding: 8px 18px;
            border-radius: 999px;
            margin-bottom: 22px;
        }
        h2 { font-size: 22px; font-weight: 800; margin: 0 0 12px; background: linear-gradient(135deg, #7fd8ff, #b98bff, #ff8bd6); -webkit-background-clip: text; background-clip: text; color: transparent; }
        p { font-size: 14px; color: #b8b0c8; line-height: 1.6; max-width: 340px; margin: 0 auto 28px; }
        button {
            padding: 15px 32px;
            font-size: 15px;
            font-weight: 700;
            background: linear-gradient(135deg, #7c3aed, #9d4edd);
            color: #fff;
            border: none;
            border-radius: 14px;
            cursor: pointer;
            box-shadow: 0 8px 24px rgba(124, 58, 237, 0.4);
        }
    </style>
</head>
<body>
    <img class="logo" src="data:image/jpeg;base64,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" alt="NCS">
    <div class="badge">NCS KORUMA AKTIF</div>
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
    app.run(host='0.0.0.0', port=5001)
