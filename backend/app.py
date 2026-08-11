from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from ytmusicapi import YTMusic
import yt_dlp
import requests
import os
import time
import traceback

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,Range"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

# Inisialisasi aman
try:
    _yt = YTMusic()
except Exception as e:
    print(f"Warning YTMusic init: {e}")

_cache = {}
CACHE_TTL_SECONDS = 300

PIPED_INSTANCES = [
    'https://pipedapi.kavin.rocks',
    'https://pipedapi.adminforge.de',
    'https://api.piped.yt',
    'https://pipedapi.tokhmi.xyz'
]

def cached(key, fn):
    now = time.time()
    hit = _cache.get(key)
    if hit is not None and now - hit[0] < CACHE_TTL_SECONDS:
        return hit[1]
    result = fn()
    _cache[key] = (now, result)
    return result

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Backend is running!"}), 200

@app.route('/api/search', methods=['GET', 'OPTIONS'])
def search_song():
    if request.method == 'OPTIONS':
        return '', 200
        
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'results': []}), 200
    
    try:
        search_results = cached(
            f"search:{query}", 
            lambda: _yt.search(query, filter="songs", limit=20)
        )
        
        results = []
        for entry in search_results:
            vid_id = entry.get('videoId')
            if not vid_id:
                continue
            
            artists_list = entry.get('artists', [])
            artist_name = artists_list[0]['name'] if artists_list else 'Unknown Artist'
            
            thumbnails = entry.get('thumbnails', [])
            cover_url = thumbnails[-1]['url'] if thumbnails else f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
            
            duration_str = entry.get('duration', '0:00')
            
            results.append({
                'id': vid_id,
                'title': entry.get('title', 'Unknown Title'),
                'artist': artist_name,
                'album': entry.get('album', {}).get('name', 'YouTube Music'),
                'dur': duration_str,
                'cover': cover_url
            })
            
        return jsonify({'results': results}), 200
    except Exception as e:
        print(f"API Search Error: {e}")
        return jsonify({'results': []}), 200

@app.route("/api/stream/<video_id>", methods=['GET', 'OPTIONS'])
def get_stream(video_id):
    if request.method == 'OPTIONS':
        return '', 200
        
    stream_url = None
    
    # Daftar instance Invidious publik yang stabil untuk cadangan stream
    INVIDIOUS_INSTANCES = [
        'https://invidious.privacyredirect.com',
        'https://vid.priv.au',
        'https://inv.nadeko.net',
        'https://invidious.flokinet.to'
    ]

    for instance in INVIDIOUS_INSTANCES:
        try:
            res = requests.get(f"{instance}/api/v1/videos/{video_id}", timeout=5)
            if res.status_code == 200:
                data = res.json()
                adaptive_formats = data.get('adaptiveFormats', [])
                # Cari format audio dengan bitrate terbaik
                audio_streams = [f for f in adaptive_formats if 'audio' in f.get('type', '')]
                if audio_streams:
                    audio_streams.sort(key=lambda x: int(x.get('bitrate', 0)), reverse=True)
                    if audio_streams[0].get('url'):
                        stream_url = audio_streams[0]['url']
                        break
        except Exception:
            continue

    if not stream_url:
        return jsonify({"error": "Gagal mendapatkan stream audio dari server Invidious"}), 500

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        }
        if request.headers.get("Range"):
            headers["Range"] = request.headers["Range"]

        r = requests.get(stream_url, headers=headers, stream=True, allow_redirects=True, timeout=15)

        response_headers = {}
        for h in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "Content-Encoding"):
            if h in r.headers:
                response_headers[h] = r.headers[h]

        if "Content-Type" not in response_headers or response_headers["Content-Type"] == "application/octet-stream":
            response_headers["Content-Type"] = "audio/mp4"

        return Response(
            r.iter_content(chunk_size=1024 * 64),
            status=r.status_code,
            headers=response_headers,
            direct_passthrough=True,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
