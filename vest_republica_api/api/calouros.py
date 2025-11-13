import os
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from supabase import create_client
from functools import wraps

# Cria o blueprint
calouros_bp = Blueprint('calouros', __name__)

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
# Adicione esta rota ao seu calouros_bp no backend

@calouros_bp.route('/selecionados', methods=['GET'])
@token_required
def listar_calouros_selecionados():
    """Lista TODOS os calouros do usuário (sem filtro) COM DADOS DA MASTER"""
    try:
        current_user = g.user
        
        # 1. Buscar república do usuário
        republica = get_user_republic(current_user['id'])
        if not republica:
            return jsonify({'error': 'Usuário não tem uma república cadastrada'}), 400
        
        # 2. 🔥 BUSCAR CALOUROS DO CRM FAZENDO JOIN COM A MASTER
        # O select "*, master_calouros(*)" faz o JOIN
        calouros_response = supabase.table("republica_calouros")\
            .select("*, master_calouros(*)")\
            .eq("republica_id", republica['id'])\
            .order("created_at", desc=True)\
            .execute()
        
        calouros_data = calouros_response.data if calouros_response.data else []
        
        print(f"✅ Retornando {len(calouros_data)} calouros do banco (com JOIN)")
        
        # 3. Formatar os dados para o frontend
        # O frontend espera uma lista "achatada" (flat)
        formatted_calouros = []
        for crm_entry in calouros_data:
            master_data = crm_entry.get('master_calouros')
            
            # Pular se o JOIN falhar (deve ser raro)
            if not master_data:
                print(f"🟡 Alerta: Entrada de CRM ID {crm_entry.get('id')} sem master_calouro correspondente.")
                continue
                
            formatted = {
                # Dados do CRM
                "id": crm_entry.get('id'), # ID do CRM (importante!)
                "republica_id": crm_entry.get('republica_id'),
                "status": crm_entry.get('status'),
                "favourite": crm_entry.get('favourite'),
                "notes": crm_entry.get('notes'),
                "email": crm_entry.get('email'),
                "phone": crm_entry.get('phone'),
                
                # Dados da Master (o que o frontend precisa)
                "name": master_data.get('name'),
                "course": master_data.get('course'),
                "university": master_data.get('university'),
                "campus": master_data.get('unidade'), # Mapeando unidade -> campus
                "gender": master_data.get('genero'),
                "entrance_year": 2025 # Você pode precisar buscar isso da master se tiver
                # "chamada": master_data.get('chamada'), # Se o frontend precisar
            }
            formatted_calouros.append(formatted)

        return jsonify({
            'calouros': formatted_calouros, # Enviar dados formatados
            'total': len(formatted_calouros)
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao listar calouros selecionados: {str(e)}")
        return jsonify({'error': f'Erro ao listar calouros selecionados: {str(e)}'}), 500
    
@calouros_bp.route('/<int:calouro_id>/favorite', methods=['PUT'])
@token_required
def favoritar_calouro(calouro_id):
    """Atualizar status de favorito do calouro"""
    try:
        current_user = g.user
        data = request.get_json()
        
        print(f"🔵 Dados recebidos: {data}")  # DEBUG
        print(f"🔵 Tipo dos dados: {type(data)}")  # DEBUG
        
        # Se data for string, tentar parsear como JSON
        if isinstance(data, str):
            try:
                import json
                data = json.loads(data)
            except json.JSONDecodeError as e:
                return jsonify({'error': f'JSON inválido: {str(e)}'}), 400
        
        favourite = data.get('favourite')
        
        if favourite is None:
            return jsonify({'error': 'Campo favourite é obrigatório'}), 400
        
        # Garantir que é booleano
        if isinstance(favourite, str):
            if favourite.lower() == 'true':
                favourite = True
            elif favourite.lower() == 'false':
                favourite = False
            else:
                return jsonify({'error': 'Valor de favourite inválido. Deve ser true ou false'}), 400
        
        print(f"🔵 Favourite após conversão: {favourite}, tipo: {type(favourite)}")  # DEBUG
        
        # Verificar se o calouro existe e pertence à república do usuário
        republica = get_user_republic(current_user['id'])
        if not republica:
            return jsonify({'error': 'Usuário não tem uma república cadastrada'}), 400
        
        calouro_response = supabase.table("republica_calouros")\
            .select("*")\
            .eq("id", calouro_id)\
            .eq("republica_id", republica['id'])\
            .execute()
        
        if not calouro_response.data:
            return jsonify({'error': 'Calouro não encontrado'}), 404
        
        # Atualizar calouro
        update_response = supabase.table("republica_calouros")\
            .update({
                "favourite": favourite,
                "updated_at": datetime.utcnow().isoformat()
            })\
            .eq("id", calouro_id)\
            .execute()
        
        print(f"🔵 Resposta do Supabase: {update_response}")  # DEBUG
        
        return jsonify({
            'message': 'Favorito do calouro atualizado com sucesso',
            'calouro_id': calouro_id,
            'favourite': favourite
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao atualizar favorito do calouro: {str(e)}")
        return jsonify({'error': f'Erro ao atualizar favorito do calouro: {str(e)}'}), 500


@calouros_bp.route('/', methods=['POST'])
@token_required
def criar_calouro():
    try:
        current_user = g.user
        data = request.get_json()
        
        print(f"🔵 DADOS RECEBIDOS DO FRONTEND: {data}")

        # 1. Buscar república do usuário
        republica = get_user_republic(current_user['id'])
        if not republica:
            return jsonify({'error': 'Usuário não tem uma república cadastrada'}), 400

        # 2. Encontrar o Calouro na tabela Master
        #    (O frontend está enviando 'campus', que no seu DB master é 'unidade')
        master_calouro_response = supabase.table("master_calouros")\
            .select("id")\
            .eq("name", data.get('name'))\
            .eq("course", data.get('course'))\
            .eq("university", data.get('university'))\
            .eq("unidade", data.get('campus')) \
            .execute()
        
        if not master_calouro_response.data:
            print(f"🔴 Erro crítico: Calouro não encontrado na master_calouros.")
            print(f"   Nome: {data.get('name')}, Curso: {data.get('course')}, Unidade: {data.get('campus')}")
            return jsonify({'error': 'Calouro não encontrado no banco de dados principal'}), 404

        master_calouro_id = master_calouro_response.data[0]['id']
        print(f"✅ Calouro mestre encontrado: ID {master_calouro_id}")

        # 3. Verificar se a república já salvou este calouro (evitar duplicatas)
        existing_crm_entry = supabase.table("republica_calouros")\
            .select("id")\
            .eq("republica_id", republica['id'])\
            .eq("master_calouro_id", master_calouro_id)\
            .execute()
        
        if existing_crm_entry.data:
            print(f"🟡 Calouro já existe no CRM da república. ID: {existing_crm_entry.data[0]['id']}")
            return jsonify({
                'message': 'Calouro já existe',
                'calouro_id': existing_crm_entry.data[0]['id']
            }), 200

        # 4. Criar a nova entrada de CRM (só com IDs e dados do CRM)
        novo_status = data.get('status', 'pending')

        novo_calouro_data_crm = {
            "republica_id": republica['id'],
            "master_calouro_id": master_calouro_id,
            "created_by": current_user['id'],
            "status": novo_status, # Usa a variável
            "favourite": data.get('favourite', False),
            "email": data.get('email'), 
            "phone": data.get('phone')
        }

        # 🔥 AUTOMAÇÃO DE DATA NA CRIAÇÃO
        # Se o calouro está sendo criado JÁ com o status 'contacted'
        if novo_status == 'contacted':
            print(f"🔥 Automação na CRIAÇÃO: Definindo contact_date")
            novo_calouro_data_crm['contact_date'] = datetime.utcnow().isoformat()

        print(f"🔵 Inserindo no CRM: {novo_calouro_data_crm}")
        
        create_response = supabase.table("republica_calouros")\
            .insert(novo_calouro_data_crm)\
            .execute()

        if not create_response.data:
            print(f"🔴 Erro ao inserir na tabela republica_calouros: {create_response.error}")
            return jsonify({'error': 'Erro ao salvar calouro no CRM'}), 500

        print(f"✅ Calouro salvo no CRM com sucesso. ID: {create_response.data[0]['id']}")
        
        return jsonify({
            'message': 'Calouro criado com sucesso',
            'calouro_id': create_response.data[0]['id']
        }), 201
            
    except Exception as e:
        print(f"🔴 Erro fatal ao criar calouro: {str(e)}")
        # Tenta extrair a mensagem de erro do Supabase se for um erro de DB
        error_message = str(e)
        if hasattr(e, 'message'):
            error_message = e.message
        
        return jsonify({'error': f'Erro ao criar calouro: {error_message}'}), 500
    

@calouros_bp.route('/<int:calouro_id>/status', methods=['PUT'])
@token_required
def atualizar_status_calouro(calouro_id):
    try:
        current_user = g.user
        data = request.get_json()
        
        novo_status = data.get('status')
        notes = data.get('notes')
        contact_date = data.get('contact_date')
        interview_date = data.get('interview_date')
        
        if not novo_status:
            return jsonify({'error': 'Novo status é obrigatório'}), 400
        
        # 🔥 CORREÇÃO: O frontend já envia o status no formato do banco (inglês)
        # Remover o mapeamento desnecessário
        status_db = novo_status  # Já vem em inglês do frontend
        
        print(f"🟡 Status recebido do frontend: {novo_status} -> Salvo como: {status_db}")  # DEBUG
        
        # Verificar se o calouro existe e pertence à república do usuário
        republica = get_user_republic(current_user['id'])
        if not republica:
            return jsonify({'error': 'Usuário não tem uma república cadastrada'}), 400
        
        calouro_response = supabase.table("republica_calouros")\
            .select("*")\
            .eq("id", calouro_id)\
            .eq("republica_id", republica['id'])\
            .execute()
        
        if not calouro_response.data:
         return jsonify({'error': 'Calouro não encontrado'}), 404
 

        calouro_atual = calouro_response.data[0]

        update_data = {
        "status": status_db, 
         "updated_at": datetime.utcnow().isoformat()
         }

         # Se o usuário não enviou uma data manualmente E
         # o status está mudando de 'pending' para 'contacted'
        if not contact_date and calouro_atual['status'] == 'pending' and status_db == 'contacted':
             print(f"🔥 Automação: Definindo contact_date para {calouro_atual['id']}")
             update_data['contact_date'] = datetime.utcnow().isoformat()
        elif contact_date:
             # Se o usuário enviou uma data (ex: do futuro modal), usa ela
             update_data['contact_date'] = contact_date

         # Adiciona outros campos se existirem
        if notes is not None:
         update_data['notes'] = notes
        if interview_date:
            update_data['interview_date'] = interview_date
        
        # Atualizar calouro
        update_response = supabase.table("republica_calouros")\
            .update(update_data)\
            .eq("id", calouro_id)\
            .execute()
        
        print(f"🟡 Resposta da atualização: {update_response}")  # DEBUG
        
        return jsonify({
            'message': 'Status do calouro atualizado com sucesso',
            'calouro_id': calouro_id,
            'status': status_db
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao atualizar status do calouro: {str(e)}")
        return jsonify({'error': f'Erro ao atualizar status do calouro: {str(e)}'}), 500

@calouros_bp.route('/', methods=['GET'])
@token_required
def listar_calouros():
    try:
        current_user = g.user
        
        # Buscar república do usuário
        republica = get_user_republic(current_user['id'])
        if not republica:
            return jsonify({'error': 'Usuário não tem uma república cadastrada'}), 400
        
        # Parâmetros de filtro
        status = request.args.get('status')
        campus = request.args.get('campus')
        university = request.args.get('university')
        favourite = request.args.get('favourite')
        
        # Query base
        query = supabase.table("republica_calouros")\
            .select("*")\
            .eq("republica_id", republica['id'])
        
        # Aplicar filtros
        if status:
            query = query.eq("status", status)
        if campus:
            query = query.eq("campus", campus)
        if university:
            query = query.eq("university", university)
        if favourite is not None:
            query = query.eq("favourite", favourite.lower() == 'true')
        
        # Executar query
        calouros_response = query.order("created_at", desc=True).execute()
        
        calouros_data = calouros_response.data if calouros_response.data else []
        
        return jsonify({
            'calouros': calouros_data,
            'total': len(calouros_data)
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao listar calouros: {str(e)}")
        return jsonify({'error': f'Erro ao listar calouros: {str(e)}'}), 500

@calouros_bp.route('/estatisticas', methods=['GET'])
@token_required
def estatisticas_calouros():
    try:
        current_user = g.user
        
        # Buscar república do usuário
        republica = get_user_republic(current_user['id'])
        if not republica:
            return jsonify({'error': 'Usuário não tem uma república cadastrada'}), 400
        
        # Buscar todos os calouros da república
        calouros_response = supabase.table("republica_calouros")\
            .select("status, favourite")\
            .eq("republica_id", republica['id'])\
            .execute()
        
        calouros_data = calouros_response.data if calouros_response.data else []
        
        # Calcular estatísticas
        por_status = {}
        total_favoritos = 0
        
        for calouro in calouros_data:
            # Contar por status
            status = calouro['status']
            por_status[status] = por_status.get(status, 0) + 1
            
            # Contar favoritos
            if calouro['favourite']:
                total_favoritos += 1
        
        estatisticas = {
            'por_status': por_status,
            'total_favoritos': total_favoritos,
            'total_calouros': len(calouros_data)
        }
        
        return jsonify(estatisticas), 200
        
    except Exception as e:
        print(f"🔴 Erro ao buscar estatísticas: {str(e)}")
        return jsonify({'error': f'Erro ao buscar estatísticas: {str(e)}'}), 500

@calouros_bp.route("/health", methods=["GET"])
def calouros_health():
    """Health check específico para calouros"""
    return jsonify({"status": "healthy", "service": "calouros"}), 200