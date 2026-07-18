import subprocess
import os
import zipfile
import uuid
from datetime import datetime

def run_otaripper(ota_url, partitions):
    """Menjalankan otaripper dan mengompresinya ke ZIP"""
    job_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = f"extracted_{job_id}"
    zip_filename = f"OTA_Dump_{job_id}_{timestamp}.zip"
    
    cmd = ["./otaripper", ota_url, "-o", out_dir, "-n", "--print-hash"]
    
    if partitions and partitions.strip():
        clean_parts = partitions.strip().replace(" ", "")
        cmd.extend(["-p", clean_parts])
        
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"Error otaripper:\n{result.stderr[:1000]}")
        
    if not os.path.exists(out_dir) or not os.listdir(out_dir):
        raise Exception("Ekstraksi selesai, tapi folder kosong.")

    # Compress to ZIP
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(out_dir):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.basename(file_path))
                
    file_size_mb = os.path.getsize(zip_filename) / (1024 * 1024)
    return zip_filename, file_size_mb, out_dir
