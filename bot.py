import os
import subprocess
import json
import zipfile
import shutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")

# Helper untuk menjalankan perintah shell
def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout, result.stderr

# PERBAIKAN: @async dihapus karena tidak valid di Python
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Halo! Kirimkan URL link OTA (.zip / payload.bin) untuk memulai proses dump.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"):
        await update.message.reply_text("❌ Mohon kirimkan URL valid yang diawali dengan http atau https.")
        return

    status_msg = await update.message.reply_text("🔍 Sedang membaca daftar partisi dari remote OTA...")
    
    # Ambil list partisi menggunakan otaripper
    stdout, stderr = run_cmd(f"./otaripper -l {url}")
    
    if "partitions" not in stdout.lower() and not stdout:
        await status_msg.edit_text(f"❌ Gagal membaca OTA. Pastikan URL valid.\nError: {stderr[:100]}")
        return

    # Simpan URL di user_data untuk tahap berikutnya
    context.user_data['ota_url'] = url

    # Setup Inline Keyboard Button
    keyboard = [
        [InlineKeyboardButton("📦 Dump Full", callback_data="dump_full")],
        [InlineKeyboardButton("🧩 Dump Boot & Vendor Only", callback_data="dump_part")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await status_msg.edit_text(
        f"✅ OTA Terdeteksi!\n\n Silakan pilih metode ekstraksi:",
        reply_markup=reply_markup
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    url = context.user_data.get('ota_url')
    if not url:
        await query.edit_message_text("❌ Sesi kedaluwarsa. Silakan kirim ulang URL OTA.")
        return

    choice = query.data
    output_dir = "extracted_ota"
    
    # Bersihkan sisa dump sebelumnya jika ada
    run_cmd("./otaripper clean")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    await query.edit_message_text("⚡ Memulai ekstraksi OTA... Proses ini memakan waktu tergantung ukuran file.")

    # Tentukan argumen perintah otaripper
    if choice == "dump_full":
        cmd = f"./otaripper {url} -o {output_dir} --print-hash -n"
    else:
        cmd = f"./otaripper {url} -p boot,init_boot,vendor_boot,system -o {output_dir} --print-hash -n"

    stdout, stderr = run_cmd(cmd)

    # Parsing output otaripper untuk mencari Hash SHA-256
    hash_data = {}
    for line in stdout.splitlines():
        if "sha256" in line.lower() or ":" in line:
            parts = line.split()
            if len(parts) >= 2:
                hash_data[parts[0]] = parts[-1]

    # Simpan hash ke file JSON di dalam folder output
    json_path = os.path.join(output_dir, "partition_hashes.json")
    with open(json_path, "w") as f:
        json.dump(hash_data, f, indent=4)

    # Bungkus hasil extract menjadi berkas .zip
    zip_filename = "dump_result.zip"
    await query.edit_message_text("🗜️ Ekstraksi selesai! Sedang mengompres berkas menjadi ZIP...")
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, output_dir))

    # Kirim berkas ke pengguna Telegram
    await query.edit_message_text("📤 Mengirimkan berkas dump ZIP ke Anda...")
    with open(zip_filename, 'rb') as document:
        await query.message.reply_document(document=document, filename=zip_filename, caption="✅ Dump Sukses menggunakan Otaripper!")

    # Cleanup berkas lokal setelah selesai dikirim
    if os.path.exists(zip_filename):
        os.remove(zip_filename)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

def main():
    if not TOKEN:
        print("Error: TELEGRAM_TOKEN tidak ditemukan di Environment Variables!")
        return
        
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("dump", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
