import json
import os
import random
import asyncio
from typing import Dict, List
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# CONFIGURATION
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

DATA_FILE = "taboo_data.json"
WIN_IMAGE_URL = "https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/YOUR_REPO/main/win.jpg"

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# DATA STORAGE SYSTEM (Persistent)
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

def load_data():
    try:
        if not os.path.exists(DATA_FILE):
            return {
                "lobbies": {},
                "used_words": []
            }
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("Load Error:", e)
        return {
            "lobbies": {},
            "used_words": []
        }

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print("Save Error:", e)

data = load_data()

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# HTML BOX DESIGN (Exact As You Said)
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

def box(text: str) -> str:
    return (
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        f"{text}\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛"
    )

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# BASIC GAME STRUCTURE TEMPLATE
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

def create_empty_lobby(chat_id: int, host_id: int, host_name: str):
    return {
        "host": host_id,
        "host_name": host_name,
        "players": {},
        "teams": {
            "BJP": [],
            "CONGRESS": []
        },
        "scores": {
            "BJP": 0,
            "CONGRESS": 0
        },
        "current_turn": None,
        "current_word": None,
        "banned_words": [],
        "game_started": False,
        "used_in_lobby": [],
        "dummy_count": 0
    }

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# CREATE LOBBY COMMAND
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def create_lobby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat = update.effective_chat
        user = update.effective_user

        # ❌ Private chat block
        if chat.type not in ["group", "supergroup"]:
            await update.message.reply_html(
                box("❌ <b>This command works only in groups.</b>")
            )
            return

        chat_id = str(chat.id)

        # ❌ Lobby already exists
        if chat_id in data["lobbies"]:
            await update.message.reply_html(
                box("⚠️ <b>Lobby already exists in this group!</b>\n\nUse /players to check.")
            )
            return

        # ✅ Create new lobby
        lobby = create_empty_lobby(
            chat_id=chat.id,
            host_id=user.id,
            host_name=user.first_name
        )

        # Add host automatically
        lobby["players"][str(user.id)] = {
            "name": user.first_name,
            "team": None,
            "score": 0,
            "is_dummy": False
        }

        data["lobbies"][chat_id] = lobby
        save_data(data)

        msg = box(
            "🎯 <b>TABOO POLITICS LOBBY CREATED</b>\n\n"
            f"👑 Host: {user.first_name}\n\n"
            "🟠 BJP vs 🔵 CONGRESS\n\n"
            "Players can now join using /join"
        )

        await update.message.reply_html(msg)

    except Exception as e:
        print("Create Lobby Error:", e)
        try:
            await update.message.reply_html(
                box("❌ <b>Unexpected error occurred while creating lobby.</b>")
            )
        except:
            pass

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# JOIN LOBBY COMMAND
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def join_lobby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat = update.effective_chat
        user = update.effective_user
        chat_id = str(chat.id)

        # ❌ Only group
        if chat.type not in ["group", "supergroup"]:
            await update.message.reply_html(
                box("❌ <b>You can only join from a group lobby.</b>")
            )
            return

        # ❌ Lobby not created
        if chat_id not in data["lobbies"]:
            await update.message.reply_html(
                box("⚠️ <b>No lobby found in this group.</b>\n\nHost must use /create_lobby first.")
            )
            return

        lobby = data["lobbies"][chat_id]

        # ❌ Game already started
        if lobby["game_started"]:
            await update.message.reply_html(
                box("🚫 <b>Game already started!</b>\nYou cannot join now.")
            )
            return

        # ❌ Already joined
        if str(user.id) in lobby["players"]:
            await update.message.reply_html(
                box("⚠️ <b>You are already in the lobby.</b>")
            )
            return

        # ✅ Auto Team Balance
        bjp_count = len(lobby["teams"]["BJP"])
        congress_count = len(lobby["teams"]["CONGRESS"])

        if bjp_count <= congress_count:
            team = "BJP"
            emoji = "🟠"
        else:
            team = "CONGRESS"
            emoji = "🔵"

        # Add player
        lobby["players"][str(user.id)] = {
            "name": user.first_name,
            "team": team,
            "score": 0,
            "is_dummy": False
        }

        lobby["teams"][team].append(str(user.id))

        save_data(data)

        msg = box(
            "✅ <b>PLAYER JOINED</b>\n\n"
            f"👤 {user.first_name}\n"
            f"Team: {emoji} <b>{team}</b>\n\n"
            "Use /players to view lobby"
        )

        await update.message.reply_html(msg)

    except Exception as e:
        print("Join Lobby Error:", e)
        try:
            await update.message.reply_html(
                box("❌ <b>Unexpected error occurred while joining.</b>")
            )
        except:
            pass

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# PLAYERS COMMAND
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def players_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat = update.effective_chat
        chat_id = str(chat.id)

        # ❌ Only group
        if chat.type not in ["group", "supergroup"]:
            await update.message.reply_html(
                box("❌ <b>This command works only in group lobby.</b>")
            )
            return

        # ❌ Lobby check
        if chat_id not in data["lobbies"]:
            await update.message.reply_html(
                box("⚠️ <b>No active lobby in this group.</b>")
            )
            return

        lobby = data["lobbies"][chat_id]

        if not lobby["players"]:
            await update.message.reply_html(
                box("⚠️ <b>No players in lobby.</b>")
            )
            return

        message = "👥 <b>LOBBY PLAYERS</b>\n\n"

        # 🟠 BJP Team
        message += "🟠 <b>BJP Team</b>\n"
        if lobby["teams"]["BJP"]:
            for uid in lobby["teams"]["BJP"]:
                player = lobby["players"][uid]
                name = player["name"]
                score = player["score"]

                host_mark = " 👑" if int(uid) == lobby["host"] else ""
                dummy_mark = " 🤖" if player["is_dummy"] else ""

                message += f"• {name}{host_mark}{dummy_mark} — {score} pts\n"
        else:
            message += "• No players\n"

        message += "\n"

        # 🔵 Congress Team
        message += "🔵 <b>CONGRESS Team</b>\n"
        if lobby["teams"]["CONGRESS"]:
            for uid in lobby["teams"]["CONGRESS"]:
                player = lobby["players"][uid]
                name = player["name"]
                score = player["score"]

                host_mark = " 👑" if int(uid) == lobby["host"] else ""
                dummy_mark = " 🤖" if player["is_dummy"] else ""

                message += f"• {name}{host_mark}{dummy_mark} — {score} pts\n"
        else:
            message += "• No players\n"

        message += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"🏆 BJP Score: {lobby['scores']['BJP']}\n"
        message += f"🏆 CONGRESS Score: {lobby['scores']['CONGRESS']}"

        await update.message.reply_html(box(message))

    except Exception as e:
        print("Players List Error:", e)
        try:
            await update.message.reply_html(
                box("❌ <b>Error fetching player list.</b>")
            )
        except:
            pass

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# ADD DUMMY COMMAND (HOST ONLY)
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def add_dummy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat = update.effective_chat
        user = update.effective_user
        chat_id = str(chat.id)

        # ❌ Only group
        if chat.type not in ["group", "supergroup"]:
            await update.message.reply_html(
                box("❌ <b>This command works only in group.</b>")
            )
            return

        # ❌ Lobby check
        if chat_id not in data["lobbies"]:
            await update.message.reply_html(
                box("⚠️ <b>No active lobby found.</b>")
            )
            return

        lobby = data["lobbies"][chat_id]

        # ❌ Only host
        if user.id != lobby["host"]:
            await update.message.reply_html(
                box("🚫 <b>Only lobby host can add dummy players.</b>")
            )
            return

        # ❌ Game started
        if lobby["game_started"]:
            await update.message.reply_html(
                box("🚫 <b>Cannot add dummy after game started.</b>")
            )
            return

        # Auto team balance
        bjp_count = len(lobby["teams"]["BJP"])
        congress_count = len(lobby["teams"]["CONGRESS"])

        if bjp_count <= congress_count:
            team = "BJP"
            emoji = "🟠"
        else:
            team = "CONGRESS"
            emoji = "🔵"

        # Create dummy
        lobby["dummy_count"] += 1
        dummy_id = f"dummy_{lobby['dummy_count']}"
        dummy_name = f"Dummy{lobby['dummy_count']}"

        lobby["players"][dummy_id] = {
            "name": dummy_name,
            "team": team,
            "score": 0,
            "is_dummy": True
        }

        lobby["teams"][team].append(dummy_id)

        save_data(data)

        msg = box(
            "🤖 <b>DUMMY PLAYER ADDED</b>\n\n"
            f"Name: {dummy_name}\n"
            f"Team: {emoji} <b>{team}</b>\n\n"
            "Use /players to check lobby"
        )

        await update.message.reply_html(msg)

    except Exception as e:
        print("Add Dummy Error:", e)
        try:
            await update.message.reply_html(
                box("❌ <b>Error while adding dummy player.</b>")
            )
        except:
            pass

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# WORD GENERATOR (Repeat Free)
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

WORD_POOL = [
    "democracy", "parliament", "election", "constitution",
    "minister", "budget", "development", "leader",
    "economy", "freedom", "policy", "vote",
    "campaign", "government", "law", "nation"
]

def generate_word():
    available_words = list(set(WORD_POOL) - set(data["used_words"]))
    if not available_words:
        data["used_words"] = []
        save_data(data)
        available_words = WORD_POOL.copy()

    word = random.choice(available_words)
    data["used_words"].append(word)
    save_data(data)

    # simple banned generator (related random words)
    banned = random.sample(
        [w for w in WORD_POOL if w != word],
        min(3, len(WORD_POOL)-1)
    )

    return word, banned


# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# START GAME COMMAND
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat = update.effective_chat
        chat_id = str(chat.id)

        if chat.type not in ["group", "supergroup"]:
            await update.message.reply_html(
                box("❌ <b>This command works only in group.</b>")
            )
            return

        if chat_id not in data["lobbies"]:
            await update.message.reply_html(
                box("⚠️ <b>No lobby found.</b>")
            )
            return

        lobby = data["lobbies"][chat_id]

        if lobby["game_started"]:
            await update.message.reply_html(
                box("⚠️ <b>Game already started.</b>")
            )
            return

        if len(lobby["teams"]["BJP"]) < 1 or len(lobby["teams"]["CONGRESS"]) < 1:
            await update.message.reply_html(
                box("🚫 <b>Need at least 1 player in each team.</b>")
            )
            return

        lobby["game_started"] = True

        # Random team turn
        team = random.choice(["BJP", "CONGRESS"])
        lobby["current_turn"] = team

        # Select explainer (prefer real player)
        team_players = lobby["teams"][team]
        real_players = [
            uid for uid in team_players
            if not lobby["players"][uid]["is_dummy"]
        ]

        if real_players:
            explainer_id = random.choice(real_players)
        else:
            explainer_id = random.choice(team_players)

        lobby["current_explainer"] = explainer_id

        # Generate word
        word, banned = generate_word()
        lobby["current_word"] = word
        lobby["banned_words"] = banned

        save_data(data)

        # Restrict explainer from chatting
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=int(explainer_id),
                permissions=ChatPermissions(
                    can_send_messages=False
                )
            )
        except:
            pass  # if dummy or bot lacks rights

        # Send word in DM
        try:
            await context.bot.send_message(
                chat_id=int(explainer_id),
                text=box(
                    f"🎯 <b>YOUR SECRET WORD</b>\n\n"
                    f"Main Word: <b>{word}</b>\n\n"
                    f"🚫 Banned Words:\n"
                    f"• {banned[0]}\n"
                    f"• {banned[1]}\n"
                    f"• {banned[2]}"
                ),
                parse_mode="HTML"
            )
        except:
            pass

        emoji = "🟠" if team == "BJP" else "🔵"

        await update.message.reply_html(
            box(
                "🚀 <b>GAME STARTED</b>\n\n"
                f"Turn: {emoji} <b>{team}</b>\n\n"
                "Explainer has received the secret word in DM.\n"
                "Team members start guessing!"
            )
        )

    except Exception as e:
        print("Start Game Error:", e)
        try:
            await update.message.reply_html(
                box("❌ <b>Error while starting game.</b>")
            )
        except:
            pass

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# MESSAGE HANDLER (GAME ENGINE)
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def game_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message
        chat = update.effective_chat
        user = update.effective_user

        if chat.type not in ["group", "supergroup"]:
            return

        chat_id = str(chat.id)

        if chat_id not in data["lobbies"]:
            return

        lobby = data["lobbies"][chat_id]

        if not lobby["game_started"]:
            return

        # ❌ Media Block
        if message.photo or message.video or message.animation or message.sticker or message.document:
            await message.delete()
            return

        # ❌ Link Block
        if message.text and ("http://" in message.text or "https://" in message.text or "t.me" in message.text):
            await message.delete()
            return

        # Ignore non-text
        if not message.text:
            return

        text = message.text.lower().strip()
        current_word = lobby["current_word"].lower()
        current_team = lobby["current_turn"]
        explainer_id = lobby.get("current_explainer")

        # Ignore explainer guess
        if str(user.id) == str(explainer_id):
            return

        # ✅ Correct Guess
        if text == current_word:

            lobby["scores"][current_team] += 1

            # Unmute old explainer
            try:
                await context.bot.restrict_chat_member(
                    chat_id=chat.id,
                    user_id=int(explainer_id),
                    permissions=ChatPermissions(
                        can_send_messages=True
                    )
                )
            except:
                pass

            # 🎉 Win Check
            if lobby["scores"][current_team] >= 5:
                winner_emoji = "🟠" if current_team == "BJP" else "🔵"

                await message.reply_photo(
                    photo=WIN_IMAGE_URL,
                    caption=box(
                        f"🏆 <b>{winner_emoji} {current_team} WINS THE GAME!</b>\n\n"
                        "Congratulations 🎉"
                    ),
                    parse_mode="HTML"
                )

                lobby["game_started"] = False
                save_data(data)
                return

            # 🔁 Switch Turn
            next_team = "CONGRESS" if current_team == "BJP" else "BJP"
            lobby["current_turn"] = next_team

            team_players = lobby["teams"][next_team]

            real_players = [
                uid for uid in team_players
                if not lobby["players"][uid]["is_dummy"]
            ]

            if real_players:
                new_explainer = random.choice(real_players)
            else:
                new_explainer = random.choice(team_players)

            lobby["current_explainer"] = new_explainer

            # Generate new word
            word, banned = generate_word()
            lobby["current_word"] = word
            lobby["banned_words"] = banned

            save_data(data)

            # Restrict new explainer
            try:
                await context.bot.restrict_chat_member(
                    chat_id=chat.id,
                    user_id=int(new_explainer),
                    permissions=ChatPermissions(
                        can_send_messages=False
                    )
                )
            except:
                pass

            # Send new word DM
            try:
                await context.bot.send_message(
                    chat_id=int(new_explainer),
                    text=box(
                        f"🎯 <b>YOUR SECRET WORD</b>\n\n"
                        f"Main Word: <b>{word}</b>\n\n"
                        f"🚫 Banned Words:\n"
                        f"• {banned[0]}\n"
                        f"• {banned[1]}\n"
                        f"• {banned[2]}"
                    ),
                    parse_mode="HTML"
                )
            except:
                pass

            emoji = "🟠" if next_team == "BJP" else "🔵"

            await message.reply_html(
                box(
                    "✅ <b>CORRECT GUESS!</b>\n\n"
                    f"Next Turn: {emoji} <b>{next_team}</b>\n\n"
                    "New explainer received word in DM."
                )
            )

    except Exception as e:
        print("Game Engine Error:", e)

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# SKIP COMMAND
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def skip_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat = update.effective_chat
        user = update.effective_user
        chat_id = str(chat.id)

        if chat.type not in ["group", "supergroup"]:
            return

        if chat_id not in data["lobbies"]:
            return

        lobby = data["lobbies"][chat_id]

        if not lobby["game_started"]:
            await update.message.reply_html(
                box("⚠️ <b>Game not started.</b>")
            )
            return

        current_team = lobby["current_turn"]

        # ❌ Only current team member can skip
        if str(user.id) not in lobby["teams"][current_team]:
            await update.message.reply_html(
                box("🚫 <b>Only current team can skip.</b>")
            )
            return

        old_explainer = lobby["current_explainer"]

        # Unmute old explainer
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=int(old_explainer),
                permissions=ChatPermissions(
                    can_send_messages=True
                )
            )
        except:
            pass

        # Select new explainer
        team_players = lobby["teams"][current_team]
        real_players = [
            uid for uid in team_players
            if not lobby["players"][uid]["is_dummy"]
        ]

        if real_players:
            new_explainer = random.choice(real_players)
        else:
            new_explainer = random.choice(team_players)

        lobby["current_explainer"] = new_explainer

        # Generate new word
        word, banned = generate_word()
        lobby["current_word"] = word
        lobby["banned_words"] = banned

        save_data(data)

        # Restrict new explainer
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=int(new_explainer),
                permissions=ChatPermissions(
                    can_send_messages=False
                )
            )
        except:
            pass

        # Send DM
        try:
            await context.bot.send_message(
                chat_id=int(new_explainer),
                text=box(
                    f"🎯 <b>NEW WORD (SKIPPED)</b>\n\n"
                    f"Main Word: <b>{word}</b>\n\n"
                    f"🚫 Banned Words:\n"
                    f"• {banned[0]}\n"
                    f"• {banned[1]}\n"
                    f"• {banned[2]}"
                ),
                parse_mode="HTML"
            )
        except:
            pass

        await update.message.reply_html(
            box("⏭ <b>Word Skipped!</b>\nNew explainer received word in DM.")
        )

    except Exception as e:
        print("Skip Error:", e)

# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# END GAME COMMAND
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

async def end_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat = update.effective_chat
        user = update.effective_user
        chat_id = str(chat.id)

        if chat_id not in data["lobbies"]:
            return

        lobby = data["lobbies"][chat_id]

        if user.id != lobby["host"]:
            await update.message.reply_html(
                box("🚫 <b>Only host can end the game.</b>")
            )
            return

        # Unmute everyone
        for uid in lobby["players"]:
            if uid.startswith("dummy"):
                continue
            try:
                await context.bot.restrict_chat_member(
                    chat_id=chat.id,
                    user_id=int(uid),
                    permissions=ChatPermissions(
                        can_send_messages=True
                    )
                )
            except:
                pass

        lobby["game_started"] = False
        lobby["scores"] = {"BJP": 0, "CONGRESS": 0}
        lobby["current_word"] = None
        lobby["banned_words"] = []

        save_data(data)

        await update.message.reply_html(
            box("🛑 <b>Game Ended by Host.</b>")
        )

    except Exception as e:
        print("End Game Error:", e)

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

TOKEN = "YOUR_BOT_TOKEN_HERE"

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("createlobby", create_lobby))
    app.add_handler(CommandHandler("join", join_lobby))
    app.add_handler(CommandHandler("players", players_list))
    app.add_handler(CommandHandler("adddummy", add_dummy))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("skip", skip_word))
    app.add_handler(CommandHandler("endgame", end_game))

    # Game Message Handler
    app.add_handler(MessageHandler(filters.ALL, game_message_handler))

    app.run_polling()

if __name__ == "__main__":
    main()