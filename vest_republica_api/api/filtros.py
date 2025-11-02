import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from supabase import create_client
from functools import wraps

# Cria o blueprint
filtros_bp = Blueprint('filtros', __name__)

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

@filtros_bp.route('/filtros/salvar', methods=['POST'])
@token_required
def salvar_filtro():
    try:
        current_user = g.user
        data = request.get_json()
        
        name = data.get('name')
        filter_type = data.get('filter_type')
        filters = data.get('filters')
        is_shared = data.get('is_shared', False)
        
        if not all([name, filter_type, filters]):
            return jsonify({'error': 'Nome, tipo e filtros são obrigatórios'}), 400
        
        # Gerar token de compartilhamento se for compartilhado
        share_token = str(uuid.uuid4()) if is_shared else None
        
        # Criar filtro
        filter_data = {
            "user_id": current_user['id'],
            "name": name,
            "filter_type": filter_type,
            "filters": filters,
            "is_shared": is_shared,
            "share_token": share_token,
            "usage_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        insert_response = supabase.table("user_filters").insert(filter_data).execute()
        
        if not insert_response.data:
            return jsonify({'error': 'Erro ao salvar filtro'}), 500
        
        novo_filtro = insert_response.data[0]
        
        return jsonify({
            'message': 'Filtro salvo com sucesso',
            'filtro_id': novo_filtro['id'],
            'share_token': share_token
        }), 201
        
    except Exception as e:
        print(f"🔴 Erro ao salvar filtro: {str(e)}")
        return jsonify({'error': f'Erro ao salvar filtro: {str(e)}'}), 500

@filtros_bp.route('/filtros/editar/<int:filtro_id>', methods=['PUT'])
@token_required
def editar_filtro(filtro_id):
    try:
        current_user = g.user
        data = request.get_json()
        
        # Verificar se o filtro existe e pertence ao usuário
        filtro_response = supabase.table("user_filters")\
            .select("*")\
            .eq("id", filtro_id)\
            .eq("user_id", current_user['id'])\
            .execute()
        
        if not filtro_response.data:
            return jsonify({'error': 'Filtro não encontrado'}), 404
        
        # Atualizar campos
        update_data = {"updated_at": datetime.utcnow().isoformat()}
        
        if 'name' in data:
            update_data['name'] = data['name']
        if 'filters' in data:
            update_data['filters'] = data['filters']
        if 'is_shared' in data:
            update_data['is_shared'] = data['is_shared']
            if data['is_shared'] and not filtro_response.data[0]['share_token']:
                update_data['share_token'] = str(uuid.uuid4())
            elif not data['is_shared']:
                update_data['share_token'] = None
        
        update_response = supabase.table("user_filters")\
            .update(update_data)\
            .eq("id", filtro_id)\
            .execute()
        
        return jsonify({
            'message': 'Filtro atualizado com sucesso',
            'filtro_id': filtro_id
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao editar filtro: {str(e)}")
        return jsonify({'error': f'Erro ao editar filtro: {str(e)}'}), 500

@filtros_bp.route('/filtros/excluir/<int:filtro_id>', methods=['DELETE'])
@token_required
def excluir_filtro(filtro_id):
    try:
        current_user = g.user
        
        # Verificar se o filtro existe e pertence ao usuário
        filtro_response = supabase.table("user_filters")\
            .select("*")\
            .eq("id", filtro_id)\
            .eq("user_id", current_user['id'])\
            .execute()
        
        if not filtro_response.data:
            return jsonify({'error': 'Filtro não encontrado'}), 404
        
        # Excluir filtro
        delete_response = supabase.table("user_filters")\
            .delete()\
            .eq("id", filtro_id)\
            .execute()
        
        return jsonify({
            'message': 'Filtro excluído com sucesso',
            'filtro_id': filtro_id
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao excluir filtro: {str(e)}")
        return jsonify({'error': f'Erro ao excluir filtro: {str(e)}'}), 500

@filtros_bp.route('/filtros/carregar/<int:filtro_id>', methods=['GET'])
@token_required
def carregar_filtro(filtro_id):
    try:
        current_user = g.user
        
        # Buscar filtro
        filtro_response = supabase.table("user_filters")\
            .select("*")\
            .eq("id", filtro_id)\
            .eq("user_id", current_user['id'])\
            .execute()
        
        if not filtro_response.data:
            return jsonify({'error': 'Filtro não encontrado'}), 404
        
        filtro = filtro_response.data[0]
        
        # Incrementar contador de uso
        update_response = supabase.table("user_filters")\
            .update({
                "usage_count": filtro['usage_count'] + 1,
                "updated_at": datetime.utcnow().isoformat()
            })\
            .eq("id", filtro_id)\
            .execute()
        
        return jsonify({
            'id': filtro['id'],
            'name': filtro['name'],
            'filter_type': filtro['filter_type'],
            'filters': filtro['filters'],
            'is_shared': filtro['is_shared'],
            'usage_count': filtro['usage_count'] + 1,
            'created_at': filtro['created_at'],
            'updated_at': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao carregar filtro: {str(e)}")
        return jsonify({'error': f'Erro ao carregar filtro: {str(e)}'}), 500

@filtros_bp.route('/filtros/listar', methods=['GET'])
@token_required
def listar_filtros():
    try:
        current_user = g.user
        
        # Buscar todos os filtros do usuário
        filtros_response = supabase.table("user_filters")\
            .select("*")\
            .eq("user_id", current_user['id'])\
            .order("updated_at", desc=True)\
            .execute()
        
        filtros_data = filtros_response.data if filtros_response.data else []
        
        return jsonify({
            'filtros': filtros_data,
            'total': len(filtros_data)
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao listar filtros: {str(e)}")
        return jsonify({'error': f'Erro ao listar filtros: {str(e)}'}), 500

@filtros_bp.route('/filtros/compartilhados/<string:share_token>', methods=['GET'])
def carregar_filtro_compartilhado(share_token):
    try:
        # Buscar filtro compartilhado
        filtro_response = supabase.table("user_filters")\
            .select("*")\
            .eq("share_token", share_token)\
            .eq("is_shared", True)\
            .execute()
        
        if not filtro_response.data:
            return jsonify({'error': 'Filtro compartilhado não encontrado'}), 404
        
        filtro = filtro_response.data[0]
        
        # Incrementar contador de uso
        update_response = supabase.table("user_filters")\
            .update({
                "usage_count": filtro['usage_count'] + 1,
                "updated_at": datetime.utcnow().isoformat()
            })\
            .eq("id", filtro['id'])\
            .execute()
        
        return jsonify({
            'id': filtro['id'],
            'name': filtro['name'],
            'filter_type': filtro['filter_type'],
            'filters': filtro['filters'],
            'usage_count': filtro['usage_count'] + 1,
            'created_at': filtro['created_at']
        }), 200
        
    except Exception as e:
        print(f"🔴 Erro ao carregar filtro compartilhado: {str(e)}")
        return jsonify({'error': f'Erro ao carregar filtro compartilhado: {str(e)}'}), 500

@filtros_bp.route("/health", methods=["GET"])
def filtros_health():
    """Health check específico para filtros"""
    return jsonify({"status": "healthy", "service": "filtros"}), 200