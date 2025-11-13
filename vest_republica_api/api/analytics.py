import os
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g
from supabase import create_client
from functools import wraps

# Cria o blueprint para as rotas de analytics
analytics_bp = Blueprint('analytics', __name__)

# --- Configuração do Supabase ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Decorators de Autenticação (Copie do seu calouros_bp.py) ---

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
    """Busca a república do usuário e armazena em g.republica"""
    try:
        if hasattr(g, 'republica'):
             return g.republica
             
        republic_response = supabase.table("republicas")\
            .select("*")\
            .eq("admin_user_id", user_id)\
            .execute()
        
        if republic_response.data:
            g.republica = republic_response.data[0]
            return g.republica
        
        member_response = supabase.table("republica_members")\
            .select("republicas(*)")\
            .eq("user_id", user_id)\
            .eq("is_active", True)\
            .execute()
            
        if member_response.data and len(member_response.data) > 0:
            g.republica = member_response.data[0]['republicas']
            return g.republica
            
        return None
    except Exception as e:
        print(f"🔴 Erro ao buscar república: {str(e)}")
        return None

# --- DECORATOR PREMIUM REQUIRED ---
def premium_required(f):
    """Verifica se o usuário da república tem um plano premium ativo"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user'):
            return jsonify({"error": "Usuário não autenticado"}), 401
        
        republica = get_user_republic(g.user['id'])
        if not republica:
             return jsonify({"error": "República não encontrada para este usuário"}), 404

        try:
            plan_response = supabase.table("user_plans")\
                .select("plan_type, status")\
                .eq("republica_id", republica['id'])\
                .eq("status", "active")\
                .execute()

            if not plan_response.data:
                return jsonify({
                    "error": "Acesso negado. Este é um recurso Premium.",
                    "code": "UPGRADE_REQUIRED"
                }), 403 

            if plan_response.data[0]['plan_type'].lower() != 'premium': 
                return jsonify({
                    "error": "Acesso negado. Este é um recurso Premium.",
                    "code": "UPGRADE_REQUIRED"
                }), 403

        except Exception as e:
            print(f"🔴 Erro ao verificar plano: {str(e)}")
            return jsonify({"error": f"Erro ao verificar plano: {str(e)}"}), 500

        return f(*args, **kwargs)
    return decorated_function


# --- ROTAS DE ANALYTICS (AGORA TODAS PREMIUM) ---

# MÓDULO 1: FUNIL PESSOAL
@analytics_bp.route('/my-funnel-stats', methods=['GET'])
@token_required
@premium_required 
def get_my_funnel_stats():
    """
    [PREMIUM] Retorna as estatísticas do funil *pessoal* da república.
    """
    try:
        republica_id = g.republica['id']

        # Esta rota usa .table() e .select(), que já está correta.
        calouros_response = supabase.table("republica_calouros")\
            .select("status, favourite")\
            .eq("republica_id", republica_id)\
            .execute()
        
        calouros_data = calouros_response.data if calouros_response.data else []
        
        por_status = {'pending': 0, 'contacted': 0, 'approved': 0, 'rejected': 0}
        total_favoritos = 0
        
        for calouro in calouros_data:
            if calouro['status'] in por_status:
                por_status[calouro['status']] += 1
            if calouro['favourite']:
                total_favoritos += 1
        
        estatisticas = {
            'por_status': por_status,
            'total_favoritos': total_favoritos,
            'total_calouros_salvos': len(calouros_data)
        }
        
        return jsonify(estatisticas), 200
        
    except Exception as e:
        print(f"🔴 Erro ao buscar estatísticas pessoais: {str(e)}")
        return jsonify({'error': f'Erro ao buscar estatísticas: {str(e)}'}), 500

# MÓDULO 2: PULSO DE MERCADO
@analytics_bp.route('/pulse', methods=['GET'])
@token_required
@premium_required
def get_market_pulse():
    """
    [PREMIUM] Retorna os 3 cartões de estatística do "Pulso de Mercado".
    (Requer a função SQL 'get_market_pulse_stats')
    """
    try:
        city = g.republica.get('city')
        if not city:
            return jsonify({"error": "Cidade da república não configurada"}), 400

        # --- CORREÇÃO AQUI ---
        response = supabase.rpc("get_market_pulse_stats", {"target_city": city}).execute()
        # --- FIM DA CORREÇÃO ---
        
        if not response or not response.data:
            return jsonify({
                "active_republics": 0,
                "new_calouros_saved": 0,
                "most_disputed_course": "N/A"
            }), 200

        return jsonify(response.data[0]), 200

    except Exception as e:
        print(f"🔴 Erro ao buscar pulso de mercado: {str(e)}")
        return jsonify({'error': f'Erro ao buscar pulso de mercado: {str(e)}'}), 500

# MÓDULO 3: LEADS QUENTES
@analytics_bp.route('/hot-leads', methods=['GET'])
@token_required
@premium_required
def get_hot_leads():
    """
    [PREMIUM] Retorna os "Leads Quentes"
    (Requer a função SQL 'get_hot_leads_for_city')
    """
    try:
        city = g.republica.get('city')
        republica_id = g.republica.get('id')

        # --- CORREÇÃO AQUI ---
        response = supabase.rpc("get_hot_leads_for_city", {
            "target_city": city,
            "requesting_republica_id": republica_id
        }).execute()
        # --- FIM DA CORREÇÃO ---
        
        return jsonify(response.data if response.data else []), 200

    except Exception as e:
        print(f"🔴 Erro ao buscar leads quentes: {str(e)}")
        return jsonify({'error': f'Erro ao buscar leads quentes: {str(e)}'}), 500

# MÓDULO 4: OPORTUNIDADES OCULTAS
@analytics_bp.route('/hidden-opportunities', methods=['GET'])
@token_required
@premium_required
def get_hidden_opportunities():
    """
    [PREMIUM] Retorna "Oportunidades Ocultas"
    """
    try:
        city = g.republica.get('city')
        
        hot_courses = [
            'Medicina', 'Engenharia de Computação', 'Direito', 
            'Engenharia de Produção', 'Arquitetura e Urbanismo', 'Economia'
        ]
        
        # Esta rota usa .table() e .select(), que já está correta.
        response = supabase.table("master_calouros")\
            .select("id, name, course, unidade, chamada, republica_calouros!left(id)")\
            .eq("cidade", city) \
            .is_("republica_calouros.id", "null") \
            .in_("course", hot_courses) \
            .limit(20) \
            .execute()

        formatted_data = [
            {
                "id": calouro["id"],
                "name": calouro["name"],
                "course": calouro["course"],
                "unidade": calouro["unidade"],
                "chamada": calouro["chamada"]
            }
            for calouro in response.data
        ]

        return jsonify(formatted_data), 200

    except Exception as e:
        print(f"🔴 Erro ao buscar oportunidades ocultas: {str(e)}")
        return jsonify({'error': f'Erro ao buscar oportunidades ocultas: {str(e)}'}), 500

# MÓDULO 5: RADAR DE CURSOS (COMPETIÇÃO)
@analytics_bp.route('/course-radar', methods=['GET'])
@token_required
@premium_required
def get_course_radar():
    """
    [PREMIUM] Retorna dados para o gráfico de Radar de Cursos
    (Requer a função SQL 'get_course_competition_radar')
    """
    try:
        city = g.republica.get('city')
        
        # --- CORREÇÃO AQUI ---
        response = supabase.rpc("get_course_competition_radar", {"target_city": city}).execute()
        # --- FIM DA CORREÇÃO ---
        
        return jsonify(response.data if response.data else []), 200

    except Exception as e:
        print(f"🔴 Erro ao buscar radar de cursos: {str(e)}")
        return jsonify({'error': f'Erro ao buscar radar de cursos: {str(e)}'}), 500

# MÓDULO 6: BENCHMARK DE CONVERSÃO (Mercado vs. Você)
@analytics_bp.route('/benchmark', methods=['GET'])
@token_required
@premium_required
def get_conversion_benchmark():
    """
    [PREMIUM] Retorna a taxa de conversão do mercado
    (Requer a função SQL 'get_market_conversion_benchmark')
    """
    try:
        city = g.republica.get('city')
        
        # --- CORREÇÃO AQUI ---
        response = supabase.rpc("get_market_conversion_benchmark", {"target_city": city}).execute()
        # --- FIM DA CORREÇÃO ---
        
        if not response or not response.data:
            return jsonify({
                "total_contacted": 0,
                "total_approved": 0,
                "market_conversion_rate": 0
            }), 200
            
        return jsonify(response.data[0]), 200

    except Exception as e:
        print(f"🔴 Erro ao buscar benchmark de conversão: {str(e)}")
        return jsonify({'error': f'Erro ao buscar benchmark de conversão: {str(e)}'}), 500

# MÓDULO 7: RADAR DE ATIVIDADE (HEATMAP)
@analytics_bp.route('/activity-heatmap', methods=['GET'])
@token_required
@premium_required
def get_activity_heatmap():
    """
    [PREMIUM] Retorna dados para o heatmap de atividade
    (Requer a função SQL 'get_activity_heatmap')
    """
    try:
        city = g.republica.get('city')
        
        # --- CORREÇÃO AQUI ---
        response = supabase.rpc("get_activity_heatmap", {"target_city": city}).execute()
        # --- FIM DA CORREÇÃO ---
        
        return jsonify(response.data if response.data else []), 200

    except Exception as e:
        print(f"🔴 Erro ao buscar dados do heatmap: {str(e)}")
        return jsonify({'error': f'Erro ao buscar dados do heatmap: {str(e)}'}), 500

# MÓDULO 8: COMPETIÇÃO POR GÊNERO
@analytics_bp.route('/gender-competition', methods=['GET'])
@token_required
@premium_required
def get_gender_competition():
    """
    [PREMIUM] Retorna o número de repúblicas concorrentes
    (Requer a função SQL 'get_gender_competition')
    """
    try:
        city = g.republica.get('city')
        
        # --- CORREÇÃO AQUI ---
        response = supabase.rpc("get_gender_competition", {"target_city": city}).execute()
        # --- FIM DA CORREÇÃO ---
        
        if not response or not response.data:
            return jsonify({
                "competition_female_leads": 0,
                "competition_male_leads": 0
            }), 200
            
        return jsonify(response.data[0]), 200

    except Exception as e:
        print(f"🔴 Erro ao buscar competição por gênero: {str(e)}")
        return jsonify({'error': f'Erro ao buscar competição por gênero: {str(e)}'}), 500

# MÓDULO 9: RANKING DE MEMBROS (Gestão Interna)
@analytics_bp.route('/member-ranking', methods=['GET'])
@token_required
@premium_required
def get_member_ranking():
    """
    [PREMIUM] Retorna um ranking de performance dos membros
    (Requer a função SQL 'get_republic_member_ranking')
    """
    try:
        republica_id = g.republica['id']
        
        # --- CORREÇÃO AQUI ---
        response = supabase.rpc("get_republic_member_ranking", {"target_republica_id": republica_id}).execute()
        # --- FIM DA CORREÇÃO ---
        
        return jsonify(response.data if response.data else []), 200

    except Exception as e:
        print(f"🔴 Erro ao buscar ranking de membros: {str(e)}")
        return jsonify({'error': f'Erro ao buscar ranking de membros: {str(e)}'}), 500