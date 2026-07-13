import os
import subprocess
import json
import shutil
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['dump'])
async def cmd_dump(message: types.Message):
    await message.reply("Kirim file OTA (.zip/payload.bin) atau URL OTA:")

@dp.message_handler(content_types=['document', 'text'])
async def handle_ota(message: types.Message):
    ota_input = None
    if message.document:
        file_path = f"downloads/{message.document.file_name}"
        await message.document.download(destination_file=file_path)
        ota_input = file_path
    else:
        ota_input = message.text.strip()

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Dump Full", callback_data=f"full|{ota_input}"))
    kb.add(InlineKeyboardButton("Dump Partition", callback_data=f"part|{ota_input}"))
    await message.reply("Pilih mode ekstraksi:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("full") or c.data.startswith("part"))
async def process_dump(callback_query: types.CallbackQuery):
    mode, ota_input = callback_query.data.split("|", 1)
    output_dir = "extracted"
    os.makedirs(output_dir, exist_ok=True)

    if mode == "full":
        cmd = ["./otaripper", ota_input, "-o", output_dir, "--print-hash", "--stats"]
    else:
        # contoh partisi default
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

    await bot.send_document(callback_query.from_user.id, open("result_with_hash.zip", "rb"))
