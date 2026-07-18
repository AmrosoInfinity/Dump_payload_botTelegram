export default {
  async fetch(request, env) {
    // 1. Menangani preflight request (CORS) agar tidak diblokir oleh browser
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type"
        }
      });
    }

    // 2. Menangani request utama dari Web App
    if (request.method === "POST") {
      try {
        const body = await request.json();
        
        // URL API GitHub Actions (Pastikan username dan nama repositori benar)
        const ghUrl = "https://api.github.com/repos/AmrosoInfinity/Dump_payload_botTelegram/actions/workflows/bot.yml/dispatches";

        // Mengirim instruksi ke GitHub
        const ghResponse = await fetch(ghUrl, {
          method: "POST",
          headers: {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Cloudflare-Worker",
            // GH_PAT adalah token GitHub rahasia yang disimpan di Environment Cloudflare
            "Authorization": `token ${env.GH_PAT}` 
          },
          body: JSON.stringify({
            ref: "main", // Branch yang digunakan (biasanya 'main' atau 'master')
            inputs: {
              chat_id: String(body.chat_id),
              url: body.url,
              partitions: body.partitions || ""
            }
          })
        });

        if (!ghResponse.ok) {
          const errText = await ghResponse.text();
          throw new Error(`GitHub API Error: ${errText}`);
        }

        // Jika berhasil, kirim respons kembali ke Web App
        return new Response(JSON.stringify({ success: true, message: "Mesin menyala!" }), {
          headers: { 
            "Access-Control-Allow-Origin": "*", 
            "Content-Type": "application/json" 
          }
        });

      } catch (error) {
        return new Response(JSON.stringify({ success: false, error: error.message }), {
          status: 500, 
          headers: { 
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json"
          }
        });
      }
    }

    // Jika metode selain POST atau OPTIONS
    return new Response("Hanya menerima metode POST.", { status: 405 });
  }
};
