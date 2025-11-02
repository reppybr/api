from flask import Blueprint, jsonify, request
from ..services.data_service import (
    get_chamada1_data, 
    get_all_city_data, 
    get_courses_summary,
    get_candidates_by_course
)

dados_bp = Blueprint('dados', __name__)

@dados_bp.route('/cidade/<string:cidade>/completo', methods=['GET'])
def get_dados_completos(cidade):
    """
    Retorna TODOS os dados de uma cidade (todas as chamadas).
    Exemplo: GET /api/v1/cidade/piracicaba/completo
    """
    data = get_all_city_data(cidade)
    
    if not data:
        return jsonify({
            "error": f"Dados não encontrados para a cidade '{cidade}'.",
            "cidade": cidade
        }), 404
        
    return jsonify({
        "cidade": cidade,
        "total_candidatos": len(data),
        "dados": data
    }), 200

@dados_bp.route('/cidade/<string:cidade>/chamada1', methods=['GET'])
def get_chamada1_cidade(cidade):
    """
    Retorna apenas os candidatos da CHAMADA 1 de uma cidade.
    Exemplo: GET /api/v1/cidade/piracicaba/chamada1
    """
    data = get_chamada1_data(cidade)
    
    if not data:
        return jsonify({
            "error": f"Dados da chamada 1 não encontrados para a cidade '{cidade}'.",
            "cidade": cidade
        }), 404
        
    return jsonify({
        "cidade": cidade,
        "chamada": 1,
        "total_classificados": len(data),
        "candidatos": data
    }), 200

@dados_bp.route('/cidade/<string:cidade>/resumo', methods=['GET'])
def get_resumo_cidade(cidade):
    """
    Retorna um resumo estatístico da cidade.
    Exemplo: GET /api/v1/cidade/piracicaba/resumo
    """
    resumo = get_courses_summary(cidade)
    
    if not resumo:
        return jsonify({
            "error": f"Dados não encontrados para a cidade '{cidade}'.",
            "cidade": cidade
        }), 404
        
    return jsonify(resumo), 200

@dados_bp.route('/cidade/<string:cidade>/curso/<string:curso>', methods=['GET'])
def get_curso_cidade(cidade, curso):
    """
    Retorna candidatos de um curso específico.
    Parâmetros: chamada (opcional) - filtrar por chamada específica
    Exemplo: 
      GET /api/v1/cidade/piracicaba/curso/Odontologia (I)
      GET /api/v1/cidade/piracicaba/curso/Odontologia (I)?chamada=1
    """
    chamada = request.args.get('chamada', type=int)
    
    data = get_candidates_by_course(cidade, curso, chamada)
    
    if not data:
        return jsonify({
            "error": f"Nenhum candidato encontrado para o curso '{curso}' na cidade '{cidade}'",
            "cidade": cidade,
            "curso": curso,
            "chamada": chamada
        }), 404
        
    return jsonify({
        "cidade": cidade,
        "curso": curso,
        "chamada": chamada,
        "total_candidatos": len(data),
        "candidatos": data
    }), 200

@dados_bp.route('/cidades', methods=['GET'])
def get_cidades_disponiveis():
    """
    Retorna a lista de cidades disponíveis na API.
    Exemplo: GET /api/v1/cidades
    """
    cidades = ["campinas", "limeira", "piracicaba"]
    
    return jsonify({
        "cidades": cidades,
        "total": len(cidades)
    }), 200