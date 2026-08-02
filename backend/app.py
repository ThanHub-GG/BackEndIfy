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

YDL_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'socket_timeout': 20,
    'extractor_args': {
        'youtube': {
            'player_client': ['ios', 'web', 'android']
        }
    },
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
    }
}

SEARCH_OPTS = {**YDL_OPTS, 'extract_flat': 'in_playlist', 'default_search': 'ytsearch8'}
STREAM_OPTS = {**YDL_OPTS, 'noplaylist': True}

@lru_cache(maxsize=100)
def fetch_search_flat(query):
    try:
        with YoutubeDL(SEARCH_OPTS) as ydl:
            return ydl.extract_info(f"ytsearch8:{query}", download=False)
    except Exception as e:
        print(f"Search error: {e}")
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
            for f in info.get('formats', []):
                if f.get('url'):
                    return f.get('url')
    except Exception as e:
        print(f"Stream error for {video_id}: {e}")
    return None

def format_duration(seconds):
    try:
        seconds = int(seconds or 0)
        return f"{seconds // 60}:{seconds % 60:02d}"
    except:
        return "0:00"

def entry_to_song(entry):
    thumbnails = entry.get('thumbnails', [])
    vid_id = entry.get('id')
    return {
        'id': vid_id,
        'title': entry.get('title', 'Unknown Title'),
        'artist': entry.get('uploader') or entry.get('channel') or 'Unknown Artist',
        'album': 'YouTube Stream',
        'dur': format_duration(entry.get('duration', 0)),
        'cover': thumbnails[-1]['url'] if thumbnails else f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg",
    }

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
            results.append(entry_to_song(entry))
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
            return jsonify({'error': 'Gagal mendapatkan stream audio'}), 500
        return jsonify({'url': stream_url}), 200
    except Exception as e:
        print(f"API Stream Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
