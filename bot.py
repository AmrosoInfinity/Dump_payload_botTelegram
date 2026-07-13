import os, asyncio, subprocess, json, shutil, logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TOKEN, request_timeout=60)
dp = Dispatcher()

# Simpan input OTA sementara per user
pending_inputs = {}

@dp.message(Command("dump"))
async def cmd_dump(message: types.Message):
    await message.answer("Silakan kirim file OTA (.zip/payload.bin) atau URL OTA:")

@dp.message()
async def handle_ota(message: types.Message):
    ota_input = None
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
            return

    # Simpan input OTA untuk user ini
    pending_inputs[message.from_user.id] = ota_input

    # List partisi
    try:
        result = subprocess.check_output(["./otaripper", "-l", ota_input], text=True)
        partitions = [p.strip() for p in result.splitlines() if p.strip()]
    except Exception as e:
        await message.answer(f"Gagal membaca OTA: {e}")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Dump Full", callback_data="full")],
        [InlineKeyboardButton(text="Dump Partition", callback_data="part")]
    ])
    await message.answer(
        "Input OTA diterima ✅\n\nDaftar partisi:\n" + "\n".join(partitions) + "\n\nPilih mode ekstraksi:",
        reply_markup=kb
    )

@dp.callback_query()
async def process_dump(callback_query: types.CallbackQuery):
    mode = callback_query.data
    ota_input = pending_inputs.get(callback_query.from_user.id)
    if not ota_input:
        await callback_query.message.answer("Tidak ada input OTA tersimpan. Kirim ulang dengan /dump.")
        return

    output_dir = "extracted"
    os.makedirs(output_dir, exist_ok=True)

    if mode == "full":
        cmd = ["./otaripper", ota_input, "-o", output_dir, "--print-hash", "--stats"]
    else:
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

    logging.info("Ekstraksi selesai, mengirim hasil ke user...")
    zip_file = FSInputFile("result_with_hash.zip")
    await bot.send_document(callback_query.from_user.id, zip_file)

    # Kirim juga file hashes.json terpisah
    json_file = FSInputFile("hashes.json")
    await bot.send_document(callback_query.from_user.id, json_file)

async def main():
    logging.info("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
