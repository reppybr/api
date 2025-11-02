# plans.py
import os
import datetime
from flask import Blueprint, jsonify, request, g
from supabase import create_client
from functools import wraps

# Cria o blueprint
plans_bp = Blueprint('plans', __name__)

# Configuração do Supabase
SUPABASE_URL = "https://wjstxyjdxijiqnlqawdr.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indqc3R4eWpkeGlqaXFubHFhd2RyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjIwMTE1NTksImV4cCI6MjA3NzU4NzU1OX0.y03cbe2BXsr6i9n4ouaYd7az7QuWH4r7vIYvb7R3_d0"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Features padrão para cada plano
PLAN_FEATURES = {
    'free': {
        'max_members': 5,
        'max_calouros': 10,
        'max_filters': 3,
        'advanced_analytics': False,
        'custom_domain': False,
        'priority_support': False,
        'export_data': False,
        'multiple_users': False
    },
    'basic': {
        'max_members': 20,
        'max_calouros': 50,
        'max_filters': 10,
        'advanced_analytics': True,
        'custom_domain': False,
        'priority_support': True,
        'export_data': True,
        'multiple_users': True
    },
    'premium': {
        'max_members': 100,
        'max_calouros': 500,
        'max_filters': 50,
        'advanced_analytics': True,
        'custom_domain': True,
        'priority_support': True,
        'export_data': True,
        'multiple_users': True
    }
}

# Preços dos planos (em centavos)
PLAN_PRICES = {
    'free': 0,
    'basic': {
        'monthly': 6500,  # R$ 65,00
        'yearly': 65000   # R$ 650,00 (com desconto)
    },
    'premium': {
        'monthly': 9500,  # R$ 95,00
        'yearly': 95000   # R$ 950,00 (com desconto)
    }
}

def token_required(f):
    """
    Decorator que verifica o token do Supabase (reutilizado do auth.py)
    """
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
    """
    Busca a república do usuário (como admin ou membro)
    """
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

def get_current_plan(user_id):
    """
    Busca o plano ativo do usuário
    """
    try:
        plan_response = supabase.table("user_plans")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        
        if plan_response.data and len(plan_response.data) > 0:
            return plan_response.data[0]
        return None
    except Exception as e:
        print(f"🔴 Erro ao buscar plano atual: {str(e)}")
        return None

def create_plan_record(user_id, republica_id, plan_type, billing_cycle, price_amount):
    """
    Cria um registro de plano na tabela user_plans
    """
    try:
        # Calcular datas do período
        current_time = datetime.datetime.utcnow()
        
        if billing_cycle == 'monthly':
            period_end = current_time + datetime.timedelta(days=30)
        else:  # yearly
            period_end = current_time + datetime.timedelta(days=365)
        
        plan_data = {
            "user_id": user_id,
            "republica_id": republica_id,
            "plan_type": plan_type,
            "status": "active",
            "current_period_start": current_time.isoformat(),
            "current_period_end": period_end.isoformat(),
            "price_amount": price_amount,
            "price_currency": "BRL",
            "features": PLAN_FEATURES[plan_type],
            "created_at": current_time.isoformat(),
            "updated_at": current_time.isoformat()
        }
        
        # Inserir plano
        plan_response = supabase.table("user_plans").insert(plan_data).execute()
        
        if not plan_response.data:
            raise Exception("Erro ao criar registro do plano")
            
        return plan_response.data[0]
        
    except Exception as e:
        print(f"🔴 Erro ao criar plano: {str(e)}")
        raise e

def update_existing_plan(plan_id, plan_type, billing_cycle, price_amount):
    """
    Atualiza um plano existente em vez de criar um novo
    """
    try:
        current_time = datetime.datetime.utcnow()
        
        if billing_cycle == 'monthly':
            period_end = current_time + datetime.timedelta(days=30)
        else:  # yearly
            period_end = current_time + datetime.timedelta(days=365)
        
        plan_data = {
            "plan_type": plan_type,
            "status": "active",
            "current_period_start": current_time.isoformat(),
            "current_period_end": period_end.isoformat(),
            "price_amount": price_amount,
            "features": PLAN_FEATURES[plan_type],
            "updated_at": current_time.isoformat()
        }
        
        update_response = supabase.table("user_plans")\
            .update(plan_data)\
            .eq("id", plan_id)\
            .execute()
        
        if not update_response.data:
            raise Exception("Erro ao atualizar plano existente")
            
        return update_response.data[0]
        
    except Exception as e:
        print(f"🔴 Erro ao atualizar plano: {str(e)}")
        raise e

def create_payment_record(user_id, plan_id, amount, payment_method, status='succeeded'):
    """
    Cria um registro de pagamento
    """
    try:
        payment_data = {
            "user_id": user_id,
            "plan_id": plan_id,
            "amount": amount,
            "currency": "BRL",
            "status": status,
            "payment_method": payment_method,
            "description": f"Pagamento plano {plan_id}",
            "paid_at": datetime.datetime.utcnow().isoformat() if status == 'succeeded' else None,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        
        payment_response = supabase.table("payments").insert(payment_data).execute()
        
        if not payment_response.data:
            raise Exception("Erro ao criar registro de pagamento")
            
        return payment_response.data[0]
        
    except Exception as e:
        print(f"🔴 Erro ao criar pagamento: {str(e)}")
        raise e

# --- ROTAS DE PLANOS ---

@plans_bp.route("/available", methods=["GET"])
@token_required
def get_available_plans():
    """
    Retorna os planos disponíveis com preços e features
    """
    try:
        current_user = g.user
        current_plan = get_current_plan(current_user['id'])
        
        plans_data = {
            "free": {
                "name": "Bixo",
                "type": "free",
                "prices": {
                    "monthly": 0,
                    "yearly": 0
                },
                "features": PLAN_FEATURES['free'],
                "description": "Perfeito para conhecer a plataforma e garantir os primeiros bixos.",
                "popular": False
            },
            "basic": {
                "name": "Veterano", 
                "type": "basic",
                "prices": {
                    "monthly": PLAN_PRICES['basic']['monthly'] / 100,  # Convert to BRL
                    "yearly": PLAN_PRICES['basic']['yearly'] / 100
                },
                "features": PLAN_FEATURES['basic'],
                "description": "A ferramenta completa para repúblicas que não perdem tempo.",
                "popular": True
            },
            "premium": {
                "name": "Veterano Mor",
                "type": "premium", 
                "prices": {
                    "monthly": PLAN_PRICES['premium']['monthly'] / 100,
                    "yearly": PLAN_PRICES['premium']['yearly'] / 100
                },
                "features": PLAN_FEATURES['premium'],
                "description": "Insights e dados customizados para repúblicas de alta performance.",
                "popular": False
            }
        }
        
        return jsonify({
            "plans": plans_data,
            "current_plan": current_plan
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao buscar planos: {str(e)}")
        return jsonify({"error": f"Erro ao buscar planos: {str(e)}"}), 500

@plans_bp.route("/choose", methods=["POST"])
@token_required
def choose_plan():
    """
    Escolher/ativar um plano (free, basic ou premium)
    """
    try:
        current_user = g.user
        data = request.get_json()
        
        if not data or 'plan_type' not in data:
            return jsonify({"error": "Tipo de plano é obrigatório"}), 400
        
        plan_type = data.get('plan_type')
        billing_cycle = data.get('billing_cycle', 'monthly')  # monthly ou yearly
        payment_method = data.get('payment_method', 'mock')   # mock, card, pix, boleto
        
        # Validar tipo de plano
        if plan_type not in ['free', 'basic', 'premium']:
            return jsonify({"error": "Tipo de plano inválido"}), 400
        
        # Validar ciclo de billing
        if billing_cycle not in ['monthly', 'yearly']:
            return jsonify({"error": "Ciclo de billing inválido"}), 400
        
        # Buscar república do usuário
        republica = get_user_republic(current_user['id'])
        if not republica:
            return jsonify({
                "error": "Usuário não tem uma república cadastrada",
                "error_code": "NO_REPUBLIC",
                "required_action": "complete_registration"
            }), 400
        
        # Verificar se já tem um plano ativo
        current_plan = get_current_plan(current_user['id'])
        
        # Calcular preço
        if plan_type == 'free':
            price_amount = 0
        else:
            price_amount = PLAN_PRICES[plan_type][billing_cycle] / 100  # Converter para BRL
        
        # 🔥 MOCK: Simular processamento de pagamento para planos pagos
        if plan_type != 'free':
            print(f"🟡 Processando pagamento MOCK para plano {plan_type} - R$ {price_amount}")
            
            # Simular delay de processamento
            import time
            time.sleep(1)
            
            # Aqui normalmente integraríamos com Stripe, Pagar.me, etc.
            # Por enquanto, mock de sucesso
            payment_status = 'succeeded'
            
            if payment_status != 'succeeded':
                return jsonify({"error": "Pagamento não aprovado"}), 402
        
        # 🔥 CORREÇÃO: Verificar se já existe um plano (ativo ou cancelado) para evitar duplicação
        existing_plans_response = supabase.table("user_plans")\
            .select("*")\
            .eq("user_id", current_user['id'])\
            .eq("republica_id", republica['id'])\
            .execute()
        
        new_plan = None
        payment = None
        
        if existing_plans_response.data and len(existing_plans_response.data) > 0:
            # 🔥 Já existe um plano - ATUALIZAR em vez de criar novo
            existing_plan = existing_plans_response.data[0]
            print(f"🟡 Plano existente encontrado (ID: {existing_plan['id']}), atualizando...")
            
            new_plan = update_existing_plan(
                plan_id=existing_plan['id'],
                plan_type=plan_type,
                billing_cycle=billing_cycle,
                price_amount=price_amount
            )
        else:
            # 🔥 Não existe plano - CRIAR novo
            print("🟡 Criando novo plano...")
            new_plan = create_plan_record(
                user_id=current_user['id'],
                republica_id=republica['id'],
                plan_type=plan_type,
                billing_cycle=billing_cycle,
                price_amount=price_amount
            )
        
        # Criar registro de pagamento (apenas para planos pagos)
        if plan_type != 'free':
            payment = create_payment_record(
                user_id=current_user['id'],
                plan_id=new_plan['id'],
                amount=price_amount,
                payment_method=payment_method,
                status='succeeded'
            )
        
        # Registrar atividade
        activity_data = {
            "user_id": current_user['id'],
            "republica_id": republica['id'],
            "activity_type": "plan_activated",
            "description": f"Plano {plan_type} ativado com sucesso",
            "metadata": {
                "plan_type": plan_type,
                "billing_cycle": billing_cycle,
                "price": price_amount
            },
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        
        supabase.table("user_activities").insert(activity_data).execute()
        
        return jsonify({
            "message": f"Plano {plan_type} ativado com sucesso!",
            "plan": new_plan,
            "payment": payment if plan_type != 'free' else None
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao escolher plano: {str(e)}")
        
        # 🔥 CORREÇÃO: Tratamento específico para erro de constraint única
        if 'duplicate key value violates unique constraint "unique_user_plan"' in str(e):
            return jsonify({
                "error": "Já existe um plano ativo para esta república. Tente atualizar o plano existente.",
                "error_code": "DUPLICATE_PLAN",
                "solution": "update_existing"
            }), 409
        
        return jsonify({"error": f"Erro ao escolher plano: {str(e)}"}), 500

@plans_bp.route("/current", methods=["GET"])
@token_required
def get_current_plan_route():
    """
    Retorna o plano atual do usuário
    """
    try:
        current_user = g.user
        current_plan = get_current_plan(current_user['id'])
        
        if not current_plan:
            return jsonify({
                "has_active_plan": False,
                "message": "Nenhum plano ativo encontrado"
            }), 200
        
        return jsonify({
            "has_active_plan": True,
            "plan": current_plan
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao buscar plano atual: {str(e)}")
        return jsonify({"error": f"Erro ao buscar plano atual: {str(e)}"}), 500

@plans_bp.route("/cancel", methods=["POST"])
@token_required
def cancel_plan():
    """
    Cancela o plano atual do usuário
    """
    try:
        current_user = g.user
        current_plan = get_current_plan(current_user['id'])
        
        if not current_plan:
            return jsonify({"error": "Nenhum plano ativo para cancelar"}), 400
        
        # Não permitir cancelar plano free
        if current_plan['plan_type'] == 'free':
            return jsonify({"error": "Plano free não pode ser cancelado"}), 400
        
        # Buscar república
        republica = get_user_republic(current_user['id'])
        
        # Atualizar status do plano para canceled
        update_response = supabase.table("user_plans")\
            .update({
                "status": "canceled",
                "cancel_at_period_end": True,
                "updated_at": datetime.datetime.utcnow().isoformat()
            })\
            .eq("id", current_plan['id'])\
            .execute()
        
        # Criar plano free automaticamente
        free_plan = create_plan_record(
            user_id=current_user['id'],
            republica_id=republica['id'],
            plan_type='free',
            billing_cycle='monthly',
            price_amount=0
        )
        
        # Registrar atividade
        activity_data = {
            "user_id": current_user['id'],
            "republica_id": republica['id'],
            "activity_type": "plan_canceled",
            "description": f"Plano {current_plan['plan_type']} cancelado, plano free ativado",
            "metadata": {
                "previous_plan": current_plan['plan_type'],
                "new_plan": 'free'
            },
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        
        supabase.table("user_activities").insert(activity_data).execute()
        
        return jsonify({
            "message": "Plano cancelado com sucesso. Plano free ativado.",
            "new_plan": free_plan
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao cancelar plano: {str(e)}")
        return jsonify({"error": f"Erro ao cancelar plano: {str(e)}"}), 500

@plans_bp.route("/upgrade", methods=["POST"])
@token_required
def upgrade_plan():
    """
    Upgrade do plano atual para um plano superior
    """
    try:
        current_user = g.user
        data = request.get_json()
        
        if not data or 'new_plan_type' not in data:
            return jsonify({"error": "Novo tipo de plano é obrigatório"}), 400
        
        new_plan_type = data.get('new_plan_type')
        billing_cycle = data.get('billing_cycle', 'monthly')
        
        # Validar upgrade
        valid_upgrades = {
            'free': ['basic', 'premium'],
            'basic': ['premium'],
            'premium': []  # Já é o mais alto
        }
        
        current_plan = get_current_plan(current_user['id'])
        current_plan_type = current_plan['plan_type'] if current_plan else 'free'
        
        if new_plan_type not in valid_upgrades[current_plan_type]:
            return jsonify({"error": f"Upgrade de {current_plan_type} para {new_plan_type} não é permitido"}), 400
        
        # Buscar república
        republica = get_user_republic(current_user['id'])
        if not republica:
            return jsonify({"error": "Usuário não tem uma república cadastrada"}), 400
        
        # 🔥 CORREÇÃO: Usar update_existing_plan em vez de cancelar e criar novo
        if current_plan:
            # Atualizar plano existente
            new_plan = update_existing_plan(
                plan_id=current_plan['id'],
                plan_type=new_plan_type,
                billing_cycle=billing_cycle,
                price_amount=PLAN_PRICES[new_plan_type][billing_cycle] / 100
            )
        else:
            # Criar novo plano se não existir (fallback)
            new_plan = create_plan_record(
                user_id=current_user['id'],
                republica_id=republica['id'],
                plan_type=new_plan_type,
                billing_cycle=billing_cycle,
                price_amount=PLAN_PRICES[new_plan_type][billing_cycle] / 100
            )
        
        # Calcular preço do novo plano
        price_amount = PLAN_PRICES[new_plan_type][billing_cycle] / 100
        
        # 🔥 MOCK: Processar pagamento
        print(f"🟡 Processando upgrade MOCK para plano {new_plan_type} - R$ {price_amount}")
        import time
        time.sleep(1)
        
        # Criar registro de pagamento
        payment = create_payment_record(
            user_id=current_user['id'],
            plan_id=new_plan['id'],
            amount=price_amount,
            payment_method='upgrade',
            status='succeeded'
        )
        
        # Registrar atividade
        activity_data = {
            "user_id": current_user['id'],
            "republica_id": republica['id'],
            "activity_type": "plan_upgraded",
            "description": f"Upgrade de plano de {current_plan_type} para {new_plan_type}",
            "metadata": {
                "from_plan": current_plan_type,
                "to_plan": new_plan_type,
                "billing_cycle": billing_cycle,
                "price": price_amount
            },
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        
        supabase.table("user_activities").insert(activity_data).execute()
        
        return jsonify({
            "message": f"Upgrade para plano {new_plan_type} realizado com sucesso!",
            "plan": new_plan,
            "payment": payment
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao fazer upgrade: {str(e)}")
        return jsonify({"error": f"Erro ao fazer upgrade: {str(e)}"}), 500

@plans_bp.route("/billing-history", methods=["GET"])
@token_required
def get_billing_history():
    """
    Retorna o histórico de pagamentos do usuário
    """
    try:
        current_user = g.user
        
        payments_response = supabase.table("payments")\
            .select("*, user_plans(plan_type)")\
            .eq("user_id", current_user['id'])\
            .order("created_at", desc=True)\
            .execute()
        
        return jsonify({
            "payments": payments_response.data if payments_response.data else []
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao buscar histórico: {str(e)}")
        return jsonify({"error": f"Erro ao buscar histórico: {str(e)}"}), 500

@plans_bp.route("/usage", methods=["GET"])
@token_required
def get_usage_stats():
    """
    Retorna estatísticas de uso baseadas no plano atual
    """
    try:
        current_user = g.user
        current_plan = get_current_plan(current_user['id'])
        republica = get_user_republic(current_user['id'])
        
        if not republica:
            return jsonify({"error": "Usuário não tem república"}), 400
        
        # Buscar contagens atuais
        members_response = supabase.table("republica_members")\
            .select("id", count="exact")\
            .eq("republica_id", republica['id'])\
            .eq("is_active", True)\
            .execute()
        
        calouros_response = supabase.table("republica_calouros")\
            .select("id", count="exact")\
            .eq("republica_id", republica['id'])\
            .execute()
        
        filters_response = supabase.table("user_filters")\
            .select("id", count="exact")\
            .eq("user_id", current_user['id'])\
            .execute()
        
        members_count = members_response.count if hasattr(members_response, 'count') else len(members_response.data)
        calouros_count = calouros_response.count if hasattr(calouros_response, 'count') else len(calouros_response.data)
        filters_count = filters_response.count if hasattr(filters_response, 'count') else len(filters_response.data)
        
        plan_limits = PLAN_FEATURES[current_plan['plan_type']] if current_plan else PLAN_FEATURES['free']
        
        return jsonify({
            "usage": {
                "members": members_count,
                "calouros": calouros_count,
                "filters": filters_count
            },
            "limits": plan_limits,
            "remaining": {
                "members": plan_limits['max_members'] - members_count,
                "calouros": plan_limits['max_calouros'] - calouros_count,
                "filters": plan_limits['max_filters'] - filters_count
            }
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao buscar estatísticas: {str(e)}")
        return jsonify({"error": f"Erro ao buscar estatísticas: {str(e)}"}), 500

# Health check
@plans_bp.route("/health", methods=["GET"])
def plans_health():
    """Health check específico para plans"""
    return jsonify({"status": "healthy", "service": "plans"}), 200