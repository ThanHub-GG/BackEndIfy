from flask import Flask, request, jsonify
from flask_cors import CORS
from yt_dlp import YoutubeDL
from functools import lru_cache
import requests
import random
import os

app = Flask(__name__)
CORS(app)

GLOBAL_RANDOM_POOLS = [
    "Top Hits Indonesia", "Lagu Populer Mahalini", "Tulus Hits",
    "Judika Terbaru", "Lagu Viral TikTok", "Noah Band Pilihan",
    "Sheila on 7 Hits", "Hivi Kereta Kencana", "Dewa 19 Kangen"
]

# Daftar API Public Node sebagai cadangan jika IP Railway diblokir YouTube
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://api.piped.privacydev.net",
    "https://pipedapi.mha.fi",
    "https://pipedapi.adminforge.de"
]

INVIDIOUS_INSTANCES = [
    "https://vid.puffyan.us",
    "https://invidious.nerdvpn.de",
    "https://inv.riverside.rocks"
]

YDL_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'socket_timeout': 10,
    'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
}

SEARCH_OPTS = {
    **YDL_OPTS,
    'extract_flat': 'in_playlist',
    'default_search': 'ytsearch8',
}

@lru_cache(maxsize=100)
def fetch_search_flat(query):
    try:
        with YoutubeDL(SEARCH_OPTS) as ydl:
            return ydl.extract_info(f"ytsearch8:{query}", download=False)
    except Exception as e:
        print(f"Search flat error: {e}")
        return None

def get_stream_from_piped(video_id):
    """Mendapatkan stream audio via Piped API Node"""
    for instance in PIPED_INSTANCES:
        try:
            r = requests.get(f"{instance}/streams/{video_id}", timeout=6)
            if r.status_code == 200:
                data = r.json()
                audio_streams = data.get('audioStreams', [])
                if audio_streams:
                    # Cari format m4a/mp4 agar kompatibel dengan Safari iOS / Chrome
                    for s in audio_streams:
                        if 'm4a' in s.get('format', '').lower() or 'mp4' in s.get('mimeType', '').lower():
                            return s.get('url')
                    return audio_streams[0].get('url')
        except Exception as e:
            print(f"Piped Node ({instance}) failed: {e}")
    return None

def get_stream_from_invidious(video_id):
    """Mendapatkan stream audio via Invidious API Node"""
    for instance in INVIDIOUS_INSTANCES:
        try:
            r = requests.get(f"{instance}/api/v1/videos/{video_id}", timeout=6)
            if r.status_code == 200:
                data = r.json()
                adaptive_formats = data.get('adaptiveFormats', [])
                for fmt in adaptive_formats:
                    if 'audio' in fmt.get('type', ''):
                        return fmt.get('url')
        except Exception as e:
            print(f"Invidious Node ({instance}) failed: {e}")
    return None

def resolve_stream_robust(video_id):
    """Sistem pencarian stream bertingkat (Anti-Block)"""
    # 1. Coba Piped API
    stream_url = get_stream_from_piped(video_id)
    if stream_url:
        return stream_url

    # 2. Fallback ke Invidious API
    stream_url = get_stream_from_invidious(video_id)
    if stream_url:
        return stream_url

    # 3. Fallback ke yt-dlp lokal
    try:
        with YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            if info and info.get('url'):
                return info.get('url')
            formats = info.get('formats', []) if info else []
            for f in formats:
                if f.get('vcodec') == 'none' and f.get('url'):
                    return f.get('url')
    except Exception as e:
        print(f"yt-dlp fallback failed: {e}")

    return None

def format_duration(seconds):
    try:
        seconds = int(seconds or 0)
        return f"{seconds // 60}:{seconds % 60:02d}"
    except:
        return "0:00"

def entry_to_song(entry, album_label='YouTube Stream'):
    thumbnails = entry.get('thumbnails', [])
    return {
        'id': entry.get('id'),
        'title': entry.get('title', 'Unknown Title'),
        'artist': entry.get('uploader') or entry.get('channel') or 'Unknown Artist',
        'album': album_label,
        'dur': format_duration(entry.get('duration', 0)),
        'cover': thumbnails[-1]['url'] if thumbnails else f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg",
    }

@app.route('/api/search', methods=['GET'])
def search_song():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Query tidak boleh kosong'}), 400
    try:
        info = fetch_search_flat(query)
        if not info or 'entries' not in info:
            return jsonify({'results': []})
            
        results = []
        for entry in info.get('entries', []):
            if not entry or not entry.get('id'):
                continue
            results.append(entry_to_song(entry))
        return jsonify({'results': results})
    except Exception as e:
        print(f"Error search: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stream/<video_id>', methods=['GET'])
def get_stream(video_id):
    try:
        stream_url = resolve_stream_robust(video_id)
        if not stream_url:
            return jsonify({'error': 'Audio stream tidak tersedia'}), 404
        return jsonify({'url': stream_url})
    except Exception as e:
        print(f"Error stream: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/random', methods=['GET'])
def random_song():
    try:
        random_query = random.choice(GLOBAL_RANDOM_POOLS)
        info = fetch_search_flat(random_query)
        entries = [e for e in info.get('entries', []) if e and e.get('id')] if info else []
        if not entries:
            return jsonify({'error': 'Gagal mengambil lagu acak'}), 500

        random_entry = random.choice(entries)
        song = entry_to_song(random_entry, album_label='Global Random Stream')
        song['url'] = resolve_stream_robust(song['id'])
        return jsonify(song)
    except Exception as e:
        print(f"Error random: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
