from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from ytmusicapi import YTMusic
import yt_dlp
import requests  # <--- PASTIKAN INI ADA DI ATAS
import os

app = Flask(__name__)
CORS(app)

ytmusic = YTMusic()

@app.route('/api/search', methods=['GET'])
def search_song():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'results': []}), 200
    try:
        search_results = ytmusic.search(query, filter="songs")
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

@app.route("/api/stream/<video_id>")
def get_stream(video_id):
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            formats = info.get('formats', [])
            
            # Prioritaskan format m4a atau audio yang memiliki url valid
            audio_formats = [
                f for f in formats 
                if f.get('vcodec') == 'none' and f.get('url')
            ]
            
            if not audio_formats:
                return jsonify({"error": "Format audio tidak ditemukan"}), 500
                
            # Urutkan agar m4a berada di prioritas utama
            audio_formats.sort(key=lambda x: 1 if x.get('ext') == 'm4a' else 0, reverse=True)
            stream_url = audio_formats[0]['url']

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

        # Pastikan Content-Type aman untuk audio HTML5 jika tidak terdeteksi
        if "Content-Type" not in response_headers or response_headers["Content-Type"] == "application/octet-stream":
            response_headers["Content-Type"] = "audio/mp4"

        response_headers["Access-Control-Allow-Origin"] = "*"
        response_headers["Cache-Control"] = "no-cache"

        return Response(
            r.iter_content(chunk_size=1024 * 64),
            status=r.status_code,
            headers=response_headers,
            direct_passthrough=True,
        )
    except Exception as e:
        print(f"Stream error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
