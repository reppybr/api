from flask_jwt_extended import JWTManager

# Inicializa o manager de JWT. Ele será usado para validar tokens.
jwt = JWTManager()

def init_extensions(app):
    """Inicializa todas as extensões registradas com a aplicação Flask."""
    # O JWTManager precisa ser configurado com a aplicação.
    jwt.init_app(app)
    
    # Se tivéssemos SQLAlchemy/Marshmallow, seriam inicializados aqui.
    # db.init_app(app)
    # ma.init_app(app)
    pass
