import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
import snowflake.connector

# ==========================================
# 1. FETCH WORD ENGINE
# ==========================================


def get_curated_word():
    easy_words_to_restrict = {
        "office",
        "morning",
        "evening",
        "welcome",
        "teacher",
        "student",
        "outside",
        "nothing",
        "brother",
        "weather",
        "company",
    }

    while True:
        random_api_url = "https://random-word-api.herokuapp.com/word?number=5"
        try:
            response = requests.get(random_api_url)
            if response.status_code != 200:
                continue
            word_list = response.json()

            for word in word_list:
                word = word.lower().strip()
                if len(word) < 6 or word in easy_words_to_restrict:
                    continue

                dict_api_url = (
                    f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
                )
                dict_response = requests.get(dict_api_url)

                if dict_response.status_code == 200:
                    data = dict_response.json()[0]
                    meanings = data.get("meanings", [])
                    if not meanings:
                        continue

                    first_def_list = meanings[0].get("definitions", [])
                    if not first_def_list:
                        continue
                    definition = first_def_list[0].get("definition")

                    example = None
                    for meaning in meanings:
                        for d in meaning.get("definitions", []):
                            if d.get("example"):
                                example = d.get("example")
                                break
                        if example:
                            break

                    if definition and example:
                        return {
                            "word": word.capitalize(),
                            "definition": definition,
                            "example_sentence": example,
                        }
        except Exception:
            pass


# ==========================================
# 2. ALERTERS & NOTIFICATIONS
# ==========================================


def send_email(vocab):
    # Retrieve secrets from environment
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
    receiver_email = os.environ.get("RECEIVER_EMAIL")

    if not all([sender_email, sender_password, receiver_email]):
        print("⚠️ Email environment variables missing. Skipping email.")
        return

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = f"📚 Word of the Day: {vocab['word']}"

    body = f"""
    <html>
      <body>
        <h2>☀️ Your Daily Vocabulary Update</h2>
        <p><strong>Word:</strong> {vocab['word']}</p>
        <p><strong>Meaning:</strong> {vocab['definition']}</p>
        <p><strong>Example Sentence:</strong> <em>"{vocab['example_sentence']}"</em></p>
      </body>
    </html>
    """
    msg.attach(MIMEText(body, "html"))

    try:
        # Standard Gmail/Yahoo/Outlook SMTP port setup
        server = smtplib.SMTP("smtp.gmail.com", 577)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print("✉️ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")


def send_telegram(vocab):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")  # Channel username e.g., @my_vocab_channel

    if not bot_token or not chat_id:
        print("⚠️ Telegram environment variables missing. Skipping Telegram.")
        return

    message = (
        f"🌟 *Word of the Day* 🌟\n\n"
        f"🗣 *Word:* {vocab['word']}\n"
        f"💡 *Meaning:* {vocab['definition']}\n"
        f"✍️ *Example:* _{vocab['example_sentence']}_\n\n"
        f"🚀 Share with others to join the channel!"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}

    try:
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            print("📢 Telegram broadcast successful!")
        else:
            print(f"❌ Telegram API Error: {res.text}")
    except Exception as e:
        print(f"❌ Failed to send Telegram message: {e}")


# ==========================================
# 3. SNOWFLAKE STORAGE ENGINE
# ==========================================


def save_to_snowflake(vocab):
    try:
        conn = snowflake.connector.connect(
            user=os.environ.get("SF_USER"),
            password=os.environ.get("SF_PASSWORD"),
            account=os.environ.get("SF_ACCOUNT"),
            warehouse="VOCAB_WH",
            database="VOCAB_DB",
            schema="PUBLIC",
        )
        cursor = conn.cursor()

        sql = """
            INSERT INTO VOCAB_DB.PUBLIC.DAILY_WORDS (WORD, MEANING, EXAMPLE_SENTENCE)
            VALUES (%s, %s, %s)
        """
        cursor.execute(sql, (vocab["word"], vocab["definition"], vocab["example_sentence"]))
        conn.commit()
        print("❄️ Word successfully logged to Snowflake!")

    except Exception as e:
        print(f"❌ Snowflake database operation failed: {e}")
    finally:
        if "conn" in locals():
            cursor.close()
            conn.close()


# ==========================================
# MAIN ROUTINE EXECUTOR
# ==========================================
if __name__ == "__main__":
    # Step A: Get the word
    data = get_curated_word()

    if not data:
        print("❌ Could not generate valid word data. Exiting.")
        sys.exit(1)

    print(f"\n🎯 Processing: {data['word']}")

    # Step B: Notify
    send_email(data)
    send_telegram(data)

    # Step C: Log to Cloud DWH
    save_to_snowflake(data)
