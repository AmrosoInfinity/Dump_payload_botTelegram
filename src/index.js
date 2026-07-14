export default {
  async fetch(request) {
    const url = new URL(request.url);
    const file = url.searchParams.get("file");
    const repo = url.searchParams.get("repo");
    
    if (!file || !repo) {
      return new Response("Akses Ditolak: Parameter tidak lengkap.", { status: 403 });
    }

    const targetUrl = `https://github.com/${repo}/releases/download/OTA-Dumps/${file}`;

    const html = `
      <!DOCTYPE html>
      <html lang="id">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verifikasi Keamanan</title>
        <style>
          body { font-family: system-ui, sans-serif; text-align: center; margin-top: 15vh; background-color: #f9fafb; color: #111827; }
          .container { max-width: 500px; margin: 0 auto; padding: 2rem; background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
          h2 { font-size: 1.5rem; margin-bottom: 1rem; }
          .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 20px auto; }
          @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
          a { color: #3b82f6; text-decoration: none; font-weight: 500; }
          a:hover { text-decoration: underline; }
        </style>
      </head>
      <body>
        <div class="container">
          <h2>Memeriksa Keamanan Tautan...</h2>
          <p>Tautan unduhan Anda sedang disiapkan.</p>
          <div class="spinner"></div>
          <p id="msg">Anda akan diarahkan dalam <span id="countdown">3</span> detik.</p>
          <p style="font-size: 0.875rem; margin-top: 2rem; color: #6b7280;">Jika tidak otomatis dialihkan, <a href="${targetUrl}">Klik di sini</a>.</p>
        </div>
        <script>
          let timeLeft = 3;
          const timer = setInterval(() => {
            timeLeft--;
            document.getElementById('countdown').innerText = timeLeft;
            if (timeLeft <= 0) {
              clearInterval(timer);
              document.getElementById('msg').innerText = "Mengalihkan...";
              window.location.href = "${targetUrl}";
            }
          }, 1000);
        </script>
      </body>
      </html>
    `;

    return new Response(html, {
      headers: { "content-type": "text/html;charset=UTF-8" },
    });
  }
}
