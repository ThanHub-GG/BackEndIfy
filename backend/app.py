from flask import Flask, request, jsonify
from flask_cors import CORS
from yt_dlp import YoutubeDL
from functools import lru_cache
import random
import os

app = Flask(__name__)
CORS(app)

GLOBAL_RANDOM_POOLS = [
    "Top Hits Indonesia", "Lagu Populer Mahalini", "Tulus Hits",
    "Judika Terbaru", "Lagu Viral TikTok", "Noah Band Pilihan"
]

YDL_BASE_OPTS = {
    'format': 'bestaudio[ext=m4a]/bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'socket_timeout': 15,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
}

SEARCH_OPTS = {**YDL_BASE_OPTS, 'extract_flat': 'in_playlist', 'default_search': 'ytsearch8'}
STREAM_OPTS = {**YDL_BASE_OPTS, 'noplaylist': True}

@lru_cache(maxsize=100)
def fetch_search_flat(query):
    with YoutubeDL(SEARCH_OPTS) as ydl:
        return ydl.extract_info(f"ytsearch8:{query}", download=False)

def resolve_stream(video_id):
    # Percobaan 1: Menggunakan opsi standar
    try:
        with YoutubeDL(STREAM_OPTS) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        
        # Cari format audio langsung yang valid
        if info.get('url'):
            return info.get('url')
            
        formats = info.get('formats', [])
        for f in formats:
            if f.get('vcodec') == 'none' and f.get('url'):
                return f.get('url')
    except Exception as e:
        print(f"Stream attempt 1 failed: {e}")

    # Percobaan 2: Fallback dengan format paling longgar jika percobaan 1 gagal
    try:
        fallback_opts = {**STREAM_OPTS, 'format': 'best'}
        with YoutubeDL(fallback_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            if info.get('url'):
                return info.get('url')
    except Exception as e:
        print(f"Stream attempt 2 (fallback) failed: {e}")
        
    return None

def format_duration(seconds):
    seconds = seconds or 0
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"

@app.route('/api/search', methods=['GET'])
def search_song():
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Query kosong'}), 400
    try:
        info = fetch_search_flat(query)
        results = []
        for entry in info.get('entries', []):
            if not entry or not entry.get('id'):
                continue
            thumbnails = entry.get('thumbnails', [])
            results.append({
                'id': entry.get('id'),
                'title': entry.get('title', 'Unknown'),
                'artist': entry.get('uploader') or entry.get('channel') or 'Unknown Artist',
                'album': 'YouTube Stream',
                'dur': format_duration(entry.get('duration', 0)),
                'cover': thumbnails[-1]['url'] if thumbnails else f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg",
            })
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stream/<video_id>', methods=['GET'])
def get_stream(video_id):
    try:
        stream_url = resolve_stream(video_id)
        if not stream_url:
            return jsonify({'error': 'Gagal mengambil stream audio'}), 500
        return jsonify({'url': stream_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/random', methods=['GET'])
def random_song():
    try:
        info = fetch_search_flat(random.choice(GLOBAL_RANDOM_POOLS))
        entries = [e for e in info.get('entries', []) if e and e.get('id')]
        if not entries:
            return jsonify({'error': 'Gagal'}), 500
        entry = random.choice(entries)
        video_id = entry.get('id')
        stream_url = resolve_stream(video_id)
        if not stream_url:
            return jsonify({'error': 'Format tidak didukung'}), 500
            
        thumbnails = entry.get('thumbnails', [])
        song = {
            'id': video_id,
            'title': entry.get('title', 'Unknown'),
            'artist': entry.get('uploader') or entry.get('channel') or 'Unknown',
            'album': 'Random',
            'dur': format_duration(entry.get('duration', 0)),
            'cover': thumbnails[-1]['url'] if thumbnails else '',
            'url': stream_url
        }
        return jsonify(song)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
