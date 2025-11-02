import os
import json
from flask import current_app
from pathlib import Path
from typing import List, Dict, Any

PACKAGE_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
STATIC_DATA_PATH = PACKAGE_ROOT / "static_data"

def get_static_json(filename: str, subfolder: str = None):
    """
    Lê e retorna o conteúdo de um arquivo JSON da pasta static_data.
    """
    if not filename.endswith('.json'):
        filename = f"{filename}.json"

    # Segurança: Evita path traversal
    if '..' in filename or filename.startswith('/'):
        current_app.logger.warning(f"Tentativa de Path Traversal bloqueada: {filename}")
        return None

    # Constrói o caminho completo
    if subfolder:
        filepath = STATIC_DATA_PATH / subfolder / filename
    else:
        filepath = STATIC_DATA_PATH / filename
    
    current_app.logger.info(f"Procurando arquivo em: {filepath}")
    
    if not filepath.exists():
        current_app.logger.error(f"Arquivo não encontrado: {filepath}")
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            current_app.logger.info(f"Dados carregados com sucesso: {filename}")
            return data
    except Exception as e:
        current_app.logger.error(f"Erro ao ler arquivo {filename}: {e}")
        return None

def get_chamada1_data(cidade: str) -> List[Dict[str, Any]]:
    """
    Busca os dados da chamada 1 de uma cidade.
    Retorna array de candidatos classificados.
    """
    data = get_static_json("c1", f"chamadas/{cidade}")
    
    if data is None:
        return []
    
    # Filtra apenas os candidatos da chamada 1
    candidatos_chamada1 = [candidato for candidato in data if candidato.get('chamada') == 1]
    return candidatos_chamada1

def get_all_city_data(cidade: str) -> List[Dict[str, Any]]:
    """
    Busca TODOS os dados de uma cidade (todas as chamadas).
    Retorna array completo de candidatos.
    """
    data = get_static_json(f"{cidade}", f"cities/{cidade}")
    
    if data is None:
        return []
    
    return data

def get_courses_summary(cidade: str) -> Dict[str, Any]:
    """
    Retorna um resumo com estatísticas por curso.
    """
    all_data = get_all_city_data(cidade)
    
    if not all_data:
        return {}
    
    # Agrupa por curso
    cursos = {}
    for candidato in all_data:
        curso = candidato.get('curso_limpo', candidato.get('curso'))
        if curso not in cursos:
            cursos[curso] = {
                'curso': curso,
                'total_candidatos': 0,
                'chamada1': 0,
                'genero': {'M': 0, 'F': 0},
                'unidade': candidato.get('unidade')
            }
        
        cursos[curso]['total_candidatos'] += 1
        if candidato.get('chamada') == 1:
            cursos[curso]['chamada1'] += 1
        
        genero = candidato.get('genero')
        if genero in cursos[curso]['genero']:
            cursos[curso]['genero'][genero] += 1
    
    return {
        'cidade': cidade,
        'total_candidatos': len(all_data),
        'cursos': list(cursos.values())
    }

def get_candidates_by_course(cidade: str, curso: str, chamada: int = None) -> List[Dict[str, Any]]:
    """
    Busca candidatos por curso e opcionalmente por chamada.
    """
    all_data = get_all_city_data(cidade)
    
    if not all_data:
        return []
    
    filtered_data = []
    for candidato in all_data:
        curso_candidato = candidato.get('curso_limpo', candidato.get('curso'))
        if curso_candidato == curso:
            if chamada is None or candidato.get('chamada') == chamada:
                filtered_data.append(candidato)
    
    return filtered_data