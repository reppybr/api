import math
from functools import wraps
from flask import Blueprint, jsonify, request, g
from supabase import create_client, Client

# --- 1. CONFIGURAÇÃO DO SUPABASE ---
# (Certifique-se de que sua chave SERVICE_ROLE está aqui)
SUPABASE_URL = "https://wjstxyjdxijiqnlqawdr.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indqc3R4eWpkeGlqaXFubHFhd2RyIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MjAxMTU1OSwiZXhwIjoyMDc3NTg3NTU5fQ.hUIOXz7uTChNvmFo_zpt3njufMZlSrwW1dGbI7NAPhk" 

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. FUNÇÕES DE SEGURANÇA (CORRIGIDAS) ---

def token_required(f):
    """Decorator que verifica o token do Supabase e busca o perfil E O PLANO"""
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

            # CORREÇÃO: Busca o usuário E TAMBÉM seus 'user_plans'
            profile_response = supabase.table("users")\
                .select("*, user_plans(*)")\
                .eq("auth_id", user_response.user.id)\
                .execute()
            
            if not profile_response.data:
                return jsonify({"error": "Perfil do usuário não encontrado"}), 404

            g.user = profile_response.data[0]
            
            # DEBUG: Você pode remover isso quando tudo funcionar
            print(f"DEBUG: Dados do usuário (com planos): {g.user}")

        except Exception as e:
            return jsonify({"error": f"Erro ao verificar token: {str(e)}"}), 401

        return f(*args, **kwargs)
    return decorated_function

def get_user_plan():
    """
    Pega o plano do usuário que foi armazenado no 'g' pelo decorator.
    Agora, ela procura na lista 'user_plans'.
    """
    try:
        user_profile = g.user
        
        # 1. Acessar a lista de planos
        plans_list = user_profile.get("user_plans", [])
        
        if not plans_list:
            print("DEBUG: Usuário não tem planos na lista. Retornando 'free'.")
            return "free"
        
        # 2. Encontrar o plano ATIVO
        active_plan = None
        for plan in plans_list:
            if plan.get("status") == "active":
                active_plan = plan
                break
        
        if active_plan:
            plan_type = active_plan.get("plan_type", "free")
            print(f"DEBUG: Plano ativo encontrado: {plan_type}")
            return plan_type.lower()
        else:
            print("DEBUG: Usuário tem planos, mas nenhum está 'active'. Retornando 'free'.")
            return "free"
            
    except Exception as e:
        print(f"Erro ao ler g.user ou user_plans: {e}. Usando plano 'free'.")
        return "free"

# --- 3. SEU BLUEPRINT E ROTAS ---

dados_bp = Blueprint('dados', __name__)

# --- FUNÇÃO DE QUERY (COM A CORREÇÃO DE SINTAXE) ---
# --- ATUALIZAR A FUNÇÃO _build_calouros_query ---

def _build_calouros_query(filters, check_plan=True):
    """
    Função auxiliar ATUALIZADA para suportar múltiplos valores nos filtros
    """
    
    # --- 1. Lógica de Segurança (Freemium no Backend) ---
    chamadas = filters.getlist('chamadas') if 'chamadas' in filters else []
    chamada = filters.get('chamada', type=int)
    
    # Se veio como array, pega o primeiro para compatibilidade
    if not chamada and chamadas:
        chamada = chamadas[0] if isinstance(chamadas, list) and len(chamadas) > 0 else None
    
    # NOVO: Lógica de plano 'free' (se check_plan for True)
    if check_plan:
        user_plan = get_user_plan() 
        if user_plan == 'free':
            chamada = 1
            chamadas = [1]  # Força apenas chamada 1 no free
            
    # --- 2. Parâmetros de Filtro e Paginação ---
    cidade = filters.get('cidade')
    
    # 🔥 AGORA SUPORTA MÚLTIPLOS VALORES
    cursos = filters.getlist('cursos') if 'cursos' in filters else []
    universidades = filters.getlist('universidades') if 'universidades' in filters else []
    unidades = filters.getlist('unidades') if 'unidades' in filters else []
    
    # Para compatibilidade com parâmetros antigos
    curso = filters.get('curso')
    universidade = filters.get('universidade')
    unidade = filters.get('unidade')
    
    # Se veio como valor único, converte para lista
    if curso and not cursos:
        cursos = [curso]
    if universidade and not universidades:
        universidades = [universidade]
    if unidade and not unidades:
        unidades = [unidade]
    
    genero = filters.get('genero') 
    
    # --- NOVOS FILTROS VINDOS DO FRONTEND ---
    q = filters.get('q')  # Busca por nome
    
    page = filters.get('page', 1, type=int)
    limit = filters.get('limit', 50, type=int) 
    
    if page < 1: page = 1
    if limit > 200: limit = 200 
    offset = (page - 1) * limit

    if not cidade:
        return None, {"error": "O parâmetro 'cidade' é obrigatório."}

    # --- 3. Construção da Query no Supabase ---
    query = supabase.table("master_calouros").select(
        "*", count="exact" 
    )
    
    # Filtro obrigatório
    query = query.eq('cidade', cidade)
    
    # --- FILTROS DINÂMICOS ATUALIZADOS (AGORA SUPORTA MÚLTIPLOS) ---
    
    # 🔥 FILTRO DE CHAMADAS (suporta múltiplas)
    if chamadas and len(chamadas) > 0:
        # Converte para inteiros
        try:
            chamadas_int = [int(c) for c in chamadas if c]
            query = query.in_('chamada', chamadas_int)
        except (ValueError, TypeError):
            # Fallback para chamada única se houver erro
            if chamada:
                query = query.eq('chamada', chamada)
    elif chamada:
        query = query.eq('chamada', chamada)
    
    # 🔥 FILTRO DE CURSOS (suporta múltiplos)
    if cursos and len(cursos) > 0:
        query = query.in_('course', cursos)
    
    # 🔥 FILTRO DE UNIVERSIDADES (suporta múltiplas)
    if universidades and len(universidades) > 0:
        query = query.in_('university', universidades)
    
    # 🔥 FILTRO DE UNIDADES (suporta múltiplas)
    if unidades and len(unidades) > 0:
        query = query.in_('unidade', unidades)
    
    if genero:
        query = query.eq('genero', genero)
        
    if q:
        query = query.ilike('name', f'%{q}%') 
    
    query = query.range(offset, offset + (limit - 1))
    query = query.order("name", desc=False)
    
    return query, None

# --- ROTAS (COM A CORREÇÃO DE PAGINAÇÃO) ---

@dados_bp.route('/calouros/completo', methods=['GET'])
@token_required 
def get_dados_completos():
    """
    Endpoint PAGO (Plano Basic/Premium) - ATUALIZADO para múltiplos filtros
    """
    
    user_plan = get_user_plan()
    if user_plan == 'free':
        return jsonify({"error": "Acesso negado. Esta rota requer um plano pago."}), 403

    try:
        query, error_response = _build_calouros_query(request.args, check_plan=False)
        
        if error_response:
            return jsonify(error_response), 400

        response = query.execute()
        
        data = response.data
        total_items = response.count 
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        if limit > 200: limit = 200
        
        if total_items is not None and total_items > 0:
            total_pages = math.ceil(total_items / limit)
        else:
            total_pages = 0 
            if total_items is None:
                total_items = 0

        if not data:
            return jsonify({
                "error": "Nenhum calouro encontrado para os filtros aplicados.",
                "data": [],
                "pagination": {"total_items": 0, "total_pages": 0, "current_page": 1}
            }), 404
            
        return jsonify({
            "data": data,
            "pagination": {
                "total_items": total_items,
                "total_pages": total_pages,
                "current_page": page,
                "limit": limit 
            }
        }), 200

    except Exception as e:
        print(f"🔴 ERRO 500 NA ROTA /calouros/completo: {e}")
        return jsonify({"error": "Erro interno ao consultar o banco de dados.", "details": str(e)}), 500


@dados_bp.route('/calouros/chamada1', methods=['GET'])
@token_required 
def get_chamada1_cidade():
    """
    Endpoint GRÁTIS (Plano Free) - ATUALIZADO
    """
    
    try:
        # Para o free, forçar apenas chamada 1 independente do filtro
        filters = request.args.copy()
        filters['chamada'] = 1
        filters['chamadas'] = [1]  # Força array com apenas chamada 1
        
        query, error_response = _build_calouros_query(filters, check_plan=False)
        
        if error_response:
            return jsonify(error_response), 400

        response = query.execute()
        
        data = response.data
        total_items = response.count
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        if limit > 200: limit = 200
        
        if total_items is not None and total_items > 0:
            total_pages = math.ceil(total_items / limit)
        else:
            total_pages = 0
            if total_items is None:
                total_items = 0

        if not data:
            return jsonify({
                "error": "Nenhum calouro encontrado para os filtros aplicados (Chamada 1).",
                "data": [],
                "pagination": {"total_items": 0, "total_pages": 0, "current_page": 1}
            }), 404
            
        return jsonify({
            "data": data,
            "pagination": {
                "total_items": total_items,
                "total_pages": total_pages,
                "current_page": page,
                "limit": limit
            }
        }), 200

    except Exception as e:
        print(f"🔴 ERRO 500 NA ROTA /calouros/chamada1: {e}")
        return jsonify({"error": "Erro interno ao consultar o banco de dados.", "details": str(e)}), 500

# --- Rotas Auxiliares de Filtros (Lendo do BD) ---
# (Estas rotas permanecem iguais)
# Adicione estas duas novas rotas ao final do seu arquivo dados_bp.py

@dados_bp.route('/filtros/unidades', methods=['GET'])
@token_required
def get_unidades_disponiveis():
    cidade = request.args.get('cidade')
    if not cidade:
        return jsonify({"error": "O parâmetro 'cidade' é obrigatório."}), 400
    try:
        response = supabase.rpc("get_distinct_unidades_by_cidade", {"p_cidade": cidade}).execute()
        unidade_list = [item['unidade'] for item in response.data if item['unidade']]
        return jsonify({
            "cidade": cidade,
            "unidades": sorted(unidade_list),
            "total": len(unidade_list)
        }), 200
    except Exception as e:
        print(f"🔴 Erro ao consultar unidades: {str(e)}")
        return jsonify({"error": "Erro ao consultar unidades. (A função 'get_distinct_unidades_by_cidade' existe?)", "details": str(e)}), 500

@dados_bp.route('/filtros/chamadas', methods=['GET'])
@token_required
def get_chamadas_disponiveis():
    cidade = request.args.get('cidade')
    if not cidade:
        return jsonify({"error": "O parâmetro 'cidade' é obrigatório."}), 400
    try:
        response = supabase.rpc("get_distinct_chamadas_by_cidade", {"p_cidade": cidade}).execute()
        chamada_list = [item['chamada'] for item in response.data if item['chamada']]
        return jsonify({
            "cidade": cidade,
            "chamadas": sorted(chamada_list),
            "total": len(chamada_list)
        }), 200
    except Exception as e:
        print(f"🔴 Erro ao consultar chamadas: {str(e)}")
        return jsonify({"error": "Erro ao consultar chamadas. (A função 'get_distinct_chamadas_by_cidade' existe?)", "details": str(e)}), 500
@dados_bp.route('/filtros/cidades', methods=['GET'])
@token_required
def get_cidades_disponiveis():
    try:
        response = supabase.rpc("get_distinct_cidades").execute()
        cidades_list = [item['cidade'] for item in response.data if item['cidade']]
        return jsonify({
            "cidades": sorted(cidades_list),
            "total": len(cidades_list)
        }), 200
    except Exception as e:
        return jsonify({"error": "Erro ao consultar cidades. (A função 'get_distinct_cidades' existe no Supabase?)", "details": str(e)}), 500

@dados_bp.route('/filtros/cursos', methods=['GET'])
@token_required
def get_cursos_disponiveis():
    cidade = request.args.get('cidade')
    if not cidade:
        return jsonify({"error": "O parâmetro 'cidade' é obrigatório."}), 400
    try:
        response = supabase.rpc("get_distinct_cursos_by_cidade", {"p_cidade": cidade}).execute()
        cursos_list = [item['course'] for item in response.data if item['course']]
        return jsonify({
            "cidade": cidade,
            "cursos": sorted(cursos_list),
            "total": len(cursos_list)
        }), 200
    except Exception as e:
        return jsonify({"error": "Erro ao consultar cursos. (A função 'get_distinct_cursos_by_cidade' existe?)", "details": str(e)}), 500

@dados_bp.route('/filtros/universidades', methods=['GET'])
@token_required
def get_universidades_disponiveis():
    cidade = request.args.get('cidade')
    if not cidade:
        return jsonify({"error": "O parâmetro 'cidade' é obrigatório."}), 400
    try:
        response = supabase.rpc("get_distinct_universidades_by_cidade", {"p_cidade": cidade}).execute()
        uni_list = [item['university'] for item in response.data if item['university']]
        return jsonify({
            "cidade": cidade,
            "universidades": sorted(uni_list),
            "total": len(uni_list)
        }), 200
    except Exception as e:
        return jsonify({"error": "Erro ao consultar universidades. (A função 'get_distinct_universidades_by_cidade' existe?)", "details": str(e)}), 500