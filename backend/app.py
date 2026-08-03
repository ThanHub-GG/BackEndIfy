from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from yt_dlp import YoutubeDL
from functools import lru_cache
import requests
import random
import os
import yt_dlp
import traceback

print("yt-dlp version:", yt_dlp.version.__version__)

app = Flask(__name__)
CORS(app)

GLOBAL_RANDOM_POOLS = [
    "Top Hits Indonesia", "Lagu Populer Mahalini", "Tulus Hits",
    "Judika Terbaru", "Lagu Viral TikTok", "Noah Band Pilihan"
]

YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "socket_timeout": 20,
    "extractor_retries": 3,
    "retries": 3,
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    },
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

# Urutan client diubah agar mweb atau android berada di awal untuk meminimalkan blokir bot
CLIENTS = [
    "mweb",
    "android",
    "ios",
    "web",
    "tv"
]

def resolve_stream(video_id):
    for client in CLIENTS:
        try:
            print(f"Trying client: {client}")

            opts = {
                **STREAM_OPTS,
                "extractor_args": {
                    "youtube": {
                        "player_client": [client],
                        # Memaksa melewati pemeriksaan client web/mweb default jika perlu
                        "skip": ["dash", "hls"]
                    }
                }
            }

            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}",
                    download=False
                )

            formats = info.get("formats", [])

            audio = [
                f for f in formats
                if f.get("vcodec") == "none"
                and f.get("acodec") not in (None, "none")
                and f.get("url")
            ]

            if audio:
                audio.sort(
                    key=lambda f: (
                        f.get("ext") == "m4a",
                        str(f.get("acodec", "")).startswith("mp4a"),
                        f.get("abr") or 0
                    ),
                    reverse=True
                )
                print(f"Success with {client}")
                return audio[0]["url"]

            fallback = [
                f for f in formats
                if f.get("acodec") not in (None, "none")
                and f.get("url")
            ]

            if fallback:
                preferred = ["140", "139", "18"]
                for pid in preferred:
                    for f in fallback:
                        if f.get("format_id") == pid:
                            print("Using preferred format:", pid)
                            return f["url"]

                print("Using fallback format:", fallback[0]["format_id"])
                return fallback[0]["url"]

        except Exception as e:
            print(f"Client {client} failed: {e}")

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

@app.route("/api/stream/<video_id>")
def get_stream(video_id):
    stream_url = resolve_stream(video_id)

    if not stream_url:
        return jsonify({"error": "Stream tidak ditemukan atau diblokir YouTube"}), 500

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        )
    }

    if request.headers.get("Range"):
        headers["Range"] = request.headers["Range"]

    try:
        r = requests.get(
            stream_url,
            headers=headers,
            stream=True,
            allow_redirects=True,
            timeout=10
        )
    except Exception as e:
        print(f"Proxy request error: {e}")
        return jsonify({"error": "Gagal menghubungkan ke server stream"}), 500

    response_headers = {}
    for h in (
        "Content-Type",
        "Content-Length",
        "Content-Range",
        "Accept-Ranges",
        "Content-Encoding",
    ):
        if h in r.headers:
            response_headers[h] = r.headers[h]

    response_headers["Access-Control-Allow-Origin"] = "*"
    response_headers["Cache-Control"] = "no-cache"

    return Response(
        r.iter_content(chunk_size=1024 * 64),
        status=r.status_code,
        headers=response_headers,
        direct_passthrough=True,
    )

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
