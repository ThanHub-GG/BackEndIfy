from flask import Flask, request, jsonify
from flask_cors import CORS
from yt_dlp import YoutubeDL
from functools import lru_cache
from pypresence import Presence
import time
import random
import os

app = Flask(__name__)
CORS(app)

# ==== Konfigurasi Discord RPC ====
client_id = '1531324674934308924'  # Ganti dengan Client ID Discord Developer milikmu jika ada
rpc = None
try:
    rpc = Presence(client_id)
    rpc.connect()
    print("✅ Berhasil terhubung ke Discord RPC!")
except Exception as e:
    print("⚠️ Gagal terhubung ke Discord (Pastikan aplikasi Discord terbuka).")

# Daftar cadangan kata kunci global untuk lagu bebas/acak
GLOBAL_RANDOM_POOLS = [
    "Top Hits Indonesia 2026", "Lagu Populer Mahalini", "Tulus Hits",
    "Judika Terbaru", "Lagu Viral TikTok", "Noah Band Pilihan",
    "Feast Peradaban", "Sheila on 7 Hits", "Hivi Kereta Kencana",
    "Rizky Febian Lagu Terbaik", "Denny Caknan Niken Salindry", "Dewa 19 Kangen"
]

# ==== Opsi yt-dlp: PENCARIAN (cepat, metadata saja, tanpa resolve stream) ====
# extract_flat='in_playlist' membuat yt-dlp TIDAK membuka tiap video satu-satu
# untuk mengambil format/stream URL-nya — ini yang membuat pencarian lama
# sebelumnya, karena setiap request search dulu menunggu 3x resolve audio.
SEARCH_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': 'in_playlist',
    'skip_download': True,
    'default_search': 'ytsearch8',
    'socket_timeout': 8,if
}

# ==== Opsi yt-dlp: RESOLVE STREAM (hanya dipanggil untuk 1 video saat diputar) ====
STREAM_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'noplaylist': True,
    'socket_timeout': 10,
}

# Cache hasil pencarian (metadata) — query yang sama tidak perlu hit YouTube lagi
@lru_cache(maxsize=100)
def fetch_search_flat(query):
    with YoutubeDL(SEARCH_OPTS) as ydl:
        return ydl.extract_info(f"ytsearch8:{query}", download=False)

# Cache stream URL per video_id dengan masa berlaku (URL audio YouTube expire
# setelah beberapa jam), supaya klik ulang lagu yang sama tidak resolve ulang
# tapi juga tidak menyajikan link basi.
_stream_cache = {}
STREAM_TTL_SECONDS = 5 * 3600  # ~5 jam, di bawah masa expire link YouTube

def resolve_stream(video_id):
    now = time.time()
    cached = _stream_cache.get(video_id)
    if cached and (now - cached['ts']) < STREAM_TTL_SECONDS:
        return cached['url']

    with YoutubeDL(STREAM_OPTS) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

    stream_url = info.get('url')
    if stream_url:
        _stream_cache[video_id] = {'url': stream_url, 'ts': now}
    return stream_url


def format_duration(seconds):
    seconds = seconds or 0
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def entry_to_song(entry, album_label='YouTube Stream'):
    thumbnails = entry.get('thumbnails', [])
    return {
        'id': entry.get('id'),
        'title': entry.get('title', 'Unknown'),
        'artist': entry.get('uploader') or entry.get('channel') or 'Unknown Artist',
        'album': album_label,
        'dur': format_duration(entry.get('duration', 0)),
        'cover': thumbnails[-1]['url'] if thumbnails else '',
    }


@app.route('/api/search', methods=['GET'])
def search_song():
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Query tidak boleh kosong'}), 400
    try:
        info = fetch_search_flat(query)
        results = []
        for entry in info.get('entries', []):
            if not entry or not entry.get('id'):
                continue
            # Tidak ada 'url' stream di sini — frontend resolve lewat
            # /api/stream/<id> hanya untuk lagu yang benar-benar diklik.
            results.append(entry_to_song(entry))
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stream/<video_id>', methods=['GET'])
def get_stream(video_id):
    try:
        stream_url = resolve_stream(video_id)
        if not stream_url:
            return jsonify({'error': 'Gagal mendapatkan stream audio'}), 500
        return jsonify({'url': stream_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/random', methods=['GET'])
def random_song():
    try:
        random_query = random.choice(GLOBAL_RANDOM_POOLS)
        info = fetch_search_flat(random_query)
        entries = [e for e in info.get('entries', []) if e and e.get('id')]
        if not entries:
            return jsonify({'error': 'Gagal mengambil lagu acak'}), 500

        random_entry = random.choice(entries)
        song = entry_to_song(random_entry, album_label='Global Random Stream')

        # Untuk /api/random kita resolve stream-nya sekalian (hanya 1 video,
        # bukan semua hasil pencarian), karena lagu ini langsung diputar otomatis.
        song['url'] = resolve_stream(song['id'])
        return jsonify(song)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==== Endpoint Discord RPC ====
@app.route('/api/rpc', methods=['POST'])
def update_rpc():
    global rpc
    data = request.json or {}
    state = data.get('state')  # 'playing' atau 'paused'

    try:
        if rpc is None:
            rpc = Presence(client_id)

        try:
            if state == 'playing':
                rpc.update(
                    state=data.get('artist', 'Artist'),
                    details=data.get('title', 'Song Title'),
                    large_image="https://i.imgur.com/8QG3X8r.png",
                    large_text="Mendengarkan di THANIFY",
                    start=int(time.time())
                )
            else:
                rpc.clear()
        except Exception:
            rpc.connect()
            if state == 'playing':
                rpc.update(
                    state=data.get('artist', 'Artist'),
                    details=data.get('title', 'Song Title'),
                    large_image="https://i.imgur.com/8QG3X8r.png",
                    large_text="Mendengarkan di THANIFY",
                    start=int(time.time())
                )
            else:
                rpc.clear()

        return jsonify({'status': 'sukses'})

    except Exception:
        return jsonify({'status': 'diabaikan', 'pesan': 'Discord belum terbuka'}), 200


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)