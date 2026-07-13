import os
import subprocess
import json
import zipfile
import shutil
import asyncio
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")

# Inisialisasi executor untuk menjalankan perintah blocking di background
executor = ThreadPoolExecutor(max_workers=3)

# Helper blocking
def _run_cmd_blocking(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout, result.stderr

# Helper asinkron agar tidak memblokir bot
async def run_cmd(cmd):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, _run_cmd_blocking, cmd)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Halo! Kirimkan URL link OTA (.zip / payload.bin) untuk memulai proses dump.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"):
        await update.message.reply_text("❌ Mohon kirimkan URL valid yang diawali dengan http atau https.")
        return

    status_msg = await update.message.reply_text("🔍 Sedang membaca daftar partisi dari remote OTA... (Proses ini butuh waktu)")
    
    # Menjalankan otaripper dengan aman di background thread
    stdout, stderr = await run_cmd(f"./otaripper -l {url}")
    
    if "partitions" not in stdout.lower() and not stdout:
        await status_msg.edit_text(f"❌ Gagal membaca OTA. Pastikan URL valid.\nError: {stderr[:100]}")
        return

    context.user_data['ota_url'] = url

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
    
    await run_cmd("./otaripper clean")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    await query.edit_message_text("⚡ Memulai ekstraksi OTA... Proses ini memakan waktu tergantung ukuran file.")

    if choice == "dump_full":
        cmd = f"./otaripper {url} -o {output_dir} --print-hash -n"
    else:
        cmd = f"./otaripper {url} -p boot,init_boot,vendor_boot,system -o {output_dir} --print-hash -n"

    # Menjalankan ekstraksi berat di background thread
    stdout, stderr = await run_cmd(cmd)

    hash_data = {}
    for line in stdout.splitlines():
        if "sha256" in line.lower() or ":" in line:
            parts = line.split()
            if len(parts) >= 2:
                hash_data[parts[0]] = parts[-1]

    json_path = os.path.join(output_dir, "partition_hashes.json")
    with open(json_path, "w") as f:
        json.dump(hash_data, f, indent=4)

    zip_filename = "dump_result.zip"
    await query.edit_message_text("🗜️ Ekstraksi selesai! Sedang mengompres berkas menjadi ZIP...")
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, output_dir))

    await query.edit_message_text("📤 Mengirimkan berkas dump ZIP ke Anda...")
    
    try:
        with open(zip_filename, 'rb') as document:
            await query.message.reply_document(
                document=document, 
                filename=zip_filename, 
                caption="✅ Dump Sukses menggunakan Otaripper!",
                read_timeout=300,  # Berikan waktu lebih longgar untuk unggah file besar
                write_timeout=300
            )
    except Exception as e:
        await query.message.reply_text(f"❌ Gagal mengirim file ZIP. Kemungkinan file terlalu besar (>50MB Limit Telegram).\nError: {str(e)}")

    # Cleanup berkas
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
