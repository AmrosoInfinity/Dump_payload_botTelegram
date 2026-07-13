import os
import asyncio
import subprocess
import json
import shutil
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TOKEN, request_timeout=60)
dp = Dispatcher()

# Step 1: User kirim /dump
@dp.message(Command("dump"))
async def cmd_dump(message: types.Message):
    await message.answer("Silakan kirim file OTA (.zip/payload.bin) atau URL OTA:")

# Step 2: User kirim file atau URL OTA
@dp.message()
async def handle_ota(message: types.Message):
    ota_input = None

    # Hanya terima file .zip/.bin atau URL http(s)
    if message.document:
        if not (message.document.file_name.endswith(".zip") or message.document.file_name.endswith(".bin")):
            await message.answer("File tidak valid. Kirim OTA .zip atau payload.bin.")
            return
        file_path = f"downloads/{message.document.file_name}"
        os.makedirs("downloads", exist_ok=True)
        await message.document.download(destination_file=file_path)
        ota_input = file_path
    else:
        text = message.text.strip()
        if text.startswith("http://") or text.startswith("https://"):
            ota_input = text
        else:
            # Abaikan input lain (misalnya /start)
            return

    # List partisi dengan otaripper -l
    try:
        result = subprocess.check_output(["./otaripper", "-l", ota_input], text=True)
        partitions = [p.strip() for p in result.splitlines() if p.strip()]
    except Exception as e:
        await message.answer(f"Gagal membaca OTA: {e}")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Dump Full", callback_data=f"full|{ota_input}")],
        [InlineKeyboardButton(text="Dump Partition", callback_data=f"part|{ota_input}")]
    ])
    await message.answer(
        "Input OTA diterima ✅\n\nDaftar partisi:\n" + "\n".join(partitions) + "\n\nPilih mode ekstraksi:",
        reply_markup=kb
    )

# Step 3: User pilih tombol
@dp.callback_query()
async def process_dump(callback_query: types.CallbackQuery):
    mode, ota_input = callback_query.data.split("|", 1)
    output_dir = "extracted"
    os.makedirs(output_dir, exist_ok=True)

    if mode == "full":
        cmd = ["./otaripper", ota_input, "-o", output_dir, "--print-hash", "--stats"]
    else:
        # Default contoh partisi, bisa diganti sesuai input user
        cmd = ["./otaripper", ota_input, "-o", output_dir, "-p", "boot,vendor_boot", "--print-hash"]

    subprocess.run(cmd, check=True)

    # Buat JSON hash
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

    await bot.send_document(callback_query.from_user.id, open("result_with_hash.zip", "rb"))

async def main():
    logging.info("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
