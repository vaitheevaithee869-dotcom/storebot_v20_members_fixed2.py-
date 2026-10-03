import os
import asyncio
import sqlite3
import random
import logging
import time
import aiohttp
import urllib.parse
import json
import re
import socket
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, Dice, BufferedInputFile, ErrorEvent
)


async def safe_edit_text(target, *args, **kwargs):
    """Safely edit a Telegram message; ignore only the harmless unchanged-message error."""
    try:
        return await target.edit_text(*args, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return None
        raise

async def safe_edit_reply_markup(target, *args, **kwargs):
    """Safely edit reply markup; ignore only the harmless unchanged-message error."""
    try:
        return await target.edit_reply_markup(*args, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return None
        raise

# ==============================================================================
# 1. BOT CONFIGURATION & CONSTANTS
# ==============================================================================
BOT_TOKEN = "8784054154:AAFDzbPkkAwgd3V3I3o6EHqNxzkPPLUllJY"
BOT_USERNAME = "@ffdarlingpanelshop_bot"
ADMIN_ID = 8433826576
SECOND_ADMIN_ID = 8615561449
ADMIN_CONTACT = "@FF_DARLING_MODZ_OWNER"

VIP_DISCOUNT_PERCENTAGE = 15.0
VIP_PRICE_INR = 299.0

WELCOME_STICKER_ID = "CAACAgIAAxkBAAEU-WZmH_..."  # Replace with your sticker ID
SPIN_DELAY_SECONDS = 2.5

FIXED_CATEGORIES = [
    "ANDROID NON ROOT PANEL",
    "ANDROID ROOT PANEL",
    "IPHONE PANEL",
    "PC PANEL",
    "GUILD GLORY CREDIT",
    "CARROM PANEL"
]

# ==============================================================================
# YOUR PREMIUM EMOJIS – all required emoji IDs
# ==============================================================================
DEFAULT_EMOJIS = {
    'product_store': '6163205892834598715',
    'profile': '6035084557378654059',
    'add_balance': '5278467510604160626',
    'history': '6160968017304888311',
    'referral': '6032609071373226027',
    'support': '6161112036148255813',
    'ludo_spin': '6147764669361692707',
    'back': '6039539366177541657',
    'upi': '5807750375033278838',
    'reseller': '6120436698695338614',
    'tutorial': '5368653135101310687',
    'download': '6161336001512874965',
    'telegram': '6161096071754818473',
    'whatsapp': '6118193823823698862',
    'welcome': '5312361253610475399',
    'vip': '6086672466132865380',
    'category_android_non_root': '6161172706856282588',
    'category_android_root': '6161449831031118974',
    'category_iphone': '6161399700172840408',
    'category_pc': '5350554349074391003',
    'grid_id': '5474625972751837256',
    'name': '5215399540814781035',
    'account_level': '6129584162992034014',
    'regular_user': '5904630315946611415',
    'wallet': '6210859306602995217',
    'current_balance': '5316711376876485361',
    'global_stats': '6161437856662298090',
    'total_orders': '6160968017304888311',
    'total_spent': '5197503331215361533',
    'total_referrals': '5938196735200333756',
    'joined_grid': '5433614043006903194',
    'info_icon': '6037421444789440735',
    'check_icon': '6161241250239356403',
    'checkbox_icon': '6161437856662298090',
    'shield_icon': '6086672466132865380',
    'money_icon': '5890848474563352982',
    'redeem_icon': '5377624166436445368',
    'validity': '6037421444789440735',
    'price': '5890848474563352982',
    'device_limit': '5215399540814781035',
    'wallet_balance': '6210859306602995217',
    'confirm': '5377624166436445368',
    'maintenance': '6037421444789440735',
    'package_name': '5215399540814781035',
    'wallet_balance': '6210859306602995217',
    'confirm_pay': '6161241250239356403',
    'maintenance': '6037421444789440735',
    'buy': '6163205892834598715',
    'pay_direct_qr': '5807750375033278838',
    'add_balance_first': '5278467510604160626',
    'cancel': '6039539366177541657',
    'wallet_left': '6210859306602995217',
    'wallet_right': '5305699699204837855',
    'point_down': '6161302621027049305',
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_activity.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

@dp.error()
async def global_error_handler(event: ErrorEvent):
    """Keep one unexpected handler exception from terminating the polling process.

    This is a safety net only. Existing handlers, payment logic, product logic,
    and API logic are left unchanged. Known harmless Telegram edit errors are
    already handled by safe_edit_text/safe_edit_reply_markup above.
    """
    exc = event.exception
    logger = logging.getLogger(__name__)
    logger.exception("Unhandled update error: %s", exc)
    try:
        update = event.update
        if isinstance(update, CallbackQuery):
            try:
                await update.answer("⚠️ Please try again.", show_alert=False)
            except Exception:
                pass
    except Exception:
        pass
    return True

# Two-admin authorization and notifications
def is_admin(user_id: int) -> bool:
    return user_id in {ADMIN_ID, SECOND_ADMIN_ID}

async def notify_admins(text: str, **kwargs):
    """Send an admin notification to both configured admins."""
    for admin_id in (ADMIN_ID, SECOND_ADMIN_ID):
        try:
            await bot.send_message(admin_id, text, **kwargs)
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

def fmt_curr(amount: float) -> str:
    return f"₹{amount:,.2f}"

def natural_sort_key(value: Any) -> List[Any]:
    """Sort names naturally: A, B, C... and 1, 2, 10 instead of 1, 10, 2."""
    text = str(value or "").strip()
    return [int(part) if part.isdigit() else part.casefold()
            for part in re.split(r"(\d+)", text)]

# ==============================================================================
# 2. DATABASE FUNCTIONS
# ==============================================================================
# In-memory settings cache: navigation used to open a new SQLite connection for
# every emoji/setting lookup. That made simple button screens unnecessarily slow.
# The bot itself updates settings through set_setting(), so the cache stays in sync.
_SETTINGS_CACHE: Dict[str, str] = {}

def db_query(query: str, params: tuple = (), fetchone: bool = False, fetchall: bool = False, commit: bool = True) -> Any:
    conn = sqlite3.connect('yp_shop.db')
    c = conn.cursor()
    try:
        c.execute(query, params)
        if fetchone:
            res = c.fetchone()
        elif fetchall:
            res = c.fetchall()
        else:
            res = None
        # SELECT/PRAGMA reads never need a commit. Avoiding a needless SQLite
        # commit on every read noticeably speeds up Telegram navigation.
        qtype = query.lstrip().upper()
        if commit and not qtype.startswith(("SELECT", "PRAGMA")):
            conn.commit()
        return res
    except Exception as e:
        logger.error(f"DB Error: {e} | Query: {query} | Params: {params}")
        if commit: conn.rollback()
        return None
    finally:
        conn.close()

def get_setting(key: str, default: str = "") -> str:
    if key in _SETTINGS_CACHE:
        value = _SETTINGS_CACHE[key]
        return value if value else default
    val = db_query("SELECT value FROM settings WHERE key=?", (key,), fetchone=True, commit=False)
    value = val[0] if val and val[0] is not None else default
    _SETTINGS_CACHE[key] = str(value)
    return str(value) if value else default

def set_setting(key: str, value: str) -> None:
    value = str(value)
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    _SETTINGS_CACHE[key] = value

def log_activity(user_id: int, action: str, details: str = "") -> None:
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_query(
            "INSERT INTO activity_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details, timestamp)
        )
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")

def get_emoji(slot: str, default_id: str = None) -> str:
    stored = get_setting(f"emoji_{slot}", "")
    emoji_id = stored if stored and stored.isdigit() else (default_id or DEFAULT_EMOJIS.get(slot, ""))
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">✨</tg-emoji>'
    return "✨"

def get_emoji_icon(slot: str, default_id: str = None) -> str:
    stored = get_setting(f"emoji_{slot}", "")
    emoji_id = stored if stored and stored.isdigit() else (default_id or DEFAULT_EMOJIS.get(slot, ""))
    return emoji_id

# ==============================================================================
# 3. STRING RESOURCES – using placeholders for premium emojis
# ==============================================================================
UI_TEXTS = {
    "start_menu": (
    "{welcome} 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 𝗗𝗔𝗥𝗟𝗜𝗡𝗚 𝗦𝗧𝗢𝗥𝗘\n\n"
    "{product_store} 𝗣𝗿𝗼𝗱𝘂𝗰𝘁 𝗦𝘁𝗼𝗿𝗲\n"
    "𝗘𝘅𝗽𝗹𝗼𝗿𝗲 𝗔𝘃𝗮𝗶𝗹𝗮𝗯𝗹𝗲 𝗞𝗲𝘆𝘀 𝗮𝗻𝗱 𝗚𝗲𝘁 𝗧𝗵𝗲𝗺 𝗗𝗲𝗹𝗶𝘃𝗲𝗿𝗲𝗱 𝗜𝗻𝘀𝘁𝗮𝗻𝘁𝗹𝘆 — 𝗙𝗮𝘀𝘁, 𝗦𝗺𝗼𝗼𝘁𝗵 & 𝗦𝗲𝗰𝘂𝗿𝗲.\n"
    "{add_balance} 𝗔𝗱𝗱 𝗕𝗮𝗹𝗮𝗻𝗰𝗲\n"
    "𝗖𝗵𝗼𝗼𝘀𝗲 𝗬𝗼𝘂𝗿 𝗔𝗺𝗼𝘂𝗻𝘁, 𝗖𝗼𝗺𝗽𝗹𝗲𝘁𝗲 𝗧𝗵𝗲 𝗣𝗮𝘆𝗺𝗲𝗻𝘁 & 𝗧𝗼𝗽 𝗨𝗽 𝗬𝗼𝘂𝗿 𝗕𝗮𝗹𝗮𝗻𝗰𝗲 𝗘𝗮𝘀𝗶𝗹𝘆.\n"
    "{history} 𝗠𝘆 𝗞𝗲𝘆\n"
    "𝗞𝗲𝗲𝗽 𝗔𝗻 𝗘𝘆𝗲 𝗢𝗻 𝗬𝗼𝘂𝗿 𝗣𝗮𝘀𝘁 𝗢𝗿𝗱𝗲𝗿𝘀, 𝗣𝗮𝘆𝗺𝗲𝗻𝘁𝘀 & 𝗔𝗰𝗰𝗼𝘂𝗻𝘁 𝗔𝗰𝘁𝗶𝘃𝗶𝘁𝘆.\n"
    "{referral} 𝗥𝗲𝗳𝗲𝗿𝗿𝗮𝗹\n"
    "𝗦𝗵𝗮𝗿𝗲 𝗧𝗵𝗲 𝗦𝘁𝗼𝗿𝗲 𝗪𝗶𝘁𝗵 𝗙𝗿𝗶𝗲𝗻𝗱𝘀 𝗮𝗻𝗱 𝗘𝗮𝗿𝗻 𝗥𝗲𝘄𝗮𝗿𝗱𝘀 𝗧𝗵𝗿𝗼𝘂𝗴𝗵 𝗬𝗼𝘂𝗿 𝗥𝗲𝗳𝗲𝗿𝗿𝗮𝗹𝘀.\n"
    "{tutorial} 𝗛𝗼𝘄 𝘁𝗼 𝘂𝘀𝗲\n"
    "𝗡𝗲𝘄 𝗛𝗲𝗿𝗲? 𝗙𝗼𝗹𝗹𝗼𝘄 𝗧𝗵𝗲 𝗚𝘂𝗶𝗱𝗲𝘀 𝗮𝗻𝗱 𝗟𝗲𝗮𝗿𝗻 𝗛𝗼𝘄 𝗧𝗵𝗲 𝗕𝗼𝘁 𝗪𝗼𝗿𝗸𝘀.\n"
    "{support} 𝗦𝘂𝗽𝗽𝗼𝗿𝘁\n"
    "𝗥𝘂𝗻 𝗜𝗻𝘁𝗼 𝗔 𝗣𝗿𝗼𝗯𝗹𝗲𝗺? 𝗚𝗲𝘁 𝗛𝗲𝗹𝗽 𝗙𝗿𝗼𝗺 𝗢𝘂𝗿 𝗦𝘂𝗽𝗽𝗼𝗿𝘁 𝗧𝗲𝗮𝗺.\n"
    "{ludo_spin} 𝗟𝘂𝗱𝗼 𝗦𝗽𝗶𝗻\n"
    "𝗧𝗮𝗸𝗲 𝗔 𝗦𝗽𝗶𝗻, 𝗧𝗿𝘆 𝗬𝗼𝘂𝗿 𝗟𝘂𝗰𝗸 & 𝗪𝗶𝗻 𝗘𝘅𝘁𝗿𝗮 𝗕𝗮𝗹𝗮𝗻𝗰𝗲.\n"
    "{download} 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱 𝗙𝗶𝗹𝗲𝘀\n"
    "𝗚𝗲𝘁 𝗧𝗵𝗲 𝗟𝗮𝘁𝗲𝘀𝘁 𝗙𝗶𝗹𝗲𝘀 𝗙𝗿𝗼𝗺 𝗧𝗵𝗲 𝗢𝗳𝗳𝗶𝗰𝗶𝗮𝗹 𝗦𝘁𝗼𝗿𝗲."
),
    "download_files": (
        "🗂 <b><u>DOWNLOAD PREMIUM APK & FILES 📊</u></b>\n\n"
        "🌐 All our highly secured, premium, and updated files\n"
        "are securely hosted on our private channel! ⚠️⛔️\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📱 <b>WHAT YOU GET:</b> 📌\n\n"
        "✔️ Latest APK Updates 🔔\n"
        "✔️ 100% Virus Free & Secure ‼️\n"
        "✔️ All Configs & Scripts 🌸\n"
        "✔️ Complete Installation Guides 🔺\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⌨️ Tap the button below to access the Download Channel! 📝"
    ),
    "lucky_dice_result": (
        "{ludo_spin} <b><u>LUCKY DICE RESULT 🔨 💯</u></b>\n\n"
        "🎲 <b>Dice Value:</b> {dice_value}\n\n"
        "💸 <b>You Won:</b> {won_amount}\n"
        "💰 <b>Total Balance:</b> {new_balance}\n\n"
        "Congratulations! Come back after 24 hours."
    ),
    "vip_menu": (
        "🌟 <b><u>VIP MEMBERSHIP CLUB</u></b> 🌟\n\n"
        "Unlock premium benefits and permanent discounts!\n\n"
        "💎 <b>VIP Benefits:</b>\n"
        "• Flat 15% off on ALL products (Stacks with Reseller!)\n"
        "• Priority Support\n"
        "• Exclusive VIP-only giveaways\n\n"
        "💳 <b>VIP Price:</b> ₹299.00 (Lifetime)\n"
        "👤 <b>Your Status:</b> {vip_status}"
    ),
    "add_balance_menu": (
        "{add_balance} <b>ADD BALANCE</b> {info_icon}\n\n"
        "{info_icon} Select your preferred payment method. {check_icon}\n\n"
        "┣ {upi} Pay with UPI — Fast Indian payments {checkbox_icon}\n"
        "{shield_icon} Payments are verified securely. {check_icon}"
    )
}

def get_ui_text(key: str, **kwargs) -> str:
    val = db_query("SELECT value FROM settings WHERE key=?", (f"ui_{key}",), fetchone=True)
    template = val[0] if val and val[0] else UI_TEXTS.get(key, "")
    emoji_map = {
        '{welcome}': get_emoji('welcome'),
        '{product_store}': get_emoji('product_store'),
        '{profile}': get_emoji('profile'),
        '{add_balance}': get_emoji('add_balance'),
        '{history}': get_emoji('history'),
        '{referral}': get_emoji('referral'),
        '{tutorial}': get_emoji('tutorial'),
        '{support}': get_emoji('support'),
        '{ludo_spin}': get_emoji('ludo_spin'),
        '{download}': get_emoji('download'),
        '{telegram}': get_emoji('telegram'),
        '{whatsapp}': get_emoji('whatsapp'),
        '{upi}': get_emoji('upi'),
        '{info_icon}': get_emoji('info_icon'),
        '{check_icon}': get_emoji('check_icon'),
        '{checkbox_icon}': get_emoji('checkbox_icon'),
        '{shield_icon}': get_emoji('shield_icon'),
        '{money_icon}': get_emoji('money_icon'),
        '{redeem_icon}': get_emoji('redeem_icon'),
        '{reseller}': get_emoji('reseller'),
        '{vip}': get_emoji('vip'),
        '{wallet_left}': get_emoji('wallet_left'),
        '{wallet_right}': get_emoji('wallet_right'),
        '{point_down}': get_emoji('point_down'),
    }
    for placeholder, emoji_tag in emoji_map.items():
        template = template.replace(placeholder, emoji_tag)

    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing formatting key for template {key}: {e}")
    return template



def get_ui_photo_id(key: str) -> str:
    """Return the saved Telegram photo file_id for an editable UI screen, if any."""
    val = db_query("SELECT value FROM settings WHERE key=?", (f"ui_{key}_photo_id",), fetchone=True, commit=False)
    return str(val[0]) if val and val[0] else ""


async def send_ui_content(ctx: Any, key: str, text: str, reply_markup=None, **kwargs):
    """Send an editable UI text or its saved premium-image version."""
    photo_id = get_ui_photo_id(key)
    if photo_id:
        if isinstance(ctx, Message):
            return await ctx.answer_photo(photo_id, caption=text, reply_markup=reply_markup, parse_mode='HTML', **kwargs)
        try:
            await ctx.message.delete()
        except Exception:
            pass
        return await ctx.message.answer_photo(photo_id, caption=text, reply_markup=reply_markup, parse_mode='HTML', **kwargs)
    if isinstance(ctx, Message):
        return await ctx.answer(text, reply_markup=reply_markup, parse_mode='HTML', **kwargs)
    return await safe_edit_text(ctx.message, text, reply_markup=reply_markup, parse_mode='HTML', **kwargs)

# ==============================================================================
# 4. DATABASE INITIALISATION & MIGRATION
# ==============================================================================
def init_db() -> None:
    conn = sqlite3.connect('yp_shop.db')
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            phone TEXT, 
            first_name TEXT, 
            username TEXT,
            balance REAL DEFAULT 0.0, 
            account_type TEXT DEFAULT 'Regular', 
            orders_count INTEGER DEFAULT 0, 
            spent REAL DEFAULT 0.0, 
            referrals_count INTEGER DEFAULT 0, 
            referral_earned REAL DEFAULT 0.0, 
            referred_by INTEGER, 
            last_spin TEXT, 
            joined_date TEXT,
            is_reseller INTEGER DEFAULT 0,
            reseller_expires_at TEXT DEFAULT NULL,
            reseller_since TEXT,
            total_saved REAL DEFAULT 0.0,
            is_banned INTEGER DEFAULT 0,
            warnings INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            vip_since TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            category TEXT, 
            panel_name TEXT DEFAULT '',
            name TEXT, 
            price_inr REAL, 
            reseller_price REAL DEFAULT 0.0,
            stock INTEGER, 
            apk_link TEXT, 
            validity TEXT DEFAULT 'Lifetime', 
            device_limit TEXT DEFAULT '1 Device',
            is_active INTEGER DEFAULT 1,
            demo_video TEXT DEFAULT ''
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS product_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            product_id INTEGER, 
            key_text TEXT, 
            is_used INTEGER DEFAULT 0
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            product_name TEXT, 
            price_paid REAL, 
            delivered_key TEXT, 
            purchase_date TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            message TEXT, 
            status TEXT DEFAULT 'Open',
            created_at TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, 
            value TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY, 
            amount REAL, 
            uses_left INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS redeemed (
            user_id INTEGER, 
            code TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            order_id TEXT PRIMARY KEY, 
            user_id INTEGER, 
            amount_inr REAL, 
            gateway_amount REAL DEFAULT 0.0,
            status TEXT, 
            timestamp INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS crypto_txns (
            txid TEXT PRIMARY KEY, 
            user_id INTEGER, 
            amount_usdt REAL, 
            timestamp INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS spin_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            amount REAL
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TEXT
        )
    ''')

    # Broadcast history: stores every new broadcast and the Telegram message
    # ID sent to each user so the admin can edit/delete that broadcast later.
    c.execute('''
        CREATE TABLE IF NOT EXISTS broadcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            source_chat_id INTEGER,
            source_message_id INTEGER,
            created_at TEXT,
            message_type TEXT DEFAULT 'text',
            title TEXT DEFAULT ''
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS broadcast_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broadcast_id INTEGER,
            user_id INTEGER,
            message_id INTEGER,
            status TEXT DEFAULT 'sent',
            FOREIGN KEY(broadcast_id) REFERENCES broadcasts(id)
        )
    ''')

    # Fast navigation indexes. These only accelerate reads and do not change
    # products, prices, payment flow, or purchase accounting.
    c.execute("CREATE INDEX IF NOT EXISTS idx_products_category_active ON products(category, is_active)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_products_category_panel_active ON products(category, panel_name, is_active)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_products_active_panel ON products(is_active, panel_name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")

    # Broadcast table migrations for existing databases.  CREATE TABLE IF NOT EXISTS
    # does not add columns to an older yp_shop.db, so the Broadcast button could
    # fail when it tried to read message_type/title/status.
    broadcast_migrations = [
        "ALTER TABLE broadcasts ADD COLUMN admin_id INTEGER",
        "ALTER TABLE broadcasts ADD COLUMN source_chat_id INTEGER",
        "ALTER TABLE broadcasts ADD COLUMN source_message_id INTEGER",
        "ALTER TABLE broadcasts ADD COLUMN created_at TEXT",
        "ALTER TABLE broadcasts ADD COLUMN message_type TEXT DEFAULT 'text'",
        "ALTER TABLE broadcasts ADD COLUMN title TEXT DEFAULT ''",
        "ALTER TABLE broadcast_messages ADD COLUMN broadcast_id INTEGER",
        "ALTER TABLE broadcast_messages ADD COLUMN user_id INTEGER",
        "ALTER TABLE broadcast_messages ADD COLUMN message_id INTEGER",
        "ALTER TABLE broadcast_messages ADD COLUMN status TEXT DEFAULT 'sent'",
    ]
    for migration in broadcast_migrations:
        try:
            c.execute(migration)
        except sqlite3.OperationalError:
            pass

    migrations = [
        "ALTER TABLE users ADD COLUMN is_vip INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN vip_since TEXT",
        "ALTER TABLE products ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE tickets ADD COLUMN created_at TEXT",
        "ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN warnings INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN panel_name TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN reseller_price REAL DEFAULT 0.0",
        "ALTER TABLE products ADD COLUMN external_enabled INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN external_product_id TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN requires_android_id INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN external_duration TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN demo_video TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN maintenance INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN external_api_type INTEGER DEFAULT 1",
        "ALTER TABLE transactions ADD COLUMN gateway_amount REAL DEFAULT 0.0",
    ]
    for mig in migrations:
        try: c.execute(mig)
        except sqlite3.OperationalError: pass

    # Backfill API metadata for existing products. Existing external products
    # stay on API 1 so their current purchase behavior is unchanged.
    try:
        c.execute("UPDATE products SET external_duration = validity WHERE COALESCE(external_duration, '') = ''")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("UPDATE products SET external_api_type = CASE WHEN COALESCE(external_enabled, 0)=1 THEN 1 ELSE 0 END WHERE external_api_type IS NULL")
    except sqlite3.OperationalError:
        pass
    
    c.execute("SELECT COUNT(*) FROM spin_rewards")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO spin_rewards (amount) VALUES (?)", [(0.0,), (1.0,), (2.0,), (5.0,), (10.0,)])

    default_settings = [
        ('spin_status', 'ON'),
        ('daily_spin_limit', '50.0'),
        ('reseller_system_status', 'ON'),
        ('bot_status', 'ON'),
        ('how_to_video', 'None'),
        ('all_files_link', 'None'),
        ('fampay_api_key', ''),
            ('fampay_base_url', 'https://fam.aryanispe.in'),
            ('fampay_merchant_email', ''),
            ('fampay_upi_id', ''),
        ('vip_status', 'OFF'),
        ('reseller_setup_fee', '200.0'),
        ('reseller_min_balance', '1.0'),
        ('migration_done', '0'),
        ('support_telegram', 'https://t.me/YOUR_SUPPORT'),
        ('support_whatsapp', 'https://wa.me/YOUR_NUMBER'),
        ('purchase_feedback', '🙏 Thanks for purchasing! Your order has been delivered successfully. ❤️'),
        ('ui_start_menu', UI_TEXTS['start_menu']),
        ('ui_download_files', UI_TEXTS['download_files']),
        ('ui_lucky_dice_result', UI_TEXTS['lucky_dice_result']),
        ('ui_vip_menu', UI_TEXTS['vip_menu']),
        ('ui_add_balance_menu', UI_TEXTS['add_balance_menu']),
        ('external_api_url', 'https://adminpanels.shop/api/reseller_v1.php'),
        ('external_api_key', ''),
        ('external_master_key', ''),
        ('external_api1_status', 'ON'),
        ('external_api2_url', 'https://keypanel.shop/reseller_gateway.php'),
        ('external_api2_key', ''),
        ('external_api2_master_key', ''),
        ('external_api2_status', 'OFF'),
    ]
    for slot, emoji_id in DEFAULT_EMOJIS.items():
        default_settings.append((f"emoji_{slot}", emoji_id))
    
    for key, val in default_settings:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

    # One-time historical repair: rebuild Total Spent and Total Orders from the
    # actual orders table. An order row is written only after a key is successfully
    # obtained/delivered, so failed API purchases are excluded automatically.
    # This repairs older users whose spent/orders counters were inflated by the
    # previous purchase-accounting bug without touching balance, products, keys,
    # payment transactions, API settings, or any order history.
    try:
        repair_flag = c.execute(
            "SELECT value FROM settings WHERE key=?",
            ("historical_spend_recalculated_v1",)
        ).fetchone()
        if not repair_flag or repair_flag[0] != "1":
            c.execute("""
                UPDATE users
                SET spent = COALESCE((
                        SELECT SUM(o.price_paid)
                        FROM orders o
                        WHERE o.user_id = users.user_id
                    ), 0.0),
                    orders_count = COALESCE((
                        SELECT COUNT(*)
                        FROM orders o
                        WHERE o.user_id = users.user_id
                    ), 0)
            """)
            c.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("historical_spend_recalculated_v1", "1")
            )
            logger.info("Historical Total Spent/Orders recalculated from successful orders.")
    except Exception as repair_err:
        logger.error("Historical spend repair failed: %s", repair_err)

    conn.commit()
    conn.close()
    # The settings table is now fully initialized. Prime the in-memory cache so
    # /start and button navigation do not open SQLite for every emoji/setting.
    try:
        _SETTINGS_CACHE.clear()
        rows = db_query("SELECT key, value FROM settings", fetchall=True, commit=False) or []
        _SETTINGS_CACHE.update({str(k): str(v or "") for k, v in rows})
    except Exception as cache_err:
        logger.debug("Settings cache warm-up skipped: %s", cache_err)

def migrate_categories() -> None:
    done = get_setting("migration_done", "0")
    
    # Seed defaults only when a setting does not already exist.
    # IMPORTANT: do not overwrite admin-customized premium emoji IDs or UI text
    # on every restart. This previously made custom emoji changes disappear.
    # Correct only the known old default startup menu. Custom Edit UI Text content is preserved.
    try:
        saved_start = get_setting("ui_start_menu", "")
        if saved_start and "𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 𝗗𝗔𝗥𝗟𝗜𝗡𝗚 𝗦𝗧𝗢𝗥𝗘" in saved_start:
            # Normalize only the old/default Startup Menu text. This specifically
            # removes any old duplicate My Key / All History entries and restores
            # the single intended My Key line (the old All History line).
            old_menu_markers = (
                "𝗔𝗹𝗹 𝗛𝗶𝘀𝘁𝗼𝗿𝘆", "All History",
                "𝗠𝘆 𝗞𝗲𝘆", "My Key",
                "𝗠𝘆 𝗣𝗿𝗼𝗳𝗶𝗹𝗲", "𝗧𝘂𝘁𝗼𝗿𝗶𝗮𝗹", "My Profile", "Tutorial"
            )
            if any(marker in saved_start for marker in old_menu_markers):
                set_setting("ui_start_menu", UI_TEXTS["start_menu"])
                logger.info("Normalized Startup Menu: All History -> My Key, no duplicate My Key section.")
    except Exception as migrate_start_err:
        logger.debug("Startup menu migration skipped: %s", migrate_start_err)

    logger.info("Checking default emoji/UI settings without overwriting custom values...")
    for slot, emoji_id in DEFAULT_EMOJIS.items():
        if not get_setting(f"emoji_{slot}", ""):
            set_setting(f"emoji_{slot}", emoji_id)

    for ui_key in ("start_menu", "add_balance_menu", "download_files", "lucky_dice_result", "vip_menu"):
        existing_ui = get_setting(f"ui_{ui_key}", "")
        if not existing_ui:
            set_setting(f"ui_{ui_key}", UI_TEXTS[ui_key])

    logger.info("Default emoji/UI settings verified; existing custom values preserved.")

    # Remove obsolete demo/gameplay video references and their old emoji settings.
    # Product rows, prices, keys, API settings, and payment data are preserved unchanged.
    try:
        db_query("UPDATE products SET demo_video='' WHERE COALESCE(demo_video, '') <> ''")
        db_query("DELETE FROM settings WHERE key IN ('emoji_gameplay', 'emoji_gameplay_video', 'cat_emoji_8 LEVEL ID')")
    except Exception as cleanup_err:
        logger.warning("Legacy demo cleanup skipped: %s", cleanup_err)

    if done == "1":
        return

    logger.info("Running category migration...")
    
    mapping = {
        "android non root panel": "ANDROID NON ROOT PANEL",
        "android root panel": "ANDROID ROOT PANEL",
        "iphone panel": "IPHONE PANEL",
        "pc panel": "PC PANEL",
        "guild calory credit": "GUILD CALORY CREDIT",
        "carrom panel": "CARROM PANEL",
    }
    for old, new in mapping.items():
        db_query("UPDATE products SET category = ? WHERE LOWER(category) = ?", (new, old))
    
    set_setting("migration_done", "1")
    logger.info("Category migration complete.")

# ==============================================================================
# 5. MIDDLEWARES & SECURITY
# ==============================================================================
class GlobalSecurityMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        now = time.time()
        if not is_admin(user_id):
            user_info = db_query("SELECT is_banned FROM users WHERE user_id=?", (user_id,), fetchone=True)
            if user_info and user_info[0] == 1:
                msg = "🚫 <b>ACCESS DENIED</b>\nYou have been banned from using this bot.\nContact support if you think this is a mistake."
                if isinstance(event, Message): await event.answer(msg)
                elif isinstance(event, CallbackQuery): await event.answer(msg, show_alert=True)
                return
                
            status_check = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
            status = status_check[0] if status_check else 'ON'
            if status == 'OFF':
                msg = "⚠️ <b>Store Maintenance</b>\n\nThe store is currently offline for updates. Please check back later!\n\nस्टोर अभी अपडेट के लिए ऑफलाइन है। कृपया बाद में चेक करें!\n\nஸ்டோர் தற்போது அப்டேட்டுக்காக ஆஃப்லைனில் உள்ளது. தயவுசெய்து பின்னர் மீண்டும் சரிபார்க்கவும்!"
                if isinstance(event, Message): await event.answer(msg)
                elif isinstance(event, CallbackQuery): await event.answer("⚠️ Bot is currently OFF for Maintenance.", show_alert=True)
                return
                
        return await handler(event, data)

dp.message.middleware(GlobalSecurityMiddleware())
dp.callback_query.middleware(GlobalSecurityMiddleware())

# ==============================================================================
# 6. FSM STATES
# ==============================================================================
class UserStates(StatesGroup):
    wait_for_ticket = State()
    wait_for_redeem = State()
    custom_amount_input = State()

class AdminStates(StatesGroup):
    add_prod_category = State()
    add_prod_panel_name = State()
    add_prod_name = State()
    add_prod_validity = State()
    add_prod_device_limit = State()
    add_prod_price = State()
    add_prod_reseller_price = State()
    add_prod_apk = State()
    add_prod_keys = State()
    
    edit_prod_field = State()
    wait_for_new_value = State()
    wait_for_add_keys = State()
    wait_for_delete_key = State()
    
    broadcast_msg = State()
    broadcast_edit_text = State()
    add_coupon_code = State()
    add_coupon_amount = State()
    add_coupon_uses = State()
    
    wait_for_fampay_api = State()
    
    ticket_reply_msg = State()
    purchase_feedback_msg = State()
    reseller_manage_id = State()
    reseller_custom_days = State()
    manage_target_user = State()
    wait_for_add_money = State()
    wait_for_minus_money = State()
    wait_for_warning = State()
    
    spin_add_reward = State()
    spin_set_limit = State()
    wait_for_howto_video = State()
    wait_for_all_files_link = State()

    # Global APK link editor: one link per panel, applied to every duration/package
    # variant belonging to that panel. This is separate from the existing
    # per-product Manage Products -> Edit APK Link flow.
    edit_all_apk_link = State()
    # Global panel-name editor: rename one panel across every duration/package
    # in the selected category. Existing per-product Edit Panel Name remains unchanged.
    edit_all_panel_name = State()
    
    edit_ui_text = State()
    edit_reseller_price = State()
    wait_for_reseller_setup_fee = State()
    wait_for_reseller_min_balance = State()
    confirm_ban = State()
    
    wait_for_support_telegram = State()
    wait_for_support_whatsapp = State()
    wait_for_category_emoji = State()
    wait_for_panel_emoji_id = State()
    wait_for_emoji_slot = State()
    wait_for_ext_url = State()
    wait_for_ext_key = State()
    wait_for_ext_master = State()
    wait_for_ext2_url = State()
    wait_for_ext2_key = State()
    wait_for_ext2_master = State()
    add_prod_external = State()
    add_prod_external_product_id = State()
    add_prod_external_duration = State()
    edit_vip_price = State()
    edit_reseller_benefits = State()
    edit_reseller_min_balance = State()
    edit_reseller_custom_days = State()

# ==============================================================================
# 7. KEYBOARDS
# ==============================================================================
def get_category_emoji(category: str) -> str:
    """Return the admin-selected custom emoji for a category, with a safe default."""
    category = str(category or "").strip().upper()

    # Admin → Set Category Emojis stores overrides as cat_emoji_<CATEGORY>.
    custom_id = get_setting(f"cat_emoji_{category}", "").strip()
    if custom_id.isdigit():
        return custom_id

    slot_map = {
        "ANDROID NON ROOT PANEL": "category_android_non_root",
        "ANDROID ROOT PANEL": "category_android_root",
        "IPHONE PANEL": "category_iphone",
        "PC PANEL": "category_pc",
        "GUILD CALORY CREDIT": "product_store",
        "CARROM PANEL": "product_store",
    }
    slot = slot_map.get(category)
    if slot:
        return get_emoji_icon(slot, DEFAULT_EMOJIS.get(slot, ""))
    return get_emoji_icon("product_store")

def get_panel_emoji(panel_name: str) -> str:
    panel_name = str(panel_name or "").strip()
    stored = get_setting(f"panel_emoji_{panel_name}", "").strip()
    if stored.isdigit():
        return stored
    return get_emoji_icon("product_store")

def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Verify Contact", request_contact=True)]], 
        resize_keyboard=True, 
        one_time_keyboard=True
    )

def refresh_reseller_status(user_id: int) -> bool:
    """Expire only admin-granted reseller plans. NULL expiry remains lifetime.
    Existing payment-based reseller activation is preserved because it keeps expiry NULL.
    """
    row = db_query("SELECT is_reseller, reseller_expires_at FROM users WHERE user_id=?", (user_id,), fetchone=True)
    if not row:
        return False
    is_res, expires_at = bool(row[0]), row[1]
    if is_res and expires_at:
        try:
            if datetime.now() >= datetime.fromisoformat(str(expires_at)):
                db_query("UPDATE users SET is_reseller=0, account_type='Regular', reseller_expires_at=NULL WHERE user_id=?", (user_id,))
                return False
        except (ValueError, TypeError):
            pass
    return is_res

def main_menu_kb(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
    sys_status = get_setting("reseller_system_status", "ON")
    vip_system = get_setting("vip_status", "OFF")
    
    is_reseller = refresh_reseller_status(user_id) if user_id else False

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="Product Store", callback_data="menu_shop",
            icon_custom_emoji_id=get_emoji_icon("product_store"),
            style="danger"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="My Profile", callback_data="menu_profile",
            icon_custom_emoji_id=get_emoji_icon("profile"),
            style="primary"
        ),
        InlineKeyboardButton(
            text="Add Balance", callback_data="menu_add_balance",
            icon_custom_emoji_id=get_emoji_icon("add_balance"),
            style="primary"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="My Key", callback_data="menu_orders",
            icon_custom_emoji_id=get_emoji_icon("history"),
            style="success"
        ),
        InlineKeyboardButton(
            text="Referral", callback_data="menu_referral",
            icon_custom_emoji_id=get_emoji_icon("referral"),
            style="success"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="How to use", callback_data="menu_how_to",
            icon_custom_emoji_id=get_emoji_icon("tutorial"),
            style="primary"
        ),
        InlineKeyboardButton(
            text="Support", callback_data="menu_support",
            icon_custom_emoji_id=get_emoji_icon("support"),
            style="success"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="Ludo Spin", callback_data="menu_spin_landing",
            icon_custom_emoji_id=get_emoji_icon("ludo_spin"),
            style="success"
        ),
        InlineKeyboardButton(
            text="Download Files", callback_data="menu_all_files",
            icon_custom_emoji_id=get_emoji_icon("download"),
            style="success"
        )
    ])
    
    extras_row = []
    if sys_status == 'ON' or is_reseller:
        extras_row.append(InlineKeyboardButton(
            text="Reseller Panel", callback_data="menu_reseller_dash",
            icon_custom_emoji_id=get_emoji_icon("reseller"),
            style="danger"
        ))
    if vip_system == 'ON':
        extras_row.append(InlineKeyboardButton(
            text="VIP Club", callback_data="menu_vip_dash",
            icon_custom_emoji_id=get_emoji_icon("vip"),
            style="success"
        ))
    if extras_row:
        kb.inline_keyboard.append(extras_row)
        
    return kb

def back_kb(callback: str = "back_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="BACK", callback_data=callback,
                icon_custom_emoji_id=get_emoji_icon("back"),
                style="danger"
            )
        ]]
    )

def admin_kb() -> InlineKeyboardMarkup:
    status = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
    status_val = status[0] if status else 'ON'
    vip_status = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    vip_val = vip_status[0] if vip_status else 'OFF'
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Bot Statistics", callback_data="admin_view_stats", icon_custom_emoji_id=get_emoji_icon("global_stats"), style="success")],
        [InlineKeyboardButton(text="👥 User Control Panel", callback_data="admin_user_control_start", icon_custom_emoji_id=get_emoji_icon("profile"), style="success")],
        [InlineKeyboardButton(text="👥 Member List", callback_data="admin_members", icon_custom_emoji_id=get_emoji_icon("profile"), style="primary")],
        [
            InlineKeyboardButton(text="➕ Add Product", callback_data="admin_add_prod", icon_custom_emoji_id=get_emoji_icon("product_store"), style="success"),
            InlineKeyboardButton(text="📦 Manage Products", callback_data="admin_manage_prods", icon_custom_emoji_id=get_emoji_icon("product_store"), style="success")
        ],
        [
            InlineKeyboardButton(text="🔗 Edit APK Links All", callback_data="admin_edit_all_apk_links", icon_custom_emoji_id=get_emoji_icon("download"), style="success"),
            InlineKeyboardButton(text="✏️ Edit Panel Names", callback_data="admin_edit_all_panel_names", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="success")
        ],
        [InlineKeyboardButton(text="🆔 Product ID", callback_data="admin_product_ids", icon_custom_emoji_id=get_emoji_icon("grid_id"), style="primary")],
        [InlineKeyboardButton(text="🛠 Maintenance Center", callback_data="admin_maintenance_center", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="danger")],
        [
            InlineKeyboardButton(text="👑 Reseller Control", callback_data="admin_reseller_menu", icon_custom_emoji_id=get_emoji_icon("reseller"), style="success"),
            InlineKeyboardButton(text="🎰 Spin Settings", callback_data="admin_spin_menu", icon_custom_emoji_id=get_emoji_icon("ludo_spin"), style="success")
        ],
        [
            InlineKeyboardButton(text="🎟 Create Coupon", callback_data="admin_create_coupon", icon_custom_emoji_id=get_emoji_icon("redeem_icon"), style="success"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast_btn", icon_custom_emoji_id=get_emoji_icon("telegram"), style="success")
        ],
        [
            InlineKeyboardButton(text="🎫 View Tickets", callback_data="admin_view_tickets", icon_custom_emoji_id=get_emoji_icon("support"), style="success"),
            InlineKeyboardButton(text="📹 Tutorial Video", callback_data="admin_set_video", icon_custom_emoji_id=get_emoji_icon("tutorial"), style="success")
        ],
        [
            InlineKeyboardButton(text="🔗 All Files Link", callback_data="admin_set_all_files", icon_custom_emoji_id=get_emoji_icon("download"), style="success"),
            InlineKeyboardButton(text="🎨 Edit All Emojis", callback_data="admin_edit_emojis", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="success")
        ],
        [
            InlineKeyboardButton(text="💳 FamPay Gateway Setup", callback_data="admin_setup_fampay", icon_custom_emoji_id=get_emoji_icon("upi"), style="success")
        ],
        [
            InlineKeyboardButton(text="🔗 External Key API", callback_data="admin_setup_external_api", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="success")
        ],
        [
            InlineKeyboardButton(text="🔗 External Key API 2", callback_data="admin_setup_external_api2", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="success")
        ],
        [
            InlineKeyboardButton(text="✏️ Edit UI Texts", callback_data="admin_edit_ui_menu", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="success"),
            InlineKeyboardButton(text="📝 Edit Reseller Price", callback_data="admin_edit_reseller_price", icon_custom_emoji_id=get_emoji_icon("money_icon"), style="success")
        ],
        [
            InlineKeyboardButton(text="📞 Set Support Links", callback_data="admin_set_support_links", icon_custom_emoji_id=get_emoji_icon("support"), style="success"),
            InlineKeyboardButton(text="🎨 Set Category Emojis", callback_data="admin_set_category_emojis", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="success")
        ],
        [
            InlineKeyboardButton(text="🖼 Set Panel Emojis", callback_data="admin_set_panel_emojis", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="success")
        ],
        [
            InlineKeyboardButton(text="💬 Purchase Feedback", callback_data="admin_purchase_feedback", icon_custom_emoji_id=get_emoji_icon("telegram"), style="success")
        ],
        [
            InlineKeyboardButton(
                text=f"Bot Status: {status_val} {'🟢' if status_val == 'ON' else '🔴'}",
                callback_data="admin_toggle_bot",
                icon_custom_emoji_id=get_emoji_icon("check_icon"),
                style="success" if status_val == 'ON' else "danger"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"VIP System: {vip_val} {'🟢' if vip_val == 'ON' else '🔴'}",
                callback_data="admin_toggle_vip_sys",
                icon_custom_emoji_id=get_emoji_icon("vip"),
                style="success" if vip_val == 'ON' else "danger"
            )
        ],
        [InlineKeyboardButton(
            text=f"💰 Edit VIP Price ({fmt_curr(VIP_PRICE_INR)})",
            callback_data="admin_edit_vip_price",
            icon_custom_emoji_id=get_emoji_icon("vip"),
            style="primary"
        )]
    ])
    return kb

def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="Back to Admin", callback_data="admin_panel_back",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ]])

# ==============================================================================
# 8. NOTIFICATIONS
# ==============================================================================
async def send_advanced_notification(user_id: int, notif_type: str, amount: float, product: str = None, key: str = None, gateway: str = "FamPay") -> None:
    user_info = db_query("SELECT first_name, phone, username, is_reseller, is_vip FROM users WHERE user_id=?", (user_id,), fetchone=True)
    
    name = user_info[0] if user_info else "Unknown"
    phone = user_info[1] if user_info and user_info[1] else "Not Provided"
    username = f"@{user_info[2]}" if user_info and user_info[2] else "None"
    
    tags = []
    if user_info and user_info[3]: tags.append("👑 Reseller")
    if user_info and user_info[4]: tags.append("🌟 VIP")
    tag_str = " | ".join(tags) if tags else "👤 Regular"
        
    time_now = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    
    if notif_type == "ORDER":
        title = "🛒 <b>NEW ORDER PROCESSED!</b> 🛒"
        details = (f"📦 <b>Product:</b> {product}\n🔑 <b>Key:</b> <code>{key}</code>\n💰 <b>Amount Paid:</b> ₹{amount:.2f}\n📅 <b>Time:</b> {time_now}")
    else:
        title = "💰 <b>NEW WALLET DEPOSIT!</b> 💰"
        details = (f"💵 <b>Amount Added:</b> ₹{amount:.2f}\n🧾 <b>Gateway:</b> {gateway}\n🆔 <b>Reference:</b> <code>{product}</code>\n📅 <b>Time:</b> {time_now}")

    msg = f"{title}\n━━━━━━━━━━━━━━━━━━\n👤 <b>Name:</b> {name}\n🆔 <b>User ID:</b> <code>{user_id}</code>\n📱 <b>Phone:</b> {phone}\n🔗 <b>Username:</b> {username}\n🏷 <b>Status:</b> {tag_str}\n━━━━━━━━━━━━━━━━━━\n{details}"
    try:
        reply_markup = None
        if notif_type == "ORDER":
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="💬 Send Purchase Feedback",
                    callback_data=f"purchase_feedback_{user_id}",
                    icon_custom_emoji_id=get_emoji_icon("telegram"),
                    style="success"
                )
            ]])
        await notify_admins(msg, parse_mode='HTML', reply_markup=reply_markup)
    except Exception as e: 
        logger.error(f"Failed to send admin notification: {e}")

# ==============================================================================
# 9. FAMPAY PAYMENT VERIFIER
# ==============================================================================
FAMPAY_DEFAULT_BASE_URL = "https://fam.aryanispe.in"
FAMPAY_ORDER_TTL = 300

def get_fampay_base_url() -> str:
    base = get_setting("fampay_base_url", FAMPAY_DEFAULT_BASE_URL).strip() or FAMPAY_DEFAULT_BASE_URL
    return base.rstrip("/")

def fampay_create_url() -> str:
    return f"{get_fampay_base_url()}/api/qr.php"

def fampay_verify_url() -> str:
    return f"{get_fampay_base_url()}/api/verify-order.php"

def mark_transaction_paid_once(order_id: str, user_id: int, amount: float) -> bool:
    """Atomically mark a pending transaction paid and credit the wallet once."""
    conn = sqlite3.connect('yp_shop.db')
    try:
        c = conn.cursor()
        c.execute("BEGIN IMMEDIATE")
        c.execute("UPDATE transactions SET status='paid' WHERE order_id=? AND user_id=? AND status='pending'", (order_id, user_id))
        if c.rowcount != 1:
            conn.rollback()
            return False
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"FamPay atomic credit failed for {order_id}: {e}")
        return False
    finally:
        conn.close()

async def run_payment_verification(user_id: int, order_id: str, reply_target: Any) -> None:
    txn = db_query("SELECT amount_inr, status, timestamp, COALESCE(gateway_amount, 0) FROM transactions WHERE order_id=? AND user_id=?", (order_id, user_id), fetchone=True)
    if not txn:
        err = "❌ Invalid or fake payment order ID."
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(err, show_alert=True)
        else: await reply_target.answer(err)
        return

    base_amount, status, created_ts, gateway_amount = txn
    if status == 'paid':
        msg = "✅ This payment has already been securely credited to your wallet."
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
        else: await reply_target.answer(msg)
        return
    if status in ('expired', 'failed') or time.time() - created_ts > FAMPAY_ORDER_TTL:
        db_query("UPDATE transactions SET status='expired' WHERE order_id=? AND status='pending'", (order_id,))
        msg = "⏳ <b>PAYMENT TRANSACTION EXPIRED</b>\n\nYour payment request has expired after 5 minutes.\nPlease create a new QR to make the payment."
        if isinstance(reply_target, CallbackQuery): await safe_edit_text(reply_target.message, msg, reply_markup=back_kb(), parse_mode='HTML')
        else: await reply_target.answer(msg, reply_markup=back_kb(), parse_mode='HTML')
        return

    api_key = get_setting("fampay_api_key", "").strip()
    if not api_key:
        msg = "⚠️ FamPay Gateway API key is not configured. Ask an admin to set it up."
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
        else: await reply_target.answer(msg)
        return

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(fampay_verify_url(), params={"api_key": api_key, "order_id": order_id}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                try: res_json = await resp.json(content_type=None)
                except Exception: res_json = {}

                if resp.status == 200 and res_json.get("status") == "success":
                    data = res_json.get("data") or {}
                    paid_amount = float(data.get("amount") or 0)
                    if gateway_amount and paid_amount and abs(paid_amount - float(gateway_amount)) > 0.011:
                        msg = "⚠️ Payment amount mismatch detected. The wallet was NOT credited."
                        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
                        else: await reply_target.answer(msg)
                        return
                    if mark_transaction_paid_once(order_id, user_id, float(base_amount)):
                        success_msg = (
                            f"🎉 <b>FAMPAY PAYMENT VERIFIED!</b>\n\n"
                            f"✅ {fmt_curr(base_amount)} has been added to your wallet.\n"
                            f"🧾 Order: <code>{order_id}</code>\n"
                            f"🔖 UTR: <code>{data.get('utr', 'N/A')}</code>"
                        )
                        if isinstance(reply_target, CallbackQuery): await safe_edit_text(reply_target.message, success_msg, reply_markup=back_kb(), parse_mode='HTML')
                        else: await reply_target.answer(success_msg, reply_markup=back_kb(), parse_mode='HTML')
                        await send_advanced_notification(user_id, "DEPOSIT", float(base_amount), product=order_id, gateway="FamPay")
                        log_activity(user_id, "DEPOSIT_SUCCESS", f"Amount: {base_amount}, Gateway: FamPay, Order: {order_id}, UTR: {data.get('utr', '')}")
                    else:
                        msg = "✅ Payment already processed. Your wallet was not credited twice."
                        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
                        else: await reply_target.answer(msg)
                    return

                if resp.status == 408 or res_json.get("status") == "expired":
                    db_query("UPDATE transactions SET status='expired' WHERE order_id=? AND status='pending'", (order_id,))
                    msg = "⏳ <b>PAYMENT TRANSACTION EXPIRED</b>\n\nYour payment request has expired after 5 minutes.\nPlease create a new QR to make the payment."
                elif resp.status == 429:
                    msg = "⏳ FamPay rate limit reached. Please wait a few seconds before verifying again."
                elif res_json.get("status") in {"pending", "processing"}:
                    msg = "⏳ Payment is still pending at FamPay. Please wait and verify again."
                else:
                    msg = f"⚠️ FamPay Gateway: {res_json.get('message', 'Payment not confirmed yet.')}"
                if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
                else: await reply_target.answer(msg)
        except Exception as e:
            logger.error(f"FamPay API Error: {e}")
            msg = "⚠️ Unable to connect to FamPay Gateway right now. Please try again shortly."
            if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
            else: await reply_target.answer(msg)

async def auto_verify_task() -> None:
    while True:
        await asyncio.sleep(15)

        pending_txns = db_query(
            "SELECT order_id, user_id, amount_inr, timestamp, "
            "COALESCE(gateway_amount, 0) "
            "FROM transactions WHERE status='pending' "
            "ORDER BY timestamp ASC LIMIT 10",
            fetchall=True
        ) or []

        if not pending_txns:
            continue

        # Expiry notification is independent of gateway verification.
        # This guarantees the customer is notified exactly when the bot-side
        # 5-minute transaction window expires.
        active_txns = []
        for order_id, user_id, amount, ts, gateway_amount in pending_txns:
            if time.time() - ts >= FAMPAY_ORDER_TTL:
                changed = db_query(
                    "UPDATE transactions SET status='expired' "
                    "WHERE order_id=? AND status='pending'",
                    (order_id,)
                )
                try:
                    await bot.send_message(
                        user_id,
                        "⏳ <b>PAYMENT TRANSACTION EXPIRED</b>\n\n"
                        "Your payment request has expired after 5 minutes.\n"
                        "Please create a new QR to make the payment.",
                        parse_mode='HTML'
                    )
                except Exception as notify_err:
                    logger.warning(
                        f"Could not send payment-expiry notification "
                        f"for {order_id}: {notify_err}"
                    )
                log_activity(
                    user_id,
                    "DEPOSIT_EXPIRED",
                    f"Payment transaction expired after 5 minutes. Order: {order_id}"
                )
            else:
                active_txns.append((order_id, user_id, amount, ts, gateway_amount))

        api_key = get_setting("fampay_api_key", "").strip()
        if not api_key or not active_txns:
            continue

        async with aiohttp.ClientSession() as session:
            for order_id, user_id, amount, ts, gateway_amount in active_txns:
                try:
                    async with session.get(
                        fampay_verify_url(),
                        params={"api_key": api_key, "order_id": order_id},
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:
                        try:
                            res_json = await resp.json(content_type=None)
                        except Exception:
                            res_json = {}

                        if resp.status == 200 and res_json.get("status") == "success":
                            data = res_json.get("data") or {}
                            paid_amount = float(data.get("amount") or 0)

                            if gateway_amount and paid_amount and abs(
                                paid_amount - float(gateway_amount)
                            ) > 0.011:
                                logger.warning(
                                    f"FamPay amount mismatch for {order_id}: "
                                    f"expected {gateway_amount}, got {paid_amount}"
                                )
                                continue

                            if mark_transaction_paid_once(
                                order_id, user_id, float(amount)
                            ):
                                try:
                                    await bot.send_message(
                                        user_id,
                                        f"✨ <b>FAMPAY AUTO-VERIFIED!</b>\n\n"
                                        f"✅ {fmt_curr(amount)} has been added to your balance.\n"
                                        f"🧾 Order: <code>{order_id}</code>",
                                        parse_mode='HTML'
                                    )
                                except Exception:
                                    pass

                                await send_advanced_notification(
                                    user_id,
                                    "DEPOSIT",
                                    float(amount),
                                    product=order_id,
                                    gateway="FamPay Auto"
                                )
                                log_activity(
                                    user_id,
                                    "DEPOSIT_AUTO_SUCCESS",
                                    f"Amount: {amount}, Gateway: FamPay Auto, "
                                    f"Order: {order_id}, UTR: {data.get('utr', '')}"
                                )

                        elif resp.status == 408 or res_json.get("status") == "expired":
                            db_query(
                                "UPDATE transactions SET status='expired' "
                                "WHERE order_id=? AND status='pending'",
                                (order_id,)
                            )
                            try:
                                await bot.send_message(
                                    user_id,
                                    "⏳ <b>PAYMENT TRANSACTION EXPIRED</b>\n\n"
                                    "Your payment request has expired.\n"
                                    "Please create a new QR to make the payment.",
                                    parse_mode='HTML'
                                )
                            except Exception:
                                pass

                except Exception as e:
                    logger.debug(
                        f"FamPay auto-verify exception for {order_id}: {e}"
                    )

# ==============================================================================
# 10. ONBOARDING & START
# ==============================================================================
async def _safe_welcome_sticker(message: Message):
    try:
        await message.answer_sticker(WELCOME_STICKER_ID)
    except Exception:
        pass

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    # Send the welcome sticker in the background so /start does not wait for it.
    if WELCOME_STICKER_ID and not WELCOME_STICKER_ID.endswith("..."):
        asyncio.create_task(_safe_welcome_sticker(message))
    
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("v_"):
        order_id = args[1].split("v_")[1]
        msg = await message.answer("🔄 <b>Verifying your payment securely...</b>\n<i>Connecting to gateway...</i>", parse_mode='HTML')
        await run_payment_verification(message.from_user.id, order_id, msg)
        return

    direct_product_id = None
    if len(args) > 1 and args[1].startswith("product_"):
        try:
            direct_product_id = int(args[1].split("product_", 1)[1])
        except (ValueError, IndexError):
            direct_product_id = None

    # Price-list deep link: /start plist_<anchor_product_id>
    # This is separate from the existing product_<id> deep link so the
    # existing direct-product/payment flow remains unchanged.
    price_list_anchor_id = None
    if len(args) > 1 and args[1].startswith("plist_"):
        try:
            price_list_anchor_id = int(args[1].split("plist_", 1)[1])
        except (ValueError, IndexError):
            price_list_anchor_id = None

    referred_by = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try: referred_by = int(args[1].split("_")[1])
        except: pass

    user = db_query("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,), fetchone=True)
    current_username = message.from_user.username or ""
    db_query("UPDATE users SET username=? WHERE user_id=?", (current_username, message.from_user.id))

    if not user or not user[0]:
        db_query("INSERT OR IGNORE INTO users (user_id, first_name, username, referred_by, joined_date) VALUES (?, ?, ?, ?, ?)", 
                 (message.from_user.id, message.from_user.first_name, current_username, referred_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        if direct_product_id is not None:
            await state.update_data(pending_product_id=direct_product_id)
        if price_list_anchor_id is not None:
            await state.update_data(pending_price_list_anchor_id=price_list_anchor_id)
        asyncio.create_task(asyncio.to_thread(log_activity, message.from_user.id, "ACCOUNT_CREATED"))
        await message.answer("<b>🛡 VERIFICATION REQUIRED</b>\n\nTo safeguard your orders and account, we need to verify you.\n👇 <b>Tap the button below:</b>", parse_mode='HTML', reply_markup=contact_kb())
    else:
        if price_list_anchor_id is not None:
            await show_price_list_from_anchor(message, price_list_anchor_id)
            return
        if direct_product_id is not None:
            await show_direct_product(message, direct_product_id)
            return
        asyncio.create_task(asyncio.to_thread(log_activity, message.from_user.id, "CMD_START"))
        await send_main_menu(message)

async def show_price_list_from_anchor(message: Message, anchor_id: int):
    """Open the complete price list represented by one stable product ID.

    The anchor is an existing product row. No product/payment data is changed;
    all package rows are read from the existing products table.
    """
    anchor = db_query(
        "SELECT category, panel_name FROM products WHERE id=? AND is_active=1",
        (anchor_id,), fetchone=True
    )
    if not anchor:
        await message.answer("❌ Price list not found.")
        return

    category, panel_name = (anchor[0] or "").strip(), (anchor[1] or "").strip()
    if panel_name:
        prods = db_query(
            """SELECT id, name, price_inr, stock, reseller_price, validity,
                      device_limit, external_enabled, maintenance
               FROM products
               WHERE category=? AND panel_name=? AND is_active=1
               ORDER BY name""",
            (category, panel_name), fetchall=True
        )
        header = f"{category} - {panel_name}"
    else:
        prods = db_query(
            """SELECT id, name, price_inr, stock, reseller_price, validity,
                      device_limit, external_enabled, maintenance
               FROM products
               WHERE category=? AND is_active=1
               ORDER BY name""",
            (category,), fetchall=True
        )
        header = category

    if not prods:
        await message.answer("❌ No active products found for this price list.")
        return

    # If the selected panel is fully under maintenance, do not expose its price list.
    if panel_name:
        state_row = db_query(
            "SELECT COUNT(*), SUM(CASE WHEN maintenance=1 THEN 1 ELSE 0 END) "
            "FROM products WHERE category=? AND panel_name=? AND is_active=1",
            (category, panel_name), fetchone=True
        )
        total = int(state_row[0] or 0) if state_row else 0
        on_count = int(state_row[1] or 0) if state_row else 0
        if total > 0 and on_count == total:
            await message.answer("🛠️ <b>This product is under maintenance.</b>", parse_mode="HTML")
            return

    user = db_query(
        "SELECT is_reseller, is_vip FROM users WHERE user_id=?",
        (message.from_user.id,), fetchone=True
    )
    is_reseller = refresh_reseller_status(message.from_user.id) if user else False
    is_vip = bool(user[1]) if user else False

    # CUSTOMER VIEW:
    # Never expose the internal Telegram/DB Product ID or Price List ID here.
    # The anchor_id is used internally only to resolve this deep link to the
    # correct price list; customers see only the actual package/price details.
    text = (
        f"{get_emoji('product_store')} <b><u>{header.upper()} PACKAGES</u></b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[])

    for prod in sorted(prods, key=lambda row: natural_sort_key(row[1])):
        prod_id, package_name, normal_price, stock, reseller_price, validity, device, external_enabled, maintenance = prod
        normal_price = float(normal_price or 0.0)
        reseller_price = float(reseller_price or 0.0)
        base_price = reseller_price if is_reseller else normal_price
        display_price = (
            base_price - (base_price * (VIP_DISCOUNT_PERCENTAGE / 100))
            if is_vip else base_price
        )
        stock_status = (
            "♾️ API Available" if external_enabled
            else ("✅ In Stock" if stock and stock > 0 else "❌ Out of Stock")
        )
        if maintenance:
            stock_status = "Maintenance"

        text += f"{get_emoji('package_name')} <b>{package_name}</b>\n"
        if is_reseller or is_vip:
            text += f"{get_emoji('price')} Regular Price: <s>{fmt_curr(normal_price)}</s>\n"
            if is_reseller and not is_vip:
                text += f"👑 <b>Reseller Price: {fmt_curr(display_price)}</b>\n"
            elif is_vip and not is_reseller:
                text += f"🌟 <b>VIP Price: {fmt_curr(display_price)}</b>\n"
            else:
                text += f"👑🌟 <b>Super Price: {fmt_curr(display_price)}</b>\n"
        else:
            text += f"{get_emoji('price')} Price: {fmt_curr(normal_price)}\n"
        text += f"{get_emoji('device_limit')} Limit: {device} | 📦 {stock_status}\n\n"

        if maintenance:
            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=package_name,
                    callback_data=f"maintenance_product_{prod_id}",
                    icon_custom_emoji_id=get_emoji_icon("maintenance"),
                    style="danger"
                )
            ])
        elif external_enabled or (stock and stock > 0):
            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"BUY {package_name} - {fmt_curr(display_price)}",
                    callback_data=f"buy_{prod_id}",
                    icon_custom_emoji_id=get_emoji_icon("buy"),
                    style="success"
                )
            ])
        else:
            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"❌ {package_name} (Out of Stock)",
                    callback_data="ignore_stock_click",
                    style="danger"
                )
            ])

    text += f"{get_emoji('point_down')} <b>Select package below to instantly purchase:</b>"
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="BACK TO STORE",
            callback_data="menu_shop",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


async def show_direct_product(message: Message, prod_id: int):
    prod = db_query(
        "SELECT id, name, price_inr, stock, reseller_price, validity, device_limit, external_enabled, maintenance "
        "FROM products WHERE id=? AND is_active=1",
        (prod_id,), fetchone=True
    )
    if not prod:
        await message.answer("❌ Product not found.")
        return

    user = db_query("SELECT is_reseller, is_vip FROM users WHERE user_id=?", (message.from_user.id,), fetchone=True)
    is_reseller = refresh_reseller_status(message.from_user.id) if user else False
    is_vip = bool(user[1]) if user else False

    _, name, normal_price, stock, reseller_price, validity, device_limit, external_enabled, maintenance = prod
    normal_price = float(normal_price or 0.0)
    reseller_price = float(reseller_price or 0.0)
    base_price = reseller_price if is_reseller else normal_price
    display_price = base_price - (base_price * (VIP_DISCOUNT_PERCENTAGE / 100)) if is_vip else base_price

    if maintenance:
        await message.answer(
            "🛠️ <b>This product is under maintenance.</b>",
            reply_markup=back_kb("menu_shop"),
            parse_mode="HTML"
        )
        return

    stock_ok = bool(external_enabled) or (stock is not None and stock > 0)
    if not stock_ok:
        await message.answer(
            f"{get_emoji('package_name')} <b>{name}</b>\n\n{get_emoji('validity')} Validity: {validity}\n{get_emoji('device_limit')} Device Limit: {device_limit}\n{get_emoji('price')} Price: {fmt_curr(display_price)}\n\n❌ <b>Out of Stock</b>"
        )
        return

    text = (
        f"📦 <b>{name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{get_emoji('validity')} <b>Validity:</b> {validity}\n"
        f"{get_emoji('device_limit')} <b>Device Limit:</b> {device_limit}\n"
        f"{get_emoji('price')} <b>Price:</b> {fmt_curr(display_price)}\n\n"
        "Select an option below:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"BUY - {fmt_curr(display_price)}",
            callback_data=f"buy_{prod_id}",
            icon_custom_emoji_id=get_emoji_icon("buy"),
            style="success"
        )],
        [InlineKeyboardButton(
            text="BACK TO STORE",
            callback_data="menu_shop",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.message(F.contact)
async def handle_contact(message: Message, state: FSMContext):
    if message.contact.user_id == message.from_user.id:
        db_query("UPDATE users SET phone=? WHERE user_id=?", (message.contact.phone_number, message.from_user.id))
        referrer = db_query("SELECT referred_by FROM users WHERE user_id=?", (message.from_user.id,), fetchone=True)
        if referrer and referrer[0]:
            db_query("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id=?", (referrer[0],))
            try: await bot.send_message(referrer[0], f"🎉 <b>Referral Success!</b>\nUser <b>{message.from_user.first_name}</b> joined using your link!", parse_mode='HTML')
            except: pass
        log_activity(message.from_user.id, "CONTACT_VERIFIED")
        pending = await state.get_data()
        pending_product_id = pending.get("pending_product_id")
        pending_price_list_anchor_id = pending.get("pending_price_list_anchor_id")
        await state.clear()
        await message.answer("✅ Verification successful! Welcome to the system.", reply_markup=ReplyKeyboardRemove())
        if pending_price_list_anchor_id is not None:
            await show_price_list_from_anchor(message, int(pending_price_list_anchor_id))
        elif pending_product_id is not None:
            await show_direct_product(message, int(pending_product_id))
        else:
            await send_main_menu(message)
    else:
        await message.answer("❌ Security Alert: Please share your OWN contact using the provided button.")

async def send_main_menu(ctx: Any):
    text = get_ui_text("start_menu")
    kb = main_menu_kb(ctx.from_user.id)
    await send_ui_content(ctx, "start_menu", text, reply_markup=kb)

@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    try:
        await call.answer()
    except Exception:
        pass
    await state.clear()
    asyncio.create_task(asyncio.to_thread(log_activity, call.from_user.id, "RETURN_MAIN_MENU"))
    await send_main_menu(call)

# ==============================================================================
# 11. ADD BALANCE
# ==============================================================================
@dp.callback_query(F.data == "menu_add_balance")
async def select_gateway_menu(call: CallbackQuery):
    log_activity(call.from_user.id, "VIEW_ADD_BALANCE")
    text = get_ui_text("add_balance_menu")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="PAY WITH UPI", callback_data="gateway_fampay", icon_custom_emoji_id=get_emoji_icon("upi"), style="success")],
        [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("product_add_balance_"))
async def product_add_balance_handler(call: CallbackQuery):
    try:
        prod_id = int(call.data.split("_", 3)[3])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid product.", show_alert=True)

    log_activity(call.from_user.id, "VIEW_ADD_BALANCE_FROM_PRODUCT")
    text = get_ui_text("add_balance_menu")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="PAY WITH UPI", callback_data="gateway_fampay", icon_custom_emoji_id=get_emoji_icon("upi"), style="success")],
        [InlineKeyboardButton(text="BACK", callback_data=f"buy_{prod_id}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')
    await call.answer()


# ==============================================================================
# 12. FAMPAY PAYMENT FLOW
# ==============================================================================
@dp.callback_query(F.data == "gateway_fampay")
async def add_balance_fampay(call: CallbackQuery):
    text = "💳 <b>— FAMPAY PAYMENT —</b> 💳\n\nSelect amount to add to your wallet:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₹50", callback_data="pay_50", icon_custom_emoji_id=get_emoji_icon("money_icon"), style="primary"), InlineKeyboardButton(text="₹100", callback_data="pay_100", icon_custom_emoji_id=get_emoji_icon("money_icon"), style="primary")],
        [InlineKeyboardButton(text="₹200", callback_data="pay_200", icon_custom_emoji_id=get_emoji_icon("money_icon"), style="primary"), InlineKeyboardButton(text="₹500", callback_data="pay_500", icon_custom_emoji_id=get_emoji_icon("money_icon"), style="primary")],
        [InlineKeyboardButton(text="Custom Amount", callback_data="custom_deposit_keypad", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")],
        [InlineKeyboardButton(text="Back", callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "custom_deposit_keypad")
async def show_custom_keypad(call: CallbackQuery, state: FSMContext):
    try:
        await call.answer()
    except Exception:
        pass
    await state.set_state(UserStates.custom_amount_input)
    await state.update_data(amount_str="0")
    await show_keypad(call.message)

async def show_keypad(message: Message, amount_str: str = "0"):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="      1      ", callback_data="kp_1", style="primary"), InlineKeyboardButton(text="      2      ", callback_data="kp_2", style="primary"), InlineKeyboardButton(text="      3      ", callback_data="kp_3", style="primary")],
        [InlineKeyboardButton(text="      4      ", callback_data="kp_4", style="primary"), InlineKeyboardButton(text="      5      ", callback_data="kp_5", style="primary"), InlineKeyboardButton(text="      6      ", callback_data="kp_6", style="primary")],
        [InlineKeyboardButton(text="      7      ", callback_data="kp_7", style="primary"), InlineKeyboardButton(text="      8      ", callback_data="kp_8", style="primary"), InlineKeyboardButton(text="      9      ", callback_data="kp_9", style="primary")],
        [InlineKeyboardButton(text="    ⌫    ", callback_data="kp_backspace", style="danger"), InlineKeyboardButton(text="      0      ", callback_data="kp_0", style="primary"), InlineKeyboardButton(text="    C    ", callback_data="kp_clear", style="danger")],
        [InlineKeyboardButton(text=f"Confirm (₹{amount_str})", callback_data="kp_confirm", icon_custom_emoji_id=get_emoji_icon("check_icon"), style="success")],
        [InlineKeyboardButton(text="Cancel", callback_data="gateway_fampay", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await safe_edit_text(message, f"💳 <b>Enter FamPay Amount (₹):</b>\n\nCurrent: ₹{amount_str}", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("kp_"), UserStates.custom_amount_input)
async def keypad_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount_str = data.get("amount_str", "0")
    action = call.data.split("_")[1]

    if action == "confirm":
        if amount_str == "0":
            await call.answer("Amount cannot be zero.", show_alert=True)
            return
        try:
            amount = float(amount_str)
            if amount < 1:
                await call.answer("Minimum deposit is ₹1.", show_alert=True)
                return
            state_data = await state.get_data()
            await state.clear()
            await safe_edit_text(call.message, "⏳ <b>Creating secure FamPay payment...</b>", parse_mode="HTML")
            # Product QR uses the exact same FamPay order creation/verification
            # connection as Add Balance. Nothing in the existing FamPay flow is changed.
            await generate_fampay_order(call.from_user.id, amount, call.message)
        except ValueError:
            await call.answer("Invalid amount.", show_alert=True)
        return

    if action == "backspace":
        amount_str = amount_str[:-1] if len(amount_str) > 1 else "0"
    elif action == "clear":
        amount_str = "0"
    else:
        amount_str = action if amount_str == "0" else amount_str + action
        amount_str = amount_str[:6]

    await state.update_data(amount_str=amount_str)
    await show_keypad(call.message, amount_str)
    await call.answer()


@dp.callback_query(F.data.startswith("pay_"))
async def process_fampay_payment_callback(call: CallbackQuery):
    try: inr_amount = float(call.data.split("_")[1])
    except (ValueError, IndexError):
        await call.answer("Invalid amount.", show_alert=True)
        return
    await safe_edit_text(call.message, "⏳ <b>Creating secure FamPay payment...</b>", parse_mode='HTML')
    await generate_fampay_order(call.from_user.id, inr_amount, call.message)

async def generate_fampay_order(user_id: int, inr_amount: float, message_obj: Message) -> None:
    api_key = get_setting("fampay_api_key", "").strip()
    if not api_key:
        return await safe_edit_text(message_obj, "⚠️ <b>FamPay Gateway is not configured.</b>\nAdmin must set the FamPay API key first.", reply_markup=back_kb("gateway_fampay"), parse_mode='HTML')

    current_time = int(time.time())
    order_id = f"FAM{user_id}{current_time}{random.randint(1000, 9999)}"
    bot_deep_link = f"https://t.me/{BOT_USERNAME}?start=v_{order_id}"
    db_query("INSERT INTO transactions (order_id, user_id, amount_inr, gateway_amount, status, timestamp) VALUES (?, ?, ?, ?, 'pending', ?)", (order_id, user_id, inr_amount, inr_amount, current_time))

    try:
        async with aiohttp.ClientSession() as session:
            params = {"api_key": api_key, "amount": f"{inr_amount:.2f}", "redirect_url": bot_deep_link}
            async with session.get(fampay_create_url(), params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                try: res_data = await resp.json(content_type=None)
                except Exception: res_data = {}
                if resp.status != 200 or res_data.get("status") != "success":
                    db_query("UPDATE transactions SET status='failed' WHERE order_id=? AND status='pending'", (order_id,))
                    return await safe_edit_text(message_obj, f"❌ <b>FamPay Gateway Error:</b> {res_data.get('message', f'HTTP {resp.status}')}", reply_markup=back_kb("gateway_fampay"), parse_mode='HTML')
                data = res_data.get("data") or {}
                gateway_order_id = data.get("order_id") or order_id
                qr_url = data.get("qr_url") or ""
                checkout_url = data.get("checkout_url") or qr_url
                payable_amount = float(data.get("payable_amount") or inr_amount)
                expires_at = "5 minutes"
                if gateway_order_id != order_id:
                    db_query("UPDATE transactions SET order_id=?, gateway_amount=? WHERE order_id=?", (gateway_order_id, payable_amount, order_id))
                    order_id = gateway_order_id
                else:
                    db_query("UPDATE transactions SET gateway_amount=? WHERE order_id=?", (payable_amount, order_id))
                if not checkout_url:
                    db_query("UPDATE transactions SET status='failed' WHERE order_id=? AND status='pending'", (order_id,))
                    return await safe_edit_text(message_obj, "❌ FamPay did not return a payment URL. Please try again.", reply_markup=back_kb("gateway_fampay"), parse_mode='HTML')
                rows = [[InlineKeyboardButton(text="Pay with QR", url=checkout_url, icon_custom_emoji_id=get_emoji_icon("upi"), style="success")]]
                rows += [[InlineKeyboardButton(text="VERIFY PAYMENT", callback_data=f"verify_{order_id}", icon_custom_emoji_id=get_emoji_icon("check_icon"), style="primary")], [InlineKeyboardButton(text="Cancel Transaction", callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]]
                text = (f"🧾 <b>FAMPAY PAYMENT CREATED</b>\n\n💰 Wallet Credit: <b>{fmt_curr(inr_amount)}</b>\n💳 Exact Payable Amount: <b>₹{payable_amount:.2f}</b>\n🆔 Order ID: <code>{order_id}</code>\n⏳ Expires: <b>{expires_at}</b>\n\n"
                        "1️⃣ Tap <b>Pay with QR</b>.\n2️⃣ Complete the payment for the exact amount shown.\n3️⃣ Return here and tap <b>Verify Payment</b>.\n\n"
                        "🔒 Duplicate verification is blocked; one successful payment can credit the wallet only once.")
                log_activity(user_id, "GENERATE_FAMPAY_INVOICE", f"Amount: {inr_amount}, Payable: {payable_amount}, Order: {order_id}")

                keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
                await safe_edit_text(message_obj, text, reply_markup=keyboard, parse_mode='HTML')
    except Exception as e:
        db_query("UPDATE transactions SET status='failed' WHERE order_id=? AND status='pending'", (order_id,))
        logger.error(f"FamPay create-order error: {e}")
        await safe_edit_text(message_obj, "❌ <b>FamPay connection error.</b> Please try again later.", reply_markup=back_kb("gateway_fampay"), parse_mode='HTML')

@dp.callback_query(F.data.startswith("verify_"))
async def manual_verify_callback(call: CallbackQuery):
    await run_payment_verification(call.from_user.id, call.data.split("_", 1)[1], call)

# ==============================================================================
# 13. SHOP – with uppercase categories and new point_down emoji
# ==============================================================================
@dp.callback_query(F.data == "menu_shop")
async def view_shop_panels(call: CallbackQuery):
    # Acknowledge BACK/SHOP navigation immediately so Telegram clears the button spinner
    # before the database/menu rendering work begins. No shop logic is changed.
    try:
        await call.answer()
    except Exception:
        pass
    asyncio.create_task(asyncio.to_thread(log_activity, call.from_user.id, "VIEW_SHOP"))
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = f"{get_emoji('product_store')} <b><u>SELECT PRODUCT PANEL</u></b>\n━━━━━━━━━━━━━━━━━━\n\n{get_emoji('point_down')} <b>Choose a panel to view its packages:</b>"
    category_counts_rows = db_query(
        "SELECT category, COUNT(*) FROM products WHERE is_active=1 GROUP BY category",
        fetchall=True
    ) or []
    category_counts = {}
    for row in category_counts_rows:
        key = str(row[0] or '').strip().upper()
        if key:
            category_counts[key] = category_counts.get(key, 0) + int(row[1] or 0)
    for cat in FIXED_CATEGORIES:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=cat,
                callback_data=f"cat_{cat[:30]}",
                icon_custom_emoji_id=get_category_emoji(cat),
                style="primary"
            )
        ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    try:
        await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')
    except TelegramBadRequest as e:
        # If the callback came from an old/deleted message, Telegram can reject
        # edit_text with MESSAGE_ID_INVALID. Show the same shop menu as a new
        # message instead; do not change the shop/payment/product flow.
        if "MESSAGE_ID_INVALID" in str(e):
            await call.message.answer(text, reply_markup=kb, parse_mode='HTML')
        else:
            raise

@dp.callback_query(F.data.startswith("cat_"))
async def view_panel_names(call: CallbackQuery):
    # Acknowledge navigation immediately; keep all existing panel/category logic unchanged.
    try:
        await call.answer()
    except Exception:
        pass
    category = call.data.split("cat_", 1)[1]
    panel_rows = db_query(
        "SELECT panel_name, COUNT(*), SUM(CASE WHEN maintenance=1 THEN 1 ELSE 0 END) "
        "FROM products WHERE category LIKE ? AND is_active=1 AND panel_name != '' GROUP BY panel_name",
        (category + '%',), fetchall=True
    ) or []
    panel_rows = sorted(panel_rows, key=lambda row: natural_sort_key(row[0]))
    panel_names = [(row[0],) for row in panel_rows]
    if not panel_names:
        prods = db_query("SELECT id, name, price_inr, stock, reseller_price, validity, device_limit, external_enabled FROM products WHERE category LIKE ? AND is_active=1", (category + '%',), fetchall=True)
        if not prods: return await call.answer("❌ No products available in this category yet.", show_alert=True)
        await show_products_for_panel(call, prods, category, back_callback="menu_shop")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = f"{get_emoji('product_store')} <b><u>{category.upper()} PANELS</u></b>\n━━━━━━━━━━━━━━━━━━\n\n{get_emoji('point_down')} <b>Choose a panel name:</b>"
    try:
        category_index = FIXED_CATEGORIES.index(category)
    except ValueError:
        category_index = 0

    for panel_index, pn in enumerate(panel_names):
        panel = pn[0]
        callback_data = f"pnl_{category_index}_{panel_index}"
        matching = next((row for row in panel_rows if str(row[0] or '') == panel), None)
        total = int(matching[1] or 0) if matching else 0
        on_count = int(matching[2] or 0) if matching else 0
        is_maintenance = total > 0 and on_count == total
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=panel,
                callback_data=callback_data,
                # Maintenance must not add any hammer/wrench/premium emoji.
                # Keep the original panel name intact and append the plain status text.
                icon_custom_emoji_id=get_emoji_icon("maintenance") if is_maintenance else (get_panel_emoji(panel) or get_emoji_icon("product_store")),
                style="danger" if is_maintenance else "success"
            )
        ])
    # Back follows the actual navigation path: panel-name list -> category list.
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK TO PANEL", callback_data="menu_shop", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    try:
        await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')
    except TelegramBadRequest as e:
        # Telegram raises this when the message already has exactly the same content/buttons.
        if "message is not modified" not in str(e).lower():
            raise
        await call.answer()

@dp.callback_query(F.data.startswith("pnl_"))
async def view_products_for_panel(call: CallbackQuery):
    parts = call.data.split("_")
    if len(parts) != 3:
        return await call.answer("Invalid selection.", show_alert=True)

    try:
        category_index = int(parts[1])
        panel_index = int(parts[2])
    except ValueError:
        return await call.answer("Invalid selection.", show_alert=True)

    if not (0 <= category_index < len(FIXED_CATEGORIES)):
        return await call.answer("Invalid category.", show_alert=True)

    category = FIXED_CATEGORIES[category_index]

    # Resolve the selected panel from the same sorted panel list used to
    # build the pnl_<category_index>_<panel_index> buttons. The previous
    # version used panel_name here before defining it, causing every panel
    # button press to crash with NameError.
    panel_names = db_query(
        "SELECT DISTINCT panel_name FROM products "
        "WHERE category LIKE ? AND is_active=1 AND panel_name != ''",
        (category + '%',), fetchall=True
    ) or []
    panel_names = sorted(panel_names, key=lambda row: natural_sort_key(row[0]))
    if not (0 <= panel_index < len(panel_names)):
        return await call.answer("Invalid panel selection.", show_alert=True)
    panel_name = str(panel_names[panel_index][0] or '').strip()
    if not panel_name:
        return await call.answer("Invalid panel selection.", show_alert=True)

    prods = db_query(
        "SELECT id, name, price_inr, stock, reseller_price, validity, device_limit, external_enabled, maintenance "
        "FROM products WHERE category LIKE ? AND panel_name=? AND is_active=1",
        (category + '%', panel_name), fetchall=True
    ) or []
    total = len(prods)
    on_count = sum(1 for row in prods if int(row[8] or 0) == 1)
    if total > 0 and on_count == total:
        return await call.answer("🛠️ This product is under maintenance.", show_alert=True)
    if not prods:
        return await call.answer("No products found for this panel.", show_alert=True)

    # Acknowledge only after validation so maintenance/no-product alerts still
    # work, while successful selections clear Telegram's loading spinner.
    try:
        await call.answer()
    except Exception:
        pass

    await show_products_for_panel(
        call,
        prods,
        f"{category} - {panel_name}",
        back_callback=f"cat_{category[:30]}"
    )

async def show_products_for_panel(call: CallbackQuery, prods: List[Tuple], header: str, back_callback: str = "menu_shop"):
    """Show the products for the selected panel and remember the correct parent for Back."""
    user = db_query("SELECT is_reseller, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    is_reseller = refresh_reseller_status(call.from_user.id) if user else False
    is_vip = bool(user[1]) if user else False
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = f"{get_emoji('product_store')} <b><u>{header.upper()} PACKAGES</u></b>\n━━━━━━━━━━━━━━━━━━\n\n"
    # Always show packages in natural A-Z / 1-2-10 order, independent of add time.
    prods = sorted(prods or [], key=lambda row: natural_sort_key(row[1]))
    for p in prods:
        prod_id, package_name, normal_price, stock, reseller_price, validity, device, external_enabled = p[:8]
        inline_maintenance = bool(p[8]) if len(p) > 8 else False
        normal_price = float(normal_price) if normal_price is not None else 0.0
        reseller_price = float(reseller_price) if reseller_price is not None else 0.0
        base_price = reseller_price if is_reseller else normal_price
        if is_vip: display_price = base_price - (base_price * (VIP_DISCOUNT_PERCENTAGE / 100))
        else: display_price = base_price
        product_maintenance = inline_maintenance
        stock_status = "♾️ API Available" if external_enabled else ("✅ In Stock" if stock > 0 else "❌ Out of Stock")
        if product_maintenance:
            stock_status = "Maintenance"
        text += f"{get_emoji('validity')} <b>Validity: {package_name}</b>\n"
        if is_reseller or is_vip:
            text += f"{get_emoji('price')} Regular Price: <s>{fmt_curr(normal_price)}</s>\n"
            if is_reseller and not is_vip: text += f"👑 <b>Reseller Price: {fmt_curr(display_price)}</b>\n"
            elif is_vip and not is_reseller: text += f"🌟 <b>VIP Price: {fmt_curr(display_price)}</b>\n"
            else: text += f"👑🌟 <b>Super Price: {fmt_curr(display_price)}</b>\n"
        else: text += f"{get_emoji('price')} Price: {fmt_curr(normal_price)}\n"
        text += f"{get_emoji('device_limit')} Limit: {device} | 📦 {stock_status}\n\n"
        if product_maintenance:
            # Maintenance packages keep the full original product name and append a plain status label.
            # Normal BUY buttons below are unchanged.
            kb.inline_keyboard.append([InlineKeyboardButton(
                        text=package_name,
                        callback_data=f"maintenance_product_{prod_id}",
                        icon_custom_emoji_id=get_emoji_icon("maintenance"),
                        style="danger"
                    )])
        elif external_enabled or stock > 0:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"BUY {package_name} - {fmt_curr(display_price)}", callback_data=f"buy_{prod_id}", icon_custom_emoji_id=get_emoji_icon("buy"), style="success")])
        else:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ {package_name} (Out of Stock)", callback_data="ignore_stock_click", style="danger")])
    text += f"{get_emoji('point_down')} <b>Select package below to instantly purchase:</b>"

    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK TO PANEL", callback_data=back_callback, icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "ignore_stock_click")
async def ignore_stock_click(call: CallbackQuery):
    await call.answer("⚠️ This duration is completely Out of Stock! Admins have been notified to refill.", show_alert=True)

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(call: CallbackQuery):
    """First click only shows the price/confirmation screen; it never charges the user."""
    try:
        prod_id = int(call.data.split("_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid product selection.", show_alert=True)

    prod = db_query("""
        SELECT name, price_inr, stock, validity, reseller_price, external_enabled
        FROM products WHERE id=? AND is_active=1
    """, (prod_id,), fetchone=True)
    user = db_query("SELECT balance, is_reseller, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if not prod:
        return await call.answer("❌ Product not found.", show_alert=True)
    if not user:
        return await call.answer("❌ User account not found.", show_alert=True)

    normal_price = float(prod[1] or 0.0)
    reseller_price = float(prod[4] or 0.0)
    base_price = reseller_price if refresh_reseller_status(call.from_user.id) else normal_price
    final_price = base_price - (base_price * (VIP_DISCOUNT_PERCENTAGE / 100)) if bool(user[2]) else base_price
    stock_ok = bool(prod[5]) or (prod[2] is not None and prod[2] > 0)
    if not stock_ok:
        return await call.answer("❌ This product is out of stock!", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Pay with Wallet Balance - {fmt_curr(final_price)}", callback_data=f"wallet_confirm_{prod_id}", icon_custom_emoji_id=get_emoji_icon("wallet_balance"), style="success")],
        [InlineKeyboardButton(text="PAY WITH DIRECT QR", callback_data=f"product_add_balance_{prod_id}", icon_custom_emoji_id=get_emoji_icon("pay_direct_qr"), style="primary")],
        [InlineKeyboardButton(text="Add Balance Plus First", callback_data=f"product_add_balance_{prod_id}", icon_custom_emoji_id=get_emoji_icon("add_balance_first"), style="primary")],
        [InlineKeyboardButton(text="Back to Panel", callback_data=f"back_product_{prod_id}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    text = (
        f"{get_emoji('buy')} <b>CONFIRM PURCHASE</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Product:</b> {prod[0]}\n"
        f"⏱ <b>Validity:</b> {prod[3]}\n"
        f"💰 <b>Price:</b> {fmt_curr(final_price)}\n\n"
        f"💳 <b>Wallet Balance</b> — use your existing wallet balance.\n"
        f"🇮🇳 <b>Pay with Direct QR</b> — go directly to the existing Add Balance menu.\n\n"
        f"Choose a payment method below."
    )
    await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith("back_product_"))
async def back_product_to_panel(call: CallbackQuery):
    try:
        prod_id = int(call.data.split("_", 2)[2])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid product.", show_alert=True)

    prod = db_query("""
        SELECT category, panel_name
        FROM products WHERE id=? AND is_active=1
    """, (prod_id,), fetchone=True)
    if not prod:
        return await call.answer("❌ Product not found.", show_alert=True)

    category, panel_name = prod
    category = (category or "").strip()
    panel_name = (panel_name or "").strip()

    # Exact purchase path: purchase confirmation -> the same package list.
    # Use exact matches here so special characters in panel names cannot break
    # the Back button's database lookup.
    if panel_name:
        prods = db_query("""
            SELECT id, name, price_inr, stock, reseller_price, validity, device_limit, external_enabled
            FROM products
            WHERE category=? AND panel_name=? AND is_active=1
        """, (category, panel_name), fetchall=True)
        if prods:
            await show_products_for_panel(
                call, prods, f"{category} - {panel_name}",
                back_callback=f"cat_{category[:30]}"
            )
            try:
                await call.answer()
            except Exception:
                pass
            return

    # Products without a panel name are shown directly under the category.
    # In that case Back must return to the main category list, not reopen the
    # same direct-product screen.
    await view_shop_panels(call)
    try:
        await call.answer()
    except Exception:
        pass


@dp.callback_query(F.data.startswith("product_qr_"))
async def product_qr_start(call: CallbackQuery, state: FSMContext):
    """Open the existing FamPay amount/QR flow from the product payment screen.
    The existing Add Balance/FamPay handlers are left unchanged.
    """
    try:
        prod_id = int(call.data.split("_", 2)[2])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid product.", show_alert=True)

    prod = db_query("""
        SELECT name, price_inr, reseller_price, validity
        FROM products WHERE id=? AND is_active=1
    """, (prod_id,), fetchone=True)
    user = db_query("SELECT is_reseller, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if not prod or not user:
        return await call.answer("❌ Product or user not found.", show_alert=True)

    normal_price = float(prod[1] or 0.0)
    reseller_price = float(prod[2] or 0.0)
    base_price = reseller_price if refresh_reseller_status(call.from_user.id) else normal_price
    final_price = base_price - (base_price * (VIP_DISCOUNT_PERCENTAGE / 100)) if bool(user[1]) else base_price

    await state.set_state(UserStates.custom_amount_input)
    await state.update_data(amount_str="0", product_qr_id=prod_id)
    await safe_edit_text(call.message, 
        f"🇮🇳 <b>PAY WITH DIRECT QR</b>\n\n"
        f"📦 Product: <b>{prod[0]}</b>\n"
        f"💰 Product Price: <b>{fmt_curr(final_price)}</b>\n\n"
        f"Enter the amount you want to add to your wallet using the existing FamPay QR verification flow.\n"
        f"After successful verification, the amount will be added to your balance.\n"
        f"Then return to the product and use <b>Wallet Balance</b>.",
        parse_mode='HTML'
    )
    await show_keypad(call.message)
    await call.answer()


async def return_to_product_price_list(call: CallbackQuery, prod_id: int) -> None:
    """Return to the exact product/package price list after cancelling wallet confirmation."""
    prod = db_query(
        "SELECT category, panel_name FROM products WHERE id=? AND is_active=1",
        (prod_id,), fetchone=True
    )
    if not prod:
        return await call.answer("❌ Product not found.", show_alert=True)

    category = (prod[0] or "").strip()
    panel_name = (prod[1] or "").strip()

    if panel_name:
        prods = db_query(
            """SELECT id, name, price_inr, stock, reseller_price, validity,
                      device_limit, external_enabled
               FROM products
               WHERE category=? AND panel_name=? AND is_active=1""",
            (category, panel_name), fetchall=True
        )
        if prods:
            await show_products_for_panel(
                call, prods, f"{category} - {panel_name}",
                back_callback=f"cat_{category[:30]}"
            )
            return

    prods = db_query(
        """SELECT id, name, price_inr, stock, reseller_price, validity,
                  device_limit, external_enabled
           FROM products
           WHERE category=? AND is_active=1""",
        (category,), fetchall=True
    )
    if prods:
        await show_products_for_panel(
            call, prods, category,
            back_callback="menu_shop"
        )
        await call.answer()
    else:
        await view_shop_panels(call)
        await call.answer()


@dp.callback_query(F.data.startswith("wallet_confirm_"))
async def wallet_purchase_confirmation(call: CallbackQuery):
    """First Wallet Balance click only opens a confirmation screen; no money is charged."""
    try:
        prod_id = int(call.data.split("_", 2)[2])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid product selection.", show_alert=True)

    prod = db_query(
        """SELECT name, price_inr, stock, validity, reseller_price,
                  external_enabled, category, panel_name
           FROM products WHERE id=? AND is_active=1""",
        (prod_id,), fetchone=True
    )
    user = db_query(
        "SELECT balance, is_reseller, is_vip FROM users WHERE user_id=?",
        (call.from_user.id,), fetchone=True
    )

    if not prod:
        return await call.answer("❌ Product not found.", show_alert=True)
    if not user:
        return await call.answer("❌ User account not found.", show_alert=True)

    normal_price = float(prod[1] or 0.0)
    reseller_price = float(prod[4] or 0.0)
    base_price = reseller_price if refresh_reseller_status(call.from_user.id) else normal_price
    final_price = base_price - (base_price * (VIP_DISCOUNT_PERCENTAGE / 100)) if bool(user[2]) else base_price

    stock_ok = bool(prod[5]) or (prod[2] is not None and prod[2] > 0)
    if not stock_ok:
        return await call.answer("❌ This product is out of stock!", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"CONFIRM BUY - {fmt_curr(final_price)}",
            callback_data=f"confirm_buy_{prod_id}",
            icon_custom_emoji_id=get_emoji_icon("confirm_pay"),
            style="success"
        )],
        [InlineKeyboardButton(
            text="CANCEL",
            callback_data=f"wallet_cancel_{prod_id}",
            icon_custom_emoji_id=get_emoji_icon("cancel"),
            style="danger"
        )]
    ])

    text = (
        f"{get_emoji('buy')} <b>CONFIRM TO BUY</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Product:</b> {prod[0]}\n"
        f"💰 <b>Price:</b> {fmt_curr(final_price)}\n"
        f"💳 <b>Wallet Balance:</b> {fmt_curr(float(user[0] or 0.0))}\n\n"
        "Are you sure you want to buy this product using your wallet balance?"
    )

    await safe_edit_text(call.message, text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("wallet_cancel_"))
async def wallet_purchase_cancel(call: CallbackQuery):
    """Cancel wallet confirmation and return to the same product price list."""
    try:
        prod_id = int(call.data.split("_", 2)[2])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid product selection.", show_alert=True)

    await return_to_product_price_list(call, prod_id)


@dp.callback_query(F.data.startswith("confirm_buy_"))
async def process_confirm_buy(call: CallbackQuery):
    """Second click performs the existing purchase flow."""
    prod_id = int(call.data.split("_", 2)[2])
    # Reuse the exact existing purchase logic below.
    prod = db_query("""
        SELECT name, price_inr, stock, apk_link, validity, device_limit,
               category, reseller_price, panel_name, external_enabled,
               external_product_id, requires_android_id, external_duration, external_api_type
        FROM products WHERE id=?
    """, (prod_id,), fetchone=True)
    user = db_query("SELECT balance, referred_by, is_reseller, total_saved, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if not prod:
        return await call.answer("❌ Critical Error: Item not found in DB!", show_alert=True)
    if not user:
        return await call.answer("❌ User account not found!", show_alert=True)

    normal_price = float(prod[1] or 0.0)
    reseller_price = float(prod[7] or 0.0)
    is_reseller = bool(user[2]); is_vip = bool(user[4])
    base_price = reseller_price if is_reseller else normal_price
    final_price = base_price - (base_price * (VIP_DISCOUNT_PERCENTAGE / 100)) if is_vip else base_price
    savings = normal_price - final_price

    # External/API products use the remote API as the real inventory source.
    # Their local stock number is only a display buffer and must not block API purchases.
    external_enabled = bool(prod[9])
    external_product_id = (prod[10] or "").strip()
    external_api_type = int(prod[13] or 1) if external_enabled else 0
    if not external_enabled and (prod[2] is None or prod[2] <= 0):
        return await call.answer("❌ This product is out of stock!", show_alert=True)
    if user[0] < final_price:
        return await call.answer(f"❌ Insufficient Balance! You need {fmt_curr(final_price)}.", show_alert=True)

    # Prevent double-click purchases while processing the external API.
    await call.answer("⏳ Processing your purchase...", show_alert=False)
    delivered_key = None
    api_response = None

    # Charge the wallet first. Purchase statistics are updated only after a
    # real key has been successfully obtained below. If the API fails or no key
    # is returned, only the wallet charge is refunded and Total Spent/Orders
    # remain unchanged.
    db_query("UPDATE users SET balance=? WHERE user_id=?",
             (user[0] - final_price, call.from_user.id))

    if external_enabled:
        api_status_key = "external_api2_status" if external_api_type == 2 else "external_api1_status"
        api_label = "External API 2" if external_api_type == 2 else "External API 1"
        if get_setting(api_status_key, "OFF" if external_api_type == 2 else "ON") != "ON":
            db_query("UPDATE users SET balance=balance+? WHERE user_id=?", (final_price, call.from_user.id))
            return await safe_edit_text(call.message, f"❌ <b>{api_label} is currently OFF.</b>\n\n💰 Your balance has been refunded.", reply_markup=back_kb("menu_shop"), parse_mode='HTML')
        if not external_product_id:
            db_query("UPDATE users SET balance=balance+? WHERE user_id=?", (final_price, call.from_user.id))
            return await safe_edit_text(call.message, "❌ API product ID is not configured for this product.", reply_markup=back_kb("menu_shop"), parse_mode='HTML')

        # IMPORTANT: use the API-specific duration first. For older products,
        # fall back to the saved validity and finally the displayed package name.
        # This fixes the old bug where the package name (e.g. "1 Hour") was sent
        # even when the API price tier was stored under a different duration.
        # API 2 uses only the database Variant ID. It does not use the API 1
        # duration/price-tier fallback logic. Send exactly one buy request.
        if external_api_type == 2:
            try:
                api_response = await fetch_external_key(external_product_id, "", "", 2)
            except Exception as api_exc:
                logger.exception("APK API purchase call crashed")
                api_response = {"status": "error", "msg": f"APK API call failed: {api_exc}"}
        else:
            # API 1 keeps its existing duration/price-tier fallback logic.
            api_duration_saved = (prod[12] or "").strip()
            duration_candidates = []
            for candidate in (api_duration_saved, prod[4], prod[0]):
                candidate = normalize_api_duration(candidate)
                if candidate and candidate not in duration_candidates:
                    duration_candidates.append(candidate)

            api_response = {"status": "error", "msg": "No API duration configured"}
            api_duration_used = ""
            for api_duration in duration_candidates:
                try:
                    logger.info("Trying external API duration=%r for product_id=%r", api_duration, external_product_id)
                    api_response = await fetch_external_key(external_product_id, api_duration, "", 1)
                except Exception as api_exc:
                    logger.exception("External API 1 purchase call crashed")
                    api_response = {"status": "error", "msg": f"API call failed: {api_exc}"}

                if api_response.get("status") == "success":
                    api_duration_used = api_duration
                    break

                error_blob = json.dumps(api_response, ensure_ascii=False).lower()
                if "price not found" not in error_blob and "price_not_found" not in error_blob:
                    break

        if api_response.get("status") != "success":
            db_query("UPDATE users SET balance=balance+? WHERE user_id=?", (final_price, call.from_user.id))
            error_msg = api_response.get("msg", "Unknown API error")
            error_text = f"❌ <b>API Error:</b> {error_msg}\n\n💰 Your balance has been refunded."
            try:
                await safe_edit_text(call.message, 
                    error_text,
                    reply_markup=back_kb("menu_shop"),
                    parse_mode='HTML'
                )
            except Exception as tg_error:
                logger.exception("Could not edit purchase message after API failure: %s", tg_error)
                try:
                    await bot.send_message(
                        call.from_user.id,
                        error_text,
                        reply_markup=back_kb("menu_shop"),
                        parse_mode='HTML'
                    )
                except Exception:
                    logger.exception("Could not send API failure message to user")
            return

        delivered_key = api_response.get("key")
        if isinstance(delivered_key, list):
            delivered_key = "\n".join(str(x) for x in delivered_key)
        if delivered_key is None or str(delivered_key).strip() in ("", "KEY_NOT_FOUND"):
            db_query("UPDATE users SET balance=balance+? WHERE user_id=?", (final_price, call.from_user.id))
            return await safe_edit_text(call.message, "❌ API returned no key.\n\n💰 Your balance has been refunded.", reply_markup=back_kb("menu_shop"), parse_mode='HTML')
        delivered_key = str(delivered_key)
        # External API products are not limited by local key-vault stock.
        # Keep the admin-entered display stock unchanged so the product never
        # becomes "Out of Stock" after a successful API purchase.
    else:
        key_data = db_query("SELECT id, key_text FROM product_keys WHERE product_id=? AND is_used=0 LIMIT 1", (prod_id,), fetchone=True)
        if not key_data:
            db_query("UPDATE users SET balance=balance+? WHERE user_id=?", (final_price, call.from_user.id))
            return await safe_edit_text(call.message, "❌ No manual key is available.\n\n💰 Your balance has been refunded.", reply_markup=back_kb("menu_shop"), parse_mode='HTML')
        delivered_key = key_data[1]
        db_query("UPDATE product_keys SET is_used=1 WHERE id=?", (key_data[0],))
        db_query("UPDATE products SET stock=CASE WHEN stock>0 THEN stock-1 ELSE 0 END WHERE id=?", (prod_id,))

    # A purchase counts toward Total Spent/Orders/Savings only after a key
    # has actually been obtained. API errors, missing keys, and other failed
    # purchases return above before reaching this block.
    db_query("UPDATE users SET spent=spent+?, orders_count=orders_count+1, total_saved=total_saved+? WHERE user_id=?",
             (final_price, savings, call.from_user.id))

    if user[1]:
        commission = final_price * 0.15
        db_query("UPDATE users SET balance=balance+?, referral_earned=referral_earned+? WHERE user_id=?", (commission, commission, user[1]))
        try:
            await bot.send_message(user[1], f"🎁 <b>Referral Bonus Added!</b>\nYou earned {fmt_curr(commission)} from a successful purchase.", parse_mode='HTML')
        except Exception:
            pass

    product_full_name = f"{prod[6]} - {prod[8]} ({prod[0]})"
    db_query("INSERT INTO orders (user_id, product_name, price_paid, delivered_key, purchase_date) VALUES (?, ?, ?, ?, ?)",
             (call.from_user.id, product_full_name, final_price, delivered_key, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_activity(call.from_user.id, "PURCHASE_SUCCESS", f"Product: {product_full_name}, Paid: {final_price}, External API: {external_enabled}")
    await send_advanced_notification(call.from_user.id, "ORDER", final_price, product=product_full_name, key=delivered_key)

    msg = (f"✅ <b>PURCHASE SUCCESSFUL!</b>\n━━━━━━━━━━━━━━━━━━\n"
           f"📦 <b>Panel:</b> {prod[6]}\n📁 <b>Panel Name:</b> {prod[8]}\n"
           f"⏱ <b>Package:</b> {prod[0]}\n💰 <b>Amount Deducted:</b> {fmt_curr(final_price)}\n"
           f"📱 <b>Device Limit:</b> {prod[5]}\n━━━━━━━━━━━━━━━━━━\n")
    if prod[3] and prod[3].startswith("http"):
        msg += f"📥 <b>APK Link:</b> <a href='{prod[3]}'>Click Here to Download</a>\n\n"
    msg += f"🔑 <b>Your Exclusive Key:</b>\n<code>{delivered_key}</code>\n\n"
    if external_enabled and api_response:
        if api_response.get("product"):
            msg += f"📌 <b>Product:</b> {api_response['product']}\n"
        if api_response.get("duration"):
            msg += f"⏳ <b>Duration:</b> {api_response['duration']}\n"
    msg += f"\n<i>For any issues, tap Support or contact: {ADMIN_CONTACT}</i>"
    await safe_edit_text(call.message, msg, reply_markup=back_kb("menu_shop"), disable_web_page_preview=True, parse_mode='HTML')

    purchase_feedback = get_setting(
        "purchase_feedback",
        "🙏 Thanks for purchasing! Your order has been delivered successfully. ❤️"
    ).strip()
    if purchase_feedback:
        try:
            await bot.send_message(call.from_user.id, purchase_feedback, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Failed to send purchase feedback to buyer {call.from_user.id}: {e}")

# ==============================================================================
# 14. USER DASHBOARD, FILES, VIP, RESELLER, ORDERS, PROFILE, REFERRAL
# ==============================================================================
@dp.callback_query(F.data == "menu_all_files")
async def all_files_handler(call: CallbackQuery):
    link_q = db_query("SELECT value FROM settings WHERE key='all_files_link'", fetchone=True)
    link = link_q[0] if link_q and link_q[0] != 'None' else None
    if link:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Access Download Channel ↗️", url=link, icon_custom_emoji_id=get_emoji_icon("download"), style="success")],
            [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
        ])
        text = get_ui_text("download_files")
        await send_ui_content(call, "download_files", text, reply_markup=kb)
    else:
        await call.answer("⚠️ Admin has not configured the private download channel link yet.", show_alert=True)

@dp.callback_query(F.data == "menu_vip_dash")
async def vip_dashboard(call: CallbackQuery):
    u = db_query("SELECT balance, is_vip, vip_since FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    is_vip = bool(u[1])
    status_str = "🟢 Active (Lifetime)" if is_vip else "🔴 Not Subscribed"
    text = get_ui_text("vip_menu", vip_status=status_str)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if is_vip:
        text += f"\n📅 <b>Member Since:</b> {u[2]}\n\nEnjoy your permanent 15% discount!"
    else:
        text += f"\n\n💳 <b>Your Current Balance:</b> {fmt_curr(u[0])}\n"
        if u[0] >= VIP_PRICE_INR: 
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"✅ Purchase VIP for {fmt_curr(VIP_PRICE_INR)}", callback_data="execute_vip_upgrade", icon_custom_emoji_id=get_emoji_icon("vip"), style="success")])
        else:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ Need {fmt_curr(VIP_PRICE_INR)} to Upgrade", callback_data="ignore_stock_click", style="danger")])
            kb.inline_keyboard.append([InlineKeyboardButton(text="💳 Add Balance Now", callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("add_balance"), style="success")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await send_ui_content(call, "vip_menu", text, reply_markup=kb)

@dp.callback_query(F.data == "execute_vip_upgrade")
async def execute_vip_upgrade(call: CallbackQuery):
    u = db_query("SELECT balance, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if u[1]: return await call.answer("⚠️ You are already a VIP Member!", show_alert=True)
    if u[0] < VIP_PRICE_INR: return await call.answer(f"❌ Your balance dropped below {VIP_PRICE_INR}.", show_alert=True)
    new_balance = u[0] - VIP_PRICE_INR
    now_date = datetime.now().strftime("%Y-%m-%d")
    db_query("UPDATE users SET balance=?, is_vip=1, vip_since=? WHERE user_id=?", (new_balance, now_date, call.from_user.id))
    log_activity(call.from_user.id, "UPGRADED_VIP")
    try: await notify_admins( f"🌟 <b>NEW VIP UPGRADE</b>\n👤 User ID: <code>{call.from_user.id}</code>", parse_mode='HTML')
    except: pass
    await call.answer("🎉 Upgrade Successful! You are now a VIP Member.", show_alert=True)
    await vip_dashboard(call)

@dp.callback_query(F.data == "menu_reseller_dash")
async def reseller_dashboard(call: CallbackQuery):
    u = db_query("SELECT balance, is_reseller, reseller_since, total_saved, reseller_expires_at FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if not u:
        return await call.answer("❌ User not found.", show_alert=True)
    refresh_reseller_status(call.from_user.id)
    u = db_query("SELECT balance, is_reseller, reseller_since, total_saved, reseller_expires_at FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    system_status = get_setting("reseller_system_status", "ON")
    setup_fee = float(get_setting("reseller_setup_fee", "200.0"))
    min_balance = float(get_setting("reseller_min_balance", "1.0"))
    benefits = get_setting("reseller_benefits", "50%+ Discount / Low Reseller Prices\nExclusive Reseller Access\nPriority Support")
    duration = get_setting("reseller_default_days", "lifetime")

    if u[1]:
        expiry_text = "Lifetime" if not u[4] else datetime.fromisoformat(str(u[4])).strftime("%d-%m-%Y %I:%M %p")
        text = (f"{get_emoji('shield_icon')} <b><u>— RESELLER DASHBOARD —</u></b> {get_emoji('shield_icon')}\n\n"
                f"🟢 <b>Status:</b> Active\n📅 <b>Since:</b> {u[2]}\n⏳ <b>Access Until:</b> {expiry_text}\n"
                f"{get_emoji('money_icon')} <b>Total Saved:</b> {fmt_curr(u[3])}\n\n"
                f"🎁 <b>Benefits:</b>\n{benefits}\n\n"
                "🎉 You are enjoying exclusive wholesale prices on all products!")
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK TO PANEL", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
        await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')
        return
    if system_status == "OFF":
        return await call.answer("⚠️ Wholesale / Reseller registrations are currently closed by Admin.", show_alert=True)

    if duration == "lifetime":
        duration_text = "Lifetime"
    else:
        duration_text = f"{duration} days"
    text = (f"⚡ <b><u>— BECOME A RESELLER —</u></b> ⚡\n\n"
             f"Access premium <b>Reseller Prices</b> at lower prices.\n\n"
             f"🎁 <b>Benefits:</b>\n{benefits}\n\n"
             f"⏳ <b>Access:</b> {duration_text}\n"
             f"📋 <b>Minimum Balance:</b> {fmt_curr(min_balance)}\n"
             f"💳 <b>Reseller Price:</b> {fmt_curr(setup_fee)}\n"
             f"💰 <b>Your Current Balance:</b> {fmt_curr(u[0])}\n")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if u[0] >= min_balance:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"✅ Confirm Buy — {fmt_curr(setup_fee)}", callback_data="execute_reseller_upgrade", icon_custom_emoji_id=get_emoji_icon("reseller"), style="success")])
    else:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ Minimum Balance Required: {fmt_curr(min_balance)}", callback_data="ignore_stock_click", style="danger")])
        kb.inline_keyboard.append([InlineKeyboardButton(text="💳 Add Balance", callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("add_balance"), style="success")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK TO PANEL", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "execute_reseller_upgrade")
async def execute_reseller_upgrade(call: CallbackQuery):
    setup_fee = float(get_setting("reseller_setup_fee", "200.0"))
    min_balance = float(get_setting("reseller_min_balance", "1.0"))
    duration = get_setting("reseller_default_days", "lifetime")
    u = db_query("SELECT balance, is_reseller FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if not u:
        return await call.answer("❌ User not found.", show_alert=True)
    refresh_reseller_status(call.from_user.id)
    u = db_query("SELECT balance, is_reseller FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if u[1]: return await call.answer("⚠️ You are already a Reseller!", show_alert=True)
    if u[0] < min_balance: return await call.answer(f"❌ Your balance is below the minimum {fmt_curr(min_balance)}.", show_alert=True)
    new_balance = u[0] - setup_fee
    if duration == "lifetime":
        expires_at = None
    else:
        try:
            expires_at = (datetime.now() + timedelta(days=int(duration))).isoformat(timespec="seconds")
        except (ValueError, TypeError):
            expires_at = None
    db_query("UPDATE users SET balance=?, is_reseller=1, reseller_since=?, reseller_expires_at=?, account_type='Reseller' WHERE user_id=?", (new_balance, datetime.now().strftime("%Y-%m-%d"), expires_at, call.from_user.id))
    log_activity(call.from_user.id, "UPGRADED_RESELLER", f"Duration: {duration}")
    try: await notify_admins(f"👑 <b>NEW RESELLER UPGRADE</b>\n👤 User ID: <code>{call.from_user.id}</code>\n⏳ Access: <b>{'Lifetime' if duration == 'lifetime' else str(duration) + ' days'}</b>", parse_mode='HTML')
    except: pass
    duration_msg = "Lifetime" if duration == "lifetime" else f"{duration} days"
    await call.answer(f"🎉 Congratulations! You are now a Reseller.\nAccess: {duration_msg}", show_alert=True)
    try:
        await bot.send_message(call.from_user.id, f"🎉 <b>Congratulations! Your Reseller Dashboard is Activated.</b>\n\n👑 <b>Reseller Access:</b> {duration_msg}\n💰 You can now access reseller prices and benefits.", parse_mode='HTML')
    except Exception as e:
        logger.warning("Reseller activation notification failed: %s", e)
    await reseller_dashboard(call)

@dp.callback_query(F.data == "menu_orders")
async def my_orders(call: CallbackQuery):
    orders = db_query("SELECT product_name, delivered_key, purchase_date, price_paid FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (call.from_user.id,), fetchall=True)
    if not orders: return await safe_edit_text(call.message, "🧾 You haven't made any purchases yet. Your vault is empty.", reply_markup=back_kb(), parse_mode='HTML')
    text = "🧾 <b><u>— YOUR RECENT ORDERS (LAST 10) —</u></b> 🧾\n\n"
    for o in orders: text += f"📦 <b>{o[0]}</b> ({fmt_curr(o[3])})\n🔑 <code>{o[1]}</code>\n📅 <i>{o[2]}</i>\n━━━━━━━━━━━━━━━━\n"
    await safe_edit_text(call.message, text, reply_markup=back_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "menu_profile")
async def show_profile(call: CallbackQuery, state: FSMContext):
    # Acknowledge immediately. Profile is text-only by design: no Telegram
    # profile-photo lookup/download/send is performed.
    try:
        await call.answer()
    except Exception:
        pass
    u = db_query("SELECT user_id, first_name, account_type, balance, orders_count, spent, referrals_count, joined_date, is_reseller, reseller_since, total_saved, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if not u:
        return await call.answer("❌ Profile not found.", show_alert=True)
    acc_type_display = []
    if u[8]: acc_type_display.append(f"{get_emoji('reseller')} Reseller")
    if u[11]: acc_type_display.append(f"{get_emoji('vip')} VIP")
    type_str = " | ".join(acc_type_display) if acc_type_display else f"{get_emoji('regular_user')} Regular User"
    text = (
        f"{get_emoji('grid_id')} <b><u>— YOUR SECURE PROFILE —</u></b> {get_emoji('grid_id')}\n\n"
        f"{get_emoji('grid_id')} <b>Grid ID:</b> <code>{u[0]}</code>\n"
        f"{get_emoji('name')} <b>Name:</b> {u[1]}\n"
        f"{get_emoji('account_level')} <b>Account Level:</b> {type_str}\n\n"
        f"{get_emoji('wallet_left')} <b>— Wallet —</b> {get_emoji('wallet_right')}\n"
        f"{get_emoji('wallet_left')} <b>Current Balance:</b> {fmt_curr(u[3])} {get_emoji('wallet_right')}\n\n"
        f"{get_emoji('global_stats')} <b>— Global Statistics —</b>\n"
        f"{get_emoji('total_orders')} <b>Total Orders:</b> {u[4]}\n"
        f"{get_emoji('total_spent')} <b>Total Spent:</b> {fmt_curr(u[5])}\n"
        f"{get_emoji('total_referrals')} <b>Total Referrals:</b> {u[6]}\n\n"
    )
    if u[8]:
        text += f"{get_emoji('shield_icon')} <b>— RESELLER METRICS —</b> {get_emoji('shield_icon')}\n{get_emoji('money_icon')} <b>Total Saved via Reseller:</b> {fmt_curr(u[10])}\n\n"
    text += f"{get_emoji('joined_grid')} <b>Joined Grid:</b> {u[7]}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Redeem Promo Code", callback_data="redeem_coupon", icon_custom_emoji_id=get_emoji_icon('redeem_icon'), style="success")],
        [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    try:
        await safe_edit_text(call.message, text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise


@dp.callback_query(F.data == "redeem_coupon")
async def redeem_coupon_start(call: CallbackQuery, state: FSMContext):
    await safe_edit_text(call.message, "🎟 <b>Please enter your VIP / Promo redeem code below:</b>", reply_markup=back_kb("menu_profile"), parse_mode='HTML')
    await state.set_state(UserStates.wait_for_redeem)

@dp.message(UserStates.wait_for_redeem)
async def process_redeem(m: Message, state: FSMContext):
    code = m.text.strip().upper()
    user_id = m.from_user.id
    if db_query("SELECT * FROM redeemed WHERE user_id=? AND code=?", (user_id, code), fetchone=True):
        await m.answer("❌ Anti-Fraud Alert: You already redeemed this unique code!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
        await state.clear()
        return
    coupon = db_query("SELECT amount, uses_left FROM coupons WHERE code=?", (code,), fetchone=True)
    if not coupon: await m.answer("❌ Invalid or Expired Code!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    elif coupon[1] <= 0: await m.answer("❌ This code's usage limit has been fully claimed by other users.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    else:
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (coupon[0], user_id))
        db_query("UPDATE coupons SET uses_left = uses_left - 1 WHERE code=?", (code,))
        db_query("INSERT INTO redeemed (user_id, code) VALUES (?, ?)", (user_id, code))
        log_activity(user_id, "PROMO_REDEEMED", f"Code: {code}, Amount: {coupon[0]}")
        await m.answer(f"🎉 <b>Success!</b>\nSafely added {fmt_curr(coupon[0])} to your balance!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
        try:
            user_info = db_query("SELECT first_name FROM users WHERE user_id=?", (user_id,), fetchone=True)
            uname = user_info[0] if user_info else "Unknown User"
            await notify_admins( f"🎟 <b>PROMO CODE REDEEMED!</b>\n👤 User: {uname} (<code>{user_id}</code>)\n🔖 Code: <b>{code}</b>\n💵 Amount: {fmt_curr(coupon[0])}", parse_mode='HTML')
        except Exception: pass
    await state.clear()

@dp.callback_query(F.data == "menu_referral")
async def show_referral(call: CallbackQuery):
    u = db_query("SELECT referrals_count, referral_earned FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{call.from_user.id}"
    text = (f"{get_emoji('referral')} <b><u>AFFILIATE PROGRAM</u></b> {get_emoji('referral')}\n\n✅ <b>Status:</b> ACTIVE\n💰 Earn <b>2% flat commission</b> on every successful purchase made by your referred friends!\n\n📊 <b>YOUR STATS:</b>\n👥 Total Invited: {u[0]}\n💵 Life-time Earned: {fmt_curr(u[1])}\n\n🔗 <b>Your Invite Link:</b>\n<code>{ref_link}</code>\n\n<i>Simply copy and share this link to start earning!</i>")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')

# ==============================================================================
# 15. LUDO / DICE SPIN
# ==============================================================================
@dp.callback_query(F.data == "menu_spin_landing")
async def lucky_spin_landing(call: CallbackQuery):
    status_check = db_query("SELECT value FROM settings WHERE key='spin_status'", fetchone=True)
    spin_status = status_check[0] if status_check else "ON"
    if spin_status == "OFF": return await call.answer("⚠️ Lucky Ludo Spin is currently disabled by Admin.", show_alert=True)
    await safe_edit_text(call.message, f"{get_emoji('ludo_spin')} <b><u>— LUDO SPIN —</u></b> {get_emoji('ludo_spin')}\n\nTest your luck! You can spin once every 24 hours.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Spin Dice Now!", callback_data="execute_spin", icon_custom_emoji_id=get_emoji_icon("ludo_spin"), style="success")], 
        [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ]), parse_mode='HTML')

@dp.callback_query(F.data == "execute_spin")
async def execute_spin(call: CallbackQuery):
    status_check = db_query("SELECT value FROM settings WHERE key='spin_status'", fetchone=True)
    if status_check and status_check[0] == "OFF": return await call.answer("⚠️ Lucky Spin is disabled.", show_alert=True)
    u = db_query("SELECT last_spin, balance, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    now = datetime.now()
    if u[0] and now < datetime.strptime(u[0], "%Y-%m-%d %H:%M:%S") + timedelta(hours=24):
        return await safe_edit_text(call.message, "❌ <b>Cooldown Active!</b>\nYou already played today. Come back tomorrow.", reply_markup=back_kb(), parse_mode='HTML')
    await call.message.delete()
    dice_msg = await bot.send_dice(chat_id=call.message.chat.id, emoji="🎲")
    await asyncio.sleep(SPIN_DELAY_SECONDS) 
    dice_val = dice_msg.dice.value
    # One fixed reward for every user. Admin sets the amount in Spin Settings;
    # the saved value is used exactly as-is for everyone (no random reward list
    # and no VIP multiplier). This prevents different users receiving different
    # amounts and keeps the spin cost predictable.
    reward_row = db_query("SELECT amount FROM spin_rewards ORDER BY id DESC LIMIT 1", fetchone=True)
    reward = float(reward_row[0]) if reward_row else 0.0
    new_bal = u[1] + reward
    db_query("UPDATE users SET balance=?, last_spin=? WHERE user_id=?", (new_bal, now.strftime("%Y-%m-%d %H:%M:%S"), call.from_user.id))
    log_activity(call.from_user.id, "PLAYED_SPIN", f"Reward: {reward}, Dice: {dice_val}")
    msg = get_ui_text("lucky_dice_result", dice_value=dice_val, won_amount=fmt_curr(reward), new_balance=fmt_curr(new_bal))
    dice_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📚 BACK TO MENU", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="success")]])
    photo_id = get_ui_photo_id("lucky_dice_result")
    if photo_id:
        await dice_msg.reply_photo(photo_id, caption=msg, reply_markup=dice_kb, parse_mode='HTML')
    else:
        await dice_msg.reply(msg, reply_markup=dice_kb, parse_mode='HTML')

# ==============================================================================
# 16. TUTORIALS & SUPPORT
# ==============================================================================
@dp.callback_query(F.data == "menu_how_to")
async def tutorial_system(call: CallbackQuery):
    video_link_query = db_query("SELECT value FROM settings WHERE key='how_to_video'", fetchone=True)
    video_link = video_link_query[0] if video_link_query and video_link_query[0] != 'None' else None
    text = (f"{get_emoji('tutorial')} <b><u>— TUTORIALS & GUIDE —</u></b> {get_emoji('tutorial')}\n\n1️⃣ Add funds via <b>Add Balance</b>\n2️⃣ Navigate to <b>Product Store</b>\n3️⃣ Choose your desired Panel and Package validity.\n4️⃣ The Key and Installation APK link will be instantly provided.")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if video_link: kb.inline_keyboard.append([InlineKeyboardButton(text="Watch Full Video Tutorial", url=video_link, icon_custom_emoji_id=get_emoji_icon("tutorial"), style="success")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "menu_support")
async def support_center(call: CallbackQuery):
    telegram_link = get_setting("support_telegram", "https://t.me/YOUR_SUPPORT")
    whatsapp_link = get_setting("support_whatsapp", "https://wa.me/YOUR_NUMBER")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Contact on Telegram", url=telegram_link, icon_custom_emoji_id=get_emoji_icon("telegram"), style="primary")],
        [InlineKeyboardButton(text="Contact on WhatsApp", url=whatsapp_link, icon_custom_emoji_id=get_emoji_icon("whatsapp"), style="primary")],
        [InlineKeyboardButton(text="🎫 Open New Ticket", callback_data="open_ticket", icon_custom_emoji_id=get_emoji_icon("support"), style="success"), 
         InlineKeyboardButton(text="📋 My Open Tickets", callback_data="my_tickets", icon_custom_emoji_id=get_emoji_icon("history"), style="success")], 
        [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await safe_edit_text(call.message, f"{get_emoji('telegram')}{get_emoji('whatsapp')} <b><u>— PREMIUM SUPPORT CENTER —</u></b>\n\nContact us via Telegram or WhatsApp for instant help, or open a support ticket for admin assistance.", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "my_tickets")
async def view_my_tickets(call: CallbackQuery):
    tickets = db_query("SELECT id, message, status, created_at FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 5", (call.from_user.id,), fetchall=True)
    if not tickets: return await safe_edit_text(call.message, "📋 You do not have any active or previous support tickets.", reply_markup=back_kb("menu_support"), parse_mode='HTML')
    text = "📋 <b><u>— Your Recent Tickets —</u></b> 📋\n\n"
    for t in tickets:
        status_icon = "🟢" if t[2] == 'Open' else "🔴"
        text += f"🎫 <b>Ticket #{t[0]}</b> | Status: {status_icon} <b>{t[2]}</b>\n📅 <i>{t[3]}</i>\n📝 <i>{t[1][:80]}...</i>\n\n"
    await safe_edit_text(call.message, text, reply_markup=back_kb("menu_support"), parse_mode='HTML')

@dp.callback_query(F.data == "open_ticket")
async def open_ticket_start(call: CallbackQuery, state: FSMContext):
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "📝 <b>Please type your issue/message below in detail:</b>", reply_markup=back_kb("menu_support"), parse_mode='HTML')
    await state.set_state(UserStates.wait_for_ticket)

@dp.message(UserStates.wait_for_ticket)
async def process_ticket(m: Message, state: FSMContext):
    db_query("INSERT INTO tickets (user_id, message, created_at) VALUES (?, ?, ?)", (m.from_user.id, m.text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await m.answer("✅ <b>Ticket Submitted Successfully!</b> Admins will reply soon.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    try: await notify_admins( f"🚨 <b>NEW SUPPORT TICKET</b>\nFrom: <code>{m.from_user.id}</code>\nMsg: {m.text}", parse_mode='HTML')
    except: pass
    log_activity(m.from_user.id, "OPENED_TICKET")
    await state.clear()

# ==============================================================================
# 17. ADMIN PANEL
# ==============================================================================
@dp.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.clear()
    await message.answer("⚙️ <b>Advanced Admin Terminal</b>\n<i>Authorized Access Granted. Use the buttons below.</i>", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_panel_back")
async def back_to_admin(call: CallbackQuery, state: FSMContext):
    try:
        await call.answer()
    except Exception:
        pass
    await state.clear()
    await safe_edit_text(call.message, "⚙️ <b>Advanced Admin Terminal</b>\n<i>Authorized Access Granted. Use the buttons below.</i>", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_toggle_vip_sys")
async def toggle_vip_sys(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    res = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    current = str(res[0]).upper() if res and res[0] else 'OFF'
    new_status = 'OFF' if current == 'ON' else 'ON'
    # Use the settings helper so the in-memory settings cache is updated too.
    # This is the VIP-menu fix only; payment code is untouched.
    set_setting("vip_status", new_status)
    try:
        await call.answer(f"VIP System: {new_status}", show_alert=True)
    except Exception:
        pass
    try:
        await safe_edit_text(call.message, 
            "⚙️ <b>Advanced Admin Terminal</b>\n<i>Authorized Access Granted. Use the buttons below.</i>",
            reply_markup=admin_kb(),
            parse_mode='HTML'
        )
    except Exception:
        try:
            await safe_edit_reply_markup(call.message, reply_markup=admin_kb())
        except Exception:
            pass

@dp.callback_query(F.data.regexp(r"^admin_members(?:_\d+)?$"))
async def admin_member_list(call: CallbackQuery):
    """Fast paginated member list: username, Telegram ID, current balance, total spent."""
    if not is_admin(call.from_user.id):
        return

    try:
        page = int(call.data.rsplit("_", 1)[1]) if "_" in call.data else 0
    except (ValueError, IndexError):
        page = 0

    per_page = 10
    total_row = db_query("SELECT COUNT(*) FROM users", fetchone=True)
    total = int(total_row[0] or 0) if total_row else 0
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    offset = page * per_page

    # Total spent is calculated from successful delivered orders, so this view
    # does not alter or depend on the payment flow.
    users = db_query("""
        SELECT
            u.user_id,
            u.username,
            u.balance,
            COALESCE(SUM(o.price_paid), 0.0) AS total_spent
        FROM users u
        LEFT JOIN orders o ON o.user_id = u.user_id
        GROUP BY u.user_id, u.username, u.balance
        ORDER BY u.user_id DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset), fetchall=True) or []

    if not users:
        text = "👥 <b>MEMBER LIST</b>\n\nNo members found."
    else:
        lines = [
            "👥 <b>MEMBER LIST</b>",
            f"Page <b>{page + 1}/{total_pages}</b> • Total Members: <b>{total}</b>",
            "━━━━━━━━━━━━━━━━━━"
        ]
        for index, (uid, username, balance, total_spent) in enumerate(users, start=offset + 1):
            uname = f"@{username}" if username else "No Username"
            lines.append(
                f"<b>{index}.</b> {uname}\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"💰 Balance: {fmt_curr(balance or 0)}\n"
                f"🛒 Total Spent: {fmt_curr(total_spent or 0)}"
            )
            lines.append("━━━━━━━━━━━━━━━━━━")
        text = "\n".join(lines)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"admin_members_{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"admin_members_{page + 1}"))

    rows = []
    if nav:
        rows.append(nav)
    rows.append([
        InlineKeyboardButton(
            text="BACK",
            callback_data="admin_panel_back",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await safe_edit_text(call.message, text, reply_markup=kb, parse_mode="HTML")
    try:
        await call.answer()
    except Exception:
        pass


@dp.callback_query(F.data == "admin_user_control_start")
async def admin_user_control_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Download Full User List", callback_data="admin_download_userlist", icon_custom_emoji_id=get_emoji_icon("download"), style="success")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await safe_edit_text(call.message, "💻 <b>User Control Terminal</b>\n\n✏️ Enter the <b>User ID</b> or <b>@Username</b> you want to investigate or manage:\n\n👇 <b>OR</b> download the full user CSV format list:", reply_markup=kb, parse_mode='HTML')
    await state.set_state(AdminStates.manage_target_user)

@dp.callback_query(F.data == "admin_download_userlist")
async def admin_download_userlist(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    users = db_query("SELECT username, user_id, phone, balance, orders_count, is_vip, is_reseller FROM users", fetchall=True)
    if not users: return await call.answer("❌ No users found in the database.", show_alert=True)
    file_content = "FULL DATABASE DUMP\n" + "="*100 + "\n"
    for u in users:
        uname = u[0] if u[0] else "No_Username"
        uid = u[1]
        phone = u[2] if u[2] else "No_Phone"
        bal = u[3]
        orders = u[4]
        vip_status = "YES" if u[5] else "NO"
        res_status = "YES" if u[6] else "NO"
        file_content += f"UID: {uid} | UNAME: {uname} | PHONE: {phone} | BAL: ₹{bal:.2f} | BUY: {orders} | VIP: {vip_status} | RES: {res_status}\n"
    doc = BufferedInputFile(file_content.encode('utf-8'), filename=f"DB_{datetime.now().strftime('%Y%m%d')}.txt")
    await call.message.answer_document(document=doc, caption="📋 <b>Database export complete.</b>", parse_mode='HTML')
    await call.answer()

@dp.message(AdminStates.manage_target_user)
async def process_user_lookup(m: Message, state: FSMContext):
    target = m.text.strip()
    if target.startswith('@'): target = target[1:]
    lookup = db_query("SELECT user_id FROM users WHERE user_id=? OR username=? COLLATE NOCASE", (target, target), fetchone=True)
    if lookup:
        refresh_reseller_status(int(lookup[0]))
    user_q = db_query("SELECT user_id, first_name, username, balance, is_reseller, orders_count, spent, joined_date, is_banned, warnings, is_vip FROM users WHERE user_id=? OR username=? COLLATE NOCASE", (target, target), fetchone=True)
    if not user_q: return await m.answer("❌ Target not found in the grid. Check ID/Username syntax.", reply_markup=admin_back_kb(), parse_mode='HTML')
    u_id, u_name, u_user, bal, is_res, orders, spent, joined, is_banned, warnings, is_vip = user_q
    await state.update_data(target_u_id=u_id)
    status_emoji = "🔴 BANNED" if is_banned else "🟢 ACTIVE"
    tags = []
    if is_res: tags.append("👑 Reseller")
    if is_vip: tags.append("🌟 VIP")
    type_str = " | ".join(tags) if tags else "👤 Regular"
    text = (f"🛡 <b><u>USER CONTROL TERMINAL</u></b> 🛡\n━━━━━━━━━━━━━━━━━━\n📛 <b>Name:</b> {u_name} (@{u_user})\n🆔 <b>ID:</b> <code>{u_id}</code>\n📊 <b>Status:</b> {status_emoji}\n🔰 <b>Type:</b> {type_str}\n⚠️ <b>Warnings Issued:</b> {warnings}\n━━━━━━━━━━━━━━━━━━\n💰 <b>Wallet Balance:</b> {fmt_curr(bal)}\n📦 <b>Orders:</b> {orders} | 💸 <b>Total Spent:</b> {fmt_curr(spent)}\n📅 <b>Joined:</b> {joined}")
    ban_btn_text = "Unban ✅" if is_banned else "Ban 🚫"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Add Funds ➕", callback_data=f"usrctrl_add_{u_id}", icon_custom_emoji_id=get_emoji_icon("add_balance"), style="success"), 
         InlineKeyboardButton(text="Minus Funds ➖", callback_data=f"usrctrl_min_{u_id}", icon_custom_emoji_id=get_emoji_icon("money_icon"), style="danger")],
        [InlineKeyboardButton(text=ban_btn_text, callback_data=f"usrctrl_ban_{u_id}", icon_custom_emoji_id=get_emoji_icon("shield_icon"), style="danger"), 
         InlineKeyboardButton(text="Warn User ⚠️", callback_data=f"usrctrl_warn_{u_id}", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="danger")],
        [InlineKeyboardButton(text="Give VIP 🌟" if not is_vip else "Remove VIP 🚫", callback_data=f"usrctrl_vip_{u_id}", icon_custom_emoji_id=get_emoji_icon("vip"), style="success")],
        [InlineKeyboardButton(text="Give Reseller 👑" if not is_res else "Remove Reseller 🚫", callback_data=f"usrctrl_reseller_{u_id}", icon_custom_emoji_id=get_emoji_icon("reseller"), style="success" if not is_res else "danger")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await m.answer(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("usrctrl_"))
async def handle_user_actions(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    action = call.data.split("_")[1]
    u_id = int(call.data.split("_")[2])
    await state.update_data(target_u_id=u_id)
    if action == "ban":
        current_status = db_query("SELECT is_banned FROM users WHERE user_id=?", (u_id,), fetchone=True)[0]
        if current_status == 0:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Yes, Ban", callback_data=f"confirm_ban_{u_id}", icon_custom_emoji_id=get_emoji_icon("check_icon"), style="danger"), 
                 InlineKeyboardButton(text="❌ Cancel", callback_data="admin_user_control_start", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
            ])
            await safe_edit_text(call.message, f"⚠️ Are you sure you want to <b>BAN</b> user <code>{u_id}</code>?", reply_markup=kb, parse_mode='HTML')
            await state.set_state(AdminStates.confirm_ban)
        else:
            db_query("UPDATE users SET is_banned=0 WHERE user_id=?", (u_id,))
            await call.answer("✅ User unbanned successfully!", show_alert=True)
            m = call.message; m.text = str(u_id); await process_user_lookup(m, state)
    elif action == "vip":
        current_status = db_query("SELECT is_vip FROM users WHERE user_id=?", (u_id,), fetchone=True)[0]
        if current_status == 1:
            db_query("UPDATE users SET is_vip=0 WHERE user_id=?", (u_id,))
            await call.answer("✅ VIP Removed!", show_alert=True)
        else:
            db_query("UPDATE users SET is_vip=1, vip_since=? WHERE user_id=?", (datetime.now().strftime("%Y-%m-%d"), u_id))
            await call.answer("✅ VIP Granted!", show_alert=True)
        m = call.message; m.text = str(u_id); await process_user_lookup(m, state)
    elif action == "reseller":
        current = db_query("SELECT is_reseller FROM users WHERE user_id=?", (u_id,), fetchone=True)
        current_status = bool(current[0]) if current else False
        if current_status:
            db_query("UPDATE users SET is_reseller=0, account_type='Regular', reseller_expires_at=NULL WHERE user_id=?", (u_id,))
            await call.answer("✅ Reseller Removed!", show_alert=True)
            m = call.message; m.text = str(u_id); await process_user_lookup(m, state)
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="1 Day", callback_data=f"usrres_plan_1_{u_id}", style="primary"),
                 InlineKeyboardButton(text="2 Days", callback_data=f"usrres_plan_2_{u_id}", style="primary"),
                 InlineKeyboardButton(text="5 Days", callback_data=f"usrres_plan_5_{u_id}", style="primary")],
                [InlineKeyboardButton(text="7 Days", callback_data=f"usrres_plan_7_{u_id}", style="primary"),
                 InlineKeyboardButton(text="30 Days", callback_data=f"usrres_plan_30_{u_id}", style="primary")],
                [InlineKeyboardButton(text="✏️ Custom Days", callback_data=f"usrres_custom_{u_id}", style="primary")],
                [InlineKeyboardButton(text="♾️ Lifetime Access", callback_data=f"usrres_lifetime_{u_id}", style="success")],
                [InlineKeyboardButton(text="Back to Panel", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
            ])
            await call.answer()
            await safe_edit_text(call.message, 
                f"👑 <b>Give Reseller Plan</b>\n\nTarget: <code>{u_id}</code>\n\n"
                "Select how long the reseller access should remain active:",
                reply_markup=kb, parse_mode='HTML'
            )
    elif action == "add":
        await safe_edit_text(call.message, "💰 Enter the amount to <b>ADD</b> to this user's wallet:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_add_money)
    elif action == "min":
        await safe_edit_text(call.message, "💸 Enter the amount to <b>DEDUCT</b> from this user's wallet:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_minus_money)
    elif action == "warn":
        await safe_edit_text(call.message, "⚠️ Type the strict warning message you want to send directly to this user:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_warning)

@dp.callback_query(F.data.startswith("usrres_plan_"))
async def admin_give_reseller_plan(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    try:
        parts = call.data.split("_")
        days = int(parts[2])
        u_id = int(parts[3])
        if days <= 0:
            raise ValueError
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid reseller plan.", show_alert=True)
    expires = datetime.now() + timedelta(days=days)
    db_query("UPDATE users SET is_reseller=1, reseller_since=?, reseller_expires_at=?, account_type='Reseller' WHERE user_id=?",
             (datetime.now().strftime("%Y-%m-%d"), expires.isoformat(timespec="seconds"), u_id))
    await call.answer(f"✅ Reseller granted for {days} day(s).", show_alert=True)
    try:
        await bot.send_message(u_id, f"🎉 <b>Congratulations! Your Reseller Dashboard is Activated.</b>\n\n👑 <b>Reseller Access:</b> {days} day(s)\n💰 You can now access reseller prices and benefits.", parse_mode='HTML')
    except Exception as e:
        logger.warning("Reseller activation notification failed: %s", e)
    m = call.message; m.text = str(u_id); await process_user_lookup(m, state)

@dp.callback_query(F.data.startswith("usrres_lifetime_"))
async def admin_give_reseller_lifetime(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    try:
        u_id = int(call.data.rsplit("_", 1)[1])
    except ValueError:
        return await call.answer("❌ Invalid user.", show_alert=True)
    db_query("UPDATE users SET is_reseller=1, reseller_since=?, reseller_expires_at=NULL, account_type='Reseller' WHERE user_id=?",
             (datetime.now().strftime("%Y-%m-%d"), u_id))
    await call.answer("✅ Lifetime Reseller Access granted.", show_alert=True)
    try:
        await bot.send_message(u_id, "🎉 <b>Congratulations! Your Reseller Dashboard is Activated.</b>\n\n👑 <b>Reseller Access:</b> Lifetime\n💰 You can now access reseller prices and benefits.", parse_mode='HTML')
    except Exception as e:
        logger.warning("Reseller activation notification failed: %s", e)
    m = call.message; m.text = str(u_id); await process_user_lookup(m, state)

@dp.callback_query(F.data.startswith("usrres_custom_"))
async def admin_custom_reseller_plan(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    try:
        u_id = int(call.data.rsplit("_", 1)[1])
    except ValueError:
        return await call.answer("❌ Invalid user.", show_alert=True)
    await state.update_data(reseller_plan_user_id=u_id)
    await call.answer()
    await safe_edit_text(call.message, 
        f"✏️ <b>Custom Reseller Plan</b>\n\nTarget: <code>{u_id}</code>\n\n"
        "Send the number of days. Example: <code>15</code>",
        reply_markup=admin_back_kb(), parse_mode='HTML'
    )
    await state.set_state(AdminStates.reseller_custom_days)

@dp.message(AdminStates.reseller_custom_days)
async def admin_save_custom_reseller_plan(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    try:
        days = int(m.text.strip())
        if days <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        return await m.answer("❌ Invalid days. Send a positive whole number, for example <code>15</code>.", parse_mode='HTML')
    data = await state.get_data()
    u_id = data.get("reseller_plan_user_id")
    if not u_id:
        await state.clear()
        return await m.answer("❌ Target user was lost. Please open User Control again.", reply_markup=admin_kb())
    expires = datetime.now() + timedelta(days=days)
    db_query("UPDATE users SET is_reseller=1, reseller_since=?, reseller_expires_at=?, account_type='Reseller' WHERE user_id=?",
             (datetime.now().strftime("%Y-%m-%d"), expires.isoformat(timespec="seconds"), u_id))
    await state.clear()
    try:
        await bot.send_message(u_id, f"🎉 <b>Congratulations! Your Reseller Dashboard is Activated.</b>\n\n👑 <b>Reseller Access:</b> {days} days\n💰 You can now access reseller prices and benefits.", parse_mode='HTML')
    except Exception as e:
        logger.warning("Reseller activation notification failed: %s", e)
    await m.answer(f"✅ Reseller granted for <b>{days} days</b> to <code>{u_id}</code>.", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data.startswith("usrres_back_"))
async def admin_reseller_plan_back(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    try:
        u_id = int(call.data.rsplit("_", 1)[1])
    except ValueError:
        return await call.answer("❌ Invalid user.", show_alert=True)
    await call.answer()
    m = call.message; m.text = str(u_id); await process_user_lookup(m, state)

@dp.callback_query(F.data.startswith("confirm_ban_"))
async def confirm_ban(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    u_id = int(call.data.split("_")[2])
    db_query("UPDATE users SET is_banned=1 WHERE user_id=?", (u_id,))
    await call.answer("🔴 User has been banned!", show_alert=True)
    await state.clear()
    m = call.message; m.text = str(u_id); await process_user_lookup(m, state)

@dp.message(AdminStates.wait_for_add_money)
async def exec_add_money(m: Message, state: FSMContext):
    try:
        amt = float(m.text)
        data = await state.get_data()
        u_id = data['target_u_id']
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (amt, u_id))
        await m.answer(f"✅ Successfully added {fmt_curr(amt)} to target <code>{u_id}</code>.", reply_markup=admin_kb(), parse_mode='HTML')
        try: await bot.send_message(u_id, f"💰 <b>Wallet Top-up!</b>\nAdmin has manually added {fmt_curr(amt)} to your wallet.", parse_mode='HTML')
        except: pass
        await state.clear()
    except ValueError: await m.answer("❌ Critical Error: Input must be a valid number.")

@dp.message(AdminStates.wait_for_minus_money)
async def exec_minus_money(m: Message, state: FSMContext):
    try:
        amt = float(m.text)
        data = await state.get_data()
        u_id = data['target_u_id']
        db_query("UPDATE users SET balance = balance - ? WHERE user_id=?", (amt, u_id))
        await m.answer(f"✅ Successfully deducted {fmt_curr(amt)} from target <code>{u_id}</code>.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Critical Error: Input must be a valid number.")

@dp.message(AdminStates.wait_for_warning)
async def exec_warn_user(m: Message, state: FSMContext):
    data = await state.get_data()
    u_id = data['target_u_id']
    warn_text = m.text
    db_query("UPDATE users SET warnings = warnings + 1 WHERE user_id=?", (u_id,))
    await m.answer(f"✅ Official warning dispatched to <code>{u_id}</code>.", reply_markup=admin_kb(), parse_mode='HTML')
    try: await bot.send_message(u_id, f"⚠️ <b>OFFICIAL WARNING FROM SYSTEM ADMIN:</b>\n\n{warn_text}\n\n<i>Subsequent infractions may lead to an automated grid ban.</i>", parse_mode='HTML')
    except: pass
    await state.clear()

# ==============================================================================
# 18. ADMIN STATISTICS
# ==============================================================================
@dp.callback_query(F.data == "admin_view_stats")
async def admin_dashboard_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    t_users = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    t_resellers = db_query("SELECT COUNT(*) FROM users WHERE is_reseller=1", fetchone=True)[0]
    t_vip = db_query("SELECT COUNT(*) FROM users WHERE is_vip=1", fetchone=True)[0]
    t_prods = db_query("SELECT COUNT(*) FROM products", fetchone=True)[0]
    t_keys = db_query("SELECT COUNT(*) FROM product_keys WHERE is_used=0", fetchone=True)[0]
    t_rev = db_query("SELECT SUM(spent) FROM users", fetchone=True)[0] or 0.0
    today_str = datetime.now().strftime("%Y-%m-%d")
    t_spins = db_query("SELECT COUNT(*) FROM users WHERE last_spin LIKE ?", (f"{today_str}%",), fetchone=True)[0]
    msg = (f"📊 <b><u>GRID INTELLIGENCE DASHBOARD</u></b> 📊\n━━━━━━━━━━━━━━━━━━\n👥 <b>Total Grid Users:</b> {t_users}\n👑 <b>Wholesale Resellers:</b> {t_resellers}\n🌟 <b>Elite VIP Members:</b> {t_vip}\n━━━━━━━━━━━━━━━━━━\n📦 <b>Active Products:</b> {t_prods}\n🔑 <b>Unused Keys in Vault:</b> {t_keys}\n💰 <b>Total Gross Revenue:</b> {fmt_curr(t_rev)}\n🎰 <b>Ludo Spins Today:</b> {t_spins}\n━━━━━━━━━━━━━━━━━━")
    await safe_edit_text(call.message, msg, reply_markup=admin_back_kb(), parse_mode='HTML')

# ==============================================================================
# 19. ADMIN PRODUCT MANAGEMENT
# ==============================================================================
@dp.callback_query(F.data == "admin_add_prod")
async def add_prod_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in FIXED_CATEGORIES:
        emoji_id = get_category_emoji(cat)
        kb.inline_keyboard.append([InlineKeyboardButton(text=cat, callback_data=f"addprod_cat_{cat}", icon_custom_emoji_id=emoji_id, style="danger")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Cancel", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await safe_edit_text(call.message, "<b>Step 1:</b> Choose the <b>Category</b> for this product:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("addprod_cat_"))
async def add_prod_category_selected(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    category = call.data.split("addprod_cat_", 1)[1]
    await state.update_data(cat=category)

    await safe_edit_text(call.message, f"<b>Step 2:</b> Enter <b>PANEL NAME</b>\n(e.g., 'MST PANEL', 'DRIP PANEL'):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_panel_name)


@dp.message(AdminStates.add_prod_panel_name)
async def add_prod_panel_name(m: Message, state: FSMContext):
    await state.update_data(panel_name=m.text)
    await m.answer("<b>Step 3:</b> Enter <b>PACKAGE DURATION/DATE NAME</b>\n(e.g., '7 Days', '1 Month'):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_name)

@dp.message(AdminStates.add_prod_name)
async def add_prod_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("⏳ Enter Time Validity String (e.g., '24 Hours'):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_validity)

@dp.message(AdminStates.add_prod_validity)
async def add_prod_validity(m: Message, state: FSMContext):
    await state.update_data(validity=m.text)
    await m.answer("📱 Enter strict Device Enforcement Limit (e.g., '1 Device HWID'):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_device_limit)

@dp.message(AdminStates.add_prod_device_limit)
async def add_prod_device_limit(m: Message, state: FSMContext):
    await state.update_data(device_limit=m.text)
    await m.answer("💰 Enter standard **User Price** in Rupees (₹) (e.g., 500):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_price)

@dp.message(AdminStates.add_prod_price)
async def add_prod_price(m: Message, state: FSMContext):
    try:
        await state.update_data(price=float(m.text))
        await m.answer("👑 Enter wholesale **Reseller Price** in Rupees (₹) (e.g., 300):", parse_mode='HTML')
        await state.set_state(AdminStates.add_prod_reseller_price)
    except ValueError: await m.answer("❌ Invalid input datatype! Must be numerical.")

@dp.message(AdminStates.add_prod_reseller_price)
async def add_prod_reseller_price(m: Message, state: FSMContext):
    try:
        await state.update_data(reseller_price=float(m.text))
        await m.answer("🔗 Enter direct APK/Payload Download Link (or type 'none' to omit):", parse_mode='HTML')
        await state.set_state(AdminStates.add_prod_apk)
    except ValueError: await m.answer("❌ Invalid input datatype! Must be numerical.")

@dp.message(AdminStates.add_prod_apk)
async def add_prod_apk(m: Message, state: FSMContext):
    await state.update_data(apk="" if m.text.lower() == 'none' else m.text)

    # Product creation follows the API that is currently ON.
    # If both are ON, the admin can choose either one. If only one is ON,
    # only that API is shown, so the product is automatically configured for it.
    api1_on = get_setting("external_api1_status", "ON") == "ON"
    api2_on = get_setting("external_api2_status", "OFF") == "ON"

    buttons = []
    if api1_on:
        buttons.append([InlineKeyboardButton(
            text="🔗 API 1 — Generate Key",
            callback_data="addprod_ext_yes",
            icon_custom_emoji_id=get_emoji_icon("check_icon"),
            style="success"
        )])
    if api2_on:
        buttons.append([InlineKeyboardButton(
            text="📱 APK API — Generate Key",
            callback_data="addprod_ext2_yes",
            icon_custom_emoji_id=get_emoji_icon("check_icon"),
            style="primary"
        )])
    buttons.append([InlineKeyboardButton(
        text="📥 Manual Keys",
        callback_data="addprod_ext_no",
        icon_custom_emoji_id=get_emoji_icon("back"),
        style="danger"
    )])

    if api1_on and api2_on:
        message = "🔗 <b>Choose the key generation source for this product:</b>\n\nBoth APIs are ON, so you can choose API 1 or APK API."
    elif api1_on:
        message = "🔗 <b>API 1 is ON.</b>\n\nThis product will use API 1. Enter the API 1 Product ID, then the API duration/price tier."
    elif api2_on:
        message = "📱 <b>APK API is ON.</b>\n\nThis product will use the APK API. Enter the Variant ID used by that API."
    else:
        message = "📥 <b>Both external APIs are OFF.</b>\n\nYou can create this product with Manual Keys."

    await m.answer(message, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_external)

@dp.callback_query(F.data == "addprod_ext_yes", AdminStates.add_prod_external)
async def add_prod_external_yes(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    if get_setting("external_api1_status", "ON") != "ON":
        return await call.answer("❌ External API 1 is OFF. Turn it ON from /admin first.", show_alert=True)
    await state.update_data(external_enabled=1, external_api_type=1)
    await safe_edit_text(call.message, "🆔 Enter the <b>External API 1 Product ID (PID)</b> used by API 1:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_external_product_id)

@dp.callback_query(F.data == "addprod_ext2_yes", AdminStates.add_prod_external)
async def add_prod_external2_yes(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    if get_setting("external_api2_status", "OFF") != "ON":
        return await call.answer("❌ APK API is OFF. Turn it ON from /admin → APK API first.", show_alert=True)
    await state.update_data(external_enabled=1, external_api_type=2)
    await safe_edit_text(call.message, "🆔 Enter the <b>APK Variant ID</b> used by API 2:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_external_product_id)

@dp.message(AdminStates.add_prod_external_product_id)
async def add_prod_external_pid(m: Message, state: FSMContext):
    pid = m.text.strip()
    if not pid:
        return await m.answer("❌ Product PID cannot be empty.")
    data = await state.get_data()
    # The API's duration is NOT necessarily the Telegram package name.
    # Ask for the exact duration/price tier configured on the API.
    await state.update_data(external_product_id=pid, requires_android_id=0)
    data = await state.get_data()
    if int(data.get("external_api_type", 1) or 1) == 2:
        conn = sqlite3.connect('yp_shop.db')
        c = conn.cursor()
        c.execute("""INSERT INTO products
            (category, panel_name, name, price_inr, reseller_price, stock, apk_link, validity, device_limit,
             external_enabled, external_product_id, requires_android_id, external_duration, external_api_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data['cat'], data['panel_name'], data['name'], data['price'], data['reseller_price'], 1,
             data['apk'], data['validity'], data['device_limit'], 1, pid, 0, '', 2))
        prod_id = c.lastrowid
        conn.commit(); conn.close()
        await m.answer(
            f"✅ <b>APK API Product Created!</b>\n\nProduct ID: <code>{prod_id}</code>\n"
            f"Variant ID: <code>{pid}</code>\n\n"
            "This product will use the Android APK gateway with quantity=1.",
            reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
        return
    await m.answer(
        "⏱ <b>Enter the exact XYZ API duration/price tier.</b>\n\n"
        "Examples: <code>3 Hours</code>, <code>1 Day</code>, <code>7 Days</code>.\n"
        f"Your shop validity is: <code>{data.get('validity', '')}</code>\n\n"
        "If the API uses the same duration, send the same value.",
        reply_markup=admin_back_kb(), parse_mode='HTML'
    )
    await state.set_state(AdminStates.add_prod_external_duration)

@dp.message(AdminStates.add_prod_external_duration)
async def add_prod_external_duration(m: Message, state: FSMContext):
    api_duration = normalize_api_duration(m.text.strip())
    if not api_duration:
        return await m.answer("❌ API duration cannot be empty.")
    data = await state.get_data()
    conn = sqlite3.connect('yp_shop.db')
    c = conn.cursor()
    c.execute("""INSERT INTO products
        (category, panel_name, name, price_inr, reseller_price, stock, apk_link, validity, device_limit,
         external_enabled, external_product_id, requires_android_id, external_duration, external_api_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data['cat'], data['panel_name'], data['name'], data['price'], data['reseller_price'], 1,
         data['apk'], data['validity'], data['device_limit'], 1, data['external_product_id'], 0, api_duration, data.get('external_api_type', 1)))
    prod_id = c.lastrowid
    conn.commit(); conn.close()
    await m.answer(
        f"✅ <b>API Product Created!</b>\n\nProduct ID: <code>{prod_id}</code>\n"
        f"External Product ID: <code>{data['external_product_id']}</code>\n"
        f"API Duration: <code>{api_duration}</code>\n\n"
        "The API will generate and deliver the key when the customer buys it.",
        reply_markup=admin_kb(), parse_mode='HTML'
    )
    await state.clear()

@dp.callback_query(F.data == "addprod_ext_no", AdminStates.add_prod_external)
async def add_prod_external_no(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    await state.update_data(external_enabled=0, external_product_id="", requires_android_id=0)
    await safe_edit_text(call.message, "📥 <b>Manual Key Product</b>\n\nNow send the keys, one key per line:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_keys)

@dp.message(AdminStates.add_prod_keys)
async def add_prod_keys(m: Message, state: FSMContext):
    keys = [k.strip() for k in m.text.strip().split('\n') if k.strip()]
    if not keys:
        return await m.answer("❌ No valid keys found. Send at least one key.")
    data = await state.get_data()
    stock = len(keys)
    conn = sqlite3.connect('yp_shop.db')
    c = conn.cursor()
    c.execute("""INSERT INTO products
        (category, panel_name, name, price_inr, reseller_price, stock, apk_link, validity, device_limit,
         external_enabled, external_product_id, requires_android_id, external_api_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data['cat'], data['panel_name'], data['name'], data['price'], data['reseller_price'], stock,
         data['apk'], data['validity'], data['device_limit'], 0, '', 0, 0))
    prod_id = c.lastrowid
    for k in keys:
        c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (prod_id, k))
    conn.commit(); conn.close()
    await m.answer(f"✅ <b>Manual Product Created!</b>\n\n📦 Product ID: <code>{prod_id}</code>\n🔒 Stock: {stock} keys", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

PRODUCTS_PER_ADMIN_PAGE = 12

async def _show_admin_manage_products(call: CallbackQuery, page: int = 0):
    if not is_admin(call.from_user.id):
        return

    prods = db_query(
        "SELECT id, name, category, panel_name, stock, is_active FROM products",
        fetchall=True
    )
    prods = sorted(
        prods or [],
        key=lambda row: (
            natural_sort_key(row[2]),
            natural_sort_key(row[3]),
            natural_sort_key(row[1])
        )
    )

    if not prods:
        return await safe_edit_text(call.message, 
            "📦 Store Database is completely empty.",
            reply_markup=admin_back_kb(),
            parse_mode='HTML'
        )

    total_pages = (len(prods) + PRODUCTS_PER_ADMIN_PAGE - 1) // PRODUCTS_PER_ADMIN_PAGE
    page = max(0, min(page, total_pages - 1))
    start = page * PRODUCTS_PER_ADMIN_PAGE
    page_prods = prods[start:start + PRODUCTS_PER_ADMIN_PAGE]

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in page_prods:
        status_dot = "🟢" if p[5] else "🔴"
        panel_name = p[3] if p[3] is not None else ""
        category = str(p[2] or "")
        name = str(p[1] or "")
        # Keep button text short so Telegram's reply_markup stays below its size limit.
        label = f"{status_dot} {category} | {panel_name} | {name} | Stock: {p[4]}"
        if len(label) > 90:
            label = label[:87] + "..."
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"admin_view_p_{p[0]}_page_{page}",
                style="primary"
            )
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="◀️ Previous",
            callback_data=f"admin_manage_prods_page_{page - 1}",
            style="primary"
        ))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(
            text="Next ▶️",
            callback_data=f"admin_manage_prods_page_{page + 1}",
            style="primary"
        ))
    if nav:
        kb.inline_keyboard.append(nav)

    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text=f"📄 Page {page + 1}/{total_pages} • {len(prods)} Products",
            callback_data="ignore_stock_click",
            style="primary"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="Back to Admin",
            callback_data="admin_panel_back",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])

    await safe_edit_text(call.message, 
        "📦 <b>Database Editor: Select Node to modify</b>\n\n"
        f"Showing {start + 1}-{start + len(page_prods)} of {len(prods)} products.",
        reply_markup=kb,
        parse_mode='HTML'
    )

@dp.callback_query(F.data == "admin_manage_prods")
async def admin_manage_prods(call: CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass
    await _show_admin_manage_products(call, 0)

@dp.callback_query(F.data.startswith("admin_manage_prods_page_"))
async def admin_manage_prods_page(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    try:
        page = int(call.data.rsplit("_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("Invalid page.", show_alert=True)
    await _show_admin_manage_products(call, page)
    await call.answer()

@dp.callback_query(F.data.startswith("admin_view_p_"))
async def admin_view_product(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    try:
        parts = call.data.split("_")
        p_id = int(parts[3])
        page = int(parts[5]) if len(parts) > 5 and parts[4] == "page" else 0
        prod = db_query("SELECT * FROM products WHERE id=?", (p_id,), fetchone=True)
        if not prod: return await call.answer("❌ Architecture fault: Node lost!", show_alert=True)
        panel_name = prod[2] if prod[2] is not None else ""
        price_inr = float(prod[4]) if prod[4] is not None and prod[4] != "" else 0.0
        reseller_price = float(prod[5]) if prod[5] is not None and prod[5] != "" else 0.0
        external_enabled = bool(prod[12]) if len(prod) > 12 else False
        external_api_type = int(prod[17] or 1) if len(prod) > 17 and prod[17] is not None else (1 if external_enabled else 0)
        api_source = "API 2" if external_enabled and external_api_type == 2 else ("API 1" if external_enabled else "Manual Keys")
        source_id_label = "API 2 Variant ID" if external_enabled and external_api_type == 2 else "API 1 PID"
        source_id_value = prod[13] if external_enabled and prod[13] else "None"
        source_duration_line = f"<b>API 1 Duration:</b> {prod[15] if len(prod) > 15 and prod[15] else 'None'}\n" if external_enabled and external_api_type == 1 else ""
        text = (f"📦 <b><u>NODE DEEP DIVE DETAILS</u></b>\n━━━━━━━━━━━━━━━━━━\n<b>ID:</b> <code>{prod[0]}</code>\n<b>Panel Group:</b> {prod[1]}\n<b>Panel Name:</b> {panel_name}\n<b>Package Date/Time:</b> {prod[3]}\n<b>Standard Price:</b> ₹{price_inr:.2f}\n👑 <b>Wholesale Price:</b> ₹{reseller_price:.2f}\n<b>Vault Stock:</b> {prod[6]}\n<b>Key Source:</b> <b>{api_source}</b>\n<b>{source_id_label}:</b> {source_id_value}\n{source_duration_line}<b>Payload Link:</b> {prod[7] if prod[7] else 'None'}\n<b>Time Config:</b> {prod[8]}\n<b>HWID Limit:</b> {prod[9]}\n<b>Visibility:</b> {'Active' if prod[10] else 'Hidden'}\n━━━━━━━━━━━━━━━━━━")
        toggle_btn_text = "Hide Product 👁‍🗨" if prod[10] else "Unhide Product 👁"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Edit Panel Group 🏷️", callback_data=f"edit_p_{p_id}_cat_page_{page}", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary"), 
             InlineKeyboardButton(text="Edit Panel Name 🏷️", callback_data=f"edit_p_{p_id}_panel_name_page_{page}", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")],
            [InlineKeyboardButton(text="Edit Package Name ✏️", callback_data=f"edit_p_{p_id}_name_page_{page}", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")],
            [InlineKeyboardButton(text="Edit Price 💰", callback_data=f"edit_p_{p_id}_price_page_{page}", icon_custom_emoji_id=get_emoji_icon("money_icon"), style="primary"), 
             InlineKeyboardButton(text="Edit R-Price 👑", callback_data=f"edit_p_{p_id}_rprice_page_{page}", icon_custom_emoji_id=get_emoji_icon("money_icon"), style="primary")],
            [InlineKeyboardButton(text="Edit Validity ⏳", callback_data=f"edit_p_{p_id}_validity_page_{page}", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary"), 
             InlineKeyboardButton(text="Edit Device 📱", callback_data=f"edit_p_{p_id}_device_page_{page}", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")],
            [InlineKeyboardButton(text="🔗 Key Source / API ON-OFF", callback_data=f"edit_p_{p_id}_api_source_page_{page}", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")],
            [InlineKeyboardButton(text="Edit APK Link 🔗", callback_data=f"edit_p_{p_id}_apk_page_{page}", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary"), 
             InlineKeyboardButton(text="Add Keys ➕", callback_data=f"edit_p_{p_id}_keys_page_{page}", icon_custom_emoji_id=get_emoji_icon("add_balance"), style="success")],
            [InlineKeyboardButton(text="Add to Stock 📦➕", callback_data=f"edit_p_{p_id}_stock_add_page_{page}", icon_custom_emoji_id=get_emoji_icon("add_balance"), style="success")],
            [InlineKeyboardButton(text="Delete Key 🗑", callback_data=f"delkey_p_{p_id}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger"), 
             InlineKeyboardButton(text=toggle_btn_text, callback_data=f"toggle_p_{p_id}", icon_custom_emoji_id=get_emoji_icon("check_icon"), style="primary")],
            [InlineKeyboardButton(text="Nuke Full Node 🗑", callback_data=f"delete_p_{p_id}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger"), 
             InlineKeyboardButton(text="BACK", callback_data=f"admin_manage_prods_page_{page}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
        ])
        if external_enabled and external_api_type == 1:
            kb.inline_keyboard.insert(6, [InlineKeyboardButton(text="Edit API 1 PID 🆔", callback_data=f"edit_p_{p_id}_api_product_id_page_{page}", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")])
            kb.inline_keyboard.insert(7, [InlineKeyboardButton(text="Edit API 1 Duration ⏱️", callback_data=f"edit_p_{p_id}_api_duration_page_{page}", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")])
        elif external_enabled and external_api_type == 2:
            kb.inline_keyboard.insert(6, [InlineKeyboardButton(text="Edit API 2 Variant ID 🆔", callback_data=f"edit_p_{p_id}_api_product_id_page_{page}", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")])

        await safe_edit_text(call.message, text, reply_markup=kb, disable_web_page_preview=True, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error in admin_view_product: {e}")
        await safe_edit_text(call.message, f"❌ Error loading product: {str(e)}", reply_markup=admin_back_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_product_ids")
async def admin_product_ids_menu(call: CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass
    if not is_admin(call.from_user.id):
        return

    rows = db_query(
        """SELECT category, MIN(id)
           FROM products
           WHERE is_active=1
           GROUP BY category
           ORDER BY category""",
        fetchall=True
    ) or []

    if not rows:
        return await safe_edit_text(call.message, 
            "🆔 <b>PRODUCT ID</b>\n\n❌ No active products found.",
            reply_markup=admin_back_kb(),
            parse_mode="HTML"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for category, anchor_id in rows:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=str(category),
                callback_data=f"admin_pid_cat_{anchor_id}",
                icon_custom_emoji_id=get_category_emoji(category),
                style="primary"
            )
        ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="Back to Admin",
            callback_data="admin_panel_back",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])
    await safe_edit_text(call.message, 
        "🆔 <b>PRODUCT ID</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        "Select the category to view its price-list Product IDs:",
        reply_markup=kb,
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("admin_pid_cat_"))
async def admin_product_ids_category(call: CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass
    if not is_admin(call.from_user.id):
        return
    try:
        anchor_id = int(call.data.split("admin_pid_cat_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid category.", show_alert=True)

    anchor = db_query(
        "SELECT category FROM products WHERE id=? AND is_active=1",
        (anchor_id,), fetchone=True
    )
    if not anchor:
        return await call.answer("❌ Category not found.", show_alert=True)

    category = (anchor[0] or "").strip()
    panels = db_query(
        """SELECT panel_name, MIN(id)
           FROM products
           WHERE category=? AND is_active=1
           GROUP BY panel_name
           ORDER BY panel_name""",
        (category,), fetchall=True
    ) or []

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for panel_name, panel_anchor_id in panels:
        label = str(panel_name).strip() if panel_name else "(No Panel Name)"
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{label} — ID {panel_anchor_id}",
                callback_data=f"admin_pid_panel_{panel_anchor_id}",
                style="primary"
            )
        ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="BACK",
            callback_data="admin_product_ids",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])

    await safe_edit_text(call.message, 
        f"🆔 <b>PRODUCT ID</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"📂 <b>Category:</b> {category}\n\n"
        "Select a panel / price list:",
        reply_markup=kb,
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("admin_pid_panel_"))
async def admin_product_ids_panel(call: CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass
    if not is_admin(call.from_user.id):
        return
    try:
        anchor_id = int(call.data.split("admin_pid_panel_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid Product ID.", show_alert=True)

    anchor = db_query(
        "SELECT category, panel_name FROM products WHERE id=? AND is_active=1",
        (anchor_id,), fetchone=True
    )
    if not anchor:
        return await call.answer("❌ Price list not found.", show_alert=True)

    category = (anchor[0] or "").strip()
    panel_name = (anchor[1] or "").strip()

    if panel_name:
        prods = db_query(
            """SELECT id, name, validity, price_inr, reseller_price
               FROM products
               WHERE category=? AND panel_name=? AND is_active=1
               ORDER BY name""",
            (category, panel_name), fetchall=True
        ) or []
    else:
        prods = db_query(
            """SELECT id, name, validity, price_inr, reseller_price
               FROM products
               WHERE category=? AND is_active=1
               ORDER BY name""",
            (category,), fetchall=True
        ) or []

    if not prods:
        return await call.answer("❌ No active products in this price list.", show_alert=True)

    text = (
        "🆔 <b>PRODUCT ID / PRICE LIST</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📂 <b>Category:</b> {category}\n"
        f"📦 <b>Panel:</b> {panel_name or 'No Panel Name'}\n"
        f"🆔 <b>PRICE LIST ID:</b> <code>{anchor_id}</code>\n\n"
        f"🔗 <b>Start:</b> <code>/start plist_{anchor_id}</code>\n\n"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[])

    for prod_id, name, validity, price_inr, reseller_price in prods:
        text += (
            f"• <b>{name}</b>\n"
            f"  🆔 Product ID: <code>{prod_id}</code>\n"
            f"  ⏱ Validity: {validity}\n"
            f"  💰 Price: {fmt_curr(float(price_inr or 0))}\n"
            f"  👑 Reseller: {fmt_curr(float(reseller_price or 0))}\n\n"
        )

    # One stable ID represents the whole price list. Existing product IDs are
    # also shown for each individual package without modifying them.
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text=f"🔗 Open Price List (plist_{anchor_id})",
            url=f"https://t.me/{BOT_USERNAME.lstrip('@')}?start=plist_{anchor_id}",
            style="success"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="BACK",
            callback_data=f"admin_pid_cat_{anchor_id}",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])
    await safe_edit_text(call.message, 
        text,
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )


@dp.callback_query(F.data == "admin_maintenance_center")
async def admin_maintenance_center(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    rows = []
    for category in FIXED_CATEGORIES:
        count = db_query("SELECT COUNT(*) FROM products WHERE category LIKE ?", (category + '%',), fetchone=True)
        if count and count[0] > 0:
            anchor = db_query("SELECT id FROM products WHERE category LIKE ? ORDER BY id LIMIT 1", (category + '%',), fetchone=True)
            if anchor:
                rows.append((category, anchor[0]))
    if not rows:
        return await safe_edit_text(call.message, "🛠 <b>MAINTENANCE CENTER</b>\n\n❌ No products have been added yet.", reply_markup=admin_back_kb(), parse_mode='HTML')
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for category, anchor_id in rows:
        kb.inline_keyboard.append([InlineKeyboardButton(text=category, callback_data=f"admin_maint_cat_{anchor_id}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await safe_edit_text(call.message, "🛠 <b>MAINTENANCE CENTER</b>\n━━━━━━━━━━━━━━━━━━\n\nSelect a category:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("admin_maint_cat_"))
async def admin_maintenance_category(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    try:
        anchor_id = int(call.data.split("admin_maint_cat_", 1)[1])
    except ValueError:
        return await call.answer("❌ Invalid category selection.", show_alert=True)
    anchor = db_query("SELECT category FROM products WHERE id=?", (anchor_id,), fetchone=True)
    if not anchor:
        return await call.answer("❌ Category not found.", show_alert=True)
    category = anchor[0]
    panels = db_query("SELECT panel_name, MIN(id) FROM products WHERE category=? GROUP BY panel_name ORDER BY panel_name", (category,), fetchall=True)
    panels = [p for p in panels if (p[0] or '').strip()]
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if panels:
        for panel, panel_anchor_id in panels:
            states = db_query("SELECT COUNT(*), SUM(CASE WHEN maintenance=1 THEN 1 ELSE 0 END) FROM products WHERE category=? AND panel_name=?", (category, panel), fetchone=True)
            total = states[0] or 0
            on_count = states[1] or 0
            state_text = "🛠 ON" if on_count == total else ("⚠️ PARTIAL" if on_count else "🟢 OFF")
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"{panel} — {state_text}", callback_data=f"admin_maint_panel_{panel_anchor_id}", style="danger" if on_count else "primary")])
    else:
        prods = db_query("SELECT id, name, maintenance FROM products WHERE category=? ORDER BY name", (category,), fetchall=True)
        for prod_id, name, maintenance in prods:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"{'🛠' if maintenance else '🟢'} {name}", callback_data=f"admin_maint_prod_{prod_id}", style="danger" if maintenance else "primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="admin_maintenance_center", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await safe_edit_text(call.message, f"🛠 <b>MAINTENANCE CENTER</b>\n\n📂 <b>Category:</b> {category}\n\nSelect panel:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("admin_maint_panel_"))
async def admin_maintenance_panel(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    try:
        anchor_id = int(call.data.split("admin_maint_panel_", 1)[1])
    except ValueError:
        return await call.answer("❌ Invalid panel selection.", show_alert=True)
    anchor = db_query("SELECT category, panel_name FROM products WHERE id=?", (anchor_id,), fetchone=True)
    if not anchor:
        return await call.answer("❌ Panel not found.", show_alert=True)
    category, panel = anchor
    rows = db_query("SELECT id, name, maintenance FROM products WHERE category=? AND panel_name=? ORDER BY name", (category, panel), fetchall=True)
    if not rows:
        return await call.answer("❌ No products found for this panel.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for prod_id, name, maintenance in rows:
        # Products/packages are only selectors here. Maintenance itself is controlled panel-wide.
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"📦 {name}", callback_data=f"admin_maint_prod_{prod_id}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data=f"admin_maint_cat_{anchor_id}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await safe_edit_text(call.message, f"🛠 <b>MAINTENANCE CENTER</b>\n\n📂 <b>Category:</b> {category}\n📦 <b>Panel:</b> {panel}\n\nSelect a product/package:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("admin_maint_prod_"))
async def admin_maintenance_product(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try: prod_id=int(call.data.split("admin_maint_prod_",1)[1])
    except ValueError: return await call.answer("❌ Invalid product selection.", show_alert=True)
    row=db_query("SELECT category,panel_name,name,maintenance FROM products WHERE id=?",(prod_id,),fetchone=True)
    if not row: return await call.answer("❌ Product not found.", show_alert=True)
    category,panel,name,maintenance=row
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 MAINTENANCE ON" if maintenance else "🔵 MAINTENANCE OFF", callback_data=f"admin_maint_toggle_{prod_id}", style="danger" if maintenance else "primary")],
        [InlineKeyboardButton(text="BACK", callback_data=f"admin_maint_panel_{prod_id}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await safe_edit_text(call.message, f"🛠 <b>MAINTENANCE CENTER</b>\n\n📂 <b>Category:</b> {category}\n📦 <b>Panel:</b> {panel or 'N/A'}\n📌 <b>Selected Product:</b> {name}\n\nThe whole panel will be affected.", reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("admin_maint_toggle_"))
async def admin_maintenance_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    # Maintenance-only fix: validate the callback/product row before
    # unpacking it, so an empty/malformed result cannot raise IndexError.
    try:
        prod_id = int(call.data.split("admin_maint_toggle_", 1)[1])
    except (ValueError, IndexError, TypeError):
        return await call.answer("❌ Invalid maintenance selection.", show_alert=True)

    row = db_query(
        "SELECT category, panel_name, name, maintenance FROM products WHERE id=?",
        (prod_id,),
        fetchone=True
    )

    if not row:
        return await call.answer("❌ Product not found.", show_alert=True)

    try:
        if len(row) < 4:
            return await call.answer("❌ Product data is incomplete.", show_alert=True)
        category, panel, name, maintenance = row[0], row[1], row[2], row[3]
    except (TypeError, IndexError):
        return await call.answer("❌ Product data is invalid.", show_alert=True)

    new_status = 0 if maintenance else 1

    if (panel or "").strip():
        db_query(
            "UPDATE products SET maintenance=? WHERE category=? AND panel_name=?",
            (new_status, category, panel)
        )
        target_name = str(panel)
    else:
        db_query(
            "UPDATE products SET maintenance=? WHERE id=?",
            (new_status, prod_id)
        )
        target_name = str(name)

    await call.answer(
        f"Maintenance {'ON' if new_status else 'OFF'}: {target_name}",
        show_alert=True
    )

    # Refresh the maintenance product screen directly. Do not call
    # admin_maintenance_product() here because the callback data is
    # admin_maint_toggle_<id>, not admin_maint_prod_<id>.
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔴 MAINTENANCE ON" if new_status else "🔵 MAINTENANCE OFF",
            callback_data=f"admin_maint_toggle_{prod_id}",
            style="danger" if new_status else "primary"
        )],
        [InlineKeyboardButton(
            text="BACK",
            callback_data=f"admin_maint_panel_{prod_id}",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )]
    ])
    await safe_edit_text(call.message, 
        f"🛠 <b>MAINTENANCE CENTER</b>\n\n📂 <b>Category:</b> {category}\n📦 <b>Panel:</b> {panel or 'N/A'}\n📌 <b>Selected Product:</b> {name}\n\nThe whole panel will be affected.",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("maintenance_product_"))
async def customer_maintenance_product(call: CallbackQuery):
    try:
        prod_id = int(call.data.split("maintenance_product_", 1)[1])
    except ValueError:
        return await call.answer("🛠️ This product is under maintenance.", show_alert=True)

    row = db_query(
        "SELECT category, panel_name, maintenance FROM products WHERE id=? AND is_active=1",
        (prod_id,), fetchone=True
    )
    if row and row[2]:
        return await call.answer("🛠️ This product is under maintenance.", show_alert=True)

    await call.answer("This product is available now. Please try again.", show_alert=True)

@dp.callback_query(F.data.startswith("toggle_p_"))
async def admin_toggle_product(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    p_id = int(call.data.split("_")[2])
    current = db_query("SELECT is_active FROM products WHERE id=?", (p_id,), fetchone=True)[0]
    new_val = 0 if current == 1 else 1
    db_query("UPDATE products SET is_active=? WHERE id=?", (new_val, p_id))
    await call.answer("Visibility updated successfully!", show_alert=True)
    await admin_view_product(call)

# ==============================================================================
# PRODUCT KEY SOURCE / API SELECTOR
# ==============================================================================
@dp.callback_query(F.data.startswith("set_api_source_"))
async def set_product_api_source(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        parts = call.data.split("_")
        source = int(parts[3])
        p_id = int(parts[4])
        page = int(parts[5]) if len(parts) > 5 else 0
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid API source selection.", show_alert=True)
    if source not in (0, 1, 2):
        return await call.answer("❌ Invalid API source.", show_alert=True)
    if source == 1 and get_setting("external_api1_status", "ON") != "ON":
        return await call.answer("❌ External API 1 is OFF. Turn it ON first.", show_alert=True)
    if source == 2 and get_setting("external_api2_status", "OFF") != "ON":
        return await call.answer("❌ External API 2 is OFF. Turn it ON first.", show_alert=True)
    if source == 0:
        db_query("UPDATE products SET external_enabled=0, external_api_type=0 WHERE id=?", (p_id,))
        await call.answer("✅ Manual Keys enabled for this product.", show_alert=True)
    else:
        db_query("UPDATE products SET external_enabled=1, external_api_type=? WHERE id=?", (source, p_id))
        await call.answer(f"✅ External API {source} enabled for this product.", show_alert=True)
    # Return directly to the exact product editor page the admin came from.
    # Do not show an intermediate "Loading product..." screen.
    call.data = f"admin_view_p_{p_id}_page_{page}"
    await admin_view_product(call)

# ==============================================================================
# FIX: Edit product field – correctly handle different data types
# ==============================================================================
@dp.callback_query(F.data.startswith("edit_p_"))
async def start_edit_product(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    parts = call.data.split("_")
    p_id = int(parts[2])
    field_parts = parts[3:]
    page = 0
    if "page" in field_parts:
        i = field_parts.index("page")
        try:
            page = int(field_parts[i + 1])
            field_parts = field_parts[:i]
        except (ValueError, IndexError):
            page = 0
    field = "_".join(field_parts)
    if field == "api_source":
        # Key Source is handled here so it cannot be intercepted by another edit_p_ callback.
        row = db_query(
            "SELECT name, external_enabled, COALESCE(external_api_type, 0) FROM products WHERE id=?",
            (p_id,), fetchone=True
        )
        if not row:
            return await call.answer("❌ Product not found.", show_alert=True)
        name, enabled, api_type = row
        current = "APK API" if enabled and int(api_type or 0) == 2 else ("API 1" if enabled else "Manual Keys")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Use API 1", callback_data=f"set_api_source_1_{p_id}_{page}", style="success")],
            [InlineKeyboardButton(text="📱 Use APK API", callback_data=f"set_api_source_2_{p_id}_{page}", style="primary")],
            [InlineKeyboardButton(text="📥 Use Manual Keys", callback_data=f"set_api_source_0_{p_id}_{page}", style="danger")],
            [InlineKeyboardButton(text="BACK", callback_data=f"admin_view_p_{p_id}_page_{page}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
        ])
        await safe_edit_text(call.message, 
            f"🔗 <b>KEY SOURCE</b>\n\n📦 <b>Product:</b> {name}\n⚙️ <b>Current:</b> {current}\n\nChoose exactly one source. Only the selected source will be used for this product.",
            reply_markup=kb, parse_mode='HTML'
        )
        return
    await state.update_data(edit_p_id=p_id, edit_field=field, manage_page=page)
    if field == 'keys':
        await safe_edit_text(call.message, "📥 <b>Vault Injection</b>\nPaste the <b>NEW KEYS</b> to append to the stock (1 key per line):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK", callback_data=f"admin_view_p_{p_id}_page_{page}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]]), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_add_keys)
    elif field == 'stock_add':
        await safe_edit_text(call.message, 
            "📦 <b>Add to Stock</b>\n\nEnter how many stock units to add.\nExample: <code>100</code> or <code>200</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK", callback_data=f"admin_view_p_{p_id}_page_{page}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]]), parse_mode='HTML'
        )
        await state.set_state(AdminStates.wait_for_new_value)
    else:
        if field == 'api_product_id':
            product_row = db_query("SELECT external_enabled, COALESCE(external_api_type,0), external_product_id FROM products WHERE id=?", (p_id,), fetchone=True)
            if not product_row or not product_row[0]:
                return await call.answer("❌ An external API source is not enabled for this product.", show_alert=True)
            api_type = int(product_row[1] or 0)
            if api_type == 1:
                prompt = "New API 1 Product ID (PID)"
            elif api_type == 2:
                prompt = "New API 2 Variant ID"
            else:
                return await call.answer("❌ Invalid API source.", show_alert=True)
            await safe_edit_text(call.message, f"✏️ <b>{prompt}</b>\n\nCurrent: <code>{product_row[2] or 'None'}</code>\n\nSend the new ID:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK", callback_data=f"admin_view_p_{p_id}_page_{page}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]]), parse_mode='HTML')
            await state.set_state(AdminStates.wait_for_new_value)
            return
        field_name_map = {'cat': 'New Panel Group/Category Name', 'panel_name': 'New Panel Name', 'name': 'New Package/Date Name', 'price': 'New Standard Price in ₹', 'rprice': 'New Reseller Price in ₹', 'validity': 'New Time Validity String', 'device': 'New HWID Limit String', 'apk': 'New Payload Link (or type "none")', 'api_duration': 'Exact API 1 Duration (e.g. 1 Day)', 'stock_add': 'Stock units to add'}
        await safe_edit_text(call.message, f"✏️ Input the required data for: <b>{field_name_map[field]}</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK", callback_data=f"admin_view_p_{p_id}_page_{page}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]]), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_new_value)

@dp.message(AdminStates.wait_for_new_value)
async def process_edit_value(m: Message, state: FSMContext):
    data = await state.get_data()
    p_id = data['edit_p_id']; field = data['edit_field']; page = int(data.get('manage_page', 0) or 0); new_val = m.text.strip()
    
    # API source identifiers are always stored as strings. They are used directly
    # by the purchase path: API 1 treats this as PID, API 2 treats it as Variant ID.
    if field == 'api_product_id':
        new_val = new_val.strip()
        if not new_val:
            return await m.answer("❌ API ID cannot be empty.", reply_markup=admin_back_kb(), parse_mode='HTML')
        source = db_query("SELECT external_enabled, COALESCE(external_api_type,0) FROM products WHERE id=?", (p_id,), fetchone=True)
        if not source or not source[0] or int(source[1] or 0) not in (1, 2):
            await state.clear()
            return await m.answer("❌ Product API source is not configured.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK TO PRODUCT", callback_data=f"admin_view_p_{p_id}_page_{page}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]]), parse_mode='HTML')
        db_query("UPDATE products SET external_product_id=? WHERE id=?", (new_val, p_id))
        label = "API 1 PID" if int(source[1]) == 1 else "API 2 Variant ID"
        await m.answer(f"✅ <b>{label} updated.</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK TO PRODUCT", callback_data=f"admin_view_p_{p_id}_page_{page}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]]), parse_mode='HTML')
        await state.clear()
        return

    # If field is price or reseller price, convert to float
    if field in ['price', 'rprice']:
        try:
            new_val = float(new_val)
        except ValueError:
            return await m.answer("❌ Invalid number format. Please enter a valid price (e.g., 500).")
    # If field is apk, store as string (don't convert to float!)
    elif field == 'apk':
        new_val = "" if new_val.lower() == 'none' else new_val
    elif field == 'stock_add':
        try:
            add_qty = int(new_val)
            if add_qty <= 0 or add_qty > 100000:
                raise ValueError
        except ValueError:
            return await m.answer("❌ Enter a positive whole number up to 100000, e.g. 100 or 200.")
        db_query("UPDATE products SET stock=COALESCE(stock,0)+? WHERE id=?", (add_qty, p_id))
        new_stock = db_query("SELECT stock FROM products WHERE id=?", (p_id,), fetchone=True)[0]
        await m.answer(f"✅ <b>Stock Added!</b>\n\n➕ Added: <code>{add_qty}</code>\n📦 New Stock: <code>{new_stock}</code>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK TO PRODUCT", callback_data=f"admin_view_p_{p_id}_page_{page}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]]), parse_mode='HTML')
        await state.clear()
        return
    # For all other fields (cat, panel_name, name, validity, device), keep as string
    
    db_col_map = {'cat': 'category', 'panel_name': 'panel_name', 'name': 'name', 'price': 'price_inr', 'rprice': 'reseller_price', 'validity': 'validity', 'device': 'device_limit', 'apk': 'apk_link', 'api_duration': 'external_duration'}
    db_query(f"UPDATE products SET {db_col_map[field]}=? WHERE id=?", (new_val, p_id))
    await m.answer("✅ <b>Node updated gracefully!</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK TO PRODUCT", callback_data=f"admin_view_p_{p_id}_page_{page}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]]), parse_mode='HTML')
    await state.clear()

@dp.message(AdminStates.wait_for_add_keys)
async def process_add_keys(m: Message, state: FSMContext):
    data = await state.get_data()
    p_id = data['edit_p_id']; page = int(data.get('manage_page', 0) or 0)
    keys = [k.strip() for k in m.text.strip().split('\n') if k.strip()]
    if len(keys) == 0: return await m.answer("❌ Protocol breach: Zero valid keys found.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK TO PRODUCT", callback_data=f"admin_view_p_{p_id}_page_{page}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]]), parse_mode='HTML')
    conn = sqlite3.connect('yp_shop.db')
    c = conn.cursor()
    for k in keys: c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (p_id, k))
    c.execute("UPDATE products SET stock = stock + ? WHERE id=?", (len(keys), p_id))
    conn.commit(); conn.close()
    await m.answer(f"✅ <b>Vault Secure!</b> {len(keys)} new keys appended and encrypted.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK TO PRODUCT", callback_data=f"admin_view_p_{p_id}_page_{page}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]]), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data.startswith("delete_p_"))
async def admin_delete_product(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    p_id = int(call.data.split("_")[2])
    db_query("DELETE FROM products WHERE id=?", (p_id,))
    db_query("DELETE FROM product_keys WHERE product_id=?", (p_id,))
    await call.answer("☢️ Nuclear wipe successful! Node and vault deleted.", show_alert=True)
    await admin_manage_prods(call)

@dp.callback_query(F.data.startswith("delkey_p_"))
async def admin_delete_key_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    p_id = int(call.data.split("_")[2])
    await state.update_data(del_p_id=p_id)
    await safe_edit_text(call.message, "🗑 Send the <b>exact string match</b> of the key you wish to purge from the vault:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_delete_key)

@dp.message(AdminStates.wait_for_delete_key)
async def process_delete_key(m: Message, state: FSMContext):
    data = await state.get_data()
    p_id = data['del_p_id']
    key_to_delete = m.text.strip()
    key_data = db_query("SELECT id, is_used FROM product_keys WHERE product_id=? AND key_text=?", (p_id, key_to_delete), fetchone=True)
    if not key_data: return await m.answer("❌ Key not found. Check logs and try again.", reply_markup=admin_back_kb(), parse_mode='HTML')
    if key_data[1] == 1: return await m.answer("⚠️ Action Blocked: This key has already been dispatched to a user.", reply_markup=admin_back_kb(), parse_mode='HTML')
    db_query("DELETE FROM product_keys WHERE id=?", (key_data[0],))
    db_query("UPDATE products SET stock = stock - 1 WHERE id=?", (p_id,))
    await m.answer(f"✅ Key <code>{key_to_delete}</code> securely purged from vault.\n📦 Database indices updated.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

# ==============================================================================
# 20. ADMIN TICKETS, BROADCAST, COUPONS
# ==============================================================================
@dp.callback_query(F.data == "admin_view_tickets")
async def admin_view_tickets(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    tickets = db_query("SELECT id, user_id, message, created_at FROM tickets WHERE status='Open' LIMIT 1", fetchall=True)
    if not tickets: return await call.answer("✅ Zero pending issues. Grid is clean!", show_alert=True)
    t = tickets[0]
    text = (f"🎫 <b><u>ACTIVE TICKET #{t[0]}</u></b>\n👤 <b>Origin UID:</b> <code>{t[1]}</code>\n📅 <b>Timestamp:</b> {t[3]}\n\n📝 <b>Payload:</b>\n{t[2]}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Formulate Reply", callback_data=f"reply_ticket_{t[0]}_{t[1]}", icon_custom_emoji_id=get_emoji_icon("telegram"), style="primary")],
        [InlineKeyboardButton(text="❌ Force Close Ticket", callback_data=f"close_ticket_{t[0]}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("close_ticket_"))
async def close_ticket(call: CallbackQuery):
    ticket_id = call.data.split("_")[2]
    db_query("UPDATE tickets SET status='Closed' WHERE id=?", (ticket_id,))
    await call.answer("✅ Status set to Closed.", show_alert=True)
    await admin_view_tickets(call) 

@dp.callback_query(F.data.startswith("reply_ticket_"))
async def reply_ticket_start(call: CallbackQuery, state: FSMContext):
    try:
        await call.answer()
    except Exception:
        pass
    data = call.data.split("_")
    ticket_id, user_id = data[2], data[3]
    await state.update_data(ticket_id=ticket_id, user_id=user_id)
    await safe_edit_text(call.message, f"💬 Formulating reply for node <code>{user_id}</code>.\n\nType your message payload:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.ticket_reply_msg)

@dp.message(AdminStates.ticket_reply_msg)
async def send_ticket_reply(m: Message, state: FSMContext):
    data = await state.get_data()
    try:
        await bot.send_message(data['user_id'], f"📞 <b>Admin Reply (Ref #{data['ticket_id']}):</b>\n\n{m.text}", parse_mode='HTML')
        db_query("UPDATE tickets SET status='Closed' WHERE id=?", (data['ticket_id'],))
        await m.answer("✅ Payload delivered and connection closed successfully.", reply_markup=admin_kb(), parse_mode='HTML')
    except Exception as e: await m.answer(f"❌ Transmission Error: {e}", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_broadcast_btn")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.clear()

    # Always open the Broadcast Manager first. The NEW BROADCAST button is
    # separate from the OLD BROADCASTS list so the admin cannot miss it.
    try:
        rows = db_query(
            "SELECT id, created_at, message_type, title FROM broadcasts ORDER BY id DESC LIMIT 50",
            fetchall=True
        ) or []
    except Exception as e:
        logger.exception("Broadcast manager database error: %s", e)
        await call.answer("❌ Broadcast database error. Restart the bot once after updating the file.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🆕 NEW BROADCAST",
            callback_data="broadcast_new",
            icon_custom_emoji_id=get_emoji_icon("telegram"),
            style="success"
        )],
        [InlineKeyboardButton(
            text="📚 OLD BROADCASTS",
            callback_data="broadcast_old_header",
            style="primary"
        )]
    ])

    if rows:
        for bid, created_at, msg_type, title in rows:
            preview = (title or "[NO TEXT]").replace("\n", " ").strip()
            if len(preview) > 24:
                preview = preview[:24] + "…"
            label = f"📢 #{bid} • {preview}"
            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"broadcast_manage_{bid}",
                    icon_custom_emoji_id=get_emoji_icon("telegram"),
                    style="primary"
                )
            ])
    else:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="No old broadcasts yet",
                callback_data="broadcast_old_header",
                style="primary"
            )
        ])

    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="🔙 BACK TO ADMIN",
            callback_data="admin_panel_back",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])

    manager_text = (
        "📢 <b>BROADCAST MANAGER</b>\n\n"
        "🆕 <b>NEW BROADCAST</b> — send a new message to all users.\n"
        "📚 <b>OLD BROADCASTS</b> — select a previous broadcast to Edit or Delete it.\n\n"
        f"<b>{len(rows)}</b> previous broadcast(s) shown below."
    )
    try:
        await safe_edit_text(call.message, manager_text, reply_markup=kb, parse_mode='HTML')
    except Exception as e:
        # Do not tell the admin to restart the bot for a Telegram UI/edit error.
        # Show the same manager as a fresh message instead.
        logger.exception("Broadcast menu edit error: %s", e)
        try:
            await call.message.answer(manager_text, reply_markup=kb, parse_mode='HTML')
        except Exception as e2:
            logger.exception("Broadcast manager send error: %s", e2)
            return await call.answer("❌ Broadcast menu could not be opened.", show_alert=True)
    await call.answer()

@dp.callback_query(F.data == "broadcast_old_header")
async def broadcast_old_header(call: CallbackQuery):
    await call.answer("Select an old broadcast below.")

@dp.callback_query(F.data == "broadcast_noop")
async def broadcast_noop(call: CallbackQuery):
    await call.answer("No broadcast history yet.")

@dp.callback_query(F.data == "broadcast_new")
async def admin_broadcast_new(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await safe_edit_text(call.message, 
        "📢 <b>NEW BROADCAST</b>\n\n"
        "Send the message/text you want to broadcast to all users.\n\n"
        "<i>Every new broadcast is saved so you can edit or delete it later.</i>",
        reply_markup=admin_back_kb(), parse_mode='HTML'
    )
    await state.set_state(AdminStates.broadcast_msg)
    await call.answer()

@dp.callback_query(F.data.startswith("broadcast_manage_"))
async def broadcast_manage(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        bid = int(call.data.split("broadcast_manage_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid broadcast.", show_alert=True)

    row = db_query(
        "SELECT id, created_at, message_type, title FROM broadcasts WHERE id=?",
        (bid,), fetchone=True
    )
    if not row:
        return await call.answer("❌ Broadcast not found.", show_alert=True)

    total = db_query("SELECT COUNT(*) FROM broadcast_messages WHERE broadcast_id=?", (bid,), fetchone=True)
    sent = db_query("SELECT COUNT(*) FROM broadcast_messages WHERE broadcast_id=? AND status='sent'", (bid,), fetchone=True)
    failed = (total[0] if total else 0) - (sent[0] if sent else 0)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit Broadcast", callback_data=f"broadcast_edit_{bid}", style="primary")],
        [InlineKeyboardButton(text="🗑 Delete Broadcast", callback_data=f"broadcast_delete_{bid}", style="danger")],
        [InlineKeyboardButton(text="BACK TO BROADCASTS", callback_data="admin_broadcast_btn", icon_custom_emoji_id=get_emoji_icon("back"), style="primary")],
    ])

    await safe_edit_text(call.message, 
        f"📢 <b>BROADCAST #{bid}</b>\n\n"
        f"📅 <b>Created:</b> {row[1]}\n"
        f"📝 <b>Type:</b> {row[2]}\n"
        f"🟢 <b>Sent:</b> {sent[0] if sent else 0}\n"
        f"🔴 <b>Failed:</b> {failed}\n\n"
        "Choose <b>Edit</b> to change the text for all successfully delivered copies, or <b>Delete</b> to remove them from all users.",
        reply_markup=kb, parse_mode='HTML'
    )
    await call.answer()

@dp.callback_query(F.data.startswith("broadcast_edit_"))
async def broadcast_edit_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        bid = int(call.data.split("broadcast_edit_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid broadcast.", show_alert=True)

    row = db_query("SELECT id, message_type FROM broadcasts WHERE id=?", (bid,), fetchone=True)
    if not row:
        return await call.answer("❌ Broadcast not found.", show_alert=True)

    # Text broadcasts can be edited directly. Captioned media can also be
    # edited through edit_message_caption; other Telegram message types are
    # not editable through the same API.
    await state.update_data(broadcast_edit_id=bid)
    await safe_edit_text(call.message, 
        f"✏️ <b>EDIT BROADCAST #{bid}</b>\n\n"
        "Send the NEW TEXT/CAPTION. It will replace the existing text for every user whose copy was delivered successfully.",
        reply_markup=admin_back_kb(), parse_mode='HTML'
    )
    await state.set_state(AdminStates.broadcast_edit_text)
    await call.answer()

@dp.message(AdminStates.broadcast_edit_text)
async def broadcast_edit_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    new_text = (message.text or message.caption or "").strip()
    if not new_text:
        return await message.answer("❌ Please send text (or a caption) to replace the broadcast.", parse_mode='HTML')

    data = await state.get_data()
    bid = data.get("broadcast_edit_id")
    if not bid:
        await state.clear()
        return await message.answer("❌ Broadcast edit session expired.", reply_markup=admin_kb())

    targets = db_query(
        "SELECT id, user_id, message_id FROM broadcast_messages WHERE broadcast_id=? AND status='sent'",
        (bid,), fetchall=True
    ) or []

    updated = 0
    failed = 0
    for map_id, user_id, message_id in targets:
        try:
            # Try normal text edit first. If the original was media with a
            # caption, fall back to caption editing.
            try:
                await bot.edit_message_text(
                    chat_id=user_id, message_id=message_id, text=new_text, parse_mode='HTML'
                )
            except Exception:
                await bot.edit_message_caption(
                    chat_id=user_id, message_id=message_id, caption=new_text, parse_mode='HTML'
                )
            updated += 1
        except Exception as e:
            failed += 1
            db_query("UPDATE broadcast_messages SET status='failed' WHERE id=?", (map_id,))
            logger.warning(f"Broadcast #{bid} edit failed for {user_id}/{message_id}: {e}")
        await asyncio.sleep(0.06)

    db_query("UPDATE broadcasts SET title=? WHERE id=?", (new_text[:80], bid))
    await state.clear()
    await message.answer(
        f"✅ <b>Broadcast #{bid} updated.</b>\n\n🟢 Updated: {updated}\n🔴 Failed: {failed}",
        reply_markup=admin_kb(), parse_mode='HTML'
    )

@dp.callback_query(F.data.startswith("broadcast_delete_"))
async def broadcast_delete(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        bid = int(call.data.split("broadcast_delete_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid broadcast.", show_alert=True)

    # Read the broadcast and its original admin message before deleting the
    # database records. The history entry itself must disappear permanently.
    row = db_query(
        "SELECT id, source_chat_id, source_message_id FROM broadcasts WHERE id=?",
        (bid,), fetchone=True
    )
    if not row:
        return await call.answer("❌ Broadcast not found.", show_alert=True)

    # Acknowledge the callback BEFORE the potentially long delete loop.
    # Otherwise Telegram may expire the callback query while old broadcast
    # messages are being deleted one by one. This does not change the delete flow.
    try:
        await call.answer()
    except TelegramBadRequest:
        pass

    source_chat_id = row[1]
    source_message_id = row[2]
    targets = db_query(
        "SELECT id, user_id, message_id FROM broadcast_messages WHERE broadcast_id=? AND status='sent'",
        (bid,), fetchall=True
    ) or []

    deleted = 0
    failed = 0
    for map_id, user_id, message_id in targets:
        try:
            await bot.delete_message(chat_id=user_id, message_id=message_id)
            deleted += 1
            db_query("UPDATE broadcast_messages SET status='deleted' WHERE id=?", (map_id,))
        except TelegramBadRequest as e:
            # The user may have already deleted/blocked the message.
            # Treat Telegram's "message to delete not found" as already deleted
            # so the broadcast cleanup continues without noisy error warnings.
            if "message to delete not found" in str(e).lower() or "message can't be deleted" in str(e).lower():
                db_query("UPDATE broadcast_messages SET status='deleted' WHERE id=?", (map_id,))
                continue
            failed += 1
            logger.warning(f"Broadcast #{bid} delete failed for {user_id}/{message_id}: {e}")
        except Exception as e:
            failed += 1
            logger.warning(f"Broadcast #{bid} delete failed for {user_id}/{message_id}: {e}")
        await asyncio.sleep(0.06)

    # Permanently remove the broadcast from the bot's history as well.
    # Delete the mapping rows first, then the broadcast row itself.
    db_query("DELETE FROM broadcast_messages WHERE broadcast_id=?", (bid,))
    db_query("DELETE FROM broadcasts WHERE id=?", (bid,))

    # Also try to remove the original admin-side source message that created
    # this broadcast, when it is still available. Failure here must not undo
    # the permanent database deletion.
    source_deleted = False
    if source_chat_id and source_message_id:
        try:
            await bot.delete_message(chat_id=source_chat_id, message_id=source_message_id)
            source_deleted = True
        except Exception as e:
            logger.info(f"Broadcast #{bid} source message could not be deleted: {e}")

    await safe_edit_text(call.message, 
        f"🗑 <b>Broadcast #{bid} permanently deleted.</b>\n\n"
        f"🟢 User copies deleted: {deleted}\n"
        f"🔴 Failed/already unavailable: {failed}\n"
        f"📚 Removed from Old Broadcasts: <b>YES</b>",
        reply_markup=admin_kb(), parse_mode='HTML'
    )
    # The callback was already acknowledged before the long-running delete loop.

@dp.message(AdminStates.broadcast_msg)
async def admin_broadcast_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return

    users = db_query("SELECT user_id FROM users", fetchall=True) or []
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    source_type = getattr(message, "content_type", "text") or "text"
    title = (message.text or message.caption or "").strip()[:80]

    # Create the history record BEFORE sending so every successful copy can be
    # linked to this broadcast ID.
    db_query(
        "INSERT INTO broadcasts (admin_id, source_chat_id, source_message_id, created_at, message_type, title) VALUES (?, ?, ?, ?, ?, ?)",
        (message.from_user.id, message.chat.id, message.message_id, created_at, str(source_type), title)
    )
    # db_query() opens a fresh SQLite connection each time, so last_insert_rowid()
    # cannot be read from a second connection. Read the newest row by id instead.
    bid_row = db_query("SELECT id FROM broadcasts ORDER BY id DESC LIMIT 1", fetchone=True)
    broadcast_id = bid_row[0] if bid_row else None

    status_msg = await message.answer("⏳ Broadcast started... Every delivered message is being recorded for future Edit/Delete.", parse_mode='HTML')
    sent, failed = 0, 0

    for u in users:
        try:
            copied = await message.send_copy(chat_id=u[0])
            sent += 1
            if broadcast_id and copied:
                db_query(
                    "INSERT INTO broadcast_messages (broadcast_id, user_id, message_id, status) VALUES (?, ?, ?, 'sent')",
                    (broadcast_id, u[0], copied.message_id)
                )
        except Exception as e:
            failed += 1
            if broadcast_id:
                db_query(
                    "INSERT INTO broadcast_messages (broadcast_id, user_id, message_id, status) VALUES (?, ?, ?, 'failed')",
                    (broadcast_id, u[0], 0)
                )
            logger.warning(f"Broadcast #{broadcast_id} failed for user {u[0]}: {e}")
        await asyncio.sleep(0.06)

    await safe_edit_text(status_msg,
        f"✅ <b>Broadcast #{broadcast_id} Complete!</b>\n\n"
        f"🟢 Delivered: {sent}\n🔴 Failed/blocked: {failed}\n\n"
        "This broadcast is now available in <b>/admin → Broadcast</b> for Edit/Delete.",
        reply_markup=admin_kb(), parse_mode='HTML'
    )
    await state.clear()

@dp.callback_query(F.data == "admin_create_coupon")
async def admin_create_coupon_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "🎟 Enter a highly secure alphanumeric sequence for the Promo Code:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_coupon_code)

@dp.message(AdminStates.add_coupon_code)
async def admin_coupon_code(m: Message, state: FSMContext):
    await state.update_data(code=m.text.strip().upper())
    await m.answer("💰 Enter the monetary reward payload in <b>RUPEES (₹)</b>:", parse_mode='HTML')
    await state.set_state(AdminStates.add_coupon_amount)

@dp.message(AdminStates.add_coupon_amount)
async def admin_coupon_amount(m: Message, state: FSMContext):
    try:
        await state.update_data(amount=float(m.text)) 
        await m.answer("👥 Enter the exact maximum threshold uses for this code:", parse_mode='HTML')
        await state.set_state(AdminStates.add_coupon_uses)
    except ValueError: await m.answer("❌ Non-numerical data detected. Aborting.")

@dp.message(AdminStates.add_coupon_uses)
async def admin_coupon_uses(m: Message, state: FSMContext):
    try:
        uses = int(m.text)
        data = await state.get_data()
        db_query("INSERT OR REPLACE INTO coupons (code, amount, uses_left) VALUES (?, ?, ?)", (data['code'], data['amount'], uses))
        await m.answer(f"✅ Protocol <b>{data['code']}</b> encoded!\nReward Vector: {fmt_curr(data['amount'])}\nThreshold Limit: {uses} executions.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Non-numerical data detected. Aborting.")

# ==============================================================================
# 21. ADMIN RESELLER & SPIN SETTINGS
# ==============================================================================

@dp.callback_query(F.data == "admin_edit_vip_price")
async def admin_edit_vip_price(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    await safe_edit_text(call.message, 
        f"💰 <b>Edit VIP Price</b>\n\n"
        f"Current VIP price: <b>{fmt_curr(VIP_PRICE_INR)}</b>\n\n"
        "Send the new VIP price in INR.\n"
        "Example: <code>299</code>",
        reply_markup=admin_back_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.edit_vip_price)

@dp.message(AdminStates.edit_vip_price)
async def admin_save_vip_price(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    try:
        value = float(m.text.strip())
        if value <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await m.answer(
            "❌ Invalid price. Send a positive number, for example <code>299</code>.",
            parse_mode="HTML"
        )
        return

    # Store only the VIP membership price. Payment handlers already read
    # VIP_PRICE_INR, so no payment-flow code is changed here.
    set_setting("vip_price_inr", f"{value:.2f}")
    globals()["VIP_PRICE_INR"] = value
    await state.clear()
    await m.answer(
        f"✅ VIP price updated to <b>{fmt_curr(value)}</b>.",
        reply_markup=admin_kb(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_reseller_menu")
async def admin_reseller_menu(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try: await call.answer()
    except Exception: pass
    status = get_setting("reseller_system_status", "ON")
    fee = float(get_setting("reseller_setup_fee", "200.0"))
    minimum = float(get_setting("reseller_min_balance", "1.0"))
    duration = get_setting("reseller_default_days", "lifetime")
    duration_text = "Lifetime" if duration == "lifetime" else f"{duration} Days"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Edit Days", callback_data="resctrl_days", icon_custom_emoji_id=get_emoji_icon("validity"), style="primary"),
         InlineKeyboardButton(text=f"💰 Reseller Price ({fmt_curr(fee)})", callback_data="resctrl_price", icon_custom_emoji_id=get_emoji_icon("money_icon"), style="success")],
        [InlineKeyboardButton(text=f"💳 Minimum Balance ({fmt_curr(minimum)})", callback_data="resctrl_min", icon_custom_emoji_id=get_emoji_icon("wallet"), style="success")],
        [InlineKeyboardButton(text="🎁 Benefits", callback_data="resctrl_benefits", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="success"),
         InlineKeyboardButton(text="📋 Reseller List", callback_data="resctrl_list", icon_custom_emoji_id=get_emoji_icon("history"), style="primary")],
        [InlineKeyboardButton(text=f"{'🟢' if status == 'ON' else '🔴'} Reseller System: {status}", callback_data="admin_toggle_reseller_sys", icon_custom_emoji_id=get_emoji_icon("check_icon"), style="success" if status == 'ON' else "danger")],
        [InlineKeyboardButton(text="BACK TO PANEL", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    try:
        await safe_edit_text(call.message, 
            f"👑 <b>RESELLER CONTROL</b>\n\n⏳ <b>Default Access:</b> {duration_text}\n💰 <b>Price:</b> {fmt_curr(fee)}\n💳 <b>Minimum Balance:</b> {fmt_curr(minimum)}",
            reply_markup=kb,
            parse_mode='HTML'
        )
    except TelegramBadRequest as e:
        # Telegram returns this when the requested screen is already identical.
        # Do not let this harmless UI refresh error crash the update handler.
        if "message is not modified" not in str(e).lower():
            raise

@dp.callback_query(F.data == "resctrl_days")
async def reseller_control_days(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 Day", callback_data="resdays_1"), InlineKeyboardButton(text="2 Days", callback_data="resdays_2"), InlineKeyboardButton(text="3 Days", callback_data="resdays_3")],
        [InlineKeyboardButton(text="5 Days", callback_data="resdays_5"), InlineKeyboardButton(text="6 Days", callback_data="resdays_6"), InlineKeyboardButton(text="7 Days", callback_data="resdays_7")],
        [InlineKeyboardButton(text="8 Days", callback_data="resdays_8"), InlineKeyboardButton(text="30 Days", callback_data="resdays_30"), InlineKeyboardButton(text="90 Days", callback_data="resdays_90")],
        [InlineKeyboardButton(text="✏️ Custom Days", callback_data="resdays_custom")],
        [InlineKeyboardButton(text="♾️ Lifetime", callback_data="resdays_lifetime")],
        [InlineKeyboardButton(text="BACK TO PANEL", callback_data="admin_reseller_menu", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.answer()
    await safe_edit_text(call.message, "⏳ <b>EDIT RESELLER ACCESS DAYS</b>\n\nChoose the default access duration customers receive when they buy the Reseller plan.", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("resdays_") & ~F.data.in_(["resdays_custom", "resdays_lifetime"]))
async def reseller_control_set_days(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    days = call.data.split("_")[1]
    set_setting("reseller_default_days", days)
    await call.answer(f"✅ Default reseller access set to {days} days.", show_alert=True)
    await admin_reseller_menu(call)

@dp.callback_query(F.data == "resdays_lifetime")
async def reseller_control_set_lifetime(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    set_setting("reseller_default_days", "lifetime")
    await call.answer("✅ Default reseller access set to Lifetime.", show_alert=True)
    await admin_reseller_menu(call)

@dp.callback_query(F.data == "resdays_custom")
async def reseller_control_custom_days(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.answer()
    await safe_edit_text(call.message, "✏️ <b>Custom Reseller Days</b>\n\nSend the number of days, for example <code>15</code>.", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.edit_reseller_custom_days)

@dp.message(AdminStates.edit_reseller_custom_days)
async def reseller_control_save_custom_days(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    try:
        days = int(m.text.strip())
        if days <= 0: raise ValueError
    except (ValueError, AttributeError):
        return await m.answer("❌ Invalid days. Send a positive whole number, for example <code>15</code>.", parse_mode='HTML')
    set_setting("reseller_default_days", str(days))
    await state.clear()
    await m.answer(f"✅ Default reseller access set to <b>{days} days</b>.", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "resctrl_price")
async def reseller_control_price(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.answer()
    await safe_edit_text(call.message, f"💰 <b>Edit Reseller Price</b>\n\nCurrent price: <b>{fmt_curr(float(get_setting('reseller_setup_fee', '200.0')))}</b>\n\nSend the new INR price.", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_reseller_setup_fee)

@dp.callback_query(F.data == "resctrl_min")
async def reseller_control_min(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.answer()
    await safe_edit_text(call.message, f"💳 <b>Edit Minimum Balance</b>\n\nCurrent minimum: <b>{fmt_curr(float(get_setting('reseller_min_balance', '1.0')))}</b>\n\nSend the new INR minimum balance.", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_reseller_min_balance)

@dp.message(AdminStates.wait_for_reseller_setup_fee)
async def reseller_control_save_price(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    try:
        value = float(m.text.strip())
        if value <= 0: raise ValueError
    except (ValueError, AttributeError):
        return await m.answer("❌ Invalid price. Send a positive number.")
    set_setting("reseller_setup_fee", f"{value:.2f}")
    await state.clear()
    await m.answer(f"✅ Reseller price updated to <b>{fmt_curr(value)}</b>.", reply_markup=admin_kb(), parse_mode='HTML')

@dp.message(AdminStates.wait_for_reseller_min_balance)
async def reseller_control_save_min(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    try:
        value = float(m.text.strip())
        if value < 0: raise ValueError
    except (ValueError, AttributeError):
        return await m.answer("❌ Invalid minimum balance. Send a valid INR amount.")
    set_setting("reseller_min_balance", f"{value:.2f}")
    await state.clear()
    await m.answer(f"✅ Minimum balance updated to <b>{fmt_curr(value)}</b>.", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "resctrl_benefits")
async def reseller_control_benefits(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.answer()
    current = get_setting("reseller_benefits", "50%+ Discount / Low Reseller Prices\nExclusive Reseller Access\nPriority Support")
    await safe_edit_text(call.message, f"🎁 <b>EDIT RESELLER BENEFITS</b>\n\nCurrent text:\n<code>{current}</code>\n\nSend the benefits text exactly as you want customers to see it.", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.edit_reseller_benefits)

@dp.message(AdminStates.edit_reseller_benefits)
async def reseller_control_save_benefits(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    value = (m.text or '').strip()
    if not value: return await m.answer("❌ Benefits text cannot be empty.")
    set_setting("reseller_benefits", value)
    await state.clear()
    await m.answer("✅ Reseller benefits updated.", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "resctrl_list")
async def reseller_control_list(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    resellers = db_query("SELECT user_id, first_name, username, reseller_expires_at FROM users WHERE is_reseller=1 ORDER BY user_id DESC", fetchall=True)
    if not resellers:
        text = "📋 <b>RESELLER LIST</b>\n\nNo active resellers found."
    else:
        lines = ["📋 <b>RESELLER LIST</b>"]
        for uid, name, username, expiry in resellers:
            if expiry:
                try: expiry_text = datetime.fromisoformat(str(expiry)).strftime("%d-%m-%Y")
                except Exception: expiry_text = str(expiry)
            else: expiry_text = "Lifetime"
            uname = f"@{username}" if username else "No Username"
            lines.append(f"\n👤 {name or 'Unknown'} ({uname})\n🆔 <code>{uid}</code>\n⏳ {expiry_text}")
        text = "\n".join(lines)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK TO PANEL", callback_data="admin_reseller_menu", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.answer()
    await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "admin_toggle_reseller_sys")
async def toggle_reseller_sys(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    res = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    current = res[0] if res else 'ON'
    new_status = 'OFF' if current == 'ON' else 'ON'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('reseller_system_status', ?)", (new_status,))
    await admin_reseller_menu(call)

@dp.callback_query(F.data.in_(["reseller_make", "reseller_remove"]))
async def reseller_prompt_id(call: CallbackQuery, state: FSMContext):
    try:
        await call.answer()
    except Exception:
        pass
    action = call.data
    await state.update_data(reseller_action=action)
    await safe_edit_text(call.message, "👤 Identify target node. Input <b>User ID</b> or <b>@username</b>:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.reseller_manage_id)

@dp.message(AdminStates.reseller_manage_id)
async def process_reseller_manage(m: Message, state: FSMContext):
    data = await state.get_data()
    target = m.text.strip()
    if target.startswith('@'): target = target[1:]
    user_q = db_query("SELECT user_id, first_name FROM users WHERE user_id=? OR username=? COLLATE NOCASE", (target, target), fetchone=True)
    if not user_q: return await m.answer("❌ Target completely ghosted. Not in database.", reply_markup=admin_back_kb(), parse_mode='HTML')
    u_id, u_name = user_q[0], user_q[1]
    if data['reseller_action'] == "reseller_make":
        db_query("UPDATE users SET is_reseller=1, reseller_since=?, account_type='Reseller' WHERE user_id=?", (datetime.now().strftime("%Y-%m-%d"), u_id))
        await m.answer(f"✅ Credentials upgraded. <b>{u_name}</b> (<code>{u_id}</code>) has reseller rights.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        db_query("UPDATE users SET is_reseller=0, account_type='Regular' WHERE user_id=?", (u_id,))
        await m.answer(f"✅ Credentials revoked. <b>{u_name}</b> (<code>{u_id}</code>) is back to regular user.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "reseller_view")
async def reseller_view(call: CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass
    resellers = db_query("SELECT user_id, first_name, username FROM users WHERE is_reseller=1", fetchall=True)
    if not resellers: return await safe_edit_text(call.message, "📋 Zero active resellers found.", reply_markup=admin_back_kb(), parse_mode='HTML')
    text = "👑 <b><u>ACTIVE RESELLER AUDIT LOG</u></b> 👑\n━━━━━━━━━━━━━━━━━━\n"
    for r in resellers:
        uname = f"(@{r[2]})" if r[2] else ""
        text += f"👤 {r[1]} {uname}\n🆔 <code>{r[0]}</code>\n\n"
    await safe_edit_text(call.message, text, reply_markup=admin_back_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_spin_menu")
async def admin_spin_menu(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    status = db_query("SELECT value FROM settings WHERE key='spin_status'", fetchone=True)
    limit = db_query("SELECT value FROM settings WHERE key='daily_spin_limit'", fetchone=True)
    reward_row = db_query("SELECT amount FROM spin_rewards ORDER BY id DESC LIMIT 1", fetchone=True)
    status_val = status[0] if status else 'ON'
    limit_val = limit[0] if limit else '50.0'
    reward_val = float(reward_row[0]) if reward_row else 0.0
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Set Fixed Reward", callback_data="spin_add", icon_custom_emoji_id=get_emoji_icon("add_balance"), style="success"),
         InlineKeyboardButton(text="❌ Drop Reward Logic", callback_data="spin_del", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
        [InlineKeyboardButton(text="📅 Daily Configuration", callback_data="spin_daily_report_0", icon_custom_emoji_id=get_emoji_icon("history"), style="primary"),
         InlineKeyboardButton(text="🗓 Monthly Configuration", callback_data="spin_monthly_report_0", icon_custom_emoji_id=get_emoji_icon("history"), style="primary")],
        [InlineKeyboardButton(text="⚙️ Daily Limit", callback_data="spin_limit", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")],
        [InlineKeyboardButton(text="🔄 Revoke Daily Rewards", callback_data="spin_revoke_daily", icon_custom_emoji_id=get_emoji_icon("check_icon"), style="success")],
        [InlineKeyboardButton(text=f"{'🟢' if status_val == 'ON' else '🔴'} Master Toggle: {status_val}", callback_data="spin_toggle", icon_custom_emoji_id=get_emoji_icon("check_icon"), style="success" if status_val == 'ON' else "danger")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await safe_edit_text(call.message, f"🎰 <b>Advanced Ludo/Spin Settings</b>\nFixed Reward: {fmt_curr(reward_val)}\nDaily Limit: {limit_val}", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "spin_toggle")
async def spin_toggle(call: CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass
    res = db_query("SELECT value FROM settings WHERE key='spin_status'", fetchone=True)
    current = res[0] if res else 'ON'
    new_status = 'OFF' if current == 'ON' else 'ON'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('spin_status', ?)", (new_status,))
    await admin_spin_menu(call)

@dp.callback_query(F.data == "admin_toggle_bot")
async def toggle_bot(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    res = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
    current = res[0] if res else 'ON'
    new_status = 'OFF' if current == 'ON' else 'ON'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('bot_status', ?)", (new_status,))
    await safe_edit_reply_markup(call.message, reply_markup=admin_kb())

@dp.callback_query(F.data == "spin_add")
async def spin_add_start(call: CallbackQuery, state: FSMContext):
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "🎰 Inject new decimal logic limit (e.g. 15.50):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.spin_add_reward)

@dp.message(AdminStates.spin_add_reward)
async def spin_add_exec(m: Message, state: FSMContext):
    try:
        amt = float(m.text.strip())
        if amt < 0:
            raise ValueError
        # Keep exactly one configured reward. Every user receives this same
        # amount on a successful spin.
        db_query("DELETE FROM spin_rewards")
        db_query("INSERT INTO spin_rewards (amount) VALUES (?)", (amt,))
        await m.answer(f"✅ Fixed reward saved: {fmt_curr(amt)}\nAll users will receive exactly this amount per spin.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError:
        await m.answer("❌ Enter a valid non-negative amount, e.g. 0.02")

@dp.callback_query(F.data == "spin_revoke_daily")
async def spin_revoke_daily(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer("Daily rewards revoked for all users.", show_alert=True)
    except Exception:
        pass
    # Clear the 24-hour cooldown for everyone. This is a one-time admin action;
    # the normal one-spin-per-24-hours rule remains unchanged afterwards.
    db_query("UPDATE users SET last_spin=NULL")
    await admin_spin_menu(call)

@dp.callback_query(F.data == "spin_limit")
async def spin_limit_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    current = db_query("SELECT value FROM settings WHERE key='daily_spin_limit'", fetchone=True)
    current_val = current[0] if current else '50.0'
    await safe_edit_text(call.message, f"⚙️ <b>Daily Spin Limit</b>\n\nCurrent limit: <b>{current_val}</b>\n\nEnter the maximum reward amount allowed by the daily spin setting:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.spin_set_limit)

@dp.message(AdminStates.spin_set_limit)
async def spin_limit_exec(m: Message, state: FSMContext):
    try:
        limit = float(m.text.strip())
        if limit < 0:
            raise ValueError
        db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('daily_spin_limit', ?)", (str(limit),))
        await m.answer(f"✅ Daily limit saved: {fmt_curr(limit)}", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError:
        await m.answer("❌ Enter a valid non-negative number.")

# ------------------------------------------------------------------------------
# Spin reports: Daily = current calendar day only; Monthly = current calendar
# month only. These reports use the existing PLAYED_SPIN activity log, so they
# do not change spin rewards, user balances, products, payments, APIs, or the
# existing total-spin statistics.
# ------------------------------------------------------------------------------
SPIN_REPORT_PAGE_SIZE = 8

def _spin_report_name(first_name: str, username: str, user_id: int) -> str:
    first_name = str(first_name or "").strip()
    username = str(username or "").strip()
    if username:
        return f"@{username.lstrip('@')}"
    if first_name:
        return first_name
    return f"User {user_id}"

def _spin_report_keyboard(kind: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"spin_{kind}_report_{page-1}", icon_custom_emoji_id=get_emoji_icon("back"), style="primary"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"spin_{kind}_report_{page+1}", icon_custom_emoji_id=get_emoji_icon("point_down"), style="primary"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔙 Back to Spin Settings", callback_data="admin_spin_menu", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    rows.append([InlineKeyboardButton(text="🔙 Back to Panel", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def _show_spin_report(call: CallbackQuery, kind: str, page: int = 0):
    if not is_admin(call.from_user.id):
        return
    try:
        await call.answer()
    except Exception:
        pass

    now = datetime.now()
    if kind == "daily":
        period_key = now.strftime("%Y-%m-%d")
        rows = db_query(
            "SELECT a.user_id, u.first_name, u.username, COUNT(*) AS spins, "
            "COALESCE(SUM(CAST(REPLACE(REPLACE(substr(a.details, instr(a.details, 'Reward: ') + 8), ',', ''), '₹', '') AS REAL)), 0) "
            "FROM activity_logs a LEFT JOIN users u ON u.user_id=a.user_id "
            "WHERE a.action='PLAYED_SPIN' AND substr(a.timestamp,1,10)=? "
            "GROUP BY a.user_id ORDER BY spins DESC, a.user_id ASC",
            (period_key,), fetchall=True
        ) or []
        title = f"📅 <b>DAILY SPIN CONFIGURATION</b>\n<i>{period_key} — today only</i>"
    else:
        period_key = now.strftime("%Y-%m")
        rows = db_query(
            "SELECT a.user_id, u.first_name, u.username, COUNT(*) AS spins, "
            "COALESCE(SUM(CAST(REPLACE(REPLACE(substr(a.details, instr(a.details, 'Reward: ') + 8), ',', ''), '₹', '') AS REAL)), 0) "
            "FROM activity_logs a LEFT JOIN users u ON u.user_id=a.user_id "
            "WHERE a.action='PLAYED_SPIN' AND substr(a.timestamp,1,7)=? "
            "GROUP BY a.user_id ORDER BY spins DESC, a.user_id ASC",
            (period_key,), fetchall=True
        ) or []
        title = f"🗓 <b>MONTHLY SPIN CONFIGURATION</b>\n<i>{period_key} — this month only</i>"

    total_users = len(rows)
    total_pages = max(1, (total_users + SPIN_REPORT_PAGE_SIZE - 1) // SPIN_REPORT_PAGE_SIZE)
    page = max(0, min(int(page), total_pages - 1))
    start = page * SPIN_REPORT_PAGE_SIZE
    page_rows = rows[start:start + SPIN_REPORT_PAGE_SIZE]

    text = title + f"\n\n👥 <b>Users:</b> {total_users}\n📄 <b>Page:</b> {page + 1}/{total_pages}\n━━━━━━━━━━━━━━━━━━\n"
    if not page_rows:
        text += "No spins recorded for this period.\n"
    else:
        for idx, row in enumerate(page_rows, start=start + 1):
            user_id, first_name, username, spins, total_reward = row
            name = _spin_report_name(first_name, username, user_id)
            text += f"{idx}. 👤 <b>{name}</b>\n   🎰 Spins: <b>{spins}</b> | 💰 Rewards: <b>{fmt_curr(float(total_reward or 0.0))}</b>\n   🆔 <code>{user_id}</code>\n\n"
    text += "━━━━━━━━━━━━━━━━━━\n<i>Only the selected day/month is included. Older periods are not added to this report.</i>"
    await safe_edit_text(call.message, text, reply_markup=_spin_report_keyboard(kind, page, total_pages), parse_mode='HTML')

@dp.callback_query(F.data.startswith("spin_daily_report_"))
async def spin_daily_report(call: CallbackQuery):
    try:
        page = int(call.data.rsplit("_", 1)[1])
    except (ValueError, IndexError):
        page = 0
    await _show_spin_report(call, "daily", page)

@dp.callback_query(F.data.startswith("spin_monthly_report_"))
async def spin_monthly_report(call: CallbackQuery):
    try:
        page = int(call.data.rsplit("_", 1)[1])
    except (ValueError, IndexError):
        page = 0
    await _show_spin_report(call, "monthly", page)

# Keep the old callback available for compatibility with any already-open admin
# message, but route it to the Daily Configuration report.
@dp.callback_query(F.data == "spin_view")
async def spin_view(call: CallbackQuery):
    await _show_spin_report(call, "daily", 0)

# ------------------------------------------------------------------------------
# Global APK link editor
# ------------------------------------------------------------------------------

@dp.callback_query(F.data == "admin_edit_all_panel_names")
async def admin_edit_all_panel_names(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    try:
        await call.answer()
    except Exception:
        pass

    rows = []
    for index, category in enumerate(FIXED_CATEGORIES):
        count = db_query(
            "SELECT COUNT(*) FROM products WHERE category LIKE ? AND panel_name IS NOT NULL AND TRIM(panel_name) != ''",
            (category + '%',), fetchone=True
        )
        if count and int(count[0] or 0) > 0:
            rows.append([
                InlineKeyboardButton(
                    text=category,
                    callback_data=f"edit_all_panel_cat_{index}",
                    icon_custom_emoji_id=get_category_emoji(category),
                    style="primary"
                )
            ])

    rows.append([
        InlineKeyboardButton(
            text="Back to Admin",
            callback_data="admin_panel_back",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])
    await safe_edit_text(
        call.message,
        "✏️ <b>EDIT PANEL NAMES</b>\n\nChoose a category:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode='HTML'
    )


@dp.callback_query(F.data.startswith("edit_all_panel_cat_"))
async def edit_all_panel_category(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    try:
        category_index = int(call.data.rsplit("_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid category.", show_alert=True)
    if not (0 <= category_index < len(FIXED_CATEGORIES)):
        return await call.answer("❌ Invalid category.", show_alert=True)

    category = FIXED_CATEGORIES[category_index]
    panels = db_query(
        "SELECT panel_name, COUNT(*) FROM products "
        "WHERE category LIKE ? AND panel_name IS NOT NULL AND TRIM(panel_name) != '' "
        "GROUP BY panel_name ORDER BY panel_name",
        (category + '%',), fetchall=True
    ) or []
    if not panels:
        return await call.answer("❌ No panel names found in this category.", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for panel_index, (panel_name, count) in enumerate(panels):
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{panel_name} ({count})",
                callback_data=f"edit_all_panel_pick_{category_index}_{panel_index}",
                icon_custom_emoji_id=get_panel_emoji(panel_name),
                style="primary"
            )
        ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="Back to Categories",
            callback_data="admin_edit_all_panel_names",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])
    await safe_edit_text(
        call.message,
        f"✏️ <b>EDIT PANEL NAMES</b>\n\n📂 Category: <b>{category}</b>\n\nChoose the panel name to rename.\nThe rename will apply to <b>all durations/packages</b> under that panel.",
        reply_markup=kb,
        parse_mode='HTML'
    )
    await call.answer()


@dp.callback_query(F.data.startswith("edit_all_panel_pick_"))
async def edit_all_panel_pick(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    try:
        parts = call.data.split("_")
        category_index = int(parts[-2])
        panel_index = int(parts[-1])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid panel selection.", show_alert=True)
    if not (0 <= category_index < len(FIXED_CATEGORIES)):
        return await call.answer("❌ Invalid category.", show_alert=True)

    category = FIXED_CATEGORIES[category_index]
    panels = db_query(
        "SELECT panel_name, COUNT(*) FROM products "
        "WHERE category LIKE ? AND panel_name IS NOT NULL AND TRIM(panel_name) != '' "
        "GROUP BY panel_name ORDER BY panel_name",
        (category + '%',), fetchall=True
    ) or []
    if not (0 <= panel_index < len(panels)):
        return await call.answer("❌ Panel selection expired. Please open Edit Panel Names again.", show_alert=True)

    panel_name = str(panels[panel_index][0] or '').strip()
    count = int(panels[panel_index][1] or 0)
    await state.update_data(edit_all_panel_category=category, edit_all_panel_name=panel_name)
    await state.set_state(AdminStates.edit_all_panel_name)
    await call.answer()
    await safe_edit_text(
        call.message,
        f"✏️ <b>RENAME PANEL</b>\n\n📂 Category: <b>{category}</b>\n📦 Current Panel Name: <b>{panel_name}</b>\n📋 Products/Durations: <b>{count}</b>\n\nSend the new panel name.\nThis will rename <b>all products/durations</b> belonging to this panel in this category.",
        reply_markup=admin_back_kb(),
        parse_mode='HTML'
    )


@dp.message(AdminStates.edit_all_panel_name)
async def edit_all_panel_name_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    category = str(data.get('edit_all_panel_category') or '').strip()
    old_name = str(data.get('edit_all_panel_name') or '').strip()
    new_name = (m.text or '').strip()

    if not category or not old_name:
        await state.clear()
        return await m.answer("❌ Panel selection expired. Please open Edit Panel Names again.", reply_markup=admin_kb(), parse_mode='HTML')
    if not new_name:
        return await m.answer("❌ Please enter a valid panel name.", reply_markup=admin_back_kb(), parse_mode='HTML')
    if len(new_name) > 100:
        return await m.answer("❌ Panel name is too long. Please keep it within 100 characters.", reply_markup=admin_back_kb(), parse_mode='HTML')
    if new_name == old_name:
        await state.clear()
        return await m.answer("ℹ️ The panel name is already the same. Nothing was changed.", reply_markup=admin_kb(), parse_mode='HTML')

    # IMPORTANT: only panel_name is changed for matching products. Prices, keys,
    # stock, APK links, API settings, maintenance, payment data, users, orders,
    # and every other product field remain untouched.
    db_query(
        "UPDATE products SET panel_name=? WHERE category LIKE ? AND panel_name=?",
        (new_name, category + '%', old_name)
    )
    updated = db_query(
        "SELECT COUNT(*) FROM products WHERE category LIKE ? AND panel_name=?",
        (category + '%', new_name), fetchone=True
    )
    count = int(updated[0] or 0) if updated else 0

    # Keep a panel-specific custom emoji attached to the renamed panel when one exists.
    old_emoji_key = f"panel_emoji_{old_name}"
    new_emoji_key = f"panel_emoji_{new_name}"
    old_emoji = get_setting(old_emoji_key, "")
    if old_emoji:
        existing_new_emoji = get_setting(new_emoji_key, "")
        if not existing_new_emoji:
            set_setting(new_emoji_key, old_emoji)
        db_query("DELETE FROM settings WHERE key=?", (old_emoji_key,))
        _SETTINGS_CACHE.pop(old_emoji_key, None)

    await state.clear()
    await m.answer(
        f"✅ <b>Panel name updated successfully.</b>\n\n"
        f"📂 Category: <b>{category}</b>\n"
        f"🔄 Old: <b>{old_name}</b>\n"
        f"✏️ New: <b>{new_name}</b>\n"
        f"📋 Updated products/durations: <b>{count}</b>",
        reply_markup=admin_kb(),
        parse_mode='HTML'
    )


@dp.callback_query(F.data == "admin_edit_all_apk_links")
async def admin_edit_all_apk_links(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    try:
        await call.answer()
    except Exception:
        pass

    rows = []
    for idx, category in enumerate(FIXED_CATEGORIES):
        count_row = db_query(
            "SELECT COUNT(*) FROM products WHERE category LIKE ? AND panel_name != ''",
            (category + '%',), fetchone=True
        )
        count = int(count_row[0] or 0) if count_row else 0
        rows.append([
            InlineKeyboardButton(
                text=f"{category} ({count})",
                callback_data=f"edit_all_apk_cat_{idx}",
                icon_custom_emoji_id=get_category_emoji(category),
                style="primary"
            )
        ])

    rows.append([InlineKeyboardButton(
        text="Back to Panel", callback_data="admin_panel_back",
        icon_custom_emoji_id=get_emoji_icon("back"), style="danger"
    )])

    await safe_edit_text(
        call.message,
        "🔗 <b>EDIT APK LINKS ALL</b>\n\n"
        "Choose a category. Then select the panel/product name.\n"
        "The link you save will be applied to <b>all duration/package variants</b> of that panel.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode='HTML'
    )


@dp.callback_query(F.data.startswith("edit_all_apk_cat_"))
async def edit_all_apk_category(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    try:
        category_index = int(call.data.rsplit("_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("Invalid category.", show_alert=True)
    if not (0 <= category_index < len(FIXED_CATEGORIES)):
        return await call.answer("Invalid category.", show_alert=True)

    category = FIXED_CATEGORIES[category_index]
    panels = db_query(
        "SELECT panel_name, COUNT(*) FROM products "
        "WHERE category LIKE ? AND panel_name != '' "
        "GROUP BY panel_name ORDER BY panel_name",
        (category + '%',), fetchall=True
    ) or []

    if not panels:
        return await call.answer("❌ No panel products found in this category.", show_alert=True)

    rows = []
    for panel_index, (panel_name, count) in enumerate(panels):
        rows.append([InlineKeyboardButton(
            text=f"{panel_name} ({int(count or 0)} packages)",
            callback_data=f"edit_all_apk_panel_{category_index}_{panel_index}",
            icon_custom_emoji_id=get_panel_emoji(str(panel_name)) or get_emoji_icon("product_store"),
            style="success"
        )])

    rows.append([InlineKeyboardButton(
        text="Back to Categories", callback_data="admin_edit_all_apk_links",
        icon_custom_emoji_id=get_emoji_icon("back"), style="danger"
    )])
    rows.append([InlineKeyboardButton(
        text="Back to Panel", callback_data="admin_panel_back",
        icon_custom_emoji_id=get_emoji_icon("back"), style="danger"
    )])

    await call.answer()
    await safe_edit_text(
        call.message,
        f"🔗 <b>EDIT APK LINKS ALL</b>\n\n📂 <b>Category:</b> {category}\n\n"
        "Choose the panel/product name. One saved link will update every duration/package under that panel.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode='HTML'
    )


@dp.callback_query(F.data.startswith("edit_all_apk_panel_"))
async def edit_all_apk_panel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    try:
        category_index = int(parts[-2])
        panel_index = int(parts[-1])
    except (ValueError, IndexError):
        return await call.answer("Invalid panel.", show_alert=True)
    if not (0 <= category_index < len(FIXED_CATEGORIES)):
        return await call.answer("Invalid category.", show_alert=True)

    category = FIXED_CATEGORIES[category_index]
    panels = db_query(
        "SELECT panel_name, COUNT(*) FROM products "
        "WHERE category LIKE ? AND panel_name != '' "
        "GROUP BY panel_name ORDER BY panel_name",
        (category + '%',), fetchall=True
    ) or []
    if not (0 <= panel_index < len(panels)):
        return await call.answer("Invalid panel.", show_alert=True)

    panel_name = str(panels[panel_index][0] or '').strip()
    variants = db_query(
        "SELECT name, apk_link FROM products "
        "WHERE category LIKE ? AND panel_name=? ORDER BY name",
        (category + '%', panel_name), fetchall=True
    ) or []
    if not variants:
        return await call.answer("❌ No products found for this panel.", show_alert=True)

    current_links = {str(row[1] or '').strip() for row in variants}
    current_link = next(iter(current_links)) if len(current_links) == 1 else "Multiple / different links"
    names = [str(row[0] or '').strip() for row in variants if str(row[0] or '').strip()]
    preview = ", ".join(names[:12])
    if len(names) > 12:
        preview += f" ... (+{len(names)-12} more)"

    await state.update_data(edit_all_apk_category=category, edit_all_apk_panel=panel_name)
    await state.set_state(AdminStates.edit_all_apk_link)
    await call.answer()
    await safe_edit_text(
        call.message,
        f"🔗 <b>EDIT APK LINK — ALL VARIANTS</b>\n\n"
        f"📂 Category: <b>{category}</b>\n"
        f"📦 Panel: <b>{panel_name}</b>\n"
        f"📋 Packages: <b>{len(variants)}</b>\n"
        f"📌 Variants: {preview}\n\n"
        f"Current link: <code>{current_link}</code>\n\n"
        "Send the new APK/file download link.\n"
        "The new link will <b>replace the existing link on every package</b> of this panel.",
        reply_markup=admin_back_kb(),
        parse_mode='HTML'
    )


@dp.message(AdminStates.edit_all_apk_link)
async def edit_all_apk_link_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    category = str(data.get('edit_all_apk_category') or '').strip()
    panel_name = str(data.get('edit_all_apk_panel') or '').strip()
    link = (m.text or '').strip()

    if not category or not panel_name:
        await state.clear()
        return await m.answer("❌ Panel selection expired. Please open Edit APK Links All again.", reply_markup=admin_kb(), parse_mode='HTML')
    if not link:
        return await m.answer("❌ Please send a valid APK/file download link.", reply_markup=admin_back_kb(), parse_mode='HTML')

    # This intentionally updates only apk_link. It does not touch price, stock,
    # keys, API source/IDs, payment data, users, orders, or any other product field.
    db_query(
        "UPDATE products SET apk_link=? WHERE category LIKE ? AND panel_name=?",
        ("" if link.lower() == "none" else link, category + '%', panel_name)
    )
    updated = db_query(
        "SELECT COUNT(*) FROM products WHERE category LIKE ? AND panel_name=?",
        (category + '%', panel_name), fetchone=True
    )
    count = int(updated[0] or 0) if updated else 0

    await state.clear()
    await m.answer(
        f"✅ <b>APK link updated successfully.</b>\n\n"
        f"📂 Category: <b>{category}</b>\n"
        f"📦 Panel: <b>{panel_name}</b>\n"
        f"🔗 Updated packages: <b>{count}</b>\n\n"
        "The new link is now used for every duration/package under this panel.",
        reply_markup=admin_kb(),
        parse_mode='HTML'
    )


@dp.callback_query(F.data == "admin_set_video")
async def admin_set_video_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "📹 Input direct streaming / YouTube Link for Tutorial system:\n<i>(Or type 'None' to clear registry):</i>", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_howto_video)

@dp.message(AdminStates.wait_for_howto_video)
async def exec_set_video(m: Message, state: FSMContext):
    link = m.text.strip()
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('how_to_video', ?)", (link,))
    await m.answer("✅ Routing complete. Video linked.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_all_files")
async def admin_set_all_files_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "🔗 Input the direct Channel / Cloud URL for 'Download Files' button:\n<i>(Or type 'None' to format data):</i>", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_all_files_link)

@dp.message(AdminStates.wait_for_all_files_link)
async def exec_set_all_files(m: Message, state: FSMContext):
    link = m.text.strip()
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('all_files_link', ?)", (link,))
    await m.answer("✅ Global resource variable updated.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_edit_emojis")
async def admin_edit_emojis(call: CallbackQuery):
    await admin_edit_emojis_page(call, 0)


@dp.callback_query(F.data.startswith("admin_edit_emojis_page_"))
async def admin_edit_emojis_page_callback(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return
    try:
        page = int(call.data.rsplit("_", 1)[1])
    except (ValueError, IndexError):
        page = 0
    await admin_edit_emojis_page(call, page)


async def admin_edit_emojis_page(call: CallbackQuery, page: int = 0):
    if not is_admin(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return
    await call.answer()

    rows = db_query(
        "SELECT key, value FROM settings WHERE key LIKE 'emoji_%'",
        fetchall=True
    ) or []
    saved = {row[0].replace("emoji_", "", 1): (row[1] or "") for row in rows}

    # Show ONLY the canonical custom-emoji slots that are actually used by
    # InlineKeyboardButton icons in this version of the bot.
    # Old/unused emoji_* settings are intentionally NOT deleted, so any
    # previously configured premium/custom IDs remain safe in the database,
    # but they will no longer appear as duplicate/obsolete entries here.
    slots = [
        "product_store", "profile", "add_balance", "history", "referral",
        "tutorial", "support", "ludo_spin", "download", "reseller", "vip",
        "back", "check_icon", "info_icon", "global_stats", "grid_id",
        "redeem_icon", "telegram", "upi", "money_icon", "wallet_balance",
        "pay_direct_qr", "add_balance_first", "confirm_pay", "cancel",
        "whatsapp", "shield_icon", "validity", "wallet", "buy", "maintenance"
    ]

    labels = {
        "product_store": "Product Store",
        "profile": "My Profile",
        "add_balance": "Add Balance",
        "history": "My Key",
        "referral": "Referral",
        "tutorial": "How to use",
        "support": "Support",
        "ludo_spin": "Ludo Spin",
        "download": "Download Files",
        "reseller": "Reseller Panel",
        "vip": "VIP Club",
        "back": "Back",
        "check_icon": "Confirm / Verify",
        "info_icon": "Info / General",
        "global_stats": "Bot Statistics",
        "grid_id": "Product ID",
        "redeem_icon": "Create Coupon",
        "telegram": "Broadcast / Telegram",
        "upi": "UPI / QR Payment",
        "money_icon": "Money / Amount",
        "wallet_balance": "Wallet Balance",
        "pay_direct_qr": "Pay With Direct QR",
        "add_balance_first": "Add Balance Plus First",
        "confirm_pay": "Confirm Pay / Confirm Buy",
        "cancel": "Cancel",
        "whatsapp": "WhatsApp",
        "shield_icon": "Security / Shield",
        "validity": "Validity",
        "wallet": "Wallet",
        "buy": "Buy",
        "maintenance": "Maintenance"
    }

    per_page = 10
    total_pages = max(1, (len(slots) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    page_slots = slots[page * per_page:(page + 1) * per_page]

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for slot in page_slots:
        current_id = saved.get(slot) or DEFAULT_EMOJIS.get(slot, "Not set")
        label = labels.get(slot, slot.replace("_", " ").title())
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{label} (ID: {current_id})",
                callback_data=f"edit_emoji_{slot}",
                icon_custom_emoji_id=str(current_id) if str(current_id).isdigit() else None,
                style="primary"
            )
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"admin_edit_emojis_page_{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"admin_edit_emojis_page_{page + 1}"))
    if nav:
        kb.inline_keyboard.append(nav)

    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="Back to Admin",
            callback_data="admin_panel_back",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])
    await safe_edit_text(call.message, 
        "🎨 <b>Edit All Emojis</b>\n\n"
        f"Page {page + 1}/{total_pages}\n\n"
        "Edit premium emojis for every customer-facing button and product-service field, "
        "including Wallet Balance, Confirm Pay, Maintenance, Buy, Direct QR, "
        "Add Balance, Cancel, Product Name, Validity, Price, Device Limit and Maintenance.",
        reply_markup=kb,
        parse_mode='HTML'
    )

@dp.callback_query(F.data.startswith("edit_emoji_"))
async def admin_edit_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return
    slot = call.data.split("edit_emoji_", 1)[1]
    if not slot:
        await call.answer("Invalid emoji slot.", show_alert=True)
        return
    await call.answer()
    await state.update_data(emoji_slot=slot)
    current = get_setting(f"emoji_{slot}", DEFAULT_EMOJIS.get(slot, "Not set"))
    await safe_edit_text(call.message, 
        f"✏️ Enter new premium emoji ID for <b>{slot.replace('_', ' ').title()}</b>:\n"
        f"Current: <code>{current}</code>\n\n"
        "(Send only the numeric custom emoji ID. Send empty to reset to default.)",
        reply_markup=admin_back_kb(),
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.wait_for_emoji_slot)

@dp.message(AdminStates.wait_for_emoji_slot)
async def save_emoji_slot(m: Message, state: FSMContext):
    data = await state.get_data()
    slot = data['emoji_slot']
    new_id = m.text.strip()
    if new_id == "":
        db_query("DELETE FROM settings WHERE key=?", (f"emoji_{slot}",))
        await m.answer(f"✅ Reset emoji for '{slot}' to default.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        if not new_id.isdigit():
            await m.answer("❌ Invalid ID! Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
            return
        set_setting(f"emoji_{slot}", new_id)
        await m.answer(f"✅ Emoji for '{slot}' updated to ID {new_id}.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_edit_ui_menu")
async def admin_edit_ui_menu(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Edit Start Menu Text", callback_data="edit_ui_start", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")],
        [InlineKeyboardButton(text="Edit Download Files Text", callback_data="edit_ui_download", icon_custom_emoji_id=get_emoji_icon("download"), style="primary")],
        [InlineKeyboardButton(text="Edit VIP Menu Text", callback_data="edit_ui_vip", icon_custom_emoji_id=get_emoji_icon("vip"), style="primary")],
        [InlineKeyboardButton(text="Edit Lucky Dice Text", callback_data="edit_ui_dice", icon_custom_emoji_id=get_emoji_icon("ludo_spin"), style="primary")],
        [InlineKeyboardButton(text="Edit Add Balance Text", callback_data="edit_ui_add_balance", icon_custom_emoji_id=get_emoji_icon("add_balance"), style="primary")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await safe_edit_text(call.message, "✏️ <b>Edit User Interface Texts</b>\nSelect which text you want to modify:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("edit_ui_"))
async def admin_edit_ui_prompt(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    ui_key = call.data.split("_", 2)[2]
    if ui_key == "start":
        ui_key = "start_menu"
    await state.update_data(ui_key=ui_key)
    current_text = get_ui_text(ui_key)
    has_image = bool(get_ui_photo_id(ui_key))
    image_note = "\n\n🖼 Current premium image: SAVED" if has_image else ""
    await safe_edit_text(call.message, f"📝 Send the new text for <b>{ui_key.upper()}</b> menu.\n\nCurrent text:\n{current_text}{image_note}\n\nYou can send plain text, or send a premium image with its caption. The same image and caption will be shown in the UI.", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.edit_ui_text)

@dp.message(AdminStates.edit_ui_text)
async def admin_save_ui_text(m: Message, state: FSMContext):
    data = await state.get_data()
    ui_key = data['ui_key']

    # Plain text message: save text and remove any previously attached UI image.
    if m.text is not None:
        new_text = m.text
        db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"ui_{ui_key}", new_text))
        db_query("DELETE FROM settings WHERE key=?", (f"ui_{ui_key}_photo_id",))
        await m.answer(f"✅ UI text <b>{ui_key}</b> updated successfully!", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
        return

    # Photo + caption: save the exact Telegram file_id and HTML caption.
    # Message.html_caption preserves custom/premium emoji entities as HTML.
    if m.photo:
        photo_id = m.photo[-1].file_id
        new_text = getattr(m, "html_caption", None) or m.caption or ""
        db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"ui_{ui_key}", new_text))
        db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"ui_{ui_key}_photo_id", photo_id))
        await m.answer(f"✅ UI text + premium image for <b>{ui_key}</b> updated successfully!", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
        return

    await m.answer("❌ Please send text, or send a photo with the text/caption.", reply_markup=admin_back_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_edit_reseller_price")
async def admin_edit_reseller_price_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return
    await _show_reseller_price_page(call, 0)

@dp.callback_query(F.data.startswith("admin_edit_reseller_page_"))
async def admin_edit_reseller_price_page(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return
    try:
        page = int(call.data.rsplit("_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("Invalid page.", show_alert=True)
    await _show_reseller_price_page(call, page)

async def _show_reseller_price_page(call: CallbackQuery, page: int = 0):
    try:
        await call.answer()
    except Exception:
        pass

    # Read only the reseller-price data; no payment/product purchase logic is touched.
    prods = db_query(
        "SELECT id, name, category, COALESCE(panel_name, ''), "
        "COALESCE(reseller_price, 0.0) "
        "FROM products ORDER BY category, panel_name, name",
        fetchall=True
    )

    if prods is None:
        try:
            await call.answer("Unable to read products.", show_alert=True)
        except Exception:
            pass
        return

    if not prods:
        await safe_edit_text(call.message, 
            "📝 <b>Edit Reseller Price</b>\n\nNo products have been added yet.",
            reply_markup=admin_back_kb(),
            parse_mode='HTML'
        )
        return

    page_size = 8
    total_pages = max(1, (len(prods) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    page_prods = prods[page * page_size:(page + 1) * page_size]

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in page_prods:
        category = str(p[2] or "").strip()
        panel_name = str(p[3] or "").strip()
        product_name = str(p[1] or "").strip()
        r_price = float(p[4] or 0.0)
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{category} - {panel_name} - {product_name} (₹{r_price:.2f})",
                callback_data=f"edit_reseller_{int(p[0])}",
                style="primary"
            )
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="◀️ Previous",
            callback_data=f"admin_edit_reseller_page_{page - 1}",
            style="primary"
        ))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(
            text="Next ▶️",
            callback_data=f"admin_edit_reseller_page_{page + 1}",
            style="primary"
        ))
    if nav:
        kb.inline_keyboard.append(nav)

    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="Back to Admin",
            callback_data="admin_panel_back",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])

    await safe_edit_text(call.message, 
        f"👑 <b>Edit Reseller Price per Product</b>\n\n"
        f"Select a product to change its reseller/wholesale price.\n"
        f"Page {page + 1}/{total_pages}",
        reply_markup=kb,
        parse_mode='HTML'
    )

@dp.callback_query(F.data.startswith("edit_reseller_"))
async def admin_edit_reseller_price_prompt(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return
    try:
        prod_id = int(call.data.rsplit("_", 1)[1])
        exists = db_query(
            "SELECT id, name, COALESCE(reseller_price, 0.0) FROM products WHERE id=?",
            (prod_id,),
            fetchone=True
        )
        if not exists:
            await call.answer("Product not found.", show_alert=True)
            return

        await call.answer()
        await state.update_data(edit_reseller_prod_id=prod_id)
        await safe_edit_text(call.message, 
            f"💰 <b>Edit Reseller Price</b>\n\n"
            f"Product: <b>{exists[1]}</b>\n"
            f"Current reseller price: <b>{fmt_curr(float(exists[2] or 0.0))}</b>\n\n"
            "Send the new price in Rupees (₹):",
            reply_markup=admin_back_kb(),
            parse_mode='HTML'
        )
        await state.set_state(AdminStates.edit_reseller_price)
    except Exception as e:
        logger.exception("Edit Reseller Price product prompt failed")
        await call.answer(f"Error: {str(e)[:150]}", show_alert=True)

@dp.message(AdminStates.edit_reseller_price)
async def admin_save_reseller_price(m: Message, state: FSMContext):
    raw = (m.text or "").strip().replace(",", "")
    try:
        new_price = float(raw)
        if new_price < 0:
            raise ValueError
    except ValueError:
        await m.answer(
            "❌ Invalid number. Please enter a valid non-negative price.",
            reply_markup=admin_back_kb(),
            parse_mode='HTML'
        )
        return

    data = await state.get_data()
    prod_id = data.get("edit_reseller_prod_id")
    if not prod_id:
        await state.clear()
        await m.answer("❌ Product selection expired. Please open Edit Reseller Price again.", reply_markup=admin_kb())
        return

    updated = db_query(
        "UPDATE products SET reseller_price=? WHERE id=?",
        (new_price, int(prod_id))
    )
    if updated is None:
        await m.answer(
            "❌ Could not save reseller price. Please restart the bot and try again.",
            reply_markup=admin_back_kb(),
            parse_mode='HTML'
        )
        return

    await m.answer(
        f"✅ Reseller price updated to {fmt_curr(new_price)} for product ID {prod_id}.",
        reply_markup=admin_kb(),
        parse_mode='HTML'
    )
    await state.clear()

@dp.callback_query(F.data == "admin_set_reseller_fee")
async def admin_set_reseller_fee(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "💰 Enter the new <b>Reseller Setup Fee</b> in Rupees (₹):\nCurrent: " + get_setting("reseller_setup_fee", "200.0"), reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_reseller_setup_fee)

@dp.message(AdminStates.wait_for_reseller_setup_fee)
async def admin_save_reseller_fee(m: Message, state: FSMContext):
    try:
        fee = float(m.text)
        set_setting("reseller_setup_fee", str(fee))
        await m.answer(f"✅ Reseller setup fee updated to {fmt_curr(fee)}.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Invalid number. Please enter a valid amount.")

@dp.callback_query(F.data == "admin_set_reseller_min")
async def admin_set_reseller_min(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "💳 Enter the new <b>Minimum Balance</b> required to become reseller (₹):\nCurrent: " + get_setting("reseller_min_balance", "1.0"), reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_reseller_min_balance)

@dp.message(AdminStates.wait_for_reseller_min_balance)
async def admin_save_reseller_min(m: Message, state: FSMContext):
    try:
        min_bal = float(m.text)
        set_setting("reseller_min_balance", str(min_bal))
        await m.answer(f"✅ Minimum reseller balance updated to {fmt_curr(min_bal)}.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Invalid number. Please enter a valid amount.")

@dp.callback_query(F.data == "admin_set_support_links")
async def admin_set_support_links(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Set Telegram Link", callback_data="admin_set_telegram", icon_custom_emoji_id=get_emoji_icon("telegram"), style="primary")],
        [InlineKeyboardButton(text="📱 Set WhatsApp Link", callback_data="admin_set_whatsapp", icon_custom_emoji_id=get_emoji_icon("whatsapp"), style="primary")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await safe_edit_text(call.message, "📌 <b>Support Contact Links</b>\nSet the URLs for Telegram and WhatsApp support:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "admin_set_telegram")
async def admin_set_telegram(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "✈️ Enter the Telegram contact URL (e.g., https://t.me/YOUR_SUPPORT):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_support_telegram)

@dp.message(AdminStates.wait_for_support_telegram)
async def save_telegram_link(m: Message, state: FSMContext):
    link = m.text.strip()
    set_setting("support_telegram", link)
    await m.answer("✅ Telegram support link updated!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_whatsapp")
async def admin_set_whatsapp(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "📱 Enter the WhatsApp contact URL (e.g., https://wa.me/1234567890):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_support_whatsapp)

@dp.message(AdminStates.wait_for_support_whatsapp)
async def save_whatsapp_link(m: Message, state: FSMContext):
    link = m.text.strip()
    set_setting("support_whatsapp", link)
    await m.answer("✅ WhatsApp support link updated!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_category_emojis")
async def admin_set_category_emojis(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in FIXED_CATEGORIES:
        current = get_setting(f"cat_emoji_{cat}", "Not set")
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{cat} (ID: {current})", callback_data=f"set_cat_emoji_{cat}", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await safe_edit_text(call.message, "🎨 <b>Set Category Emojis</b>\nChoose a category to set its custom emoji ID:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("set_cat_emoji_"))
async def admin_set_category_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    category = call.data.split("set_cat_emoji_", 1)[1]
    await state.update_data(cat_emoji_category=category)
    await safe_edit_text(call.message, f"🎨 Enter the emoji ID for <b>{category}</b>:\n(Leave empty to reset to default)", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_category_emoji)

@dp.message(AdminStates.wait_for_category_emoji)
async def save_category_emoji(m: Message, state: FSMContext):
    data = await state.get_data()
    category = data['cat_emoji_category']
    emoji_id = m.text.strip()
    if emoji_id == "":
        db_query("DELETE FROM settings WHERE key=?", (f"cat_emoji_{category}",))
        await m.answer(f"✅ Reset emoji for {category} to default.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        if not emoji_id.isdigit():
            await m.answer("❌ Invalid ID! Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
            return
        set_setting(f"cat_emoji_{category}", emoji_id)
        await m.answer(f"✅ Emoji set for {category} successfully!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_panel_emojis")
async def admin_set_panel_emojis(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    panels = db_query(
        "SELECT DISTINCT panel_name FROM products "
        "WHERE panel_name != '' ORDER BY panel_name",
        fetchall=True
    )

    if not panels:
        await safe_edit_text(call.message, 
            "No panel names found in products.",
            reply_markup=admin_back_kb(),
            parse_mode='HTML'
        )
        await call.answer()
        return

    # Use a short numeric callback ID instead of putting the full panel name
    # into callback_data. Telegram callback_data is limited to 64 bytes.
    kb = InlineKeyboardMarkup(inline_keyboard=[])

    for index, p in enumerate(panels):
        panel = str(p[0])
        current = get_setting(f"panel_emoji_{panel}", "Not set")

        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{panel} (ID: {current})",
                callback_data=f"set_panel_emoji_idx_{index}",
                icon_custom_emoji_id=get_emoji_icon("info_icon"),
                style="primary"
            )
        ])

    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="Back to Admin",
            callback_data="admin_panel_back",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])

    await safe_edit_text(call.message, 
        "🖼 <b>Set Panel Emojis</b>\n"
        "Choose a panel name to set its custom emoji ID:",
        reply_markup=kb,
        parse_mode='HTML'
    )
    await call.answer()


@dp.callback_query(F.data.startswith("set_panel_emoji_idx_"))
async def admin_set_panel_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return

    try:
        index = int(call.data.split("set_panel_emoji_idx_", 1)[1])
    except (ValueError, IndexError):
        await call.answer("❌ Invalid panel selection.", show_alert=True)
        return

    panels = db_query(
        "SELECT DISTINCT panel_name FROM products "
        "WHERE panel_name != '' ORDER BY panel_name",
        fetchall=True
    ) or []

    if index < 0 or index >= len(panels):
        await call.answer("❌ Panel not found. Please reopen Set Panel Emojis.", show_alert=True)
        return

    panel_name = str(panels[index][0])

    await state.update_data(panel_emoji_name=panel_name)
    await safe_edit_text(call.message, 
        f"🎨 Enter the emoji ID for panel <b>{panel_name}</b>:\n"
        "(Leave empty to reset to default)",
        reply_markup=admin_back_kb(),
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.wait_for_panel_emoji_id)
    await call.answer()

@dp.message(AdminStates.wait_for_panel_emoji_id)
async def save_panel_emoji(m: Message, state: FSMContext):
    data = await state.get_data()
    panel_name = data['panel_emoji_name']
    emoji_id = m.text.strip()
    if emoji_id == "":
        db_query("DELETE FROM settings WHERE key=?", (f"panel_emoji_{panel_name}",))
        await m.answer(f"✅ Reset emoji for panel '{panel_name}'.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        if not emoji_id.isdigit():
            await m.answer("❌ Invalid ID! Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
            return
        set_setting(f"panel_emoji_{panel_name}", emoji_id)
        await m.answer(f"✅ Emoji set for panel '{panel_name}'!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_setup_fampay")
async def setup_fampay_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    current_key = get_setting("fampay_api_key", "")
    current_url = get_fampay_base_url()
    current_email = get_setting("fampay_merchant_email", "")
    current_upi = get_setting("fampay_upi_id", "")
    masked = (current_key[:4] + "••••••" + current_key[-4:]) if len(current_key) > 8 else ("Not configured" if not current_key else "Configured")
    text = ("💳 <b>FAMPAY GATEWAY SETUP</b>\n\n"
            f"🌐 Base URL: <code>{current_url}</code>\n"
            f"🔑 API Key: <code>{masked}</code>\n"
            f"📧 Merchant Gmail: <code>{current_email or 'Not set'}</code>\n"
            f"🆔 FamPay UPI ID: <code>{current_upi or 'Not set'}</code>\n\n"
            "Send settings one by one. This bot uses the FamGateway-compatible API endpoints /api/qr.php and /api/verify-order.php.\n"
            "⚠️ The Gmail App Password is NOT stored in this bot; it must be configured securely inside your gateway provider dashboard.\n\n"
            "<i>Step 1/4 — send the gateway Base URL, or send SKIP to keep the current URL.</i>\n"
            "<i>Type /cancel to abort.</i>")
    await safe_edit_text(call.message, text, reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_fampay_api)
    await state.update_data(fampay_setup_step='url')

@dp.message(AdminStates.wait_for_fampay_api)
async def fampay_api(m: Message, state: FSMContext):
    value = (m.text or '').strip()
    if value.lower() == '/cancel':
        await state.clear()
        return await m.answer("Setup cancelled.", reply_markup=admin_kb(), parse_mode='HTML')
    data = await state.get_data()
    step = data.get('fampay_setup_step', 'url')
    if step == 'url':
        if value.upper() != 'SKIP':
            if not (value.startswith('https://') or value.startswith('http://')):
                return await m.answer("❌ Invalid URL. Send a full http(s) URL or SKIP.", parse_mode='HTML')
            set_setting('fampay_base_url', value.rstrip('/'))
        await state.update_data(fampay_setup_step='api')
        return await m.answer("Step 2/4 — Send the <b>FamGateway API key</b> (or SKIP to keep current).", parse_mode='HTML')
    if step == 'api':
        if value.upper() != 'SKIP':
            if len(value) < 8:
                return await m.answer("❌ API key looks too short. Send the valid key or SKIP.", parse_mode='HTML')
            set_setting('fampay_api_key', value)
        await state.update_data(fampay_setup_step='email')
        return await m.answer("Step 3/4 — Send the <b>FamPay-linked Gmail address</b> (or SKIP). This is for your reference only; configure the Gmail/App Password in the gateway dashboard.", parse_mode='HTML')
    if step == 'email':
        if value.upper() != 'SKIP':
            if '@' not in value or '.' not in value.split('@')[-1]:
                return await m.answer("❌ Invalid email. Send a valid Gmail address or SKIP.", parse_mode='HTML')
            set_setting('fampay_merchant_email', value)
        await state.update_data(fampay_setup_step='upi')
        return await m.answer("Step 4/4 — Send your <b>FamPay UPI ID</b> (for example <code>name@fam</code>) or SKIP.", parse_mode='HTML')
    if step == 'upi':
        if value.upper() != 'SKIP':
            if '@' not in value:
                return await m.answer("❌ Invalid UPI ID. Send something like <code>name@fam</code> or SKIP.", parse_mode='HTML')
            set_setting('fampay_upi_id', value)
        await state.clear()
        await m.answer(
            f"✅ <b>FamPay gateway setup saved.</b>\n\n🌐 <code>{get_fampay_base_url()}</code>\n🔑 API: {'Configured' if get_setting('fampay_api_key','') else 'Not configured'}\n📧 Gmail: <code>{get_setting('fampay_merchant_email','') or 'Not set'}</code>\n🆔 UPI: <code>{get_setting('fampay_upi_id','') or 'Not set'}</code>\n\n⚠️ Keep the Gmail App Password inside the gateway provider dashboard, not in the bot.",
            reply_markup=admin_kb(), parse_mode='HTML')

# ==============================================================================
# 22. BOOTSTRAPPING & MAIN
# ==============================================================================
async def main() -> None:
    global bot

    init_db()
    # Self-heal older databases: admin-granted reseller plans use an optional expiry.
    try:
        conn = sqlite3.connect("yp_shop.db")
        cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "reseller_expires_at" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN reseller_expires_at TEXT DEFAULT NULL")
            conn.commit()
        conn.close()
    except Exception:
        logger.exception("Failed to add reseller expiry column")
    globals()["VIP_PRICE_INR"] = float(get_setting("vip_price_inr", str(VIP_PRICE_INR)))
    logger.info("Initializing DB structure...")
    migrate_categories()
    asyncio.create_task(auto_verify_task())
    logger.info("FamPay Auto-Verifier Daemon Running in Background.")
    logger.info("🚀 CORE SYSTEM IS FULLY OPERATIONAL...")

    # Keep the Telegram polling process alive. If a temporary network,
    # connection, or polling error stops start_polling(), wait briefly,
    # recreate the Bot session, and reconnect automatically.
    while True:
        try:
            logger.info("Starting Telegram polling...")
            await dp.start_polling(bot)
            logger.warning("Telegram polling stopped. Reconnecting in 5 seconds...")
        except (KeyboardInterrupt, SystemExit):
            logger.info("System shutting down gracefully. Goodbye.")
            break
        except asyncio.CancelledError:
            logger.info("Polling task cancelled. Shutting down.")
            break
        except Exception as err:
            logger.error(f"Telegram polling/connection error: {err}")
            logger.info("Automatic reconnect in 5 seconds...")
        finally:
            try:
                await bot.session.close()
            except Exception as close_err:
                logger.debug(f"Bot session close error: {close_err}")

        await asyncio.sleep(5)
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
        logger.info("Telegram bot session recreated. Retrying connection...")

# ==============================================================================
# EXTERNAL KEY GENERATION API
# ==============================================================================
def normalize_api_duration(duration: str) -> str:
    """Normalize the package name into the duration format expected by the API."""
    value = str(duration or "").strip()
    if not value:
        return value

    # Normalize whitespace
    value = re.sub(r"\s+", " ", value)
    
    # Define exact mapping for your API format
    # API expects: "X Hours" or "X DaYs" (with capital D and Y)
    duration_map = {
        # Hours - API expects "X Hours"
        "1 hour": "1 Hours",
        "1 hours": "1 Hours",
        "1hr": "1 Hours",
        "1h": "1 Hours",
        "2 hour": "2 Hours",
        "2 hours": "2 Hours",
        "2hr": "2 Hours",
        "3 hour": "3 Hours",
        "3 hours": "3 Hours",
        "3hr": "3 Hours",
        "6 hour": "6 Hours",
        "6 hours": "6 Hours",
        "6hr": "6 Hours",
        "12 hour": "12 Hours",
        "12 hours": "12 Hours",
        "12hr": "12 Hours",
        
        # Days - API expects "X DaYs" (capital D and Y)
        "1 day": "1 DaYs",
        "1 days": "1 DaYs",
        "1d": "1 DaYs",
        "2 day": "2 DaYs",
        "2 days": "2 DaYs",
        "2d": "2 DaYs",
        "3 day": "3 DaYs",
        "3 days": "3 DaYs",
        "3d": "3 DaYs",
        "5 day": "5 DaYs",
        "5 days": "5 DaYs",
        "5d": "5 DaYs",
        "7 day": "7 DaYs",
        "7 days": "7 DaYs",
        "7d": "7 DaYs",
    }
    
    # Check exact matches first (case insensitive)
    lower_val = value.lower()
    for pattern, result in duration_map.items():
        if lower_val == pattern.lower():
            return result
    
    # Check if it's already in correct format
    if value in ["1 Hours", "2 Hours", "3 Hours", "6 Hours", "12 Hours", 
                 "1 DaYs", "2 DaYs", "3 DaYs", "5 DaYs", "7 DaYs"]:
        return value
    
    # Try to extract number and determine unit
    match = re.match(r"(\d+)\s*(hour|hours|hr|hrs|h|day|days|d)", value, re.IGNORECASE)
    if match:
        number = match.group(1)
        unit = match.group(2).lower()
        if unit in ["hour", "hours", "hr", "hrs", "h"]:
            return f"{number} Hours"
        if unit in ["day", "days", "d"]:
            return f"{number} DaYs"
    
    # If it's just a number, treat as hours
    if value.isdigit():
        return f"{value} Hours"
    
    # Return as-is if nothing matches (fallback)
    return value

async def fetch_external_key(product_id: str, duration: str, android_id: str = "", api_type: int = 1) -> dict:
    """Buy a key using API 1 or the separate APK gateway API 2."""
    api_type = 2 if int(api_type or 1) == 2 else 1

    if api_type == 2:
        # External API 2 follows the supplied PHP gateway example exactly:
        # POST form fields: action=buy, variant_id=<variant>, quantity=1
        # Header: x-master-key=<master key>
        # The supplied PHP example does not send a separate API-key field.
        url = get_setting("external_api2_url", "https://keypanel.shop/reseller_gateway.php").strip()
        master_key = get_setting("external_api2_master_key", "").strip()
        variant_id = str(product_id or "").strip()
        if not url:
            return {"status": "error", "msg": "APK API URL is not configured"}
        if not master_key:
            return {"status": "error", "msg": "APK API master key is not configured"}
        if not variant_id:
            return {"status": "error", "msg": "APK Variant ID is empty"}

        data = {"action": "buy", "variant_id": variant_id, "quantity": "1"}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json, text/plain, */*",
            "x-master-key": master_key,
        }
        timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_connect=5, sock_read=10)
        for attempt in range(1, 3):
            try:
                logger.info("APK API BUY attempt=%s variant_id=%r quantity=1", attempt, variant_id)
                connector = aiohttp.TCPConnector(family=socket.AF_INET, force_close=True, ssl=True)
                try:
                    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                        async with session.post(url, data=data, headers=headers, allow_redirects=True) as resp:
                            raw = await resp.text()
                            logger.info("APK API response: HTTP %s body=%s", resp.status, raw[:1000])
                            if resp.status != 200:
                                return {"status": "error", "msg": f"HTTP {resp.status}: {raw[:500]}"}
                            if not raw.strip():
                                return {"status": "error", "msg": "APK API returned an empty response"}
                            try:
                                result = json.loads(raw)
                            except json.JSONDecodeError:
                                return {"status": "error", "msg": f"APK API returned invalid JSON: {raw[:300]}"}
                            if not isinstance(result, dict):
                                return {"status": "error", "msg": "APK API returned an invalid response object"}
                            if result.get("ok") is True:
                                keys = result.get("keys")
                                key = result.get("key")
                                if isinstance(keys, list) and keys:
                                    key = "\n".join(str(x) for x in keys)
                                if key is None or not str(key).strip():
                                    return {"status": "error", "msg": "APK API returned no key"}
                                return {
                                    "status": "success",
                                    "key": str(key),
                                    "order_id": result.get("order_id", ""),
                                    "expires_at": result.get("expires_at", ""),
                                    "raw": result,
                                }
                            error = result.get("error", "Unknown APK API error")
                            shortfall = result.get("shortfall")
                            if shortfall is not None:
                                error = f"{error} (need ₹{shortfall} more)"
                            return {"status": "error", "msg": str(error), "raw": result}
                finally:
                    if not connector.closed:
                        await connector.close()
            except (aiohttp.ClientConnectorError, aiohttp.ClientConnectionError, aiohttp.ServerTimeoutError, asyncio.TimeoutError) as exc:
                logger.warning("APK API connection attempt %s failed: %s", attempt, exc)
                if attempt == 1:
                    await asyncio.sleep(1)
                    continue
                return {"status": "error", "msg": f"APK API connection failed: {type(exc).__name__}: {exc}"}
            except aiohttp.ClientError as exc:
                logger.exception("APK API client error")
                return {"status": "error", "msg": f"APK API client error: {exc}"}
            except Exception as exc:
                logger.exception("APK API unexpected error")
                return {"status": "error", "msg": f"APK API unexpected error: {exc}"}
        return {"status": "error", "msg": "APK API request failed after retries"}

    # API 1 remains exactly on its existing API-key/product-id/duration flow.
    url = get_setting("external_api_url", "https://adminpanels.shop/api/reseller_v1.php").strip()
    api_key = get_setting("external_api_key", "").strip()
    master_key = get_setting("external_master_key", "").strip()
    if not url:
        return {"status": "error", "msg": "External API 1 URL is not configured"}
    if not api_key:
        return {"status": "error", "msg": "External API 1 API key is not configured"}
    product_id = str(product_id or "").strip()
    duration = str(duration or "").strip()
    if not product_id:
        return {"status": "error", "msg": "External API 1 Product ID is empty"}
    if not duration:
        return {"status": "error", "msg": "Product duration is empty"}
    data = {"api_key": api_key, "action": "buy", "product_id": product_id, "duration": duration}
    if android_id:
        data["android_id"] = str(android_id).strip()
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json, text/plain, */*"}
    if master_key:
        headers["x-master-key"] = master_key
    timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_connect=5, sock_read=10)
    for attempt in range(1, 3):
        try:
            logger.info("External API 1 BUY attempt=%s product_id=%r duration=%r", attempt, product_id, duration)
            connector = aiohttp.TCPConnector(family=socket.AF_INET, force_close=True, ssl=True)
            try:
                async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                    async with session.post(url, data=data, headers=headers, allow_redirects=True) as resp:
                        raw = await resp.text()
                        if resp.status != 200:
                            return {"status": "error", "msg": f"HTTP {resp.status}: {raw[:500]}"}
                        if not raw.strip():
                            return {"status": "error", "msg": "External API 1 returned an empty response"}
                        try:
                            result = json.loads(raw)
                        except json.JSONDecodeError:
                            return {"status": "error", "msg": f"External API 1 returned invalid JSON: {raw[:300]}"}
                        return result if isinstance(result, dict) else {"status": "error", "msg": "External API 1 returned an invalid response object"}
            finally:
                if not connector.closed:
                    await connector.close()
        except (aiohttp.ClientConnectorError, aiohttp.ClientConnectionError, aiohttp.ServerTimeoutError, asyncio.TimeoutError) as exc:
            if attempt == 1:
                await asyncio.sleep(1); continue
            return {"status": "error", "msg": f"External API 1 connection failed: {type(exc).__name__}: {exc}"}
        except aiohttp.ClientError as exc:
            return {"status": "error", "msg": f"External API 1 client error: {exc}"}
        except Exception as exc:
            logger.exception("External API 1 unexpected error")
            return {"status": "error", "msg": f"External API 1 unexpected error: {exc}"}
    return {"status": "error", "msg": "External API 1 request failed after retries"}

@dp.callback_query(F.data == "admin_purchase_feedback")
async def admin_purchase_feedback_start(call: CallbackQuery, state: FSMContext):
    try:
        await call.answer()
    except Exception:
        pass
    if not is_admin(call.from_user.id):
        return
    current = get_setting("purchase_feedback", "")
    preview = current if current else "Not configured"
    await safe_edit_text(call.message, 
        "💬 <b>PURCHASE FEEDBACK</b>\n\n"
        "This message is sent only to the customer who completes a purchase.\n\n"
        f"<b>Current message:</b>\n{preview}\n\n"
        "Send the new feedback text now. It will replace the current message.",
        reply_markup=admin_back_kb(),
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.purchase_feedback_msg)

@dp.message(AdminStates.purchase_feedback_msg)
async def save_purchase_feedback(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    text = (m.text or "").strip()
    if not text:
        return await m.answer("❌ Feedback message cannot be empty.", reply_markup=admin_back_kb(), parse_mode='HTML')
    set_setting("purchase_feedback", text)
    await state.clear()
    await m.answer("✅ Purchase feedback message saved. It will be sent only to customers after their successful purchase.", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data.startswith("purchase_feedback_"))
async def send_purchase_feedback(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    try:
        user_id = int(call.data.split("purchase_feedback_", 1)[1])
    except ValueError:
        return await call.answer("❌ Invalid customer ID.", show_alert=True)
    feedback = get_setting("purchase_feedback", "🙏 Thanks for purchasing! Your order has been delivered successfully. ❤️").strip()
    if not feedback:
        return await call.answer("❌ Purchase feedback is not configured.", show_alert=True)
    try:
        await bot.send_message(user_id, feedback, parse_mode='HTML')
        await call.answer("✅ Feedback sent to this customer only.", show_alert=True)
    except Exception as e:
        logger.error(f"Failed to send purchase feedback to {user_id}: {e}")
        await call.answer("❌ Could not send feedback to this customer.", show_alert=True)

@dp.callback_query(F.data == "admin_setup_external_api")
async def admin_setup_external_api(call: CallbackQuery, state: FSMContext):
    try:
        await call.answer()
    except Exception:
        pass
    if not is_admin(call.from_user.id):
        return
    url = get_setting("external_api_url", "")
    key = get_setting("external_api_key", "")
    master = get_setting("external_master_key", "")
    mask = lambda x: (x[:4] + "••••" + x[-4:]) if len(x) > 8 else ("Configured" if x else "Not set")
    api1_status = get_setting("external_api1_status", "ON")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Set API URL", callback_data="admin_set_ext_url", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")],
        [InlineKeyboardButton(text="Set API Key", callback_data="admin_set_ext_key", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")],
        [InlineKeyboardButton(text="Set Master Key", callback_data="admin_set_ext_master", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")],
        [InlineKeyboardButton(text=f"API 1 Status: {api1_status} {'🟢' if api1_status == 'ON' else '🔴'}", callback_data="admin_toggle_ext1", icon_custom_emoji_id=get_emoji_icon("check_icon"), style="success" if api1_status == "ON" else "danger")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    text = ("🔗 <b>External Key API Configuration</b>\n\n"
            f"Status: <b>{api1_status}</b>\n"
            f"URL: <code>{url or 'Not set'}</code>\n"
            f"API Key: <code>{mask(key)}</code>\n"
            f"Master Key: <code>{mask(master)}</code>\n\n"
            "Products can be switched to API generation from the Add Product flow.")
    await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "admin_toggle_ext1")
async def toggle_external_api1(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    current = get_setting("external_api1_status", "ON")
    new_status = "OFF" if current == "ON" else "ON"
    set_setting("external_api1_status", new_status)
    await call.answer(f"External API 1: {new_status}", show_alert=True)
    await admin_setup_external_api(call, FSMContext)

@dp.callback_query(F.data == "admin_setup_external_api2")
async def admin_setup_external_api2(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    url = get_setting("external_api2_url", "")
    key = get_setting("external_api2_key", "")
    master = get_setting("external_api2_master_key", "")
    status = get_setting("external_api2_status", "OFF")
    mask = lambda x: (x[:4] + "••••" + x[-4:]) if len(x) > 8 else ("Configured" if x else "Not set")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Set API URL", callback_data="admin_set_ext2_url", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")],
        [InlineKeyboardButton(text="Set API Key", callback_data="admin_set_ext2_key", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")],
        [InlineKeyboardButton(text="Set X-Master Key", callback_data="admin_set_ext2_master", icon_custom_emoji_id=get_emoji_icon("info_icon"), style="primary")],
        [InlineKeyboardButton(text=f"External API 2 Status: {status} {'🟢' if status == 'ON' else '🔴'}", callback_data="admin_toggle_ext2", icon_custom_emoji_id=get_emoji_icon("check_icon"), style="success" if status == "ON" else "danger")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    text = ("🔗 <b>External Key API 2 Configuration</b>\n\n"
            f"Status: <b>{status}</b>\n"
            f"API URL: <code>{url or 'Not set'}</code>\n"
            f"API Key: <code>{mask(key)}</code>\n"
            f"X-Master Key: <code>{mask(master)}</code>\n\n"
            "Products assigned to External API 2 use the Variant ID. The purchase request follows the supplied PHP gateway format: action=buy, variant_id, quantity=1, and the x-master-key header.")
    await safe_edit_text(call.message, text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "admin_toggle_ext2")
async def toggle_external_api2(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    current = get_setting("external_api2_status", "OFF")
    new_status = "OFF" if current == "ON" else "ON"
    set_setting("external_api2_status", new_status)
    await call.answer(f"APK API: {new_status}", show_alert=True)
    await admin_setup_external_api2(call, FSMContext)

@dp.callback_query(F.data == "admin_set_ext2_url")
async def set_ext2_url(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "Enter External API 2 URL:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_ext2_url)

@dp.message(AdminStates.wait_for_ext2_url)
async def save_ext2_url(m: Message, state: FSMContext):
    value = m.text.strip()
    if not value.startswith(("http://", "https://")):
        return await m.answer("❌ URL must start with http:// or https://")
    set_setting("external_api2_url", value)
    await m.answer("✅ External API 2 URL saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_ext2_key")
async def set_ext2_key(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "Enter External API 2 API Key:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_ext2_key)

@dp.message(AdminStates.wait_for_ext2_key)
async def save_ext2_key(m: Message, state: FSMContext):
    set_setting("external_api2_key", m.text.strip())
    await m.answer("✅ External API 2 API Key saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_ext2_master")
async def set_ext2_master(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "Enter External API 2 X-Master Key:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_ext2_master)

@dp.message(AdminStates.wait_for_ext2_master)
async def save_ext2_master(m: Message, state: FSMContext):
    set_setting("external_api2_master_key", m.text.strip())
    await m.answer("✅ External API 2 X-Master Key saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_ext_url")
async def set_ext_url(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "Enter External API URL:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_ext_url)

@dp.message(AdminStates.wait_for_ext_url)
async def save_ext_url(m: Message, state: FSMContext):
    value = m.text.strip()
    if not value.startswith(("http://", "https://")):
        return await m.answer("❌ URL must start with http:// or https://")
    set_setting("external_api_url", value)
    await m.answer("✅ External API URL saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_ext_key")
async def set_ext_key(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "Enter External API Key:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_ext_key)

@dp.message(AdminStates.wait_for_ext_key)
async def save_ext_key(m: Message, state: FSMContext):
    set_setting("external_api_key", m.text.strip())
    await m.answer("✅ External API Key saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_ext_master")
async def set_ext_master(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    try:
        await call.answer()
    except Exception:
        pass
    await safe_edit_text(call.message, "Enter External API Master Key:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_ext_master)

@dp.message(AdminStates.wait_for_ext_master)
async def save_ext_master(m: Message, state: FSMContext):
    set_setting("external_master_key", m.text.strip())
    await m.answer("✅ External API Master Key saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("System shutting down gracefully. Goodbye.")
