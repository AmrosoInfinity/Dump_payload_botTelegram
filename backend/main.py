import asyncio
import os
import shutil
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from config import API_ID, API_HASH, SESSION_STRING, CHAT_ID, OTA_URL, PARTITIONS
from extractor import run_otaripper

async def main():
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.connect()

    async def send_msg(text):
        await client.send_message(CHAT_ID, text)

    out_dir = None
    zip_filename = None

    try:
        await send_msg("⚙️ **[Userbot] Mesin Server Linux menyala.**\nSedang memulai proses ekstraksi OTA, mohon tunggu...")
        
        # Panggil fungsi eksekutor dari extractor.py
        zip_filename, file_size_mb, out_dir = run_otaripper(OTA_URL, PARTITIONS)
        
        await send_msg(f"✅ Kompresi selesai! (Ukuran: {file_size_mb:.2f} MB)\n🚀 Sedang mengunggah file ke Telegram, proses ini membutuhkan waktu...")
        
        # Upload menggunakan Userbot (Bypass limit 50MB)
        await client.send_file(
            CHAT_ID, 
            zip_filename, 
            caption=f"✅ **Dump Selesai!**\n\n📁 **Ukuran:** {file_size_mb:.2f} MB"
        )

    except Exception as e:
        await send_msg(f"❌ Terjadi kesalahan sistem internal:\n`{str(e)}`")

    finally:
        # Cleanup
        if out_dir and os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        if zip_filename and os.path.exists(zip_filename):
            os.remove(zip_filename)

if __name__ == "__main__":
    asyncio.run(main())
