import os, asyncio, subprocess, json, shutil, logging, re
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TOKEN, request_timeout=60)
dp = Dispatcher()

pending_inputs = {}
selected_partitions = {}

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

    user_id = message.from_user.id
    pending_inputs[user_id] = ota_input
    selected_partitions[user_id] = []

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
    user_id = callback_query.from_user.id
    ota_input = pending_inputs.get(user_id)
    if not ota_input:
        await callback_query.message.answer("Tidak ada input OTA tersimpan. Kirim ulang dengan /dump.")
        return

    output_dir = "extracted"
    os.makedirs(output_dir, exist_ok=True)

    if callback_query.data == "full":
        cmd = ["./otaripper", ota_input, "-o", output_dir, "--print-hash", "--stats"]
        subprocess.run(cmd, check=True)

    elif callback_query.data == "part":
        # tampilkan daftar partisi untuk dipilih
        try:
            result = subprocess.check_output(["./otaripper", "-l", ota_input], text=True)
            partitions = [p.strip() for p in result.splitlines() if p.strip()]
        except Exception as e:
            await callback_query.message.answer(f"Gagal membaca OTA: {e}")
            return

        kb = InlineKeyboardMarkup()
        for p in partitions:
            safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', p)[:60]
            kb.inline_keyboard.append([InlineKeyboardButton(text=p, callback_data=f"choose|{safe_name}")])
        kb.inline_keyboard.append([InlineKeyboardButton(text="Ekstrak Sekarang", callback_data="extract")])

        await callback_query.message.answer(
            "Pilih partisi dengan klik tombol. Setiap klik akan menambahkan nama partisi ke daftar pilihan "
            "(dipisahkan koma). Setelah selesai, tekan Ekstrak Sekarang.",
            reply_markup=kb
        )

    elif callback_query.data.startswith("choose|"):
        part = callback_query.data.split("|", 1)[1]
        if part not in selected_partitions[user_id]:
            selected_partitions[user_id].append(part)
        current = ",".join(selected_partitions[user_id])
        await callback_query.message.answer(f"Pilihan partisi saat ini: {current}")
        await callback_query.answer(f"{part} ditambahkan ✅")
        return

    elif callback_query.data == "extract":
        parts = ",".join(selected_partitions[user_id])
        if not parts:
            await callback_query.message.answer("Belum ada partisi dipilih. Klik partisi dulu.")
            return
        cmd = ["./otaripper", ota_input, "-o", output_dir, "-p", parts, "--print-hash"]
        subprocess.run(cmd, check=True)

    else:
        return

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
    await bot.send_document(user_id, zip_file)

    json_file = FSInputFile("hashes.json")
    await bot.send_document(user_id, json_file)

async def main():
    logging.info("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
