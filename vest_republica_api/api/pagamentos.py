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

def create_mercado_pago_preference(user_data, plan_data, republica_id):
    """
    Cria uma preferência de pagamento no Mercado Pago
    """
    try:
        print(f"🟡 Criando preferência MP para {user_data['email']}")
        print(f"🟡 Plano: {plan_data['title']} - R$ {plan_data['unit_price']}")
        
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
            print("🔴 ALERTA: APP_BASE_URL não está configurada. A API do MP pode falhar.")
            # Como fallback (não ideal para MP)
            BASE_URL = request.host_url.rstrip('/') 

        # Garante que a URL não tem uma barra no final
        base_url = BASE_URL.rstrip('/')
        
        # URLs agora usarão a URL pública
        success_url = f"{base_url}/pagamentos/success"
        failure_url = f"{base_url}/pagamentos/failure"
        pending_url = f"{base_url}/pagamentos/pending"
        notification_url = f"{base_url}/pagamentos/webhook"
        
        # 🔥 CORREÇÃO: O preço deve ser um número (float) - JÁ CORRETO DO BANCO
        price_amount = float(plan_data['unit_price'])
        
        # 🔥 CORREÇÃO: Habilitar PIX explicitamente
        preference_data = {
            "items": [
                {
                    "id": plan_data['id'],
                    "title": plan_data['title'],
                    "description": plan_data['description'],
                    "picture_url": plan_data['picture_url'],
                    "category_id": plan_data.get('category_id', 'services'),
                    "quantity": 1,
                    "currency_id": plan_data.get('currency_id', 'BRL'),
                    "unit_price": price_amount  # Já em reais, não multiplicar!
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
            "external_reference": f"user_{user_data['id']}_plan_{plan_data['id']}",
            "metadata": {
                "user_id": user_data['id'],
                "plan_type": plan_data['plan_type'],
                "billing_cycle": plan_data['billing_cycle'],
                "republica_id": republica_id,
                "platform": "reppy"
            },
            "statement_descriptor": "REPPY",
            "additional_info": plan_data.get('additional_info', 'Assinatura Reppy'),
            # 🔥 CORREÇÃO: Habilitar PIX explicitamente
           "payment_methods": {
    "included_payment_types": [
        {"id": "pix"},
        {"id": "credit_card"},
        {"id": "debit_card"},
        {"id": "ticket"}  # Boleto
    ],
    "installments": 1,
    "default_installments": 1
}
        }
        
        print(f"🟡 Dados da preferência: {json.dumps(preference_data, indent=2)}")
        
        response = requests.post(
            f"{MERCADO_PAGO_BASE_URL}/checkout/preferences",
            headers=headers,
            json=preference_data,
            timeout=30
        )
        
        print(f"🟡 Resposta MP - Status: {response.status_code}")
        
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
        billing_cycle = data.get('billing_cycle', 'semester')  # 🔥 Mudei para 'semester' como padrão
        
        print(f"🟡 Iniciando checkout para usuário {current_user['email']}")
        print(f"🟡 Plano: {plan_type}, Ciclo: {billing_cycle}")
        
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
        
        print(f"🟡 Preço do plano: R$ {plan['unit_price']}")
        
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
        print(f"🟡 Checkout salvo no banco: {len(insert_result.data)} registros")
        
 
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

@pagamentos_bp.route("/plans", methods=["GET"])
@token_required
def get_plans():
    """Busca todos os planos disponíveis do Supabase"""
    try:
        print("🟡 Buscando planos no Supabase...")
        
        response = supabase.table("plans")\
            .select("*")\
            .eq("active", True)\
            .execute()
        
        if not response.data:
            return jsonify({"error": "Nenhum plano encontrado"}), 404
        
        plans = response.data
        print(f"✅ {len(plans)} planos encontrados")
        
        return jsonify({
            "plans": plans,
            "count": len(plans)
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao buscar planos: {str(e)}")
        return jsonify({"error": f"Erro ao buscar planos: {str(e)}"}), 500

@pagamentos_bp.route("/webhook", methods=["POST"])
def mercado_pago_webhook():
    """
    Webhook para receber notificações do Mercado Pago
    """
    try:
        data = request.get_json()
        print(f"🟡 Webhook MP recebido: {json.dumps(data, indent=2)}")
        
        # Verificar se é uma notificação de pagamento
        if data.get('type') == 'payment':
            payment_id = data.get('data', {}).get('id')
            print(f"🟡 Processando pagamento: {payment_id}")
            
            # Buscar detalhes do pagamento
            headers = {
                'Authorization': f'Bearer {MERCADO_PAGO_ACCESS_TOKEN}',
                'Content-Type': 'application/json'
            }
            
            payment_response = requests.get(
                f"{MERCADO_PAGO_BASE_URL}/v1/payments/{payment_id}",
                headers=headers
            )
            
            if payment_response.status_code == 200:
                payment_data = payment_response.json()
                print(f"🟡 Dados do pagamento: {json.dumps(payment_data, indent=2)}")
                
                # Aqui você processaria o pagamento e ativaria o plano
                # status = payment_data.get('status')
                # external_reference = payment_data.get('external_reference')
                
        return jsonify({"status": "received"}), 200
        
    except Exception as e:
        print(f"🔴 Erro no webhook MP: {str(e)}")
        return jsonify({"error": "Erro no webhook"}), 500

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

@pagamentos_bp.route("/health", methods=["GET"])
def health_check():
    """Health check do serviço de pagamentos"""
    return jsonify({
        "status": "healthy",
        "service": "pagamentos",
        "mp_configured": MERCADO_PAGO_ACCESS_TOKEN != 'TEST-XXXX'
    }), 200