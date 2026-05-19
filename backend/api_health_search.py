"""Endpoints de salud del servidor y búsqueda.

Extraído de server.py para reducir tamaño sin cambiar comportamiento.
"""

from __future__ import annotations

from backend.deps import HealthSearchDeps


def register_health_search_endpoints(
    app,
    deps: HealthSearchDeps,
):
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Estado del servidor"""
        with deps.downloads_lock:
            active_count = len([
                d for d in deps.active_downloads.values()
                if d['status'] in ['processing', 'downloading', 'converting']
            ])

        return deps.jsonify({
            'status': 'ok',
            'ffmpeg_available': deps.check_ffmpeg(),
            'active_downloads': active_count,
            'queue_size': deps.download_queue.qsize(),
            'max_concurrent': deps.max_concurrent_downloads,
            'downloads_folder': str(deps.download_folder),
            'frontend_folder': str(deps.frontend_folder),
            'mode': 'websocket'
        })

    @app.route('/api/search', methods=['POST', 'OPTIONS'])
    @deps.limiter.limit("10 per minute")
    def search_youtube():
        """Proxy para YouTube Search API"""
        if deps.request.method == 'OPTIONS':
            return '', 204

        if not deps.config.YOUTUBE_API_KEY:
            return deps.jsonify({'error': 'YouTube API key no configurada'}), 503

        try:
            from googleapiclient.discovery import build

            data = deps.request.json
            query = data.get('query')
            max_results = data.get('maxResults', 10)

            if not query:
                return deps.jsonify({'error': 'Query requerida'}), 400

            youtube = build('youtube', 'v3', developerKey=deps.config.YOUTUBE_API_KEY)

            search_response = youtube.search().list(
                q=query,
                part='id,snippet',
                maxResults=max_results,
                type='video'
            ).execute()

            results = []
            for item in search_response.get('items', []):
                video_id = item['id']['videoId']
                results.append({
                    'id': video_id,
                    'url': f'https://www.youtube.com/watch?v={video_id}',
                    'title': item['snippet']['title'],
                    'thumbnail': item['snippet']['thumbnails']['medium']['url'],
                    'channelTitle': item['snippet']['channelTitle'],
                    'duration': None  # Would need additional API call
                })

            return deps.jsonify({'success': True, 'results': results})

        except Exception as e:
            deps.logger.error(f"Search error: {str(e)}")
            return deps.jsonify({'error': str(e)}), 500
