import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import subprocess
import os
import shutil
import json
import zipfile
import uuid
import re

# Ambil token dari environment variables GitHub Actions
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Dictionary untuk menyimpan state user (URL Ota, dll)
user_data = {}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Halo! Saya adalah Bot OTA Ripper.\nGunakan perintah /dump untuk memulai ekstraksi OTA.")

@bot.message_handler(commands=['dump'])
def dump_command(message):
    msg = bot.reply_to(message, "Silakan kirimkan URL dari file OTA (.zip atau payload.bin):")
    bot.register_next_step_handler(msg, process_ota_url)

def process_ota_url(message):
    url = message.text.strip()
    if not url.startswith("http"):
        bot.reply_to(message, "Harap masukkan URL yang valid (dimulai dengan http/https). Ketik /dump untuk mengulang.")
        return

    chat_id = message.chat.id
    user_data[chat_id] = {'url': url}
    
    bot.send_message(chat_id, "⏳ Mengambil daftar partisi dari URL...")
    
    # Jalankan otaripper untuk melist partisi
    try:
        result = subprocess.run(["./otaripper", "-l", url], capture_output=True, text=True, timeout=60)
        output = result.stdout + result.stderr
        
        if result.returncode != 0:
            bot.send_message(chat_id, f"❌ Gagal mengambil partisi:\n```\n{output[:1000]}\n```", parse_mode="Markdown")
            return
        
        # Buat Inline Keyboard
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Dump Full", callback_data="dump_full"),
                   InlineKeyboardButton("Dump Partition", callback_data="dump_part"))
        
        bot.send_message(chat_id, f"✅ Partisi berhasil dibaca!\n\nPilih metode ekstraksi:", reply_markup=markup)

    except Exception as e:
        bot.send_message(chat_id, f"❌ Terjadi kesalahan: {str(e)}")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    if chat_id not in user_data:
        bot.answer_callback_query(call.id, "Sesi kedaluwarsa. Ketik /dump lagi.")
        return

    if call.data == "dump_full":
        bot.answer_callback_query(call.id, "Memulai Dump Full...")
        execute_dump(chat_id, user_data[chat_id]['url'], None)
    
    elif call.data == "dump_part":
        msg = bot.send_message(chat_id, "Kirimkan nama partisi yang ingin di-dump (pisahkan dengan koma, contoh: boot,init_boot,vendor_boot):")
        bot.register_next_step_handler(msg, process_specific_partitions)

def process_specific_partitions(message):
    chat_id = message.chat.id
    partitions = message.text.strip()
    
    if chat_id not in user_data:
        bot.reply_to(message, "Sesi kedaluwarsa. Ketik /dump lagi.")
        return
        
    bot.reply_to(message, f"Memulai Dump untuk partisi: {partitions}...")
    execute_dump(chat_id, user_data[chat_id]['url'], partitions)

def execute_dump(chat_id, url, partitions):
    bot.send_message(chat_id, "⚙️ Sedang mengekstrak. Ini mungkin membutuhkan waktu...")
    
    job_id = str(uuid.uuid4())[:8]
    out_dir = f"extracted_{job_id}"
    
    cmd = ["./otaripper", url, "-o", out_dir, "-n", "--print-hash"]
    if partitions:
        cmd.extend(["-p", partitions])
        
    try:
        # Jalankan otaripper
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            bot.send_message(chat_id, f"❌ Gagal mengekstrak:\n```\n{result.stderr[:1000]}\n```", parse_mode="Markdown")
            return
        
        # Ekstrak hash dari output stdout otaripper (Mencari pola hash SHA-256)
        hashes = {}
        # Asumsi regex sederhana untuk mencari nama partisi dan hash-nya pada log CLI
        hash_pattern = re.findall(r'([a-zA-Z0-9_]+)\.(?:img|bin).*?([a-fA-F0-9]{64})', result.stdout)
        for part, sha in hash_pattern:
            hashes[part] = sha
            
        # Tulis ke hashes.json
        json_path = os.path.join(out_dir, "hashes.json")
        with open(json_path, "w") as f:
            json.dump(hashes, f, indent=4)
            
        # Zip folder output
        zip_filename = f"OTA_Dump_{job_id}.zip"
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(out_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.basename(file_path))
                    
        # Kirim file zip
        file_size_mb = os.path.getsize(zip_filename) / (1024 * 1024)
        if file_size_mb > 50:
            bot.send_message(chat_id, f"⚠️ Ukuran file ({file_size_mb:.2f} MB) melebihi batas upload Telegram (50 MB). Pengiriman dibatalkan.")
        else:
            bot.send_message(chat_id, "✅ Ekstraksi selesai! Mengunggah file...")
            with open(zip_filename, 'rb') as f:
                bot.send_document(chat_id, f)
                
    except Exception as e:
        bot.send_message(chat_id, f"❌ Terjadi kesalahan saat sistem berjalan: {str(e)}")
    
    finally:
        # Cleanup
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
        # Hapus data sesi agar bersih
        if chat_id in user_data:
            del user_data[chat_id]

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
