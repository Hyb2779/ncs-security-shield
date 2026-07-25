import functools
import datetime
from flask import Blueprint, request, session, redirect, url_for, render_template_string
from werkzeug.security import check_password_hash
import db
import tg_actions

panel_bp = Blueprint('panel', __name__, url_prefix='/panel')

def login_required(f):
    @functools.wraps(f)
    def wrapper(*a, **kw):
        if not session.get('logged_in'):
            return redirect(url_for('panel.login'))
        return f(*a, **kw)
    return wrapper

STYLE = """
<style>
* { box-sizing: border-box; }
body { font-family: -apple-system, Segoe UI, sans-serif; background:#0f1620; color:#e6edf3; margin:0; }
.topbar { background:#18222d; padding:16px 24px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #263140; }
.topbar h1 { font-size:18px; margin:0; color:#2481cc; }
.topbar a { color:#8b98a5; text-decoration:none; margin-left:16px; font-size:14px; }
.container { padding:24px; max-width:1200px; margin:0 auto; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:24px; }
.card { background:#18222d; border:1px solid #263140; border-radius:10px; padding:18px; }
.card .label { color:#8b98a5; font-size:13px; margin-bottom:6px; }
.card .value { font-size:28px; font-weight:700; }
.card .value.danger { color:#e5484d; }
.card .value.ok { color:#3fb950; }
.panel-box { background:#18222d; border:1px solid #263140; border-radius:10px; padding:18px; margin-bottom:24px; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th, td { text-align:left; padding:8px 10px; border-bottom:1px solid #263140; }
th { color:#8b98a5; font-weight:600; }
.badge { padding:2px 8px; border-radius:6px; font-size:12px; }
.badge.banned { background:#3d1a1c; color:#e5484d; }
.badge.success { background:#132d1c; color:#3fb950; }
input, select, button { background:#0f1620; border:1px solid #263140; color:#e6edf3; padding:8px 10px; border-radius:6px; font-size:14px; }
button { background:#2481cc; border:none; cursor:pointer; }
button.danger { background:#e5484d; }
.row { display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap; }
.login-box { max-width:340px; margin:80px auto; background:#18222d; padding:30px; border-radius:12px; border:1px solid #263140; }
.login-box input { width:100%; margin-bottom:12px; }
.login-box button { width:100%; padding:10px; }
</style>
"""

NAV = """
<div class="topbar">
  <h1>NCS <span style="color:#8b98a5;font-weight:400;">| Security Shield</span></h1>
  <div>
    <a href="/panel">Dashboard</a>
    <a href="/panel/logs">Loglar</a>
    <a href="/panel/banned">Ban Listesi</a>
    <a href="/panel/logout">Cikis</a>
  </div>
</div>
"""

LOGIN_HTML = STYLE + """
<div class="login-box">
  <div style="text-align:center;margin-bottom:6px;"><span style="font-size:22px;font-weight:800;color:#2481cc;">NCS</span></div><h2 style="text-align:center;color:#8b98a5;font-size:15px;font-weight:500;margin-top:0;">Security Shield &mdash; Ban Koruma Sistemi</h2>
  {% if error %}<p style="color:#e5484d;text-align:center;">{{ error }}</p>{% endif %}
  <form method="post">
    <input type="text" name="username" placeholder="Kullanici adi" required>
    <input type="password" name="password" placeholder="Sifre" required>
    <button type="submit">Giris Yap</button>
  </form>
</div>
"""

DASHBOARD_HTML = STYLE + NAV + """
<div class="container">
  <div class="cards">
    <div class="card"><div class="label">Toplam Dogrulama</div><div class="value">{{ stats.total_events }}</div></div>
    <div class="card"><div class="label">Engellenen (Ban)</div><div class="value danger">{{ stats.blocked_attempts }}</div></div>
    <div class="card"><div class="label">Basarili Giris</div><div class="value ok">{{ stats.success }}</div></div>
    <div class="card"><div class="label">Toplam Banli Cihaz</div><div class="value">{{ stats.total_banned }}</div></div>
    <div class="card"><div class="label">Son 24 Saat</div><div class="value">{{ stats.last24_events }}</div></div>
    <div class="card"><div class="label">Son 24s Engellenen</div><div class="value danger">{{ stats.last24_blocked }}</div></div>
  </div>
  <div class="panel-box">
    <h3 style="margin-top:0;">Son 24 Saat Aktivite</h3>
    <canvas id="chart" height="80"></canvas>
  </div>
  <div class="panel-box">
    <h3 style="margin-top:0;">Son Olaylar</h3>
    <table>
      <tr><th>Zaman</th><th>Telegram ID</th><th>IP</th><th>Sonuc</th></tr>
      {% for e in recent %}
      <tr><td>{{ e.time_str }}</td><td>{{ e.telegram_id or '-' }}</td><td>{{ e.ip }}</td>
      <td><span class="badge {{ 'banned' if e.result=='banned' else 'success' }}">{{ e.result }}</span></td></tr>
      {% endfor %}
    </table>
  </div>
</div>
<div style="text-align:center;padding:20px;color:#4a5568;font-size:12px;">NCS Security Shield &copy; 2026 &mdash; Nitro Core Systems</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
new Chart(document.getElementById('chart'), {
  type: 'line',
  data: { labels: {{ labels|safe }}, datasets: [
    { label: 'Basarili', data: {{ success_data|safe }}, borderColor: '#3fb950', tension: 0.3 },
    { label: 'Engellenen', data: {{ banned_data|safe }}, borderColor: '#e5484d', tension: 0.3 }
  ]},
  options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }, plugins: { legend: { labels: { color: '#e6edf3' } } } }
});
</script>
"""

LOGS_HTML = STYLE + NAV + """
<div class="container">
  <div class="panel-box">
    <form class="row" method="get">
      <input type="text" name="q" placeholder="ID / IP / hash ara..." value="{{ q or '' }}">
      <select name="result">
        <option value="">Tumu</option>
        <option value="banned" {{ 'selected' if result_filter=='banned' else '' }}>Banned</option>
        <option value="success" {{ 'selected' if result_filter=='success' else '' }}>Success</option>
      </select>
      <button type="submit">Filtrele</button>
    </form>
    <table>
      <tr><th>Zaman</th><th>Telegram ID</th><th>IP</th><th>User-Agent</th><th>Hash</th><th>Sonuc</th></tr>
      {% for e in events %}
      <tr><td>{{ e.time_str }}</td><td>{{ e.telegram_id or '-' }}</td><td>{{ e.ip }}</td>
      <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{{ e.user_agent }}</td>
      <td style="font-size:11px;">{{ e.hash[:16] }}...</td>
      <td><span class="badge {{ 'banned' if e.result=='banned' else 'success' }}">{{ e.result }}</span></td></tr>
      {% endfor %}
    </table>
  </div>
</div>
"""

BANNED_HTML = STYLE + NAV + """
<div class="container">
  <div class="panel-box">
    <h3 style="margin-top:0;">Manuel Islem</h3>
    <form class="row" method="post" action="/panel/ban">
      <input type="text" name="hash" placeholder="Hash ile banla" style="flex:1;">
      <button type="submit">Banla</button>
    </form>
    <form class="row" method="post" action="/panel/kick">
      <input type="text" name="telegram_id" placeholder="Telegram ID ile gruptan at + banla" style="flex:1;">
      <button type="submit" class="danger">Gruptan At</button>
    </form>
  </div>
  <div class="panel-box">
    <h3 style="margin-top:0;">Banli Cihazlar ({{ banned|length }})</h3>
    <table>
      <tr><th>Hash</th><th>Sebep</th><th>Tarih</th><th></th></tr>
      {% for b in banned %}
      <tr><td style="font-size:11px;">{{ b.hash[:24] }}...</td><td>{{ b.reason }}</td><td>{{ b.time_str }}</td>
      <td><form method="post" action="/panel/unban" style="margin:0;"><input type="hidden" name="hash" value="{{ b.hash }}"><button type="submit">Kaldir</button></form></td></tr>
      {% endfor %}
    </table>
  </div>
</div>
<div style="text-align:center;padding:20px;color:#4a5568;font-size:12px;">NCS Security Shield &copy; 2026 &mdash; Nitro Core Systems</div>
"""

def _fmt(rows):
    for r in rows:
        r['time_str'] = datetime.datetime.fromtimestamp(r['created_at']).strftime('%d.%m %H:%M:%S')
    return rows

@panel_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        u, p = request.form.get('username', ''), request.form.get('password', '')
        with db.get_conn() as conn:
            row = conn.execute('SELECT * FROM admins WHERE username = ?', (u,)).fetchone()
        if row and check_password_hash(row['password_hash'], p):
            session['logged_in'] = True
            session['username'] = u
            return redirect(url_for('panel.dashboard'))
        error = 'Kullanici adi veya sifre hatali.'
    return render_template_string(LOGIN_HTML, error=error)

@panel_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('panel.login'))

@panel_bp.route('/')
@login_required
def dashboard():
    stats = db.get_stats()
    labels, succ, ban = db.get_hourly_chart(24)
    recent = _fmt(db.get_events(limit=15))
    return render_template_string(DASHBOARD_HTML, stats=stats, recent=recent,
                                   labels=labels, success_data=succ, banned_data=ban)

@panel_bp.route('/logs')
@login_required
def logs():
    q = request.args.get('q', '').strip()
    rf = request.args.get('result', '').strip()
    events = _fmt(db.get_events(limit=200, search=q or None, result_filter=rf or None))
    return render_template_string(LOGS_HTML, events=events, q=q, result_filter=rf)

@panel_bp.route('/banned')
@login_required
def banned():
    return render_template_string(BANNED_HTML, banned=_fmt(db.get_banned_list()))

@panel_bp.route('/ban', methods=['POST'])
@login_required
def ban_action():
    h = request.form.get('hash', '').strip()
    if h:
        db.ban_hash(h, reason='panelden manuel ban')
    return redirect(url_for('panel.banned'))

@panel_bp.route('/unban', methods=['POST'])
@login_required
def unban_action():
    h = request.form.get('hash', '').strip()
    if h:
        db.unban_hash(h)
    return redirect(url_for('panel.banned'))

@panel_bp.route('/kick', methods=['POST'])
@login_required
def kick_action():
    tid = request.form.get('telegram_id', '').strip()
    if tid:
        tg_actions.kick_user(int(tid))
        h = db.latest_hash_for_telegram_id(tid)
        if h:
            db.ban_hash(h, reason=f'panelden manuel kick: {tid}')
    return redirect(url_for('panel.banned'))
