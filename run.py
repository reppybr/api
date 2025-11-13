from vest_republica_api import create_app
import os

app = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    # Render (e outros) define a porta pela variável de ambiente PORT
    port = int(os.environ.get('PORT', 5000))
    
    # Debug deve ser Falso em produção
    # O Render define FLASK_ENV=production por padrão
    is_debug = os.environ.get('FLASK_ENV') != 'production'

    # 👇 A MUDANÇA PRINCIPAL ESTÁ AQUI
    app.run(host="0.0.0.0", port=port, debug=is_debug, threaded=is_debug)
