#!/usr/bin/env python3
# Hestle.Exe — Telegram Business assistant
# Python 3.10+ | standard library only

import ast
import html
import json
import logging
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

BOT_TOKEN = "9157080448:AAHamktOtlIaqjmoJnFJ2mUFv1MMYmiz4xc"
DB_FILE = Path("hestle_data.json")
API = ""

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("Hestle.Exe")

DEFAULT_TEXTS = {
    "spam": "🍒 Обнаружен вирус в телеграм аккаунте!!! удалите аккаунт!!!",
    "mute": "🔒 Режим тишины активирован. Новые сообщения будут удаляться.",
    "nomute": "🔓 Режим тишины отключён. Чат снова открыт для сообщений.",
    "auto": "👋 Привет! Сейчас я не у экрана, но ваше сообщение уже увидел. Отвечу, как только вернусь.",
    "auto_on": "✓ Автоответчик активирован. Я отвечу на следующее входящее сообщение.",
    "auto_off": "✓ Автоответчик отключён. Автоматические ответы больше не отправляются.",
    "fallback": "Здравствуйте! Спасибо за сообщение. Я получил его и вернусь с ответом, как только освобожусь.",
}

DEFAULT_DATA = {
    "connections": {},
    "texts": {},
    "muted": [],
    "autoresponders": [],
    "cooldowns": {},
    "spam": {},
    "jobs": [],
    "pending_edits": {},
}


def load_data():
    try:
        value = json.loads(DB_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


data = load_data()
for key, value in DEFAULT_DATA.items():
    data.setdefault(key, value)


def save():
    DB_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_texts(user_id):
    key = str(user_id)
    if key not in data["texts"]:
        data["texts"][key] = DEFAULT_TEXTS.copy()
        save()
    else:
        for name, value in DEFAULT_TEXTS.items():
            data["texts"][key].setdefault(name, value)
    return data["texts"][key]


def api(method, payload=None):
    request = urllib.request.Request(
        API + method,
        data=json.dumps(payload or {}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok"):
            description = result.get("description", "неизвестная ошибка")
            error_code = result.get("error_code", "?")
            log.error("Telegram API %s: HTTP/API %s — %s", method, error_code, description)
            return None
        return result.get("result")
    except Exception as exc:
        log.exception("Не удалось выполнить Telegram API %s: %s", method, exc)
        return None


def send(chat_id, text, business_id=None, markup=None, parse_mode=None):
    payload = {"chat_id": chat_id, "text": text}
    if business_id:
        payload["business_connection_id"] = business_id
    if markup:
        payload["reply_markup"] = markup
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return api("sendMessage", payload)


def delete_business(business_id, message_ids):
    if not business_id or not message_ids:
        return None
    return api("deleteBusinessMessages", {
        "business_connection_id": business_id,
        "message_ids": message_ids[:100],
    })


def edit_message(chat_id, message_id, text, markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if markup:
        payload["reply_markup"] = markup
    return api("editMessageText", payload)


def home_keyboard():
    return {"inline_keyboard": [
        [
            {"text": "⌘ Команды", "callback_data": "commands"},
            {"text": "⚙️ Настройки", "callback_data": "settings"},
        ],
        [
            {"text": "↗️ Подключение", "callback_data": "howto"},
            {"text": "▤ Мои тексты", "callback_data": "show"},
        ],
    ]}


def back_keyboard():
    return {"inline_keyboard": [[
        {"text": "← Назад", "callback_data": "home"}
    ]]}


TEXT_LABELS = {
    "spam": "🍒 Текст команды .spam",
    "mute": "🔒 Сообщение при .mute",
    "nomute": "🔑 Сообщение при .nomute",
    "auto": "💬 Текст автоответчика",
    "auto_on": "Уведомление о включении автоответчика",
    "auto_off": "Уведомление о выключении автоответчика",
    "fallback": "✉️ Стандартный автоответ",
}


def settings_keyboard():
    rows = []
    keys = list(TEXT_LABELS)
    for index in range(0, len(keys), 2):
        rows.append([
            {"text": TEXT_LABELS[key], "callback_data": "edit:" + key}
            for key in keys[index:index + 2]
        ])
    rows.append([{"text": "← Назад", "callback_data": "home"}])
    return {"inline_keyboard": rows}


COMMANDS = (
    "✦ <b>Hestle.Exe · Команды</b>\n\n"
    "<b>Управление чатом</b>\n"
    "• <code>.spam</code> — отправить короткую серию сообщений.\n"
    "• <code>.nospam</code> — остановить серию.\n"
    "• <code>.mute</code> — включить удаление новых входящих сообщений.\n"
    "• <code>.nomute</code> — выключить режим удаления.\n"
    "• <code>.Avtootvet</code> — включить автоответчик.\n"
    "• <code>.noavtootvet</code> — выключить автоответчик.\n\n"
    "<b>Инструменты</b>\n"
    "• <code>.timer 2 Текст</code> — отправить текст и удалить через 2 минуты.\n"
    "• <code>.calc 12*(3+4)</code> — вычислить выражение.\n"
    "• <code>.snos</code> — показать демонстрационный экран отчёта.\n\n"
    "<i>Команды вводятся в подключённом Business-чате. Для проверки прав отправьте боту /status.</i>"
)

HOWTO = (
    "↗️ <b>Подключение Hestle.Exe</b>\n\n"
    "1. Открой Telegram → Настройки → Telegram Business.\n"
    "2. Перейди в «Чат-боты» и добавь своего бота.\n"
    "3. Выбери личные чаты, где бот должен работать.\n"
    "4. Разреши боту отвечать на сообщения.\n"
    "5. Для .mute выдай право удалять сообщения.\n\n"
    "<i>Если права не выданы, Telegram не позволит боту удалять сообщения.</i>"
)


def safe_calc(expression):
    if len(expression) > 100 or not re.fullmatch(r"[0-9+*/(). %\-]+", expression):
        raise ValueError("Недопустимое выражение")
    tree = ast.parse(expression, mode="eval")
    allowed = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
        ast.Pow, ast.USub, ast.UAdd,
    )

    def validate(node):
        if not isinstance(node, allowed):
            raise ValueError("Недопустимая операция")
        if isinstance(node, ast.Constant) and (
            not isinstance(node.value, (int, float)) or abs(node.value) > 10**9
        ):
            raise ValueError("Недопустимое число")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            if not isinstance(node.right, ast.Constant) or abs(node.right.value) > 8:
                raise ValueError("Слишком большая степень")
        for child in ast.iter_child_nodes(node):
            validate(child)

    validate(tree)
    result = eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, {})
    if not isinstance(result, (int, float)) or abs(result) > 10**12:
        raise ValueError("Результат слишком большой")
    return str(result)


def get_connection(connection_id):
    connection = data["connections"].get(connection_id)
    if connection and connection.get("owner"):
        return connection

    # Recover connection metadata if its update was missed before the bot restarted.
    fresh = api("getBusinessConnection", {"business_connection_id": connection_id})
    if not fresh:
        return None
    handle_connection(fresh)
    return data["connections"].get(connection_id)


def handle_connection(connection):
    rights = connection.get("rights") or {}
    data["connections"][connection["id"]] = {
        "owner": (connection.get("user") or {}).get("id"),
        "enabled": connection.get("is_enabled", False),
        "reply": rights.get("can_reply", False),
        "delete_all": rights.get("can_delete_all_messages", False),
        "delete_sent": rights.get("can_delete_sent_messages", False),
    }
    save()
    log.info(
        "Business-подключение обновлено: id=%s owner=%s enabled=%s can_reply=%s delete_all=%s",
        connection["id"],
        (connection.get("user") or {}).get("id"),
        connection.get("is_enabled"),
        rights.get("can_reply"),
        rights.get("can_delete_all_messages"),
    )


def queue_job(job):
    data["jobs"].append(job)
    save()


def erase_command(connection_id, message_id, rights):
    if not message_id:
        log.warning("Не удалось удалить команду: Telegram не передал message_id.")
        return False
    if not rights.get("delete_all"):
        log.error(
            "НЕТ ПРАВА НА УДАЛЕНИЕ: включите can_delete_all_messages "
            "в Telegram → Настройки → Telegram Business → Чат-боты → Hestle.Exe."
        )
        return False
    result = delete_business(connection_id, [message_id])
    if result is True:
        log.info("Команда message_id=%s успешно удалена.", message_id)
        return True
    log.error(
        "Telegram не удалил message_id=%s. Проверьте право can_delete_all_messages "
        "и текст ошибки Telegram выше.", message_id
    )
    return False


def handle_private(message):
    user = message.get("from") or {}
    chat_id = (message.get("chat") or {}).get("id")
    user_id = user.get("id")
    raw = (message.get("text") or "").strip()
    if not chat_id or not user_id:
        return

    pending = data["pending_edits"].get(str(user_id))
    if pending and raw and not raw.startswith("/"):
        if raw.lower() in ("/cancel", "отмена"):
            data["pending_edits"].pop(str(user_id), None)
            save()
            send(chat_id, "Изменение отменено.")
            return
        get_texts(user_id)[pending] = raw
        data["pending_edits"].pop(str(user_id), None)
        save()
        send(chat_id, "✓ Текст сохранён.")
        return

    if raw == "/start":
        send(
            chat_id,
            "✦ <b>Hestle.Exe</b>\n<i>Business assistant</i>\n\n"
            "Добро пожаловать. Выберите нужный раздел:",
            markup=home_keyboard(),
            parse_mode="HTML",
        )
    elif raw == "/id":
        send(chat_id, f"Ваш Telegram ID: <code>{user_id}</code>", parse_mode="HTML")
    elif raw == "/status":
        owned = [
            (connection_id, info)
            for connection_id, info in data["connections"].items()
            if info.get("owner") == user_id
        ]
        if not owned:
            send(chat_id, "⚠️ Business-подключение не найдено. Переподключите бота в настройках Telegram Business.")
        else:
            lines = ["✦ <b>Статус Hestle.Exe</b>"]
            for number, (connection_id, info) in enumerate(owned, 1):
                lines.extend([
                    "",
                    f"<b>Подключение {number}</b>",
                    "• Статус: " + ("активно" if info.get("enabled") else "выключено"),
                    "• Ответы: " + ("разрешены" if info.get("reply") else "нет права"),
                    "• Удаление любых сообщений: " + ("разрешено ✓" if info.get("delete_all") else "не разрешено ✕"),
                    "• Удаление сообщений бота: " + ("разрешено" if info.get("delete_sent") else "не разрешено"),
                ])
            send(chat_id, "\\n".join(lines), parse_mode="HTML")
    elif raw == ".команды":
        send(chat_id, COMMANDS, parse_mode="HTML")
    elif raw.startswith(".calc "):
        try:
            send(chat_id, safe_calc(raw[6:].strip()))
        except Exception:
            send(chat_id, "Не удалось вычислить выражение.")
    elif raw.startswith(".текст "):
        match = re.match(r"^\.текст\s+(spam|mute|nomute|auto|auto_on|auto_off|fallback)\s+(.+)$", raw, re.S)
        if match:
            key, value = match.groups()
            get_texts(user_id)[key] = value.strip()
            save()
            send(chat_id, "✓ Текст обновлён. Новое значение будет использоваться в подключённых чатах.")
        else:
            send(chat_id, "Формат: .текст mute Новый текст")


def handle_callback(callback):
    api("answerCallbackQuery", {"callback_query_id": callback["id"]})
    user = callback.get("from") or {}
    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")
    user_id = user.get("id")
    action = callback.get("data", "")
    if not chat_id or not message_id or not user_id:
        return

    if action == "home":
        text, keyboard = (
            "✦ <b>Hestle.Exe</b>\n<i>Business assistant</i>\n\n"
            "Добро пожаловать. Выберите нужный раздел:",
            home_keyboard(),
        )
    elif action == "commands":
        text, keyboard = COMMANDS, back_keyboard()
    elif action == "howto":
        text, keyboard = HOWTO, back_keyboard()
    elif action == "settings":
        text = (
            "⚙️ <b>Настройки Hestle.Exe</b>\n\n"
            "Выберите сообщение, текст которого хотите изменить. "
            "После нажатия отправьте новый вариант в личный чат с ботом."
        )
        keyboard = settings_keyboard()
    elif action == "show":
        current = get_texts(user_id)
        text = "▤ <b>Тексты Hestle.Exe</b>\n\n" + "\n\n".join(
            "<b>" + html.escape(label) + "</b>\n" + html.escape(current[key])
            for key, label in TEXT_LABELS.items()
        )
        keyboard = back_keyboard()
    elif action.startswith("edit:"):
        key = action.split(":", 1)[1]
        if key not in TEXT_LABELS:
            return
        data["pending_edits"][str(user_id)] = key
        save()
        text = (
            "✏️ <b>" + html.escape(TEXT_LABELS[key]) + "</b>\n\n"
            "Отправьте новый текст следующим сообщением.\n"
            "Для отмены отправьте /cancel."
        )
        keyboard = back_keyboard()
    else:
        return

    api("editMessageText", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": keyboard,
    })


def handle_business(message):
    connection_id = message.get("business_connection_id")
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")
    if not connection_id or not chat_id:
        return

    connection = get_connection(connection_id)
    if not connection:
        log.error("Нет данных Business-подключения %s. Проверьте права и подключение.", connection_id)
        return
    if not connection.get("enabled"):
        log.warning("Business-подключение выключено: %s", connection_id)
        return
    if not connection.get("reply"):
        log.warning("У бота нет права can_reply для подключения %s", connection_id)
        return

    owner_id = connection.get("owner")
    if not owner_id:
        log.error("Не найден владелец Business-подключения %s", connection_id)
        return

    sender = message.get("from") or {}
    sender_id = sender.get("id")
    is_owner = sender_id == owner_id
    is_bot_message = bool(message.get("sender_business_bot"))
    raw = (message.get("text") or message.get("caption") or "").strip()
    command = raw.lower()
    key = connection_id + ":" + str(chat_id)
    texts = get_texts(owner_id)

    log.info(
        "Business message: chat=%s sender=%s owner=%s owner_message=%s text=%r",
        chat_id, sender_id, owner_id, is_owner, raw[:100],
    )

    def remove_command():
        erase_command(connection_id, message_id, connection)

    # Commands are accepted only from the owner of the connected Business account.
    if is_owner and not is_bot_message:
        if command == ".mute":
            remove_command()
            if not connection.get("delete_all"):
                send(
                    chat_id,
                    "⚠️ Для .mute не выдано право удалять сообщения. "
                    "Включите это разрешение в настройках Telegram Business.",
                    business_id=connection_id,
                )
                return
            if key not in data["muted"]:
                data["muted"].append(key)
                save()
            send(chat_id, texts["mute"], business_id=connection_id)
            log.info("Команда .mute выполнена для чата %s", chat_id)
            return

        if command == ".nomute":
            remove_command()
            data["muted"] = [item for item in data["muted"] if item != key]
            save()
            send(chat_id, texts["nomute"], business_id=connection_id)
            log.info("Команда .nomute выполнена для чата %s", chat_id)
            return

        if command.startswith(".spam"):
            remove_command()
            match = re.fullmatch(r"\\.spam\\s+(\\d{1,3})\\s+(.+)", raw, re.S | re.I)
            if not match:
                send(
                    chat_id,
                    "Формат: .spam [количество 1–10] [текст]\\n"
                    "Пример: .spam 5 Всем привет!",
                    business_id=connection_id,
                )
                return
            count = int(match.group(1))
            spam_text = match.group(2).strip()
            if not 1 <= count <= 10 or not spam_text or len(spam_text) > 300:
                send(chat_id, "⚠️ Допустимо от 1 до 10 сообщений; текст — до 300 символов.", business_id=connection_id)
                return
            if key in data["spam"]:
                send(chat_id, "ℹ️ Серия уже запущена. Сначала отправьте .nospam.", business_id=connection_id)
                return
            sent = send(chat_id, spam_text, business_id=connection_id)
            if sent and count > 1:
                data["spam"][key] = {
                    "remaining": count - 1,
                    "next_at": time.time() + 5,
                    "business_id": connection_id,
                    "chat_id": chat_id,
                    "text": spam_text,
                }
                save()
            log.info("Команда .spam: запрошено %s сообщений в чате %s", count, chat_id)
            return

        if command == ".nospam":
            remove_command()
            data["spam"].pop(key, None)
            save()
            log.info("Команда .nospam выполнена для чата %s", chat_id)
            return

        if command == ".avtootvet":
            remove_command()
            if key not in data["autoresponders"]:
                data["autoresponders"].append(key)
                save()
            notice = send(chat_id, texts["auto_on"], business_id=connection_id)
            if notice and connection.get("delete_sent"):
                queue_job({
                    "type": "delete",
                    "business_id": connection_id,
                    "message_id": notice["message_id"],
                    "at": time.time() + 2,
                })
            log.info("Автоответчик включён для чата %s", chat_id)
            return

        if command == ".noavtootvet":
            remove_command()
            data["autoresponders"] = [
                item for item in data["autoresponders"] if item != key
            ]
            save()
            notice = send(chat_id, texts["auto_off"], business_id=connection_id)
            if notice and connection.get("delete_sent"):
                queue_job({
                    "type": "delete",
                    "business_id": connection_id,
                    "message_id": notice["message_id"],
                    "at": time.time() + 2,
                })
            log.info("Автоответчик выключен для чата %s", chat_id)
            return

        if command.startswith(".calc "):
            remove_command()
            try:
                send(chat_id, safe_calc(raw[6:].strip()), business_id=connection_id)
            except Exception:
                send(chat_id, "⚠️ Не удалось вычислить выражение.", business_id=connection_id)
            return

        if command.startswith(".timer "):
            parts = raw.split(maxsplit=2)
            remove_command()
            try:
                minutes = int(parts[1])
                if not 1 <= minutes <= 1440 or len(parts) != 3:
                    raise ValueError
                sent = send(chat_id, parts[2], business_id=connection_id)
                if sent and connection.get("delete_sent"):
                    queue_job({
                        "type": "delete",
                        "business_id": connection_id,
                        "message_id": sent["message_id"],
                        "at": time.time() + minutes * 60,
                    })
            except (ValueError, IndexError):
                send(chat_id, "Формат: .timer 2 Текст (от 1 до 1440 минут).", business_id=connection_id)
            return

        if command == ".snos":
            remove_command()
            first = send(
                chat_id,
                "🔒 Подготавливаю демонстрационный отчёт…\n"
                "<i>Реальные жалобы не отправляются.</i>",
                business_id=connection_id,
                parse_mode="HTML",
            )
            if first:
                quote_message = message.get("reply_to_message") or {}
                quote = quote_message.get("text") or quote_message.get("caption") or "Цитируемый текст не указан."
                queue_job({
                    "type": "snos",
                    "business_id": connection_id,
                    "chat_id": chat_id,
                    "message_id": first["message_id"],
                    "quote": quote[:700],
                    "step": 1,
                    "at": time.time() + 2,
                })
            return

        # Owner's ordinary messages must not trigger the autoresponder.
        if is_owner or is_bot_message:
            return

    # Incoming messages from other people.
    if is_bot_message:
        return
    if key in data["muted"]:
        if connection.get("delete_all") and message_id:
            delete_business(connection_id, [message_id])
        return

    if key in data["autoresponders"]:
        send(chat_id, texts["auto"], business_id=connection_id)
        return

    now = time.time()
    last = data["cooldowns"].get(key, 0)
    if now - last >= 2:
        sent = send(chat_id, texts["fallback"], business_id=connection_id)
        if sent:
            data["cooldowns"][key] = now
            save()


def run_jobs():
    now = time.time()
    remaining = []

    for job in data["jobs"]:
        if job.get("at", 0) > now:
            remaining.append(job)
            continue

        business_id = job.get("business_id")
        if job.get("type") == "delete":
            delete_business(business_id, [job["message_id"]])

        elif job.get("type") == "snos":
            if job.get("step") == 1:
                edit_message(
                    job["chat_id"],
                    job["message_id"],
                    "🔑 Формирую отчёт…\n"
                    "<i>Демонстрация интерфейса — реальные жалобы не отправляются.</i>",
                )
                job["step"] = 2
                job["at"] = now + 2
                remaining.append(job)
            else:
                report = (
                    "🔒 <b>Демонстрационный отчёт</b>\n"
                    "<i>Реальные жалобы не отправлялись.</i>\n\n"
                    "Отправлено: 283\n"
                    "Не отправлено: 17\n\n"
                    "<b>Цитируемый текст:</b>\n"
                    "<blockquote>" + html.escape(job["quote"]) + "</blockquote>\n\n"
                    "Статистика сформирована локально и не является подтверждением отправки жалоб."
                )
                api("editMessageText", {
                    "chat_id": job["chat_id"],
                    "message_id": job["message_id"],
                    "text": report,
                    "parse_mode": "HTML",
                })

    for key, spam in list(data["spam"].items()):
        if spam["next_at"] > now:
            continue
        if spam["remaining"] <= 0:
            data["spam"].pop(key, None)
            continue
        send(spam["chat_id"], spam["text"], business_id=spam["business_id"])
        spam["remaining"] -= 1
        spam["next_at"] = now + 5
        if spam["remaining"] <= 0:
            data["spam"].pop(key, None)

    if remaining != data["jobs"]:
        data["jobs"] = remaining
    save()


def main():
    global API
    if BOT_TOKEN == "ВСТАВЬ_ТОКЕН_ОТ_BOTFATHER":
        raise SystemExit(
            "ОШИБКА: открой Hestle_Exe_fixed.py и вставь токен в BOT_TOKEN."
        )

    API = "https://api.telegram.org/bot" + BOT_TOKEN + "/"
    me = api("getMe")
    if not me:
        raise SystemExit("Не удалось подключиться. Проверь токен и интернет.")

    log.info("✦ Hestle.Exe запущен: @%s", me.get("username"))
    log.info("Ожидаю сообщения. Для остановки нажми Ctrl+C. Проверка прав: отправьте боту /status.")

    webhook = api("deleteWebhook", {"drop_pending_updates": False})
    if webhook is None:
        log.warning("Не удалось удалить webhook. Проверь, не запущен ли другой экземпляр.")

    offset = 0
    allowed_updates = [
        "message",
        "callback_query",
        "business_connection",
        "business_message",
        "edited_business_message",
        "deleted_business_messages",
    ]

    while True:
        try:
            updates = api("getUpdates", {
                "offset": offset,
                "timeout": 25,
                "allowed_updates": allowed_updates,
            })
            if updates is None:
                time.sleep(3)
                continue

            for update in updates:
                offset = update["update_id"] + 1
                try:
                    if "message" in update:
                        handle_private(update["message"])
                    elif "callback_query" in update:
                        handle_callback(update["callback_query"])
                    elif "business_connection" in update:
                        handle_connection(update["business_connection"])
                    elif "business_message" in update:
                        log.info("Получено Business-сообщение.")
                        handle_business(update["business_message"])
                    elif "edited_business_message" in update:
                        log.info("Получено изменение Business-сообщения.")
                    elif "deleted_business_messages" in update:
                        log.info("Telegram сообщил об удалении Business-сообщений: %s", update["deleted_business_messages"].get("message_ids", []))
                except Exception:
                    log.exception("Ошибка обработки update_id=%s", update.get("update_id"))

            run_jobs()

        except KeyboardInterrupt:
            log.info("Hestle.Exe остановлен.")
            break
        except Exception:
            log.exception("Ошибка основного цикла polling")
            time.sleep(3)


if __name__ == "__main__":
    main()
