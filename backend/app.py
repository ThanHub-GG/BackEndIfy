from flask import Flask, request, jsonify
from flask_cors import CORS
from yt_dlp import YoutubeDL
from functools import lru_cache
import time
import random
import os

app = Flask(__name__)
CORS(app)

GLOBAL_RANDOM_POOLS = [
    "Top Hits Indonesia", "Lagu Populer Mahalini", "Tulus Hits",
    "Judika Terbaru", "Lagu Viral TikTok", "Noah Band Pilihan",
    "Sheila on 7 Hits", "Hivi Kereta Kencana", "Dewa 19 Kangen"
]

SEARCH_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': 'in_playlist',
    'skip_download': True,
    'default_search': 'ytsearch8',
    'socket_timeout': 10,
}

STREAM_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'noplaylist': True,
    'socket_timeout': 10,
}

@lru_cache(maxsize=100)
def fetch_search_flat(query):
    with YoutubeDL(SEARCH_OPTS) as ydl:
        return ydl.extract_info(f"ytsearch8:{query}", download=False)

_stream_cache = {}
STREAM_TTL_SECONDS = 5 * 3600

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
            results.append(entry_to_song(entry))
        return jsonify({'results': results})
    except Exception as e:
        print(f"Error pada pencarian: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stream/<video_id>', methods=['GET'])
def get_stream(video_id):
    try:
        stream_url = resolve_stream(video_id)
        if not stream_url:
            return jsonify({'error': 'Gagal mendapatkan stream audio'}), 500
        return jsonify({'url': stream_url})
    except Exception as e:
        print(f"Error pada stream: {str(e)}")
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
        song['url'] = resolve_stream(song['id'])
        return jsonify(song)
    except Exception as e:
        print(f"Error pada random: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
