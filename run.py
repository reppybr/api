from vest_republica_api import create_app
import os

app = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    app.run(host="localhost", port=5000, debug=True)