const tg = window.Telegram.WebApp;
tg.expand();
tg.MainButton.hide();

// GANTI URL INI DENGAN URL WORKER CLOUDFLARE KAMU
const WORKER_API_URL = "https://api-trigger.ahmadjulio01234.workers.dev/";

async function startEngine() {
    const urlInput = document.getElementById('otaUrl').value.trim();
    const partInput = document.getElementById('partitions').value.trim();

    if (!urlInput) {
        tg.showAlert("Harap masukkan URL OTA yang valid.");
        return;
    }

    document.getElementById('input-screen').classList.add('hidden');
    document.getElementById('loader-screen').classList.remove('hidden');

    const statusEl = document.getElementById('status-text');
    const steps = [
        "Menghubungkan ke GitHub Actions...",
        "Menghidupkan mesin Virtual Linux...",
        "Menyiapkan modul otaripper...",
        "Mengirim payload eksekusi..."
    ];

    for (let i = 0; i < steps.length; i++) {
        statusEl.innerText = steps[i];
        await new Promise(r => setTimeout(r, 800));
    }

    const chatId = tg.initDataUnsafe?.user?.id || "123456789"; 

    try {
        const payload = { chat_id: chatId, url: urlInput, partitions: partInput };

        const response = await fetch(WORKER_API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            statusEl.innerText = "Mesin berhasil dijalankan!";
            document.querySelector('.status-sub').innerText = "Ekstraksi berjalan di background. File akan dikirim ke chat. Menutup aplikasi...";
            setTimeout(() => { tg.close(); }, 3000);
        } else {
            throw new Error("Gagal memicu server.");
        }
    } catch (error) {
        statusEl.innerText = "Terjadi Kesalahan Koneksi.";
        statusEl.style.color = "var(--danger)";
        document.querySelector('.status-sub').innerText = error.message;
        document.querySelector('.gear-icon').style.animation = "none"; 
        
        setTimeout(() => {
            document.getElementById('loader-screen').classList.add('hidden');
            document.getElementById('input-screen').classList.remove('hidden');
            document.querySelector('.gear-icon').style.animation = "spin 2s linear infinite";
            statusEl.style.color = "var(--text-main)";
        }, 4000);
    }
}
