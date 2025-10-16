import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import json
import os
from datetime import datetime, timedelta
import re
import webshare_api as webshare

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot Configuration
TOKEN = '8327443445:AAH4qPxGvy84neGs3nAdoV1p3ebRaoAnWwc'
ADMIN_CHAT_ID = '8083915428'

# Payment Information
PAYMENT_INFO = {
    'bkash': '01760935893',
    'nagad': '01732551463',
    'rocket': '01732551463-7'
}

PRICING = {
    '12': {'hours': 12, 'price': 100, 'label': '12 Hours - 100 BDT'},
    '24': {'hours': 24, 'price': 140, 'label': '24 Hours - 140 BDT'}
}

# Data storage
DATA_DIR = 'data'
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
ORDERS_FILE = os.path.join(DATA_DIR, 'orders.json')
PROXIES_FILE = os.path.join(DATA_DIR, 'proxies.json')

users = {}
orders = {}
proxies = {}
user_sessions = {}

def init_data():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    global users, orders, proxies
    
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
    else:
        save_users()
    
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, 'r') as f:
            orders = json.load(f)
    else:
        save_orders()
    
    if os.path.exists(PROXIES_FILE):
        with open(PROXIES_FILE, 'r') as f:
            proxies = json.load(f)
    else:
        save_proxies()

def save_users():
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def save_orders():
    with open(ORDERS_FILE, 'w') as f:
        json.dump(orders, f, indent=2)

def save_proxies():
    with open(PROXIES_FILE, 'w') as f:
        json.dump(proxies, f, indent=2)

def generate_id():
    from time import time
    import random
    return f"{int(time())}{random.randint(1000, 9999)}"

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    welcome_text = """
🌐 *Welcome to B-The Proxy Service!* 🌐

High-quality HTTP & SOCKS5 proxies available 24/7.

Choose an option below:
"""
    
    keyboard = [
        [InlineKeyboardButton("📝 Sign Up", callback_data='signup')],
        [InlineKeyboardButton("🔐 Login", callback_data='login')],
        [InlineKeyboardButton("📋 My Proxies", callback_data='my_proxies')],
        [InlineKeyboardButton("💰 Buy Proxy", callback_data='buy_proxy')],
        [InlineKeyboardButton("ℹ️ Help", callback_data='help')]
    ]
    
    if user_id == ADMIN_CHAT_ID:
        keyboard.append([InlineKeyboardButton("👨‍💼 Admin Panel", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_admin_approve(query, context, user_id, order_id):
    """Admin approves payment - Auto assign proxy from Webshare"""
    
    if user_id != ADMIN_CHAT_ID:
        await query.answer("❌ No access!", show_alert=True)
        return
    
    order = orders.get(order_id)
    if not order:
        await query.edit_message_text('❌ Order not found')
        return
    
    await query.edit_message_text('⏳ Getting proxy...')
    
    raw_proxy = webshare.get_random_proxy()
    
    if not raw_proxy:
        await query.edit_message_text(
            '❌ *No proxies!*\n\nCheck Webshare:\n• Buy proxies\n• Verify API',
            parse_mode='Markdown'
        )
        return
    
    proxy_details = webshare.extract_proxy_details(raw_proxy, order['proxy_type'])
    expiry_date = datetime.now() + timedelta(hours=order['duration'])
    
    proxy = {
        'proxy_id': generate_id(),
        'order_id': order_id,
        'type': order['proxy_type'],
        'ip': proxy_details['ip'],
        'port': proxy_details['port'],
        'username': proxy_details['username'],
        'password': proxy_details['password'],
        'webshare_proxy_id': proxy_details['webshare_id'],
        'expires_at': expiry_date.isoformat(),
        'created_at': datetime.now().isoformat(),
        'rotation_count': 0
    }
    
    customer_id = order['user_id']
    if customer_id not in proxies:
        proxies[customer_id] = []
    
    proxies[customer_id].append(proxy)
    order['status'] = 'approved'
    order['approved_at'] = datetime.now().isoformat()
    
    save_proxies()
    save_orders()
    
    user_message = f"""
🎉 *Proxy Ready!*

✅ Order: `{order_id}`
🔧 Type: *{proxy['type']}*
⏰ Valid: {expiry_date.strftime('%Y-%m-%d %H:%M')}

💡 Change IP 5 times/day!
"""
    
    keyboard = [
        [InlineKeyboardButton("📋 View", callback_data=f'view_proxy_{proxy["proxy_id"]}')],
        [InlineKeyboardButton("🔄 Change IP", callback_data=f'rotate_ip_{proxy["proxy_id"]}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(
            chat_id=int(customer_id), 
            text=user_message, 
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        await query.edit_message_text(
            f"✅ *Approved!*\n\n"
            f"📦 `{order_id}`\n"
            f"📍 `{proxy['ip']}`\n"
            f"✅ Customer notified!",
            parse_mode='Markdown'
        )
    except Exception as e:
        await query.edit_message_text(f'✅ Done but notify error: {e}')

async def handle_ip_rotation(query, context, user_id, proxy_id):
    """Handle IP rotation request"""
    
    user_proxies = proxies.get(user_id, [])
    current_proxy = None
    
    for p in user_proxies:
        if p['proxy_id'] == proxy_id:
            current_proxy = p
            break
    
    if not current_proxy:
        await query.answer("❌ Not found!", show_alert=True)
        return
    
    expiry_date = datetime.fromisoformat(current_proxy['expires_at'])
    if datetime.now() > expiry_date:
        await query.answer("❌ Expired!", show_alert=True)
        return
    
    rotation_count = current_proxy.get('rotation_count', 0)
    if rotation_count >= 5:
        await query.answer("⚠️ Limit 5/5 reached", show_alert=True)
        return
    
    await query.edit_message_text('🔄 Rotating...')
    
    new_raw_proxy = webshare.rotate_ip(current_proxy.get('webshare_proxy_id'))
    
    if not new_raw_proxy:
        await query.answer("❌ Failed", show_alert=True)
        return
    
    new_details = webshare.extract_proxy_details(new_raw_proxy, current_proxy['type'])
    
    current_proxy['ip'] = new_details['ip']
    current_proxy['port'] = new_details['port']
    current_proxy['username'] = new_details['username']
    current_proxy['password'] = new_details['password']
    current_proxy['webshare_proxy_id'] = new_details['webshare_id']
    current_proxy['rotation_count'] = rotation_count + 1
    current_proxy['last_rotated'] = datetime.now().isoformat()
    
    save_proxies()
    
    success_msg = f"""
✅ *IP Changed!*

🔄 IP: `{current_proxy['ip']}`
🔌 Port: `{current_proxy['port']}`
👤 User: `{current_proxy['username']}`
🔑 Pass: `{current_proxy['password']}`

📊 {current_proxy['rotation_count']}/5
⏰ {expiry_date.strftime('%Y-%m-%d %H:%M')}
"""
    
    keyboard = [
        [InlineKeyboardButton("📋 Details", callback_data=f'view_proxy_{proxy_id}')],
        [InlineKeyboardButton("🔄 Again", callback_data=f'rotate_ip_{proxy_id}')],
        [InlineKeyboardButton("◀️ Back", callback_data='my_proxies')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(success_msg, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_view_proxy_details(query, context, user_id, proxy_id):
    """View proxy with rotation button"""
    
    user_proxies = proxies.get(user_id, [])
    proxy = None
    
    for p in user_proxies:
        if p['proxy_id'] == proxy_id:
            proxy = p
            break
    
    if not proxy:
        await query.answer("❌ Not found!", show_alert=True)
        return
    
    expiry_date = datetime.fromisoformat(proxy['expires_at'])
    is_active = expiry_date > datetime.now()
    rotation_count = proxy.get('rotation_count', 0)
    
    details_message = f"""
{'✅' if is_active else '❌'} *Proxy Details*

🔧 *Type:* {proxy['type']}
📍 *IP:* `{proxy['ip']}`
🔌 *Port:* `{proxy['port']}`
👤 *User:* `{proxy['username']}`
🔑 *Pass:* `{proxy['password']}`

📊 *Rotations:* {rotation_count}/5
⏰ *Expires:* {expiry_date.strftime('%Y-%m-%d %H:%M')}
{'🟢 Active' if is_active else '🔴 Expired'}

📋 *String:*
`{proxy['ip']}:{proxy['port']}:{proxy['username']}:{proxy['password']}`
"""
    
    keyboard = []
    
    if is_active:
        keyboard.append([
            InlineKeyboardButton("🔄 Change IP", callback_data=f'rotate_ip_{proxy_id}')
        ])
    
    keyboard.append([
        InlineKeyboardButton("◀️ Back", callback_data='my_proxies')
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(details_message, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    data = query.data
    
    if data == 'signup':
        await handle_signup(query, context, user_id)
    elif data == 'login':
        await handle_login(query, context, user_id)
    elif data == 'buy_proxy':
        await handle_buy_proxy(query, context, user_id)
    elif data == 'my_proxies':
        await handle_my_proxies(query, context, user_id)
    elif data == 'help':
        await handle_help(query, context)
    elif data == 'admin_panel':
        await handle_admin_panel(query, context, user_id)
    elif data.startswith('proxy_type_'):
        proxy_type = data.replace('proxy_type_', '')
        await handle_proxy_type(query, context, user_id, proxy_type)
    elif data.startswith('duration_'):
        duration = data.replace('duration_', '')
        await handle_duration(query, context, user_id, duration)
    elif data.startswith('admin_yes_'):
        order_id = data.replace('admin_yes_', '')
        await handle_admin_approve(query, context, user_id, order_id)
    elif data.startswith('admin_no_'):
        order_id = data.replace('admin_no_', '')
        await handle_admin_reject(query, context, user_id, order_id)
    elif data.startswith('view_proxy_'):
        proxy_id = data.replace('view_proxy_', '')
        await handle_view_proxy_details(query, context, user_id, proxy_id)
    elif data.startswith('view_order_'):
        order_id = data.replace('view_order_', '')
        await handle_view_order(query, context, user_id, order_id)
    elif data.startswith('rotate_ip_'):
        proxy_id = data.replace('rotate_ip_', '')
        await handle_ip_rotation(query, context, user_id, proxy_id)

async def handle_signup(query, context, user_id):
    user_sessions[user_id] = {'state': 'awaiting_email'}
    await query.edit_message_text('📧 *Please enter your email address:*', parse_mode='Markdown')

async def handle_login(query, context, user_id):
    user_sessions[user_id] = {'state': 'awaiting_login_email'}
    await query.edit_message_text('📧 *Please enter your email:*', parse_mode='Markdown')

async def handle_buy_proxy(query, context, user_id):
    if user_id not in users:
        await query.edit_message_text('❌ Please sign up first using /start')
        return
    
    keyboard = [
        [InlineKeyboardButton("🌐 HTTP Proxy", callback_data='proxy_type_HTTP')],
        [InlineKeyboardButton("🔒 SOCKS5 Proxy", callback_data='proxy_type_SOCKS5')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text('🔧 *Select proxy type:*', reply_markup=reply_markup, parse_mode='Markdown')

async def handle_proxy_type(query, context, user_id, proxy_type):
    user_sessions[user_id] = {
        'state': 'selecting_duration',
        'proxy_type': proxy_type
    }
    
    keyboard = [
        [InlineKeyboardButton("⏰ 12 Hours - 100 BDT", callback_data='duration_12')],
        [InlineKeyboardButton("⏰ 24 Hours - 140 BDT", callback_data='duration_24')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text('⏱️ *Select duration:*', reply_markup=reply_markup, parse_mode='Markdown')

async def handle_duration(query, context, user_id, duration):
    session = user_sessions.get(user_id, {})
    pricing = PRICING[duration]
    
    order_id = generate_id()
    orders[order_id] = {
        'order_id': order_id,
        'user_id': user_id,
        'proxy_type': session['proxy_type'],
        'duration': pricing['hours'],
        'price': pricing['price'],
        'status': 'awaiting_payment',
        'created_at': datetime.now().isoformat()
    }
    save_orders()
    
    session['order_id'] = order_id
    session['state'] = 'awaiting_transaction_id'
    user_sessions[user_id] = session
    
    payment_text = f"""
💳 *Payment Information*

📦 Order ID: `{order_id}`
🔧 Proxy Type: *{session['proxy_type']}*
⏱️ Duration: *{pricing['hours']} hours*
💰 Amount: *{pricing['price']} BDT*

📱 *Payment Methods:*

💚 bKash: `{PAYMENT_INFO['bkash']}`
💙 Nagad: `{PAYMENT_INFO['nagad']}`
🚀 Rocket: `{PAYMENT_INFO['rocket']}`

📝 *After payment, please send:*
1️⃣ Transaction ID
2️⃣ Screenshot of payment

*Type your transaction ID below:*
"""
    await query.edit_message_text(payment_text, parse_mode='Markdown')

async def handle_my_proxies(query, context, user_id):
    if user_id not in users:
        await query.edit_message_text('❌ Please sign up first using /start')
        return
    
    user_proxies = proxies.get(user_id, [])
    
    if not user_proxies:
        await query.edit_message_text('📭 You have no active proxies. Use /start to buy one!')
        return
    
    message = '📋 *Your Active Proxies:*\n\n'
    
    for idx, proxy in enumerate(user_proxies, 1):
        expiry_date = datetime.fromisoformat(proxy['expires_at'])
        now = datetime.now()
        is_active = expiry_date > now
        
        message += f"{idx}. *{proxy['type']}*\n"
        message += f"   📍 IP: `{proxy['ip']}`\n"
        message += f"   🔌 Port: `{proxy['port']}`\n"
        message += f"   👤 Username: `{proxy['username']}`\n"
        message += f"   🔑 Password: `{proxy['password']}`\n"
        message += f"   {'✅' if is_active else '❌'} Status: *{'Active' if is_active else 'Expired'}*\n"
        message += f"   ⏰ Expires: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    await query.edit_message_text(message, parse_mode='Markdown')

async def handle_help(query, context):
    help_text = f"""
ℹ️ *Help & Information*

📝 *How to use:*
1. Sign up with email and password
2. Choose proxy type (HTTP or SOCKS5)
3. Select duration (12 or 24 hours)
4. Make payment via bKash/Nagad/Rocket
5. Submit transaction ID and screenshot
6. Receive proxy details after approval

💰 *Pricing:*
• 12 Hours: 100 BDT
• 24 Hours: 140 BDT

📱 *Payment Methods:*
• bKash: `{PAYMENT_INFO['bkash']}`
• Nagad: `{PAYMENT_INFO['nagad']}`
• Rocket: `{PAYMENT_INFO['rocket']}`

⏱️ Approval Time: 5-30 minutes

❓ Need help? Contact support.
"""
    await query.edit_message_text(help_text, parse_mode='Markdown')

async def handle_admin_panel(query, context, user_id):
    if user_id != ADMIN_CHAT_ID:
        await query.answer("❌ You don't have admin access!", show_alert=True)
        return
    
    pending_orders = [o for o in orders.values() if o['status'] == 'awaiting_payment' or o['status'] == 'pending_approval']
    
    if not pending_orders:
        await query.edit_message_text('📭 No pending orders')
        return
    
    keyboard = []
    for order in pending_orders:
        user_email = users.get(order['user_id'], {}).get('email', 'Unknown')
        keyboard.append([
            InlineKeyboardButton(
                f"Order #{order['order_id'][:8]} - {order['proxy_type']} - {order['price']} BDT",
                callback_data=f"view_order_{order['order_id']}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f'👨‍💼 *Admin Panel*\n\n📦 Pending Orders: {len(pending_orders)}',
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_view_order(query, context, user_id, order_id):
    if user_id != ADMIN_CHAT_ID:
        await query.answer("❌ You don't have admin access!", show_alert=True)
        return
    
    order = orders.get(order_id)
    if not order:
        await query.edit_message_text('❌ Order not found')
        return
    
    user = users.get(order['user_id'], {})
    
    order_text = f"""
📦 *Order Details*

🆔 Order ID: `{order_id}`
👤 User: {user.get('email', 'Unknown')}
🔧 Type: *{order['proxy_type']}*
⏱️ Duration: *{order['duration']} hours*
💰 Amount: *{order['price']} BDT*
💳 Transaction ID: `{order.get('transaction_id', 'Not provided')}`
📅 Created: {order['created_at']}
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f'admin_yes_{order_id}'),
            InlineKeyboardButton("❌ Reject", callback_data=f'admin_no_{order_id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(order_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_admin_reject(query, context, user_id, order_id):
    if user_id != ADMIN_CHAT_ID:
        await query.answer("❌ You don't have admin access!", show_alert=True)
        return
    
    order = orders.get(order_id)
    if not order:
        await query.edit_message_text('❌ Order not found')
        return
    
    orders[order_id]['status'] = 'rejected'
    orders[order_id]['rejected_at'] = datetime.now().isoformat()
    save_orders()
    
    user_id_customer = order['user_id']
    rejection_message = f"""
❌ *Payment Canceled*

📋 Order ID: `{order_id}`
💳 Transaction ID: `{order.get('transaction_id', 'N/A')}`

Your payment could not be verified. Please contact support if you believe this is an error.

Use /start to try again.
"""
    
    try:
        await context.bot.send_message(
            chat_id=int(user_id_customer),
            text=rejection_message,
            parse_mode='Markdown'
        )
        await query.edit_message_text(f'❌ Order #{order_id} rejected and user notified.')
    except Exception as e:
        await query.edit_message_text(f'❌ Order rejected but could not notify user: {e}')

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text
    session = user_sessions.get(user_id, {})
    
    state = session.get('state')
    
    if state == 'awaiting_email':
        await handle_email_input(update, context, user_id, text)
    elif state == 'awaiting_password':
        await handle_password_input(update, context, user_id, text)
    elif state == 'awaiting_login_email':
        await handle_login_email(update, context, user_id, text)
    elif state == 'awaiting_login_password':
        await handle_login_password(update, context, user_id, text)
    elif state == 'awaiting_transaction_id':
        await handle_transaction_id(update, context, user_id, text)

async def handle_email_input(update, context, user_id, email):
    if not is_valid_email(email):
        await update.message.reply_text('❌ Invalid email format. Please enter a valid email:')
        return
    
    for uid, user in users.items():
        if user.get('email') == email:
            await update.message.reply_text('❌ This email is already registered. Please use /start to login.')
            if user_id in user_sessions:
                del user_sessions[user_id]
            return
    
    user_sessions[user_id]['email'] = email
    user_sessions[user_id]['state'] = 'awaiting_password'
    await update.message.reply_text('🔒 *Please enter your password (minimum 6 characters):*', parse_mode='Markdown')

async def handle_password_input(update, context, user_id, password):
    if len(password) < 6:
        await update.message.reply_text('❌ Password must be at least 6 characters. Please try again:')
        return
    
    session = user_sessions[user_id]
    
    users[user_id] = {
        'user_id': user_id,
        'email': session['email'],
        'password': password,
        'created_at': datetime.now().isoformat(),
        'proxies': []
    }
    save_users()
    
    await update.message.reply_text(
        f"✅ *Account created successfully!*\n\n📧 Email: {session['email']}\n\nYou can now purchase proxies. Use /start to continue.",
        parse_mode='Markdown'
    )
    
    del user_sessions[user_id]

async def handle_login_email(update, context, user_id, email):
    user_sessions[user_id]['login_email'] = email
    user_sessions[user_id]['state'] = 'awaiting_login_password'
    await update.message.reply_text('🔒 *Please enter your password:*', parse_mode='Markdown')

async def handle_login_password(update, context, user_id, password):
    session = user_sessions[user_id]
    email = session['login_email']
    
    found_user = None
    for uid, user in users.items():
        if user.get('email') == email and user.get('password') == password:
            found_user = user
            break
    
    if not found_user:
        await update.message.reply_text('❌ Invalid email or password. Please try again with /start')
        del user_sessions[user_id]
        return
    
    await update.message.reply_text(
        f"✅ *Login successful!*\n\nWelcome back, {email}!\n\nUse /start to access the menu.",
        parse_mode='Markdown'
    )
    
    del user_sessions[user_id]

async def handle_transaction_id(update, context, user_id, transaction_id):
    session = user_sessions.get(user_id, {})
    order_id = session.get('order_id')
    
    if not order_id or order_id not in orders:
        await update.message.reply_text('❌ Invalid order. Please start again with /start')
        return
    
    orders[order_id]['transaction_id'] = transaction_id
    save_orders()
    
    session['state'] = 'awaiting_screenshot'
    user_sessions[user_id] = session
    
    await update.message.reply_text('📸 *Now please send the payment screenshot:*', parse_mode='Markdown')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    session = user_sessions.get(user_id, {})
    
    if session.get('state') == 'awaiting_screenshot':
        order_id = session.get('order_id')
        if order_id and order_id in orders:
            photo = update.message.photo[-1]
            file_id = photo.file_id
            
            orders[order_id]['screenshot'] = file_id
            orders[order_id]['status'] = 'pending_approval'
            orders[order_id]['submitted_at'] = datetime.now().isoformat()
            save_orders()
            
            await update.message.reply_text(
                f"""✅ *Payment information received!*

📋 Order ID: `{order_id}`
💳 Transaction ID: `{orders[order_id]['transaction_id']}`

Your order is now pending approval. You'll receive your proxy details once the admin approves your payment.

⏱️ Approval usually takes 5-30 minutes.""",
                parse_mode='Markdown'
            )
            
            await notify_admin_new_order(context, order_id)
            
            if user_id in user_sessions:
                del user_sessions[user_id]

async def notify_admin_new_order(context, order_id):
    order = orders[order_id]
    user = users.get(order['user_id'], {})
    
    admin_message = f"""
🔔 *New Payment Received!*

📋 Order ID: `{order_id}`
👤 User: {user.get('email', 'Unknown')}
🔧 Type: *{order['proxy_type']}*
⏱️ Duration: *{order['duration']} hours*
💰 Amount: *{order['price']} BDT*
💳 Transaction ID: `{order.get('transaction_id', 'N/A')}`

⚠️ *Please confirm this payment:*
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ YES - Approve", callback_data=f'admin_yes_{order_id}'),
            InlineKeyboardButton("❌ NO - Reject", callback_data=f'admin_no_{order_id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID, 
            text=admin_message, 
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        if order.get('screenshot'):
            await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=order['screenshot'])
    except Exception as e:
        logger.error(f"Error notifying admin: {e}")

def main():
    init_data()
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    print("🤖 Bot is running...")
    print(f"📁 Data directory: {os.path.abspath(DATA_DIR)}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
