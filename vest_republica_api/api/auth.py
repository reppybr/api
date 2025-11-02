
import os
import datetime
from flask import Blueprint, jsonify, request, g
from supabase import create_client
from functools import wraps

# Cria o blueprint
auth_bp = Blueprint('auth', __name__)

# Configuração do Supabase
SUPABASE_URL = "https://wjstxyjdxijiqnlqawdr.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indqc3R4eWpkeGlqaXFubHFhd2RyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjIwMTE1NTksImV4cCI6MjA3NzU4NzU1OX0.y03cbe2BXsr6i9n4ouaYd7az7QuWH4r7vIYvb7R3_d0"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_or_create_user_profile(supabase_user):
    """
    Busca ou cria perfil do usuário na tabela public.users.
    """
    try:
        print(f"🟡 [AUTH] Buscando usuário com auth_id: {supabase_user.id}")
        
        # Buscar usuário existente
        response = supabase.table("users").select("*").eq("auth_id", supabase_user.id).execute()

        print(f"🟡 [AUTH] Resposta do Supabase (users table): {len(response.data) if response.data else 0} registros")

        if response.data:
            user_data = response.data[0]
            print(f"✅ [AUTH] Usuário encontrado: {user_data['email']} (ID: {user_data['id']})")
            return user_data
        else:
            print("🟡 [AUTH] Criando novo usuário na tabela users...")
            # Criar novo usuário
            user_metadata = supabase_user.user_metadata or {}
            user_data = {
                "auth_id": supabase_user.id,
                "email": supabase_user.email,
                "full_name": user_metadata.get("full_name") or supabase_user.email.split("@")[0],
                "avatar_url": user_metadata.get("avatar_url"),
                "role": "user",
                "email_verified": supabase_user.email_confirmed_at is not None,
                "is_active": True,
                "created_at": datetime.datetime.utcnow().isoformat()
            }

            new_user = supabase.table("users").insert(user_data).execute()
            print(f"🟡 [AUTH] Resposta da criação: {new_user}")
            
            if new_user.data:
                created_user = new_user.data[0]
                print(f"✅ [AUTH] Novo usuário criado: {created_user['email']} (ID: {created_user['id']})")
                return created_user
            else:
                error_msg = "Erro ao criar perfil do usuário no banco de dados"
                print(f"🔴 [AUTH] {error_msg}")
                raise Exception(error_msg)

    except Exception as e:
        print(f"🔴 [AUTH] Erro em get_or_create_user_profile: {str(e)}")
        raise Exception(f"Erro ao processar perfil do usuário: {str(e)}")

def token_required(f):
    """
    Decorator que verifica o token do Supabase.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print("🟡 [AUTH] token_required - Iniciando verificação...")
        
        auth_header = request.headers.get('Authorization')
        print(f"🟡 [AUTH] Authorization header: {auth_header}")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            print("🔴 [AUTH] Token não encontrado ou formato inválido")
            return jsonify({"error": "Token de autorização inválido"}), 401

        token = auth_header.replace("Bearer ", "")
        print(f"🟡 [AUTH] Token recebido (primeiros 20 chars): {token[:20]}...")

        try:
            print("🟡 [AUTH] Verificando token com Supabase...")
            # Verificar token com Supabase
            user_response = supabase.auth.get_user(token)
            print(f"🟡 [AUTH] Resposta do Supabase.auth.get_user: {user_response}")
            
            if not user_response.user:
                print("🔴 [AUTH] Supabase retornou user=None")
                return jsonify({"error": "Token do Supabase inválido"}), 401

            print(f"✅ [AUTH] Token válido! User ID: {user_response.user.id}")
            print(f"🟡 [AUTH] User email: {user_response.user.email}")

            # Buscar ou criar perfil do usuário
            user_profile = get_or_create_user_profile(user_response.user)
            
            # Anexa o perfil do usuário ao objeto 'g' (global) do Flask
            g.user = user_profile
            print(f"✅ [AUTH] Perfil do usuário anexado: {user_profile['email']}")

        except Exception as e:
            print(f"🔴 [AUTH] Exception em token_required: {str(e)}")
            return jsonify({"error": f"Erro ao verificar token: {str(e)}"}), 401

        return f(*args, **kwargs)
    return decorated_function

# --- ROTAS DE AUTENTICAÇÃO ---

@auth_bp.route("/register", methods=["POST"])
def register():
    """Registro tradicional com email/senha"""
    print("🟡 [AUTH] /register chamado")
    user_data = request.get_json()
    if not user_data:
        return jsonify({"error": "Corpo da requisição inválido"}), 400

    try:
        # Criar usuário no Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": user_data.get('email'),
            "password": user_data.get('password'),
            "options": {
                "data": {
                    "full_name": user_data.get('full_name'),
                    "phone": user_data.get('phone')
                }
            }
        })

        print(f"🟡 [AUTH] Resposta do sign_up: {auth_response}")

        if auth_response.user:
            # Criar perfil na tabela public.users
            user_profile = {
                "auth_id": auth_response.user.id,
                "email": user_data.get('email'),
                "full_name": user_data.get('full_name'),
                "phone": user_data.get('phone'),
                "role": "user",
                "email_verified": False,
                "is_active": True,
                "created_at": datetime.datetime.utcnow().isoformat()
            }
            
            insert_response = supabase.table("users").insert(user_profile).execute()
            print(f"🟡 [AUTH] Resposta da inserção na tabela users: {insert_response}")

            return jsonify({
                "message": "Usuário criado com sucesso",
                "user_id": auth_response.user.id,
                "email_verified": False
            }), 201
        else:
            return jsonify({"error": "Erro ao criar usuário no Supabase"}), 400

    except Exception as e:
        print(f"🔴 [AUTH] Erro no registro: {str(e)}")
        return jsonify({"error": f"Erro no registro: {str(e)}"}), 400

@auth_bp.route("/login", methods=["POST"])
def login():
    """Login tradicional com email/senha"""
    print("🟡 [AUTH] /login chamado")
    login_data = request.get_json()
    if not login_data:
        return jsonify({"error": "Corpo da requisição inválido"}), 400

    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": login_data.get('email'),
            "password": login_data.get('password')
        })

        print(f"🟡 [AUTH] Resposta do sign_in: {auth_response}")

        if auth_response.user:
            # Buscar perfil do usuário
            user_profile = get_or_create_user_profile(auth_response.user)
            return jsonify({
                "access_token": auth_response.session.access_token,
                "token_type": "bearer",
                "user": user_profile
            }), 200
        else:
            return jsonify({"error": "Credenciais inválidas"}), 401

    except Exception as e:
        print(f"🔴 [AUTH] Erro no login: {str(e)}")
        return jsonify({"error": f"Erro no login: {str(e)}"}), 401

@auth_bp.route("/complete-registration", methods=["POST"])
@token_required
def complete_registration():
    """Completar registro criando uma república"""
    print("🟡 [AUTH] /complete-registration chamado")
    registration_data = request.get_json()
    
    if not registration_data or 'republic_name' not in registration_data:
        return jsonify({"error": "Nome da república é obrigatório"}), 400
    
    current_user = g.user
    republic_name = registration_data.get('republic_name')
    republic_type = registration_data.get('republic_type', 'mista')
    city = registration_data.get('city')  # AGORA PEGA DO FRONTEND
    state = registration_data.get('state') # AGORA PEGA DO FRONTEND

    # Validações
    if not city:
        return jsonify({"error": "Cidade é obrigatória"}), 400
    
    if not state:
        return jsonify({"error": "Estado é obrigatório"}), 400

    if republic_type not in ['feminina', 'masculina', 'mista']:
        republic_type = 'mista'

    try:
        print(f"🟡 [AUTH] Criando república '{republic_name}' em {city}/{state} (tipo: {republic_type}) para usuário {current_user['id']}")
        
        # 1. Criar a república na tabela republicas
        republic_data = {
            "name": republic_name,
            "tipo": republic_type,  
            "city": city,           # USA A CIDADE DO FRONTEND
            "state": state,         # USA O ESTADO DO FRONTEND
            "admin_user_id": current_user['id'],
            "is_active": True,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "updated_at": datetime.datetime.utcnow().isoformat()
        }
        
        print(f"🟡 [AUTH] Dados da república: {republic_data}")
        
        republic_response = supabase.table("republicas").insert(republic_data).execute()
        
        if not republic_response.data:
            print(f"🔴 [AUTH] Erro ao criar república: {republic_response}")
            return jsonify({"error": "Erro ao criar república"}), 500
        
        created_republic = republic_response.data[0]
        print(f"✅ [AUTH] República criada: {created_republic}")
        
        # 2. Adicionar o usuário como membro admin da república
        member_data = {
            "republica_id": created_republic['id'],
            "user_id": current_user['id'],
            "role": "admin",
            "is_active": True,
            "joined_at": datetime.datetime.utcnow().isoformat()
        }
        
        member_response = supabase.table("republica_members").insert(member_data).execute()
        
        if not member_response.data:
            print(f"🔴 [AUTH] Erro ao adicionar usuário como membro: {member_response}")
            # Se falhar ao adicionar como membro, deleta a república criada
            supabase.table("republicas").delete().eq("id", created_republic['id']).execute()
            return jsonify({"error": "Erro ao vincular usuário à república"}), 500
        
        print(f"✅ [AUTH] Usuário adicionado como admin da república")
        
        # 3. Retornar os dados completos (usuário + república)
        user_with_republic = {
            **current_user,
            "republica": created_republic,
            "has_republic": True
        }
        
        return jsonify(user_with_republic), 200

    except Exception as e:
        print(f"🔴 [AUTH] Erro ao completar registro: {str(e)}")
        return jsonify({"error": f"Erro ao completar registro: {str(e)}"}), 400

@auth_bp.route("/me", methods=["GET"])
@token_required
def get_current_user_profile():
    """Obter perfil do usuário atual com informações completas"""
    print(f"✅ [AUTH] /me acessado por: {g.user['email']}")
    
    current_user = g.user
    
    try:
        # 🔥 BUSCAR REPÚBLICA DO USUÁRIO (com mais detalhes)
        republic_response = supabase.table("republicas")\
            .select("*")\
            .eq("admin_user_id", current_user['id'])\
            .execute()
        
        republica = None
        has_republic = False
        user_city = None  # 🔥 NOVO: cidade do usuário
        
        if republic_response.data:
            republica = republic_response.data[0]
            has_republic = True
            user_city = republica.get('city')  # 🔥 PEGA A CIDADE DA REPÚBLICA
            print(f"✅ [AUTH] Usuário tem república: {republica['name']} em {user_city}")
        else:
            # Se não for admin, verificar se é membro de alguma república
            member_response = supabase.table("republica_members")\
                .select("republicas(*)")\
                .eq("user_id", current_user['id'])\
                .eq("is_active", True)\
                .execute()
            
            if member_response.data and len(member_response.data) > 0:
                republica = member_response.data[0]['republicas']
                has_republic = True
                user_city = republica.get('city')  # 🔥 PEGA A CIDADE DA REPÚBLICA
                print(f"✅ [AUTH] Usuário é membro da república: {republica['name']} em {user_city}")
            else:
                print(f"🟡 [AUTH] Usuário não tem república")

        # 🔥 BUSCAR FILTROS SALVOS DO USUÁRIO
        filters_response = supabase.table("user_filters")\
            .select("*")\
            .eq("user_id", current_user['id'])\
            .order("created_at", desc=True)\
            .execute()
        
        user_filters = filters_response.data if filters_response.data else []
        print(f"✅ [AUTH] Usuário tem {len(user_filters)} filtros salvos")

        # 🔥 BUSCAR CALOUROS DA REPÚBLICA (se tiver república)
        user_calouros = []
        if has_republic and republica:
            calouros_response = supabase.table("republica_calouros")\
                .select("*")\
                .eq("republica_id", republica['id'])\
                .order("created_at", desc=True)\
                .execute()
            
            user_calouros = calouros_response.data if calouros_response.data else []
            print(f"✅ [AUTH] República tem {len(user_calouros)} calouros")

        # 🔥 BUSCAR MEMBROS DA REPÚBLICA (se tiver república)
        republic_members = []
        if has_republic and republica:
            members_response = supabase.table("republica_members")\
                .select("*, users(full_name, email, avatar_url)")\
                .eq("republica_id", republica['id'])\
                .eq("is_active", True)\
                .execute()
            
            republic_members = members_response.data if members_response.data else []
            print(f"✅ [AUTH] República tem {len(republic_members)} membros")

        # 🔥 BUSCAR PLANO DO USUÁRIO
        plan_response = supabase.table("user_plans")\
            .select("*")\
            .eq("user_id", current_user['id'])\
            .eq("status", "active")\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        
        user_plan = None
        has_active_plan = False
        
        if plan_response.data and len(plan_response.data) > 0:
            user_plan = plan_response.data[0]
            has_active_plan = True
            print(f"✅ [AUTH] Usuário tem plano ativo: {user_plan['plan_type']}")
        else:
            has_active_plan = False
            print(f"🟡 [AUTH] Usuário SEM plano ativo - precisa escolher")
        
        # 🔥 CONSTRUIR RESPOSTA COMPLETA
        user_with_data = {
            **current_user,
            "has_republic": has_republic,
            "has_active_plan": has_active_plan,
            "user_plan": user_plan,
            "user_filters": user_filters,
            "user_calouros": user_calouros,
            "republic_members": republic_members,
            "user_city": user_city  # 🔥 NOVO: inclui a cidade do usuário
        }
        
        if has_republic:
            user_with_data["republica"] = republica
        
        return jsonify(user_with_data), 200
        
    except Exception as e:
        print(f"🔴 [AUTH] Erro ao buscar perfil: {str(e)}")
        # Retorna usuário com estrutura básica em caso de erro
        user_with_data = {
            **current_user,
            "has_republic": False,
            "has_active_plan": False,
            "user_plan": None,
            "user_filters": [],
            "user_calouros": [],
            "republic_members": [],
            "user_city": None  # 🔥 NOVO: inclui a cidade mesmo em caso de erro
        }
        return jsonify(user_with_data), 200
@auth_bp.route("/google", methods=["POST"])
def google_login():
    """Login com Google (para uso futuro)"""
    return jsonify({"message": "Endpoint /auth/google não implementado"}), 501

@auth_bp.route("/solana", methods=["POST"])
def solana_login():
    """Login com Solana (para uso futuro)"""
    return jsonify({"message": "Endpoint /auth/solana não implementado"}), 501

@auth_bp.route("/logout", methods=["POST"])
@token_required
def logout():
    """Logout do usuário"""
    print(f"🟡 [AUTH] /logout chamado por: {g.user['email']}")
    return jsonify({"message": "Logout recebido pelo backend"}), 200

# Health check da auth
@auth_bp.route("/health", methods=["GET"])
def auth_health():
    """Health check específico para auth"""
    return jsonify({"status": "healthy", "service": "auth"}), 200