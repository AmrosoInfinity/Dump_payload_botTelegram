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
BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# Dictionary untuk menyimpan state user (URL Ota, daftar partisi, dll)
user_data = {}

def clean_ansi(text):
    """Fungsi untuk membersihkan kode warna terminal (ANSI) agar rapi di Telegram"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

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
    
    bot.send_message(chat_id, "⏳ Membaca daftar partisi dari URL... Ini mungkin memakan waktu sebentar.")
    
    try:
        # Jalankan otaripper untuk melist partisi
        result = subprocess.run(["./otaripper", "-l", url], capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            error_msg = clean_ansi(result.stderr or result.stdout)[:1000]
            bot.send_message(chat_id, f"❌ Gagal mengambil partisi:\n```\n{error_msg}\n```", parse_mode="Markdown")
            return
        
        # Simpan output daftar partisi (bersihkan dari ansi color codes)
        clean_list_output = clean_ansi(result.stdout)
        user_data[chat_id]['partitions_list'] = clean_list_output

        # Buat Inline Keyboard
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📦 Dump Full", callback_data="dump_full"),
                   InlineKeyboardButton("🗂 Dump Partition", callback_data="dump_part"))
        
        bot.send_message(chat_id, f"✅ File berhasil diakses dan partisi berhasil dibaca!\n\nPilih metode ekstraksi:", reply_markup=markup)

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
        bot.answer_callback_query(call.id, "Menyiapkan daftar partisi...")
        
        # Ambil daftar partisi yang tadi disimpan
        partitions_text = user_data[chat_id].get('partitions_list', 'Daftar partisi tidak ditemukan.')
        
        # Potong teks jika terlalu panjang (Batas Telegram ~4096 char)
        if len(partitions_text) > 3500:
            partitions_text = partitions_text[:3500] + "\n... [Daftar dipotong karena terlalu panjang]"

        msg_text = f"📜 **Daftar Partisi yang Tersedia:**\n```text\n{partitions_text}\n```\n\n✏️ **Kirimkan nama partisi** yang ingin di-dump (pisahkan dengan koma jika lebih dari satu).\n*Contoh: boot, init_boot, vendor_boot*"
        
        msg = bot.send_message(chat_id, msg_text, parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_specific_partitions)

def process_specific_partitions(message):
    chat_id = message.chat.id
    # Hilangkan spasi jika user mengetik "boot, vendor" menjadi "boot,vendor"
    partitions = message.text.strip().replace(" ", "")
    
    if chat_id not in user_data:
        bot.reply_to(message, "Sesi kedaluwarsa. Ketik /dump lagi.")
        return
        
    bot.reply_to(message, f"🚀 Memulai ekstraksi untuk partisi:\n`{partitions}`", parse_mode="Markdown")
    execute_dump(chat_id, user_data[chat_id]['url'], partitions)

def execute_dump(chat_id, url, partitions):
    bot.send_message(chat_id, "⚙️ Sedang mengekstrak. Silakan tunggu, ini membutuhkan waktu tergantung ukuran file dan kecepatan server...")
    
    job_id = str(uuid.uuid4())[:8]
    out_dir = f"extracted_{job_id}"
    
    cmd = ["./otaripper", url, "-o", out_dir, "-n", "--print-hash"]
    if partitions:
        cmd.extend(["-p", partitions])
        
    try:
        # Jalankan otaripper untuk extract
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            error_msg = clean_ansi(result.stderr or result.stdout)[:1000]
            bot.send_message(chat_id, f"❌ Gagal mengekstrak:\n```\n{error_msg}\n```", parse_mode="Markdown")
            return
        
        # Ekstrak hash dari output log
        clean_output = clean_ansi(result.stdout)
        hashes = {}
        # Mencari pola partisi dan hash SHA-256 pada log otaripper
        hash_pattern = re.findall(r'([a-zA-Z0-9_-]+)\.(?:img|bin).*?([a-fA-F0-9]{64})', clean_output)
        for part, sha in hash_pattern:
            hashes[part] = sha
            
        # Tulis ke hashes.json jika ada
        if hashes:
            json_path = os.path.join(out_dir, "hashes.json")
            with open(json_path, "w") as f:
                json.dump(hashes, f, indent=4)
            
        # Periksa apakah folder ekstraksi memiliki isi
        if not os.path.exists(out_dir) or not os.listdir(out_dir):
            bot.send_message(chat_id, "❌ Ekstraksi selesai, tapi folder kosong. Partisi mungkin salah ketik atau tidak ada.")
            return

        # Zip folder output
        zip_filename = f"OTA_Dump_{job_id}.zip"
        bot.send_message(chat_id, "📦 Mengompresi file hasil ekstraksi...")
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(out_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.basename(file_path))
                    
        # Hitung ukuran dan langsung kirim tanpa batasan limit
        file_size_mb = os.path.getsize(zip_filename) / (1024 * 1024)
        bot.send_message(chat_id, f"✅ Kompresi selesai! (Ukuran: {file_size_mb:.2f} MB)\nMengirim file zip ke Anda...")
        
        with open(zip_filename, 'rb') as f:
            bot.send_document(chat_id, f)
                
    except Exception as e:
        # Menangkap error jika Telegram menolak file yang terlalu besar (misal HTTP 413)
        bot.send_message(chat_id, f"❌ Terjadi kesalahan saat pengiriman: {str(e)}")
    
    finally:
        # Bersihkan folder dan file sampah agar runner GitHub tidak penuh
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        if 'zip_filename' in locals() and os.path.exists(zip_filename):
            os.remove(zip_filename)
        # Hapus data sesi user
        if chat_id in user_data:
            del user_data[chat_id]

if __name__ == "__main__":
    print("Bot is running and ready to serve...")
    bot.infinity_polling()
