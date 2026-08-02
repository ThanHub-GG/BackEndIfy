from flask import Flask, request, jsonify
from flask_cors import CORS
from yt_dlp import YoutubeDL
from functools import lru_cache
import random
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

GLOBAL_RANDOM_POOLS = [
    "Top Hits Indonesia", "Lagu Populer Mahalini", "Tulus Hits",
    "Judika Terbaru", "Lagu Viral TikTok", "Noah Band Pilihan"
]

YDL_BASE_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'socket_timeout': 15,
    'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }
}

SEARCH_OPTS = {**YDL_BASE_OPTS, 'extract_flat': 'in_playlist', 'default_search': 'ytsearch8'}
STREAM_OPTS = {**YDL_BASE_OPTS, 'noplaylist': True}

@lru_cache(maxsize=100)
def fetch_search_flat(query):
    try:
        with YoutubeDL(SEARCH_OPTS) as ydl:
            return ydl.extract_info(f"ytsearch8:{query}", download=False)
    except Exception as e:
        print(f"Search extraction error: {e}")
        return None

def resolve_stream(video_id):
    try:
        with YoutubeDL(STREAM_OPTS) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            if not info:
                return None
            if info.get('url'):
                return info.get('url')
            for f in info.get('formats', []):
                if f.get('vcodec') == 'none' and f.get('url'):
                    return f.get('url')
    except Exception as e:
        print(f"Stream resolution error for {video_id}: {e}")
    return None

def format_duration(seconds):
    try:
        seconds = int(seconds or 0)
        return f"{seconds // 60}:{seconds % 60:02d}"
    except:
        return "0:00"

@app.route('/api/search', methods=['GET'])
def search_song():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'results': []}), 200
    try:
        info = fetch_search_flat(query)
        if not info or 'entries' not in info:
            return jsonify({'results': []}), 200
            
        results = []
        for entry in info.get('entries', []):
            if not entry or not entry.get('id'):
                continue
            vid_id = entry.get('id')
            title = entry.get('title', 'Unknown Title')
            artist = entry.get('uploader') or entry.get('channel') or 'Unknown Artist'
            duration = entry.get('duration', 0)
            
            thumbnails = entry.get('thumbnails', [])
            cover_url = thumbnails[-1]['url'] if thumbnails else f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
            
            results.append({
                'id': vid_id,
                'title': title,
                'artist': artist,
                'album': 'YouTube Stream',
                'dur': format_duration(duration),
                'cover': cover_url
            })
        return jsonify({'results': results}), 200
    except Exception as e:
        print(f"API Search Error: {e}")
        return jsonify({'results': []}), 200

@app.route('/api/stream/<video_id>', methods=['GET'])
def get_stream(video_id):
    try:
        if not video_id:
            return jsonify({'error': 'ID tidak valid'}), 400
        stream_url = resolve_stream(video_id)
        if not stream_url:
            return jsonify({'error': 'Gagal mengambil stream audio'}), 500
        return jsonify({'url': stream_url}), 200
    except Exception as e:
        print(f"API Stream Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'online'}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
