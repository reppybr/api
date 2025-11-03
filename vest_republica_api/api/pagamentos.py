import os
import datetime
from flask import Blueprint, jsonify, request, g
from supabase import create_client
from functools import wraps
import requests
import json

# Cria o blueprint
pagamentos_bp = Blueprint('pagamentos', __name__)

# Configuração do Supabase
SUPABASE_URL = "https://wjstxyjdxijiqnlqawdr.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indqc3R4eWpkeGlqaXFubHFhd2RyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjIwMTE1NTksImV4cCI6MjA3NzU4NzU1OX0.y03cbe2BXsr6i9n4ouaYd7az7QuWH4r7vIYvb7R3_d0"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configuração do Mercado Pago
MERCADO_PAGO_ACCESS_TOKEN = os.getenv('MERCADO_PAGO_ACCESS_TOKEN', 'TEST-XXXX')
MERCADO_PAGO_BASE_URL = "https://api.mercadopago.com"

# ========== DECORATORS E FUNÇÕES AUXILIARES ==========

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

            # Buscar perfil do usuário por email
            profile_response = supabase.table("users")\
                .select("*")\
                .eq("email", user_response.user.email)\
                .execute()
            
            if not profile_response.data:
                return jsonify({"error": "Perfil do usuário não encontrado"}), 404

            g.user = profile_response.data[0]

        except Exception as e:
            print(f"🔴 Erro ao verificar token: {str(e)}")
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

def get_plan_from_supabase(plan_type, billing_cycle):
    """Busca plano do Supabase em vez do JSON local"""
    try:
        print(f"🟡 Buscando plano no Supabase: {plan_type} - {billing_cycle}")
        
        response = supabase.table("plans")\
            .select("*")\
            .eq("plan_type", plan_type)\
            .eq("billing_cycle", billing_cycle)\
            .eq("active", True)\
            .execute()
        
        if not response.data or len(response.data) == 0:
            print(f"🔴 Plano não encontrado: {plan_type} - {billing_cycle}")
            return None
            
        plan = response.data[0]
        print(f"✅ Plano encontrado: {plan['title']} - R$ {plan['unit_price']}")
        return plan
        
    except Exception as e:
        print(f"🔴 Erro ao buscar plano no Supabase: {str(e)}")
        return None

# ========== FUNÇÕES AUXILIARES REFATORADAS ==========

def get_mp_payment_details(payment_id):
    """
    Busca detalhes do pagamento no Mercado Pago
    """
    try:
        if not MERCADO_PAGO_ACCESS_TOKEN or MERCADO_PAGO_ACCESS_TOKEN == 'TEST-XXXX':
            print("⚠️ Token do Mercado Pago não configurado")
            return None

        headers = {
            'Authorization': f'Bearer {MERCADO_PAGO_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{MERCADO_PAGO_BASE_URL}/v1/payments/{payment_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"✅ Detalhes do pagamento {payment_id} obtidos com sucesso")
            return response.json()
        else:
            print(f"🔴 Erro ao buscar detalhes do pagamento: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"🔴 Erro na função get_mp_payment_details: {str(e)}")
        return None

def calculate_plan_duration(billing_cycle):
    """
    Calcula a duração do plano com base no ciclo de faturamento
    """
    if billing_cycle == 'semester':
        return 6  # meses
    elif billing_cycle == 'yearly':
        return 12  # meses
    else:
        print(f"⚠️ Ciclo de faturamento inválido: {billing_cycle}, usando padrão de 6 meses")
        return 6

def activate_user_plan_and_register_payment(checkout_session, payment_data):
    """
    Ativa o plano do usuário e registra o pagamento
    """
    try:
        print(f"🟡 Iniciando ativação do plano para sessão {checkout_session['id']}")
        
        # Calcular duração do plano
        duration_months = calculate_plan_duration(checkout_session['billing_cycle'])
        
        # Calcular datas
        current_time = datetime.datetime.utcnow()
        current_period_start = current_time
        current_period_end = current_time + datetime.timedelta(days=duration_months * 30)  # Aproximação de 30 dias por mês
        
        # Buscar detalhes do plano para obter features
        plan_details = get_plan_from_supabase(
            checkout_session['plan_type'], 
            checkout_session['billing_cycle']
        )
        
        if not plan_details:
            raise Exception("Plano não encontrado para ativação")
        
        # Preparar features do plano
        plan_features = {
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
        }.get(checkout_session['plan_type'], {})
        
        # ========== REGISTRAR PAGAMENTO ==========
        payment_record = {
            "user_id": checkout_session['user_id'],
            "plan_id": checkout_session['plan_id'],
            "amount": float(checkout_session['price_amount']),
            "currency": "BRL",
            "status": "paid",
            "payment_method": "mercado_pago",
            "mp_payment_id": payment_data.get('id'),
            "description": f"Pagamento plano {checkout_session['plan_type']} - {checkout_session['billing_cycle']}",
            "paid_at": current_time.isoformat(),
            "created_at": current_time.isoformat()
        }
        
        payment_insert = supabase.table("payments").insert(payment_record).execute()
        
        if not payment_insert.data:
            raise Exception("Erro ao registrar pagamento")
        
        print(f"✅ Pagamento registrado com ID: {payment_insert.data[0]['id']}")
        
        # ========== ATIVAR/ATUALIZAR PLANO DO USUÁRIO ==========
        user_plan_data = {
            "user_id": checkout_session['user_id'],
            "republica_id": checkout_session['republica_id'],
            "plan_type": checkout_session['plan_type'],
            "status": "active",
            "current_period_start": current_period_start.isoformat(),
            "current_period_end": current_period_end.isoformat(),
            "price_amount": float(checkout_session['price_amount']),
            "price_currency": "BRL",
            "features": plan_features,
            "updated_at": current_time.isoformat()
        }
        
        # Verificar se já existe um plano para atualizar ou criar novo
        existing_plan = supabase.table("user_plans")\
            .select("*")\
            .eq("user_id", checkout_session['user_id'])\
            .eq("republica_id", checkout_session['republica_id'])\
            .execute()
        
        if existing_plan.data and len(existing_plan.data) > 0:
            # Atualizar plano existente
            plan_update = supabase.table("user_plans")\
                .update(user_plan_data)\
                .eq("id", existing_plan.data[0]['id'])\
                .execute()
            
            if not plan_update.data:
                raise Exception("Erro ao atualizar plano do usuário")
            
            print(f"✅ Plano do usuário atualizado: {existing_plan.data[0]['id']}")
        else:
            # Criar novo plano
            user_plan_data["created_at"] = current_time.isoformat()
            plan_insert = supabase.table("user_plans").insert(user_plan_data).execute()
            
            if not plan_insert.data:
                raise Exception("Erro ao criar plano do usuário")
            
            print(f"✅ Novo plano do usuário criado: {plan_insert.data[0]['id']}")
        
        # ========== ATUALIZAR STATUS DA SESSÃO DE CHECKOUT ==========
        session_update = supabase.table("checkout_sessions")\
            .update({
                "status": "paid",
                "updated_at": current_time.isoformat()
            })\
            .eq("id", checkout_session['id'])\
            .execute()
        
        if not session_update.data:
            print("⚠️ Aviso: Sessão de checkout não foi atualizada, mas plano foi ativado")
        else:
            print(f"✅ Sessão de checkout atualizada para 'paid': {checkout_session['id']}")
        
        # Registrar atividade
        activity_data = {
            "user_id": checkout_session['user_id'],
            "republica_id": checkout_session['republica_id'],
            "activity_type": "plan_activated",
            "description": f"Plano {checkout_session['plan_type']} ativado via Mercado Pago",
            "metadata": {
                "plan_type": checkout_session['plan_type'],
                "billing_cycle": checkout_session['billing_cycle'],
                "price": checkout_session['price_amount'],
                "payment_id": payment_data.get('id')
            },
            "created_at": current_time.isoformat()
        }
        
        supabase.table("user_activities").insert(activity_data).execute()
        
        print(f"✅ Plano ativado com sucesso para o usuário {checkout_session['user_id']}")
        return True
        
    except Exception as e:
        print(f"🔴 Erro na função activate_user_plan_and_register_payment: {str(e)}")
        return False

# ========== CRIAÇÃO DE PREFERÊNCIA DE PAGAMENTO ==========

def create_mercado_pago_preference(user_data, plan_data, republica_id):
    """
    Cria uma preferência de pagamento no Mercado Pago
    """
    try:
        print(f"🟡 Criando preferência MP para {user_data['email']}")
        
        # 🔥 VERIFICAÇÃO CRÍTICA DO TOKEN
        if MERCADO_PAGO_ACCESS_TOKEN == 'TEST-XXXX' or not MERCADO_PAGO_ACCESS_TOKEN.startswith('APP_USR-'):
            print("🔴 Token do Mercado Pago inválido ou não configurado")
            raise Exception("Token do Mercado Pago não configurado corretamente")
        
        headers = {
            'Authorization': f'Bearer {MERCADO_PAGO_ACCESS_TOKEN}',
            'Content-Type': 'application/json',
            'User-Agent': 'Reppy/1.0'
        }
        
        BASE_URL = os.getenv('APP_BASE_URL') 
        
        if not BASE_URL:
            print("⚠️ ALERTA: APP_BASE_URL não está configurada.")
            BASE_URL = request.host_url.rstrip('/') 

        base_url = BASE_URL.rstrip('/')
        
        # URLs
        success_url = f"{base_url}/pagamentos/success"
        failure_url = f"{base_url}/pagamentos/failure"
        pending_url = f"{base_url}/pagamentos/pending"
        notification_url = f"{base_url}/pagamentos/webhook"
        
        # Garantir que temos uma imagem válida
        picture_url = plan_data.get('picture_url')
        if not picture_url:
            picture_url = f"{base_url}/static/images/plans/{plan_data['plan_type']}.jpg"
            print(f"🟡 Usando imagem padrão: {picture_url}")
        
        # Garantir que o preço seja float
        price_amount = float(plan_data['unit_price'])
        
        # Descrição do plano
        plan_description = plan_data.get('description', '')
        if not plan_description:
            if plan_data['plan_type'] == 'basic':
                plan_description = "Plano Basic - Ideal para repúblicas pequenas"
            elif plan_data['plan_type'] == 'premium':
                plan_description = "Plano Premium - Recursos completos para sua república"
        
        # Dados da preferência
        preference_data = {
            "items": [
                {
                    "id": plan_data['id'],
                    "title": f"Reppy - {plan_data['title']}",
                    "description": plan_description,
                    "picture_url": picture_url,
                    "category_id": "services",
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": price_amount
                }
            ],
            "payer": {
                "name": user_data.get('full_name', 'Cliente Reppy'),
                "email": user_data['email'],
                "identification": {
                    "type": "email",
                    "number": user_data['email']
                }
            },
            "back_urls": {
                "success": success_url,
                "failure": failure_url, 
                "pending": pending_url
            },
            "auto_return": "approved",
            "notification_url": notification_url,
            "external_reference": f"reppy_user_{user_data['id']}_plan_{plan_data['id']}_rep_{republica_id}",
            "metadata": {
                "user_id": user_data['id'],
                "user_email": user_data['email'],
                "plan_type": plan_data['plan_type'],
                "billing_cycle": plan_data['billing_cycle'],
                "republica_id": republica_id,
                "platform": "reppy",
                "product": "republica_management"
            },
            "statement_descriptor": "REPPY*PLANOS",
            "additional_info": f"Assinatura Reppy - {plan_data['title']}",
            "payment_methods": {
                "excluded_payment_types": [],
                "excluded_payment_methods": [],
                "installments": 12,
                "default_installments": 1
            },
            "expires": False
        }
        
        response = requests.post(
            f"{MERCADO_PAGO_BASE_URL}/checkout/preferences",
            headers=headers,
            json=preference_data,
            timeout=30
        )
        
        if response.status_code == 401:
            print("🔴 ERRO 401: Token do Mercado Pago inválido ou expirado")
            raise Exception("Token de acesso do Mercado Pago inválido. Verifique as credenciais.")
        
        if response.status_code == 403:
            print("🔴 ERRO 403: Acesso negado pelo Mercado Pago")
            error_data = response.json()
            raise Exception(f"Acesso negado: {error_data.get('message', 'Verifique as permissões da conta')}")
        
        if response.status_code != 201:
            error_msg = f"Erro ao criar preferência: {response.status_code} - {response.text}"
            print(f"🔴 {error_msg}")
            raise Exception(error_msg)
        
        result = response.json()
        print(f"✅ Preferência criada com sucesso: {result.get('id')}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"🔴 Erro de conexão com Mercado Pago: {str(e)}")
        raise Exception(f"Erro de conexão com o Mercado Pago: {str(e)}")
    except Exception as e:
        print(f"🔴 Erro ao criar preferência MP: {str(e)}")
        raise e

# ========== ROTAS PRINCIPAIS ==========

@pagamentos_bp.route("/create-checkout", methods=["POST"])
@token_required
def create_checkout():
    """
    Cria sessão de checkout no Mercado Pago
    """
    try:
        current_user = g.user
        data = request.get_json()
        
        if not data or 'plan_type' not in data:
            return jsonify({"error": "Tipo de plano é obrigatório"}), 400
        
        plan_type = data.get('plan_type')
        billing_cycle = data.get('billing_cycle', 'semester')
        
        print(f"🟡 Iniciando checkout para usuário {current_user['email']}")
        
        # Validar tipo de plano
        if plan_type not in ['basic', 'premium']:
            return jsonify({"error": "Tipo de plano inválido para checkout"}), 400
        
        # Validar ciclo de faturamento
        if billing_cycle not in ['semester', 'yearly']:
            return jsonify({"error": "Ciclo de faturamento inválido. Use 'semester' ou 'yearly'"}), 400
        
        # Buscar república do usuário
        republica = get_user_republic(current_user['id'])
        if not republica:
            return jsonify({"error": "Usuário não tem uma república cadastrada"}), 400
        
        print(f"🟡 República encontrada: {republica['name']}")
        
        # Buscar plano do Supabase
        plan = get_plan_from_supabase(plan_type, billing_cycle)
        if not plan:
            return jsonify({"error": "Plano não encontrado ou indisponível"}), 404
        
        # Criar preferência no Mercado Pago
        mp_preference = create_mercado_pago_preference(current_user, plan, republica['id'])
        
        # Salvar dados do checkout
        checkout_data = {
            "user_id": current_user['id'],
            "republica_id": republica['id'],
            "plan_id": plan['id'],
            "plan_type": plan_type,
            "billing_cycle": billing_cycle,
            "price_amount": float(plan['unit_price']),
            "mp_preference_id": mp_preference['id'],
            "status": "pending",
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        
        # Inserir registro de checkout
        insert_result = supabase.table("checkout_sessions").insert(checkout_data).execute()
        print(f"✅ Checkout salvo no banco: {len(insert_result.data)} registros")
        
        checkout_url = mp_preference.get('init_point')

        if not checkout_url:
            print("🔴 ERRO: 'init_point' não encontrado na resposta do MP.")
            raise Exception("init_point não encontrado na resposta do Mercado Pago")
        
        return jsonify({
            "checkout_url": checkout_url,
            "preference_id": mp_preference['id'],
            "plan_type": plan_type,
            "billing_cycle": billing_cycle,
            "price": float(plan['unit_price']),
            "plan_title": plan['title']
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao criar checkout: {str(e)}")
        return jsonify({"error": f"Erro ao criar checkout: {str(e)}"}), 500

# ========== WEBHOOK COMPLETO ==========

@pagamentos_bp.route("/webhook", methods=["POST"])
def mercado_pago_webhook():
    """
    Webhook para receber notificações do Mercado Pago
    """
    try:
        data = request.get_json()
        print(f"🟡 Webhook MP recebido: {data.get('type', 'unknown')}")
        
        # Verificar se é uma notificação de pagamento
        if data.get('type') == 'payment':
            payment_id = data.get('data', {}).get('id')
            
            if not payment_id:
                print("⚠️ Webhook recebido sem ID de pagamento")
                return jsonify({"status": "received"}), 200
            
            print(f"🟡 Processando pagamento: {payment_id}")
            
            # Buscar detalhes do pagamento
            payment_data = get_mp_payment_details(payment_id)
            
            if not payment_data:
                print(f"🔴 Não foi possível obter detalhes do pagamento {payment_id}")
                return jsonify({"status": "received"}), 200
            
            # Verificar status do pagamento
            payment_status = payment_data.get('status')
            print(f"🟡 Status do pagamento {payment_id}: {payment_status}")
            
            # Processar apenas pagamentos aprovados
            if payment_status != 'approved':
                print(f"⚠️ Pagamento {payment_id} não aprovado (status: {payment_status})")
                return jsonify({"status": "received"}), 200
            
            # Buscar external_reference para encontrar a checkout_session
            external_reference = payment_data.get('external_reference')
            if not external_reference:
                print(f"🔴 Pagamento {payment_id} sem external_reference")
                return jsonify({"status": "received"}), 200
            
            print(f"🟡 External reference: {external_reference}")
            
            # Buscar checkout_session pelo preference_id (mp_preference_id)
            # O external_reference contém informações, mas vamos buscar pela preference_id do pagamento
            preference_id = payment_data.get('point_of_interaction', {}).get('transaction_data', {}).get('preference_id')
            
            if not preference_id:
                print(f"🔴 Não foi possível encontrar preference_id no pagamento {payment_id}")
                return jsonify({"status": "received"}), 200
            
            # Buscar checkout_session pelo mp_preference_id
            checkout_response = supabase.table("checkout_sessions")\
                .select("*")\
                .eq("mp_preference_id", preference_id)\
                .eq("status", "pending")\
                .execute()
            
            if not checkout_response.data or len(checkout_response.data) == 0:
                print(f"🔴 Sessão de checkout não encontrada para preference_id: {preference_id}")
                return jsonify({"status": "received"}), 200
            
            checkout_session = checkout_response.data[0]
            print(f"✅ Sessão de checkout encontrada: {checkout_session['id']}")
            
            # Ativar plano e registrar pagamento
            success = activate_user_plan_and_register_payment(checkout_session, payment_data)
            
            if success:
                print(f"✅ Processamento completo do pagamento {payment_id}")
            else:
                print(f"🔴 Falha no processamento do pagamento {payment_id}")
        
        return jsonify({"status": "received"}), 200
        
    except Exception as e:
        print(f"🔴 Erro no webhook MP: {str(e)}")
        # Sempre retornar 200 para evitar reenvios
        return jsonify({"status": "received"}), 200

# ========== ROTAS DE REDIRECIONAMENTO ==========

@pagamentos_bp.route("/success", methods=["GET"])
def payment_success():
    """Página de sucesso do pagamento"""
    return jsonify({
        "message": "Pagamento aprovado! Seu plano será ativado em breve.",
        "next_steps": [
            "Aguarde a confirmação do pagamento",
            "Seu plano será ativado automaticamente",
            "Você receberá um email de confirmação"
        ]
    }), 200

@pagamentos_bp.route("/failure", methods=["GET"])
def payment_failure():
    """Página de falha do pagamento"""
    return jsonify({
        "error": "Pagamento não aprovado",
        "suggestion": "Tente novamente ou entre em contato com o suporte"
    }), 400

@pagamentos_bp.route("/pending", methods=["GET"])
def payment_pending():
    """Página de pagamento pendente"""
    return jsonify({
        "message": "Pagamento pendente",
        "instructions": "Aguarde a confirmação do pagamento. Você receberá um email quando for aprovado."
    }), 200

# ========== HEALTH CHECK ==========

@pagamentos_bp.route("/health", methods=["GET"])
def health_check():
    """Health check do serviço de pagamentos"""
    mp_configured = MERCADO_PAGO_ACCESS_TOKEN != 'TEST-XXXX' and MERCADO_PAGO_ACCESS_TOKEN.startswith('APP_USR-')
    
    return jsonify({
        "status": "healthy",
        "service": "pagamentos",
        "mp_configured": mp_configured,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }), 200