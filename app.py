from flask import Flask, render_template

from config import MAX_UPLOAD_MB, ensure_dirs


def create_app() -> Flask:
    """Create and configure the Converza Flask application."""
    ensure_dirs()
    application = Flask(__name__)
    application.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_MB * 1024 * 1024

    @application.get('/')
    def index():
        return render_template('index.html')

    @application.get('/healthz')
    def healthz():
        return 'ok', 200, {'Content-Type': 'text/plain; charset=utf-8'}

    return application


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
