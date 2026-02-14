import json
import os
import random
import asyncio
from typing import Dict, List
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#       CONFIGURATION & DATA
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

DATA_FILE = "taboo_database.json"
WIN_IMAGE_URL = "https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/YOUR_REPO/main/win.jpg"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "lobbies": {}, 
            "used_words": [], 
            "profiles": {} # To store global wins/scores
        }
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Critcal Load Error: {e}")
        return {"lobbies": {}, "used_words": [], "profiles": {}}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Save Error: {e}")

# Global data object
db = load_data()

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#      STYLING ENGINE (HTML)
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

def ui_box(title: str, content: str) -> str:
    """Creates a professional styled box for Telegram"""
    return (
        f"<b>┏━━━━━━ {title.upper()} ━━━━━━┓</b>\n\n"
        f"{content}\n"
        f"<b>┗━━━━━━━━━━━━━━━━━━━━━━┛</b>"
    )

def update_profile_data(user):
    uid = str(user.id)
    name = user.first_name
    
    if uid not in db["profiles"]:
        db["profiles"][uid] = {
            "name": name,
            "wins": 0,
            "total_score": 0
        }
    else:
        # Naam update kar do agar player ne telegram par change kiya ho
        db["profiles"][uid]["name"] = name
    
    save_data(db)

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#    CORE DATA STRUCTURES
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

def create_empty_lobby(chat_id: int, host_id: int, host_name: str):
    return {
        "host": host_id,
        "host_name": host_name,
        "players": {}, # {user_id: {name, team, score, is_dummy}}
        "teams": {
            "BJP": [],
            "CONGRESS": []
        },
        "scores": {
            "BJP": 0,
            "CONGRESS": 0
        },
        "current_turn": None, # 'BJP' or 'CONGRESS'
        "current_explainer": None,
        "current_word": None,
        "banned_words": [],
        "game_started": False,
        "dummy_count": 0,
        "round_end_time": None
    }

# Word Pool with Banned words (Professional Format)
WORD_POOL = {
    "Democracy": ["Vote", "Freedom", "Country"],
    "Parliament": ["Building", "Delhi", "MP"],
    "Election": ["Booth", "Campaign", "Result"],
    "Constitution": ["Law", "Ambedkar", "Rights"],
    "Budget": ["Finance", "Money", "Taxes"],
    "Prime Minister": ["Modi", "Leader", "Head"],
    "Opposition": ["Rahul", "Congress", "Protest"]
}

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#      LOBBY MANAGEMENT
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def create_lobby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    cid = str(chat.id)

    if chat.type not in ["group", "supergroup"]:
        return await update.message.reply_html(ui_box("error", "❌ <b>This game is built for groups only!</b>"))

    if cid in db["lobbies"]:
        return await update.message.reply_html(ui_box("lobby", "⚠️ <b>Lobby already exists!</b>\nUse /players to see who's in."))

    # Create Lobby
    db["lobbies"][cid] = create_empty_lobby(chat.id, user.id, user.first_name)
    
    # Auto-add host to a team (Starting with BJP)
    uid = str(user.id)
    db["lobbies"][cid]["players"][uid] = {
        "name": user.first_name,
        "team": "BJP",
        "score": 0,
        "is_dummy": False
    }
    db["lobbies"][cid]["teams"]["BJP"].append(uid)
    save_data(db)

    msg = (
        f"👑 <b>Host:</b> {user.first_name}\n"
        f"🏁 <b>Status:</b> Waiting for players...\n\n"
        f"Players can join using /join\n"
        f"Host can add bots using /adddummy"
    )
    await update.message.reply_html(ui_box("taboo politics", msg))

async def join_lobby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user = update.effective_user
    uid = str(user.id)
    update_profile_data(user)

    if chat_id not in db["lobbies"]:
        return await update.message.reply_html("❌ No active lobby. Use /createlobby")

    lobby = db["lobbies"][chat_id]

    if lobby["game_started"]:
        return await update.message.reply_html("🚫 <b>Match in progress!</b> Wait for the next one.")

    if uid in lobby["players"]:
        return await update.message.reply_html("⚠️ <b>You are already in the team!</b>")

    # ⚖️ Auto-Balance Logic
    bjp_count = len(lobby["teams"]["BJP"])
    cong_count = len(lobby["teams"]["CONGRESS"])
    
    team = "CONGRESS" if cong_count < bjp_count else "BJP"
    emoji = "🔵" if team == "CONGRESS" else "🟠"

    lobby["players"][uid] = {
        "name": user.first_name,
        "team": team,
        "score": 0,
        "is_dummy": False
    }
    lobby["teams"][team].append(uid)
    save_data(db)

    await update.message.reply_html(ui_box("new player", f"👤 <b>{user.first_name}</b> joined {emoji} <b>{team}</b>"))

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#      DUMMY PLAYER SYSTEM
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def add_dummy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user = update.effective_user

    if chat_id not in db["lobbies"]: return
    lobby = db["lobbies"][chat_id]

    if user.id != lobby["host"]:
        return await update.message.reply_html("🚫 <b>Only the Host can add dummies!</b>")

    if lobby["game_started"]:
        return await update.message.reply_html("🚫 Cannot add dummies during the match.")

    # Balance dummies
    team = "CONGRESS" if len(lobby["teams"]["CONGRESS"]) < len(lobby["teams"]["BJP"]) else "BJP"
    emoji = "🔵" if team == "CONGRESS" else "🟠"
    
    lobby["dummy_count"] += 1
    d_id = f"dummy_{lobby['dummy_count']}"
    d_name = f"Bot-Netra_{lobby['dummy_count']}"

    lobby["players"][d_id] = {
        "name": d_name,
        "team": team,
        "score": 0,
        "is_dummy": True
    }
    lobby["teams"][team].append(d_id)
    save_data(db)

    await update.message.reply_html(ui_box("dummy added", f"🤖 <b>{d_name}</b> deployed to {emoji} <b>{team}</b>"))

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#      WORD GENERATOR ENGINE
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

def generate_secret_word(chat_id: str):
    lobby = db["lobbies"][chat_id]
    
    # Filter out words already used in THIS specific lobby session
    available_words = [w for w in WORD_POOL.keys() if w not in lobby.get("used_in_lobby", [])]
    
    # If all words used, reset the session list
    if not available_words:
        lobby["used_in_lobby"] = []
        available_words = list(WORD_POOL.keys())

    word = random.choice(available_words)
    banned = WORD_POOL[word]
    
    lobby.setdefault("used_in_lobby", []).append(word)
    return word, banned

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#       START GAME COMMAND
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user = update.effective_user

    if chat_id not in db["lobbies"]: return
    lobby = db["lobbies"][chat_id]

    # Host Check
    if user.id != lobby["host"]:
        return await update.message.reply_html("🚫 <b>Only the Host can fire the starting gun!</b>")

    if lobby["game_started"]:
        return await update.message.reply_html("⚠️ Game is already running!")

    # Minimum Player Check (1 in each team)
    if not lobby["teams"]["BJP"] or not lobby["teams"]["CONGRESS"]:
        return await update.message.reply_html(ui_box("error", "❌ <b>Need at least 1 player in each team to start!</b>\nUse /adddummy if you're alone."))

    lobby["game_started"] = True
    
    # Randomly pick starting team
    starting_team = random.choice(["BJP", "CONGRESS"])
    lobby["current_turn"] = starting_team
    
    await trigger_new_round(chat_id, context)

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#       ROUND TRIGGER SYSTEM
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def trigger_new_round(chat_id: str, context: ContextTypes.DEFAULT_TYPE):
    lobby = db["lobbies"][chat_id]
    team = lobby["current_turn"]
    emoji = "🟠" if team == "BJP" else "🔵"

    # 🗣️ Select Explainer (Prefer real players over dummies)
    team_players = lobby["teams"][team]
    real_players = [uid for uid in team_players if not lobby["players"][uid]["is_dummy"]]
    
    # If real players exist, pick one. Otherwise, game can't proceed (bots can't explain!)
    if not real_players:
        await context.bot.send_message(chat_id, ui_box("error", f"❌ No real players in {team} to explain! Ending game."))
        del db["lobbies"][chat_id]
        save_data(db)
        return

    explainer_id = random.choice(real_players)
    lobby["current_explainer"] = explainer_id
    
    # 🎯 Generate Word
    word, banned = generate_secret_word(chat_id)
    lobby["current_word"] = word
    lobby["banned_words"] = banned
    save_data(db)

    # 🔇 Restrict Explainer in Group
    try:
        await context.bot.restrict_chat_member(
            chat_id=int(chat_id),
            user_id=int(explainer_id),
            permissions=ChatPermissions(can_send_messages=False)
        )
    except Exception as e:
        print(f"Mute Error: {e}")

    # 📥 Send Word to DM
    try:
        banned_text = "\n• ".join(banned)
        msg = (
            f"🎯 <b>YOUR SECRET WORD:</b> <code>{word.upper()}</code>\n\n"
            f"🚫 <b>BANNED WORDS (Don't use these!):</b>\n"
            f"• {banned_text}\n\n"
            f"<i>Explain this to your team in the group! You are currently muted in the group to prevent accidental leaks.</i>"
        )
        await context.bot.send_message(chat_id=int(explainer_id), text=ui_box("secret mission", msg), parse_mode="HTML")
    except:
        await context.bot.send_message(chat_id, "❌ <b>CRITICAL:</b> Explainer must start the bot in DM to receive the word!")
        # Unmute if DM fails
        await context.bot.restrict_chat_member(chat_id=int(chat_id), user_id=int(explainer_id), permissions=ChatPermissions(can_send_messages=True))
        return

    # 📢 Announce in Group
    announcement = (
        f"🚀 <b>ROUND STARTED!</b>\n\n"
        f"Turn: {emoji} <b>{team}</b>\n"
        f"Explainer: <b>{lobby['players'][explainer_id]['name']}</b>\n\n"
        f"Team members, start guessing! You have 60 seconds."
    )
    await context.bot.send_message(chat_id, ui_box("taboo live", announcement), parse_mode="HTML")
    
    # Start Timer (Part 4 mein handles hoga)
    # Part 3/4 ke trigger_new_round mein ye update kar lo:
    timer_seconds = lobby.get("timer_limit", 60) # Default 60 if not set
    asyncio.create_task(start_turn_timer(chat_id, context, timer_seconds))

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#      MESSAGE HANDLER ENGINE
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def game_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.message
    
    if not message or not message.text: return
    chat_id = str(chat.id)

    if chat_id not in db["lobbies"]: return
    lobby = db["lobbies"][chat_id]

    if not lobby["game_started"]: return

    uid = str(user.id)
    text = message.text.lower().strip()
    
    # Activity track karne ke liye (Inactivity system ke liye)
    lobby["last_activity"] = asyncio.get_event_loop().time()

    current_word = lobby["current_word"].lower()
    banned_words = [w.lower() for w in lobby["banned_words"]]
    explainer_id = str(lobby["current_explainer"])
    current_team = lobby["current_turn"]

    # 1. 🚫 ANTI-CHEAT SYSTEM (Explainer Check)
    if uid == explainer_id:
        # Check if they leaked the word or used banned words
        is_cheating = False
        if current_word in text: 
            is_cheating = True
        elif any(bw in text for bw in banned_words):
            is_cheating = True
            
        if is_cheating:
            try:
                await message.delete() # 🗑️ Cheat message turant delete!
            except Exception as e:
                print(f"Delete Error: {e}") # Bot admin hona chahiye group mein

            await context.bot.send_message(
                chat_id=int(chat_id),
                text=ui_box("cheat alert", f"❌ <b>CHEATING DETECTED!</b>\n\nExplainer <b>{user.first_name}</b> ne secret ya banned word likha.\n\nPoint cancelled! Turn switching..."),
                parse_mode="HTML"
            )
            # Switch turn as penalty
            await end_round(chat_id, context, penalty=True)
            return
        return # Explainer ka normal message (agar mute na ho) ignore karein

    # 2. ✅ CORRECT GUESS LOGIC
    if text == current_word:
        # Check if the person guessing is in the current team
        if lobby["players"].get(uid, {}).get("team") != current_team:
            return # Opposite team guessing doesn't count

        # Award points
        lobby["scores"][current_team] += 1
        lobby["players"][uid]["score"] += 1
        
        # Update Global Profile
        if uid not in db["profiles"]: 
            db["profiles"][uid] = {"name": user.first_name, "wins": 0, "total_score": 0}
        
        db["profiles"][uid]["total_score"] += 1
        save_data(db)

        await message.reply_html(f"🎯 <b>CORRECT GUESS!</b>\n👤 {user.first_name} earned +1 for {current_team}.")
        
        # 🎉 Win Check (10 Points to Win)
        if lobby["scores"][current_team] >= 10:
            await announce_winner(chat_id, current_team, context)
        else:
            await end_round(chat_id, context)

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#       ROUND END & CLEANUP
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def end_round(chat_id, context, penalty=False):
    lobby = db["lobbies"][chat_id]
    
    # Unmute the explainer
    try:
        await context.bot.restrict_chat_member(
            chat_id=int(chat_id),
            user_id=int(lobby["current_explainer"]),
            permissions=ChatPermissions(can_send_messages=True)
        )
    except: pass

    # Switch Turn
    lobby["current_turn"] = "CONGRESS" if lobby["current_turn"] == "BJP" else "BJP"
    save_data(db)

    if not penalty:
        await trigger_new_round(chat_id, context)

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#       TURN TIMER SYSTEM
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def start_turn_timer(chat_id, context):
    lobby = db["lobbies"][chat_id]
    word_at_start = lobby["current_word"]
    
    await asyncio.sleep(60) # 1 Minute Turn

    # Check if the round is still active with the SAME word
    if chat_id in db["lobbies"] and db["lobbies"][chat_id]["current_word"] == word_at_start:
        await context.bot.send_message(chat_id, ui_box("time up", "⏰ <b>Time's over!</b>\nNo one guessed it. Switching turns..."))
        await end_round(chat_id, context)

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#       WINNER ANNOUNCEMENT
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def announce_winner(chat_id, team, context):
    lobby = db["lobbies"][chat_id]
    emoji = "🟠" if team == "BJP" else "🔵"
    
    # Update global wins for the whole team
    for uid in lobby["teams"][team]:
        if not uid.startswith("dummy"):
            if uid not in db["profiles"]: db["profiles"][uid] = {"wins": 0, "total_score": 0}
            db["profiles"][uid]["wins"] += 1
    
    msg = (
        f"🏆 <b>VICTORY FOR {team}!</b> {emoji}\n\n"
        f"Final Scores:\n"
        f"🟠 BJP: {lobby['scores']['BJP']}\n"
        f"🔵 CONGRESS: {lobby['scores']['CONGRESS']}\n\n"
        f"The lobby is now closed. Use /createlobby for a rematch!"
    )
    
    await context.bot.send_photo(chat_id, photo=WIN_IMAGE_URL, caption=ui_box("match over", msg), parse_mode="HTML")
    
    # Cleanup: Unmute last explainer and delete lobby
    try:
        await context.bot.restrict_chat_member(chat_id=int(chat_id), user_id=int(lobby["current_explainer"]), permissions=ChatPermissions(can_send_messages=True))
    except: pass
    
    del db["lobbies"][chat_id]
    save_data(db)

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#      UTILITY COMMANDS
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    update_profile_data(user)
    
    # Check if profile exists
    if uid not in db["profiles"]:
        db["profiles"][uid] = {"wins": 0, "total_score": 0}
        save_data(db)
        
    p = db["profiles"][uid]
    
    stats = (
        f"👤 <b>Player:</b> {user.first_name}\n\n"
        f"🏆 <b>Total Wins:</b> {p['wins']}\n"
        f"⭐ <b>Lifetime Points:</b> {p['total_score']}\n"
        f"🏅 <b>Rank:</b> {'Senior Politician' if p['wins'] > 5 else 'New Candidate'}"
    )
    await update.message.reply_html(ui_box("player profile", stats))

async def players_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id not in db["lobbies"]:
        return await update.message.reply_html("❌ No active lobby.")

    lobby = db["lobbies"][chat_id]
    
    def get_team_list(team_name):
        players = []
        for uid in lobby["teams"][team_name]:
            p = lobby["players"][uid]
            mark = "👑" if int(uid) == lobby["host"] else ("🤖" if p["is_dummy"] else "👤")
            players.append(f"• {mark} {p['name']} ({p['score']} pts)")
        return "\n".join(players) if players else "• No players"

    msg = (
        f"🟠 <b>BJP TEAM</b>\n{get_team_list('BJP')}\n\n"
        f"🔵 <b>CONGRESS TEAM</b>\n{get_team_list('CONGRESS')}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"📊 <b>Score:</b> BJP {lobby['scores']['BJP']} - {lobby['scores']['CONGRESS']} CONG"
    )
    await update.message.reply_html(ui_box("lobby status", msg))

async def skip_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user = update.effective_user
    
    if chat_id not in db["lobbies"]: return
    lobby = db["lobbies"][chat_id]

    if not lobby["game_started"]: return

    # Only host or current explainer can skip
    if user.id == lobby["host"] or str(user.id) == lobby["current_explainer"]:
        await update.message.reply_html("⏭ <b>Word Skipped!</b> Switching turns...")
        await end_round(chat_id, context, penalty=False)
    else:
        await update.message.reply_html("🚫 Only the Host or Explainer can skip.")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db["profiles"]:
        return await update.message.reply_html(ui_box("stats", "📊 No player records found yet!"))

    # Sorting players by Wins (Primary) and Total Score (Secondary)
    sorted_players = sorted(
        db["profiles"].items(), 
        key=lambda item: (item[1]['wins'], item[1]['total_score']), 
        reverse=True
    )[:10]

    board_text = "🏆 <b>TOP 10 POLITICIANS</b>\n\n"
    
    for i, (uid, stats) in enumerate(sorted_players, 1):
        # Medals for Top 3
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"<b>{i}.</b>"
        
        name = stats.get("name", "Unknown Player")
        wins = stats.get("wins", 0)
        points = stats.get("total_score", 0)
        
        board_text += f"{medal} {name}\n   └ Wins: <b>{wins}</b> | Score: <b>{points}</b>\n\n"

    board_text += "Keep winning to rule the board! 🚩"
    await update.message.reply_html(ui_box("global leaderboard", board_text))

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ⚠️ APNI ID YAHAN DAALEIN (Check @MissRose_bot /id in Telegram)
    OWNER_ID =  5841500098 # <-- Replace this with your ID
    
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return await update.message.reply_text("🚫 <b>Access Denied!</b>\nSirf mere Developer hi announcement kar sakte hain.")

    if not context.args:
        return await update.message.reply_html("📝 <b>Format:</b> /broadcast [Apka Message]")

    broadcast_msg = " ".join(context.args)
    
    # Saari active lobbies ki list
    all_chats = list(db["lobbies"].keys())
    success = 0
    failed = 0

    sent_msg = await update.message.reply_text("📣 Broadcasting started...")

    for cid in all_chats:
        try:
            await context.bot.send_message(
                chat_id=int(cid),
                text=ui_box("📢 announcement", broadcast_msg),
                parse_mode="HTML"
            )
            success += 1
            await asyncio.sleep(0.1) # Flood wait se bachne ke liye
        except:
            failed += 1

    await sent_msg.edit_text(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"🟢 Success: {success}\n"
        f"🔴 Failed: {failed}",
        parse_mode="HTML"
    )

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#      TEAM CHANGE COMMAND
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def change_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user = update.effective_user
    uid = str(user.id)

    if chat_id not in db["lobbies"]:
        return await update.message.reply_text("❌ No active lobby found!")

    lobby = db["lobbies"][chat_id]

    if lobby["game_started"]:
        return await update.message.reply_html("🚫 <b>Match in progress!</b> You can't switch sides now.")

    if uid not in lobby["players"]:
        return await update.message.reply_text("⚠️ You must /join first!")

    # Current team identify karo
    old_team = lobby["players"][uid]["team"]
    new_team = "CONGRESS" if old_team == "BJP" else "BJP"
    emoji = "🔵" if new_team == "CONGRESS" else "🟠"

    # Swap logic
    lobby["teams"][old_team].remove(uid)
    lobby["teams"][new_team].append(uid)
    lobby["players"][uid]["team"] = new_team
    
    save_data(db)

    await update.message.reply_html(
        ui_box("team switch", f"🔄 <b>{user.first_name}</b> shifted to {emoji} <b>{new_team}</b>!")
    )

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#      SHUFFLE TEAMS (HOST ONLY)
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def shuffle_teams(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user = update.effective_user

    if chat_id not in db["lobbies"]: return
    lobby = db["lobbies"][chat_id]

    if user.id != lobby["host"]:
        return await update.message.reply_html("🚫 <b>Only the Host can shuffle teams!</b>")

    if lobby["game_started"]:
        return await update.message.reply_html("🚫 Cannot shuffle during a live match.")

    # Saare players (Dummies + Real) ko ek list mein daalo
    all_players = list(lobby["players"].keys())
    random.shuffle(all_players)

    # Teams reset karo
    lobby["teams"]["BJP"] = []
    lobby["teams"]["CONGRESS"] = []

    # Aadhe idhar, aadhe udhar
    for i, uid in enumerate(all_players):
        team = "BJP" if i % 2 == 0 else "CONGRESS"
        lobby["teams"][team].append(uid)
        lobby["players"][uid]["team"] = team

    save_data(db)

    msg = "🎲 <b>Teams have been shuffled randomly!</b>\n\nUse /players to see your new squads."
    await update.message.reply_html(ui_box("shuffled", msg))

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#      DYNAMIC TIMER SETTING
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user = update.effective_user
    
    if chat_id not in db["lobbies"]: return
    lobby = db["lobbies"][chat_id]

    if user.id != lobby["host"]:
        return await update.message.reply_html(ui_box("error", "🚫 <b>Only Host can change the timer!</b>"))

    try:
        # Command: /timer 45
        new_time = int(context.args[0])
        if 20 <= new_time <= 180:
            lobby["timer_limit"] = new_time
            save_data(db)
            await update.message.reply_html(ui_box("timer updated", f"⏱ <b>New Round Limit:</b> {new_time} seconds"))
        else:
            await update.message.reply_text("⚠️ Keep timer between 20 and 180 seconds.")
    except (IndexError, ValueError):
        await update.message.reply_text("📝 Format: /timer [seconds]")

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#    2. AUTO-INACTIVITY CLEANER
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
# Ise main() function ke start mein ek baar call karna hai

async def inactivity_checker(context: ContextTypes.DEFAULT_TYPE):
    """Background task jo har 5 min mein check karega ki koi game stalled toh nahi hai"""
    while True:
        await asyncio.sleep(300) # Har 5 minute mein checking
        current_time = asyncio.get_event_loop().time()
        
        # Ek list banao un lobbies ki jinhe delete karna hai
        to_delete = []
        
        for cid, lobby in db["lobbies"].items():
            last_act = lobby.get("last_activity", current_time)
            # Agar 20 min se koi activity nahi hui (No messages, no guesses)
            if current_time - last_act > 1200: 
                to_delete.append(cid)
        
        for cid in to_delete:
            try:
                # Unmute explainer if stuck
                exp_id = db["lobbies"][cid].get("current_explainer")
                if exp_id:
                    await context.bot.restrict_chat_member(int(cid), int(exp_id), permissions=ChatPermissions(can_send_messages=True))
                
                await context.bot.send_message(int(cid), ui_box("auto-cleanup", "💤 <b>Game Terminated!</b>\nMatch ended due to 20 minutes of inactivity."))
                del db["lobbies"][cid]
            except: pass
        
        if to_delete:
            save_data(db)

async def end_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id not in db["lobbies"]: return
    
    lobby = db["lobbies"][chat_id]
    if update.effective_user.id != lobby["host"]:
        return await update.message.reply_html("🚫 Only the Host can end the match.")

    # Unmute explainer if any
    if lobby["current_explainer"]:
        try:
            await context.bot.restrict_chat_member(int(chat_id), int(lobby["current_explainer"]), permissions=ChatPermissions(can_send_messages=True))
        except: pass

    del db["lobbies"][chat_id]
    save_data(db)
    await update.message.reply_html(ui_box("game ended", "🛑 The host has terminated the game.\nLobby cleared."))

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
#     MAIN BOT RUNNER
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

def main():
    # Replace with your actual Token
    TOKEN = "8518352198:AAGWMCHk4_2XDsvioGSohLybN3FrI7azFPQ"
    
    app = ApplicationBuilder().token(TOKEN).build()

    # Commands
    job_queue = app.job_queue
    job_queue.run_repeating(inactivity_checker, interval=300, first=10)
    app.add_handler(CommandHandler("createlobby", create_lobby))
    app.add_handler(CommandHandler("join", join_lobby))
    app.add_handler(CommandHandler("adddummy", add_dummy))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("players", players_list))
    app.add_handler(CommandHandler("skip", skip_word))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("timer", set_timer))
    app.add_handler(CommandHandler("changeteam", change_team))
    app.add_handler(CommandHandler("shuffle", shuffle_teams))
    app.add_handler(CommandHandler("endgame", end_game))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # Message Handler for game guesses
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, game_message_handler))

    print("--- Taboo Politics Bot Started ---")
    app.run_polling()

if __name__ == "__main__":
    main()
