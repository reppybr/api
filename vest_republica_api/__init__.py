from flask import Flask, jsonify, request
from flask_cors import CORS
import os

def create_app(config_name='default'):
    app = Flask(__name__)
    
    # Importação ABSOLUTA para evitar problemas
    from .config import Config
    
    # Configuração
    app.config.from_object(Config[config_name])

    # 🔥 CORS MEGA PERMISSIVO
    CORS(app, 
         resources={r"/*": {"origins": "*"}},
         supports_credentials=True,
         allow_headers=["*"],
         methods=["*"],
         expose_headers=["*"])

    # Handler para requisições OPTIONS (CORS preflight)
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            response = jsonify({"status": "success"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            response.headers.add("Access-Control-Allow-Headers", "*")
            response.headers.add("Access-Control-Allow-Methods", "*")
            return response

    # Registrar Blueprints
    from .api.auth import auth_bp
    from .api.dados import dados_bp
    from .api.plans import plans_bp
    from .api.pagamentos import pagamentos_bp


    from .api.calouros import calouros_bp

    from .api.filtros import filtros_bp
    app.register_blueprint(calouros_bp, url_prefix='/calouros')
    from .api.config import config_bp
    app.register_blueprint(filtros_bp, url_prefix='/filtros_bp')
    app.register_blueprint(pagamentos_bp, url_prefix='/pagamentos')
    app.register_blueprint(config_bp, url_prefix='/config')
    app.register_blueprint(plans_bp, url_prefix='/plans')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dados_bp, url_prefix='/api/v1')

    # Health check básico
    @app.route('/')
    def root():
        return jsonify({"message": "Vest Republica API está funcionando!"}), 200

    @app.route('/health')
    def health_check():
        return jsonify({"status": "healthy"}), 200
    
    return app

# 🔥 ADICIONE ESTA PARTE para poder executar diretamente
if __name__ == '__main__':
    app = create_app('development')
    app.run(host="localhost", port=5000, debug=True)