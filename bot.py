import os
import asyncio
import subprocess
import json
import shutil
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

# Setup logging
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TOKEN, request_timeout=60)  # timeout lebih panjang
dp = Dispatcher()

# Handler untuk command /dump
@dp.message(Command("dump"))
async def cmd_dump(message: types.Message):
    logging.info(f"Received /dump from {message.from_user.id}")
    await message.answer("Kirim file OTA (.zip/payload.bin) atau URL OTA:")

# Handler untuk semua pesan (file atau teks)
@dp.message()
async def handle_ota(message: types.Message):
    ota_input = None
    if message.document:
        file_path = f"downloads/{message.document.file_name}"
        os.makedirs("downloads", exist_ok=True)
        await message.document.download(destination_file=file_path)
        ota_input = file_path
        logging.info(f"File OTA diterima: {file_path}")
    else:
        ota_input = message.text.strip()
        logging.info(f"URL OTA diterima: {ota_input}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Dump Full", callback_data=f"full|{ota_input}")],
        [InlineKeyboardButton(text="Dump Partition", callback_data=f"part|{ota_input}")]
    ])
    await message.answer("Pilih mode ekstraksi:", reply_markup=kb)

# Handler untuk tombol inline
@dp.callback_query()
async def process_dump(callback_query: types.CallbackQuery):
    mode, ota_input = callback_query.data.split("|", 1)
    output_dir = "extracted"
    os.makedirs(output_dir, exist_ok=True)

    logging.info(f"Mulai ekstraksi mode={mode}, input={ota_input}")

    if mode == "full":
        cmd = ["./otaripper", ota_input, "-o", output_dir, "--print-hash", "--stats"]
    else:
        cmd = ["./otaripper", ota_input, "-o", output_dir, "-p", "boot,vendor_boot", "--print-hash"]

    subprocess.run(cmd, check=True)

    # kumpulkan hash ke JSON
    hashes = {}
    for root, _, files in os.walk(output_dir):
        for f in files:
            if f.endswith(".img"):
                path = os.path.join(root, f)
                h = subprocess.check_output(["sha256sum", path]).decode().split()[0]
                hashes[f] = h

    with open("hashes.json", "w") as jf:
        json.dump(hashes, jf, indent=2)

    shutil.make_archive("result", "zip", output_dir)
    shutil.move("result.zip", "result_with_hash.zip")

    logging.info("Ekstraksi selesai, mengirim hasil ke user...")
    await bot.send_document(callback_query.from_user.id, open("result_with_hash.zip", "rb"))

async def main():
    logging.info("Bot is running, connecting to Telegram...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
