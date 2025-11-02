# config_bp.py
import os
import datetime
from flask import Blueprint, jsonify, request, g
from supabase import create_client
from functools import wraps

# Cria o blueprint
config_bp = Blueprint('config', __name__)

# Configuração do Supabase
SUPABASE_URL = "https://wjstxyjdxijiqnlqawdr.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indqc3R4eWpkeGlqaXFubHFhd2RyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjIwMTE1NTksImV4cCI6MjA3NzU4NzU1OX0.y03cbe2BXsr6i9n4ouaYd7az7QuWH4r7vIYvb7R3_d0"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def token_required(f):
    """Decorator que verifica o token do Supabase"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Token de autorização inválido"}), 401

        token = auth_header.replace("Bearer ", "")

        try:
            user_response = supabase.auth.get_user(token)
            
            if not user_response.user:
                return jsonify({"error": "Token do Supabase inválido"}), 401

            # Buscar perfil do usuário
            profile_response = supabase.table("users")\
                .select("*")\
                .eq("auth_id", user_response.user.id)\
                .execute()
            
            if not profile_response.data:
                return jsonify({"error": "Perfil do usuário não encontrado"}), 404

            g.user = profile_response.data[0]

        except Exception as e:
            return jsonify({"error": f"Erro ao verificar token: {str(e)}"}), 401

        return f(*args, **kwargs)
    return decorated_function

def get_user_republic(user_id):
    """Busca a república do usuário"""
    try:
        # Buscar como admin
        republic_response = supabase.table("republicas")\
            .select("*")\
            .eq("admin_user_id", user_id)\
            .execute()
        
        if republic_response.data:
            return republic_response.data[0]
        
        # Buscar como membro
        member_response = supabase.table("republica_members")\
            .select("republicas(*)")\
            .eq("user_id", user_id)\
            .eq("is_active", True)\
            .execute()
            
        if member_response.data and len(member_response.data) > 0:
            return member_response.data[0]['republicas']
            
        return None
    except Exception as e:
        print(f"🔴 Erro ao buscar república: {str(e)}")
        return None

# =============================================
# ROTAS DE CONFIGURAÇÃO DA REPÚBLICA
# =============================================

@config_bp.route('/republic', methods=['GET'])
@token_required
def get_republic_config():
    """Buscar configurações atuais da república"""
    try:
        current_user = g.user
        
        # Buscar república do usuário
        republica = get_user_republic(current_user['id'])
        if not republica:
            return jsonify({'error': 'Usuário não tem uma república cadastrada'}), 400
        
        print(f"✅ [CONFIG] Configurações da república buscadas: {republica['name']}")
        
        return jsonify({
            'republica': republica,
            'message': 'Configurações carregadas com sucesso'
        }), 200
        
    except Exception as e:
        print(f"🔴 [CONFIG] Erro ao buscar configurações da república: {str(e)}")
        return jsonify({'error': f'Erro ao buscar configurações: {str(e)}'}), 500

@config_bp.route('/republic', methods=['PUT'])
@token_required
def update_republic_config():
    """Atualizar configurações da república"""
    try:
        current_user = g.user
        data = request.get_json()
        
        print(f"🟡 [CONFIG] Dados recebidos para atualização: {data}")
        
        # Buscar república do usuário
        republica = get_user_republic(current_user['id'])
        if not republica:
            return jsonify({'error': 'Usuário não tem uma república cadastrada'}), 400
        
        # Verificar se o usuário é admin da república
        if republica['admin_user_id'] != current_user['id']:
            return jsonify({'error': 'Apenas o administrador pode alterar as configurações'}), 403
        
        # Campos permitidos para atualização
        allowed_fields = ['name', 'tipo', 'city', 'state', 'description', 'contact_phone', 'contact_email']
        update_data = {}
        
        for field in allowed_fields:
            if field in data and data[field] is not None:
                update_data[field] = data[field]
        
        # Adicionar timestamp de atualização
        update_data['updated_at'] = datetime.datetime.utcnow().isoformat()
        
        if not update_data:
            return jsonify({'error': 'Nenhum campo válido para atualização'}), 400
        
        print(f"🟡 [CONFIG] Atualizando república {republica['id']} com dados: {update_data}")
        
        # Atualizar república
        update_response = supabase.table("republicas")\
            .update(update_data)\
            .eq("id", republica['id'])\
            .execute()
        
        if not update_response.data:
            return jsonify({'error': 'Erro ao atualizar república'}), 500
        
        print(f"✅ [CONFIG] República atualizada com sucesso: {update_response.data[0]['name']}")
        
        return jsonify({
            'message': 'Configurações atualizadas com sucesso',
            'republica': update_response.data[0]
        }), 200
        
    except Exception as e:
        print(f"🔴 [CONFIG] Erro ao atualizar configurações da república: {str(e)}")
        return jsonify({'error': f'Erro ao atualizar configurações: {str(e)}'}), 500

# =============================================
# ROTAS DE CONFIGURAÇÕES DO USUÁRIO
# =============================================

@config_bp.route('/notifications', methods=['GET'])
@token_required
def get_user_notifications():
    """Buscar configurações de notificação do usuário"""
    try:
        current_user = g.user
        
        # Buscar configurações de notificação do usuário
        # Por enquanto, vamos usar um campo simples na tabela users
        user_response = supabase.table("users")\
            .select("email_notifications, push_notifications")\
            .eq("id", current_user['id'])\
            .execute()
        
        user_data = user_response.data[0] if user_response.data else {}
        
        notifications_config = {
            'email_notifications': user_data.get('email_notifications', True),
            'push_notifications': user_data.get('push_notifications', True)
        }
        
        print(f"✅ [CONFIG] Configurações de notificação carregadas para: {current_user['email']}")
        
        return jsonify({
            'notifications': notifications_config,
            'message': 'Configurações de notificação carregadas'
        }), 200
        
    except Exception as e:
        print(f"🔴 [CONFIG] Erro ao buscar configurações de notificação: {str(e)}")
        return jsonify({'error': f'Erro ao buscar configurações de notificação: {str(e)}'}), 500

@config_bp.route('/notifications', methods=['PUT'])
@token_required
def update_user_notifications():
    """Atualizar configurações de notificação do usuário"""
    try:
        current_user = g.user
        data = request.get_json()
        
        print(f"🟡 [CONFIG] Atualizando notificações: {data}")
        
        # Campos permitidos para atualização
        update_data = {}
        if 'email_notifications' in data:
            update_data['email_notifications'] = data['email_notifications']
        if 'push_notifications' in data:
            update_data['push_notifications'] = data['push_notifications']
        
        if not update_data:
            return jsonify({'error': 'Nenhuma configuração de notificação fornecida'}), 400
        
        # Atualizar usuário
        update_response = supabase.table("users")\
            .update(update_data)\
            .eq("id", current_user['id'])\
            .execute()
        
        if not update_response.data:
            return jsonify({'error': 'Erro ao atualizar configurações de notificação'}), 500
        
        print(f"✅ [CONFIG] Notificações atualizadas para: {current_user['email']}")
        
        return jsonify({
            'message': 'Configurações de notificação atualizadas com sucesso',
            'notifications': {
                'email_notifications': update_response.data[0].get('email_notifications', True),
                'push_notifications': update_response.data[0].get('push_notifications', True)
            }
        }), 200
        
    except Exception as e:
        print(f"🔴 [CONFIG] Erro ao atualizar configurações de notificação: {str(e)}")
        return jsonify({'error': f'Erro ao atualizar notificações: {str(e)}'}), 500

# =============================================
# ROTAS DE PLANOS E ASSINATURAS
# =============================================

@config_bp.route('/plan', methods=['GET'])
@token_required
def get_user_plan():
    """Buscar informações do plano atual do usuário"""
    try:
        current_user = g.user
        
        # Buscar plano ativo do usuário
        plan_response = supabase.table("user_plans")\
            .select("*, plans(*)")\
            .eq("user_id", current_user['id'])\
            .eq("status", "active")\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        
        user_plan = plan_response.data[0] if plan_response.data else None
        
        # Se não tem plano ativo, retorna plano free padrão
        if not user_plan:
            user_plan = {
                'plan_type': 'free',
                'status': 'active',
                'features': {
                    'max_calouros': 50,
                    'advanced_filters': False,
                    'team_management': False,
                    'export_data': False
                }
            }
        
        print(f"✅ [CONFIG] Plano carregado para: {current_user['email']} - {user_plan.get('plan_type', 'free')}")
        
        return jsonify({
            'plan': user_plan,
            'message': 'Informações do plano carregadas'
        }), 200
        
    except Exception as e:
        print(f"🔴 [CONFIG] Erro ao buscar informações do plano: {str(e)}")
        return jsonify({'error': f'Erro ao buscar informações do plano: {str(e)}'}), 500

@config_bp.route('/plan', methods=['PUT'])
@token_required
def update_user_plan():
    """Atualizar plano do usuário (upgrade/downgrade)"""
    try:
        current_user = g.user
        data = request.get_json()
        
        plan_type = data.get('plan_type')
        
        if not plan_type or plan_type not in ['free', 'basic', 'premium']:
            return jsonify({'error': 'Tipo de plano inválido'}), 400
        
        print(f"🟡 [CONFIG] Atualizando plano para: {plan_type} - Usuário: {current_user['email']}")
        
        # Aqui você implementaria a lógica de pagamento
        # Por enquanto, vamos apenas simular a atualização
        
        # Buscar plano atual para desativar
        supabase.table("user_plans")\
            .update({"status": "inactive"})\
            .eq("user_id", current_user['id'])\
            .eq("status", "active")\
            .execute()
        
        # Criar novo plano
        new_plan_data = {
            "user_id": current_user['id'],
            "plan_type": plan_type,
            "status": "active",
            "start_date": datetime.datetime.utcnow().isoformat(),
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        
        create_response = supabase.table("user_plans")\
            .insert(new_plan_data)\
            .execute()
        
        if not create_response.data:
            return jsonify({'error': 'Erro ao atualizar plano'}), 500
        
        print(f"✅ [CONFIG] Plano atualizado com sucesso: {plan_type}")
        
        return jsonify({
            'message': f'Plano atualizado para {plan_type} com sucesso',
            'plan': create_response.data[0]
        }), 200
        
    except Exception as e:
        print(f"🔴 [CONFIG] Erro ao atualizar plano: {str(e)}")
        return jsonify({'error': f'Erro ao atualizar plano: {str(e)}'}), 500

# Health check
@config_bp.route("/health", methods=["GET"])
def config_health():
    """Health check específico para config"""
    return jsonify({"status": "healthy", "service": "config"}), 200