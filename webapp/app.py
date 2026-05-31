"""
Aplicación Web Unificada para QualityAI
Servidor Flask que expone los servicios de ambos módulos:
- Módulo 1: Requirements Refiner (análisis de ambigüedades)
- Módulo 2: Test Architect (generación de escenarios Gherkin)
"""

import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer
import chromadb

from src.ambiguity_detector import AmbiguityDetector
from src.contract_a import (
    AcceptanceCriterion,
    AmbiguityResolution,
    RefinedRequirements,
    UserStory,
    Priority,
    StoryType,
)
from src.contract_b import (
    CoverageMatrix,
    GherkinFeature,
    GherkinScenario,
    GherkinStep,
    GherkinTestSuite,
    QualityCharacteristic,
    ScenarioType,
)

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("ADVERTENCIA: No se encontró GROQ_API_KEY en .env")

modelo = None
collection = None
code_collection = None
detector = AmbiguityDetector()


def init_models():
    """Inicializa los modelos y la base de conocimiento"""
    global modelo, collection

    if modelo is None:
        print("Cargando modelo de embeddings...")
        modelo = SentenceTransformer("all-MiniLM-L6-v2")
        print("Modelo cargado")

    if collection is None:
        kb_path = Path(__file__).parent / "knowledge_base_data"
        client = chromadb.PersistentClient(path=str(kb_path))
        collection = client.get_or_create_collection(
            name="katary_sgc",
            metadata={"hnsw:space": "cosine"},
        )

        if collection.count() == 0:
            print("Cargando base de conocimiento...")
            stories_path = Path(__file__).parent / "knowledge_base" / "katary_stories.json"
            with open(stories_path, "r", encoding="utf-8") as f:
                stories = json.load(f)

            textos = [s["texto"] for s in stories]
            embeddings = modelo.encode(textos).tolist()
            collection.add(
                ids=[s["id"] for s in stories],
                embeddings=embeddings,
                documents=textos,
                metadatas=[{"dominio": s.get("dominio", "general"), "criterios": s.get("criterios", "")} for s in
                           stories],
            )
            print(f"{collection.count()} historias indexadas")
        else:
            print(f"Base de conocimiento: {collection.count()} historias")


def init_code_patterns_kb():
    global code_collection, modelo
    if modelo is None:
        init_models()
    if code_collection is None:
        kb_path = Path(__file__).parent / "knowledge_base_data"
        client = chromadb.PersistentClient(path=str(kb_path))
        code_collection = client.get_or_create_collection(
            name="katary_code_patterns",
            metadata={"hnsw:space": "cosine"},
        )
        if code_collection.count() == 0:
            patterns_path = Path(__file__).parent / "knowledge_base" / "katary_code_patterns.json"
            with open(patterns_path, "r", encoding="utf-8") as f:
                patterns = json.load(f)
            textos = [
                f"{p['domain']}. {p['code_pattern_typical']}. {p['katary_context']}"
                for p in patterns
            ]
            embeddings = modelo.encode(textos).tolist()
            code_collection.add(
                ids=[p["id"] for p in patterns],
                embeddings=embeddings,
                documents=textos,
                metadatas=[{
                    "domain": p["domain"],
                    "quality_practices": json.dumps(p["quality_practices"], ensure_ascii=False),
                    "typical_functions": json.dumps(p["typical_functions"], ensure_ascii=False),
                    "common_smells": json.dumps(p["common_smells"], ensure_ascii=False),
                    "lessons_learned_katary": p["lessons_learned_katary"],
                } for p in patterns],
            )
            print(f"KB codigo: {code_collection.count()} patrones indexados")
        else:
            print(f"KB codigo existente: {code_collection.count()} patrones")


# ============================================================
# RUTAS ESTÁTICAS
# ============================================================

@app.route('/')
def index():
    return send_from_directory('static/home', 'index.html')


@app.route('/static/home/')
def home():
    return send_from_directory('static/home', 'index.html')


@app.route('/app.js')
def app_js():
    return send_from_directory('static/home', 'app.js')


@app.route('/static/home/app.js')
def home_app_js():
    return send_from_directory('static/home', 'app.js')


@app.route('/static/scenarios/')
def scenarios():
    return send_from_directory('static/scenarios', 'index.html')


@app.route('/static/scenarios/scenarios.js')
def scenarios_js():
    return send_from_directory('static/scenarios', 'scenarios.js')


@app.route('/static/review/')
def review():
    return send_from_directory('static/review', 'index.html')


@app.route('/static/review/review.js')
def review_js():
    return send_from_directory('static/review', 'review.js')


@app.route('/static/report/')
def report():
    return send_from_directory('static/report', 'index.html')


@app.route('/static/report/report.js')
def report_js():
    return send_from_directory('static/report', 'report.js')


@app.route('/static/code/')
def code_page():
    return send_from_directory('static/code', 'index.html')


@app.route('/static/code/code.js')
def code_js():
    return send_from_directory('static/code', 'code.js')


def get_groq_api_key():
    """Obtiene la API Key desde el header o variable de entorno"""
    # Primero intenta obtenerla del header
    api_key = request.headers.get('X-Groq-API-Key')
    if api_key:
        return api_key
    # Si no está en el header, usa la variable de entorno
    return GROQ_API_KEY


@app.route('/api/health', methods=['GET'])
def health():
    """Endpoint de salud"""
    return jsonify({
        'status': 'ok',
        'groq_configured': GROQ_API_KEY is not None,
        'models_loaded': modelo is not None and collection is not None,
        'kb_count': collection.count() if collection else 0
    })


@app.route('/api/analyze-ambiguities', methods=['POST'])
def analyze_ambiguities():
    """Analiza ambigüedades en un requerimiento"""
    data = request.json
    requirement_text = data.get('requirement_text', '')

    if not requirement_text:
        return jsonify({'error': 'requirement_text es requerido'}), 400

    # Obtener API Key del request
    api_key = get_groq_api_key()
    if not api_key:
        return jsonify({'error': 'API Key de Groq no configurada'}), 401

    # Crear cliente Groq con la API Key del request
    client = Groq(api_key=api_key)
    detector_instance = AmbiguityDetector()
    detector_instance.client = client

    ambiguities = detector_instance.analyze(requirement_text)

    result = []
    for amb in ambiguities:
        result.append({
            'word': amb.word,
            'category': amb.category,
            'ieee_830_violation': amb.ieee_830_violation,
            'iso_25010_category': amb.iso_25010_category,
            'suggestion': amb.suggestion,
            'context': amb.context,
            'severity': amb.severity
        })

    return jsonify({
        'ambiguities': result,
        'total': len(result),
        'severity_count': {
            'alta': sum(1 for a in ambiguities if a.severity == 'alta'),
            'media': sum(1 for a in ambiguities if a.severity == 'media'),
            'baja': sum(1 for a in ambiguities if a.severity == 'baja')
        }
    })


@app.route('/api/refine-requirements', methods=['POST'])
def refine_requirements():
    """Refina requerimientos usando el pipeline completo"""
    # Obtener API Key del request
    api_key = get_groq_api_key()
    if not api_key:
        return jsonify({'error': 'API Key de Groq no configurada'}), 401

    # Crear cliente Groq con la API Key del request
    client = Groq(api_key=api_key)

    init_models()

    data = request.json
    requirement_text = data.get('requirement_text', '')
    version = data.get('version', 'v4')  # v1, v2, v3, v4
    analyst_resolutions = data.get('analyst_resolutions', [])

    if not requirement_text:
        return jsonify({'error': 'requirement_text es requerido'}), 400

    try:
        # 1. Detectar ambigüedades
        detector_instance = AmbiguityDetector()
        detector_instance.client = client
        ambiguities = detector_instance.analyze(requirement_text)

        # 2. Buscar historias similares (RAG)
        query_emb = modelo.encode([requirement_text]).tolist()
        resultados = collection.query(
            query_embeddings=query_emb,
            n_results=3,
            include=["documents", "metadatas", "distances"],
        )

        historias = []
        for i in range(len(resultados["ids"][0])):
            sim = 1 - resultados["distances"][0][i]
            historias.append({
                "id": resultados["ids"][0][i],
                "texto": resultados["documents"][0][i],
                "criterios": resultados["metadatas"][0][i].get("criterios", ""),
                "dominio": resultados["metadatas"][0][i].get("dominio", ""),
                "similitud": sim,
            })

        # 3. Construir contexto RAG
        contexto_kb = "## HISTORIAS DE REFERENCIA DEL SGC DE KATARY\n"
        contexto_kb += "Usa estas historias como modelo de calidad y profundidad:\n\n"
        for i, h in enumerate(historias, 1):
            contexto_kb += f"### Referencia {i} [{h['id']}] (similitud: {h['similitud']:.2f})\n"
            contexto_kb += f"**Historia:** {h['texto']}\n"
            contexto_kb += f"**Criterios:** {h['criterios']}\n\n"

        # 4. Construir sección de ambigüedades según versión
        full_context = contexto_kb
        requerimiento_enriquecido = requirement_text

        if version == 'v4' and analyst_resolutions:
            # Human-in-the-Loop: usar resoluciones del analista
            seccion_ambiguedades = detector.build_resolved_prompt_section(analyst_resolutions)
            if seccion_ambiguedades:
                full_context += "\n" + seccion_ambiguedades

            # Enriquecer requerimiento
            aclaraciones = []
            for res in analyst_resolutions:
                if res.get('status') == 'resolved':
                    aclaraciones.append(f"- \"{res['word']}\": {res['analyst_resolution']}")

            if aclaraciones:
                requerimiento_enriquecido = requirement_text + "\n\nACLARACIONES DEL ANALISTA:\n"
                requerimiento_enriquecido += "\n".join(aclaraciones)

        elif version == 'v3' and ambiguities:
            # Detector automático
            seccion_ambiguedades = detector.build_prompt_section(ambiguities)
            if seccion_ambiguedades:
                full_context += "\n" + seccion_ambiguedades

        # 5. Construir prompt
        system_prompt = f"""Eres un Analista de Requerimientos Senior de Katary Software (CMMI-DEV L3, 19 años).
Transforma requerimientos ambiguos en historias de usuario estructuradas (IEEE 830 / ISO 25010).

{full_context}

## FORMATO JSON OBLIGATORIO
Responde SOLO con JSON válido, sin texto ni markdown. Estructura:
{{"project_context": "resumen", "user_stories": [
  {{"id": "US-001", "title": "min 10 chars", "story_type": "functional|non_functional|technical",
    "priority": "critical|high|medium|low", "as_a": "rol", "i_want": "acción", "so_that": "beneficio",
    "acceptance_criteria": [
      {{"id": "AC-001", "description": "min 20 chars", "given": "precondición concreta",
        "when": "acción específica", "then": "resultado verificable con tiempos",
        "test_data_examples": [{{"campo": "val", "expected": "resultado"}}],
        "is_negative_case": false, "boundary_values": ["min", "max"]}}],
    "business_rules": [], "dependencies": [], "ui_elements": [], "api_endpoints": [],
    "ambiguities_resolved": [
      {{"original_text": "texto ambiguo", "issue": "por qué", "resolution": "valores concretos", "assumption_made": {"false" if version == 'v4' else "true"}}}]
  }}]}}

## REGLAS
1. IDs: US-001, AC-001 (3 dígitos). ACs secuenciales globales
2. Cada criterio: given/when/then con datos concretos, min 2 test_data_examples
3. Por cada caso positivo, incluir 1 criterio negativo (is_negative_case: true)
4. {"Resolver ambigüedades usando las DECISIONES DEL ANALISTA (assumption_made: false)" if version == 'v4' else "Detectar y resolver ambigüedades con valores concretos en ambiguities_resolved"}
5. Responde SOLO JSON"""

        user_message = f"""Analiza el siguiente requerimiento y transfórmalo en historias
de usuario con el nivel de calidad de las referencias del SGC de Katary.

REQUERIMIENTO:
{requerimiento_enriquecido}"""

        # 6. Llamar a Groq
        respuesta = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=4000,
        )

        respuesta_raw = respuesta.choices[0].message.content

        # 7. Parsear JSON
        text = respuesta_raw.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1]
            text = text.rsplit("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1]
            text = text.rsplit("```", 1)[0]

        start = text.find("{")
        end = text.rfind("}") + 1
        datos = json.loads(text[start:end])

        # 8. Validar con Contract A
        user_stories = []
        ac_counter = 0
        for story_data in datos.get("user_stories", []):
            criteria = []
            for ac_data in story_data.get("acceptance_criteria", []):
                ac_counter += 1
                criteria.append(AcceptanceCriterion(
                    id=ac_data.get("id", f"AC-{ac_counter:03d}"),
                    description=ac_data.get("description", ""),
                    given=ac_data.get("given", ""),
                    when=ac_data.get("when", ""),
                    then=ac_data.get("then", ""),
                    test_data_examples=ac_data.get("test_data_examples", []),
                    is_negative_case=ac_data.get("is_negative_case", False),
                    boundary_values=ac_data.get("boundary_values", []),
                ))

            ambiguities_resolved = []
            for amb_data in story_data.get("ambiguities_resolved", []):
                ambiguities_resolved.append(AmbiguityResolution(
                    original_text=amb_data.get("original_text", ""),
                    issue=amb_data.get("issue", ""),
                    resolution=amb_data.get("resolution", ""),
                    assumption_made=amb_data.get("assumption_made", False),
                ))

            try:
                story_type = StoryType(story_data.get("story_type", "functional"))
            except ValueError:
                story_type = StoryType.FUNCTIONAL
            try:
                priority = Priority(story_data.get("priority", "medium"))
            except ValueError:
                priority = Priority.MEDIUM

            user_stories.append(UserStory(
                id=story_data.get("id", f"US-{len(user_stories) + 1:03d}"),
                title=story_data.get("title", "Sin título"),
                story_type=story_type,
                priority=priority,
                as_a=story_data.get("as_a", ""),
                i_want=story_data.get("i_want", ""),
                so_that=story_data.get("so_that", ""),
                acceptance_criteria=criteria,
                business_rules=story_data.get("business_rules", []),
                dependencies=story_data.get("dependencies", []),
                ui_elements=story_data.get("ui_elements", []),
                api_endpoints=story_data.get("api_endpoints", []),
                ambiguities_resolved=ambiguities_resolved,
            ))

        total_ambiguities = sum(len(s.ambiguities_resolved) for s in user_stories)
        total_assumptions = sum(
            sum(1 for a in s.ambiguities_resolved if a.assumption_made)
            for s in user_stories
        )

        resultado = RefinedRequirements(
            pipeline_run_id=f"webapp-{uuid.uuid4().hex[:8]}",
            agent_version=version,
            original_requirements_text=requirement_text,
            project_context=datos.get("project_context", ""),
            user_stories=user_stories,
            total_ambiguities_found=total_ambiguities,
            total_assumptions_made=total_assumptions,
        )

        # 9. Guardar resultado
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"webapp_{version}_{timestamp}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(resultado.model_dump(mode="json"), f, ensure_ascii=False, indent=2, default=str)

        return jsonify({
            'success': True,
            'result': resultado.model_dump(mode="json"),
            'output_file': str(output_file),
            'tokens_used': respuesta.usage.total_tokens
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# MÓDULO 2: TEST ARCHITECT - Endpoint para generar escenarios
# ============================================================

@app.route('/api/m2/generate-scenarios', methods=['POST'])
def generate_scenarios_m2():
    """Genera escenarios Gherkin desde Contract A (salida del módulo 1)"""
    # Obtener API Key del request
    api_key = get_groq_api_key()
    if not api_key:
        return jsonify({'error': 'API Key de Groq no configurada'}), 401

    # Crear cliente Groq con la API Key del request
    client = Groq(api_key=api_key)

    try:
        datos = request.json
        contract_a_data = datos.get('contract_a')
        version = datos.get('version', 'v1')

        # Validar Contract A
        contract_a = RefinedRequirements(**contract_a_data)

        # Asegurar modelos cargados para RAG
        init_models()

        # Generar con V3 (incluye heurísticas EP/BVA/DT + clasificación ISO 25010)
        test_suite = generar_escenarios_v3_completo(contract_a, client)

        # Guardar resultado
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True, parents=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"contract_b_{version}_{timestamp}.json"

        # Serializar usando Pydantic
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(test_suite.model_dump(mode="json"), f, ensure_ascii=False, indent=2, default=str)

        return jsonify({
            'success': True,
            'contract_b': test_suite.model_dump(mode="json"),
            'output_file': str(output_file),
            'version': version
        })

    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


def _parse_scenario_type(val: str) -> ScenarioType:
    """Convierte string a ScenarioType enum."""
    m = {
        "positive": ScenarioType.POSITIVE,
        "negative": ScenarioType.NEGATIVE,
        "boundary": ScenarioType.BOUNDARY,
        "edge_case": ScenarioType.EDGE_CASE,
        "error_handling": ScenarioType.ERROR_HANDLING,
    }
    return m.get(val.strip().lower(), ScenarioType.POSITIVE)


def _parse_quality_characteristic(val: str) -> QualityCharacteristic:
    """Convierte string a QualityCharacteristic enum."""
    m = {
        "functional_suitability": QualityCharacteristic.FUNCTIONAL_SUITABILITY,
        "performance_efficiency": QualityCharacteristic.PERFORMANCE_EFFICIENCY,
        "compatibility": QualityCharacteristic.COMPATIBILITY,
        "usability": QualityCharacteristic.USABILITY,
        "reliability": QualityCharacteristic.RELIABILITY,
        "security": QualityCharacteristic.SECURITY,
        "maintainability": QualityCharacteristic.MAINTAINABILITY,
        "portability": QualityCharacteristic.PORTABILITY,
    }
    return m.get(val.strip().lower(), QualityCharacteristic.FUNCTIONAL_SUITABILITY)


def generar_escenarios_v3_completo(
        contract_a: RefinedRequirements,
        client: Groq
) -> GherkinTestSuite:
    """Genera escenarios Gherkin usando V3 y retorna un GherkinTestSuite Pydantic."""
    features: list[GherkinFeature] = []
    coverage_matrix: list[CoverageMatrix] = []

    for story in contract_a.user_stories:
        scenarios: list[GherkinScenario] = []

        for ac in story.acceptance_criteria:
            patrones_similares = []
            if modelo and collection:
                try:
                    ac_embedding = modelo.encode(ac.description)
                    resultados = collection.query(
                        query_embeddings=[ac_embedding.tolist()],
                        n_results=3
                    )
                    for i in range(len(resultados["ids"][0])):
                        similitud = 1 - resultados["distances"][0][i]
                        patrones_similares.append({
                            "id": resultados["ids"][0][i],
                            "domain": resultados["metadatas"][0][i].get("domain", "general"),
                            "techniques": resultados["metadatas"][0][i].get("techniques_used", ""),
                            "similitud": similitud
                        })
                except Exception as e:
                    print(f"Error en RAG: {e}")

            contexto_kb = "## PATRONES DE TESTING SIMILARES\n"
            for i, p in enumerate(patrones_similares, 1):
                contexto_kb += f"Patrón {i}: {p['domain']} (similitud: {p['similitud']:.2f})\n"
                contexto_kb += f"Técnicas: {p['techniques']}\n\n"

            system_prompt = (
                "Eres un Test Architect que convierte criterios de aceptación en\n"
                "escenarios Gherkin (BDD) aplicando técnicas de caja negra disciplinadas\n"
                "y clasificándolos según ISO/IEC 25010.\n\n"
                f"{contexto_kb}\n"
                "## INSTRUCCIONES DE TESTING DISCIPLINADO (OBLIGATORIAS)\n"
                "\n"
                "Para el criterio de aceptación recibido, aplica las siguientes técnicas:\n"
                "\n"
                "1. EQUIVALENCE PARTITIONING (EP):\n"
                "   - Identifica las clases equivalentes válidas e inválidas del AC.\n"
                "   - Genera UN escenario por cada clase identificada.\n"
                "\n"
                "2. BOUNDARY VALUE ANALYSIS (BVA):\n"
                "   - Si el AC menciona un rango numérico, genera escenarios con:\n"
                "     límite inferior, justo debajo, límite superior, justo encima.\n"
                "\n"
                "3. DECISION TABLES (DT):\n"
                "   - Si el AC tiene múltiples condiciones combinadas, genera UN\n"
                "     escenario por cada combinación relevante.\n"
                "\n"
                "## CLASIFICACIÓN ISO/IEC 25010 (OBLIGATORIA)\n"
                "\n"
                "Por cada escenario, asigna `quality_characteristic` con UNA de estas:\n"
                "\n"
                "   - functional_suitability  (lógica de negocio, validaciones, reglas)\n"
                "   - performance_efficiency  (tiempos de respuesta, carga concurrente)\n"
                "   - security                (autenticación, autorización, bloqueo, cifrado)\n"
                "   - usability               (mensajes claros, accesibilidad, navegación)\n"
                "   - reliability             (recuperación de fallas, manejo de errores)\n"
                "   - compatibility           (interoperabilidad, formatos, navegadores)\n"
                "   - maintainability         (rara vez aplica a BDD funcionales)\n"
                "   - portability             (rara vez aplica a BDD funcionales)\n"
                "\n"
                "REGLAS PARA DECIDIR:\n"
                "   - Si prueba validación de entrada o regla de negocio: functional_suitability\n"
                "   - Si prueba bloqueo tras N intentos o control de acceso: security\n"
                "   - Si prueba tiempo de respuesta o concurrencia: performance_efficiency\n"
                "   - Si prueba mensaje de error claro o accesibilidad: usability\n"
                "\n"
                "## FORMATO DE RESPUESTA OBLIGATORIO\n"
                "Devuelve ÚNICAMENTE un JSON válido con LISTA de escenarios:\n"
                "{\n"
                '  "scenarios": [\n'
                "    {\n"
                '      "name": "nombre descriptivo del escenario",\n'
                '      "scenario_type": "positive" | "negative" | "boundary",\n'
                '      "quality_characteristic": "functional_suitability" | "security" | ...,\n'
                '      "steps": [\n'
                '        {"keyword": "Given", "text": "..."},\n'
                '        {"keyword": "When", "text": "..."},\n'
                '        {"keyword": "Then", "text": "..."}\n'
                "      ]\n"
                "    }\n"
                "  ]\n"
                "}\n"
            )

            user_prompt = (
                f"Historia: {story.title}\n"
                f"Como {story.as_a}, quiero {story.i_want}, para {story.so_that}.\n\n"
                f"Criterio {ac.id}:\n"
                f"Descripción: {ac.description}\n"
                f"Given: {ac.given}\n"
                f"When: {ac.when}\n"
                f"Then: {ac.then}\n"
                f"Caso negativo: {'Sí' if ac.is_negative_case else 'No'}\n"
                f"Test data examples: {ac.test_data_examples}\n"
                f"Boundary values: {ac.boundary_values}\n\n"
                f"Genera la LISTA de escenarios Gherkin aplicando EP, BVA y/o DT,\n"
                f"y CLASIFICA cada uno con su característica ISO/IEC 25010."
            )

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                seed=42,
                max_tokens=2500,
            )

            raw_text = response.choices[0].message.content

            text = raw_text.strip()
            if "```json" in text:
                text = text.split("```json", 1)[1].rsplit("```", 1)[0]
            elif "```" in text:
                text = text.split("```", 1)[1].rsplit("```", 1)[0]

            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == 0:
                print(f"No se encontró JSON válido en la respuesta para AC {ac.id}")
                continue

            json_str = text[start:end]
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"Error al parsear JSON para AC {ac.id}: {e}")
                continue

            escenarios_generados = data.get("scenarios", [data])

            scenario_names = []
            coverage_types: list[ScenarioType] = []
            quality_chars: list[QualityCharacteristic] = []

            for esc_data in escenarios_generados:
                steps_pydantic = [
                    GherkinStep(keyword=s["keyword"], text=s["text"])
                    for s in esc_data.get("steps", [])
                    if s.get("keyword") and s.get("text")
                ]
                if len(steps_pydantic) < 3:
                    continue

                scenario = GherkinScenario(
                    name=esc_data["name"],
                    scenario_type=_parse_scenario_type(esc_data.get("scenario_type", "positive")),
                    quality_characteristic=_parse_quality_characteristic(
                        esc_data.get("quality_characteristic", "functional_suitability")
                    ),
                    tags=esc_data.get("tags", []),
                    steps=steps_pydantic,
                    acceptance_criterion_id=ac.id,
                    user_story_id=story.id,
                )
                scenarios.append(scenario)

                scenario_names.append(scenario.name)
                coverage_types.append(scenario.scenario_type)
                quality_chars.append(scenario.quality_characteristic)

            coverage_matrix.append(CoverageMatrix(
                user_story_id=story.id,
                criterion_id=ac.id,
                scenario_names=scenario_names,
                coverage_type=coverage_types,
                quality_characteristics_covered=quality_chars,
            ))

        features.append(GherkinFeature(
            name=story.title,
            description=f"Como {story.as_a}, quiero {story.i_want}, para {story.so_that}",
            scenarios=scenarios,
            user_story_id=story.id,
        ))

    all_scenarios = [s for f in features for s in f.scenarios]
    total_scenarios = len(all_scenarios)
    total_positive = sum(1 for s in all_scenarios if s.scenario_type == ScenarioType.POSITIVE)
    total_negative = sum(1 for s in all_scenarios if s.scenario_type == ScenarioType.NEGATIVE)
    total_boundary = sum(1 for s in all_scenarios if s.scenario_type == ScenarioType.BOUNDARY)

    coverage_by_characteristic = {
        "functional_suitability": 0,
        "performance_efficiency": 0,
        "compatibility": 0,
        "usability": 0,
        "reliability": 0,
        "security": 0,
        "maintainability": 0,
        "portability": 0,
    }
    for s in all_scenarios:
        qc = s.quality_characteristic.value
        coverage_by_characteristic[qc] = coverage_by_characteristic.get(qc, 0) + 1

    return GherkinTestSuite(
        pipeline_run_id=f"webapp-m2-{uuid.uuid4().hex[:8]}",
        agent_version="0.3.0-v3-iso25010",
        features=features,
        coverage_matrix=coverage_matrix,
        total_scenarios=total_scenarios,
        total_positive=total_positive,
        total_negative=total_negative,
        total_boundary=total_boundary,
        coverage_by_characteristic=coverage_by_characteristic,
    )


# ============================================================
# MÓDULO 3: CODE GENERATOR — Funciones del pipeline
# ============================================================

import re
import subprocess
import tempfile


# --- V1: Generación de código ---

def buscar_patrones_codigo(feature: dict, top_k: int = 3) -> list[dict]:
    """Busca patrones de código Katary similares a una feature."""
    global modelo, code_collection
    if modelo is None or code_collection is None or code_collection.count() == 0:
        return []
    nombres_escenarios = " ".join(s.get("name", "") for s in feature.get("scenarios", []))
    consulta = f"{feature.get('name', '')}. {feature.get('description', '')}. {nombres_escenarios}"
    query_emb = modelo.encode([consulta]).tolist()
    resultados = code_collection.query(query_embeddings=query_emb, n_results=top_k)
    patrones = []
    for idx in range(len(resultados["ids"][0])):
        meta = resultados["metadatas"][0][idx]
        distancia = resultados["distances"][0][idx]
        patrones.append({
            "id": resultados["ids"][0][idx],
            "domain": meta["domain"],
            "quality_practices": json.loads(meta.get("quality_practices", "[]")),
            "typical_functions": json.loads(meta.get("typical_functions", "[]")),
            "common_smells": json.loads(meta.get("common_smells", "[]")),
            "lessons_learned_katary": meta.get("lessons_learned_katary", ""),
            "similitud": 1 - distancia,
        })
    return patrones


def construir_prompt_codigo(feature: dict, patrones: list[dict]) -> tuple[str, str]:
    """Construye el prompt para generación de código + tests."""
    bloques_kb = []
    for p in patrones:
        bloques_kb.append(
            f"--- Patron: {p['domain']} (similitud {p['similitud']:.2f}) ---\n"
            f"Practicas de calidad: {', '.join(p['quality_practices'])}\n"
            f"Funciones tipicas: {', '.join(p['typical_functions'])}\n"
            f"Smells comunes a evitar: {', '.join(p['common_smells'])}\n"
            f"Leccion aprendida en Katary: {p['lessons_learned_katary']}\n"
        )
    contexto_kb = "\n".join(bloques_kb)

    system_prompt = (
        "Eres un generador de codigo Python. Recibes una feature con escenarios "
        "Gherkin y debes devolver UNICAMENTE un objeto JSON valido con esta estructura, "
        "sin texto antes ni despues, sin bloques de markdown, sin comentarios:\n"
        "{\n"
        '  "modules": [\n'
        '    {"filename": "archivo.py", "source_code": "codigo python sin escapar caracteres especiales", "description": "que hace"}\n'
        "  ],\n"
        '  "tests": [\n'
        '    {"test_name": "test_nombre", "source_code": "codigo python del test", '
        '"target_module": "archivo.py", "scenario_ids": ["AC-001"]}\n'
        "  ]\n"
        "}\n\n"
        "IMPORTANTE: Escapa correctamente las comillas dobles dentro del codigo fuente (\\\") "
        "y las barras invertidas (\\\\). Asegurate de que el JSON sea sintacticamente valido.\n\n"
        "Usa el contexto de patrones Katary como guia de calidad y estilo."
    )

    bloques_escenarios = []
    for s in feature.get("scenarios", []):
        pasos = "\n".join(f"  {step['keyword']} {step['text']}" for step in s.get("steps", []))
        bloques_escenarios.append(
            f"Escenario [{s.get('acceptance_criterion_id', '')}] {s.get('name', '')}\n{pasos}"
        )
    escenarios_txt = "\n\n".join(bloques_escenarios)

    user_message = (
        f"CONTEXTO DE PATRONES KATARY (RAG):\n{contexto_kb}\n\n"
        f"FEATURE A IMPLEMENTAR:\n"
        f"Nombre: {feature.get('name', '')}\n"
        f"Descripcion: {feature.get('description', '')}\n"
        f"User Story: {feature.get('user_story_id', '')}\n\n"
        f"ESCENARIOS:\n{escenarios_txt}\n\n"
        f"Genera el codigo Python que implementa esta feature y los tests Pytest. "
        f"En cada test, scenario_ids debe contener SOLO los IDs (ej: AC-003, sin corchetes) "
        f"de los escenarios que ese test verifica."
    )
    return system_prompt, user_message


def parsear_respuesta_codigo(raw_text: str, user_story_id: str):
    """Parsea la respuesta del LLM en GeneratedCodeModule + GeneratedTest."""
    from src.contract_c import GeneratedCodeModule, GeneratedTest

    texto = raw_text.strip()

    # Remover bloques markdown ```json ... ```
    if "```" in texto:
        partes = texto.split("```")
        for i, parte in enumerate(partes):
            parte = parte.strip()
            if parte.startswith("json"):
                parte = parte[4:].strip()
            if parte.startswith("{") or parte.startswith("["):
                texto = parte
                break
        else:
            texto = partes[-1]

    # Remover texto antes del primer { y despues del ultimo }
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio == -1 or fin == -1 or fin <= inicio:
        raise ValueError("No se encontro JSON valido en la respuesta del LLM")

    raw_json = texto[inicio:fin + 1]

    # Sanitizar: remover trailing commas antes de ] y }
    raw_json = re.sub(r",\s*([\]}])", r"\1", raw_json)

    data = json.loads(raw_json)

    modulos = []
    for item in data.get("modules", []):
        modulos.append(GeneratedCodeModule(
            filename=item["filename"],
            source_code=item["source_code"],
            description=item.get("description", ""),
            user_story_id=user_story_id,
        ))

    tests = []
    for item in data.get("tests", []):
        tests.append(GeneratedTest(
            test_name=item["test_name"],
            source_code=item["source_code"],
            target_module=item.get("target_module", ""),
            scenario_ids=[
                sid.strip("[]") for sid in item.get("scenario_ids", [])
            ],
        ))
    return modulos, tests


# --- V2: Análisis estático ---

def volcar_codigo_a_disco(modulos: list) -> Path:
    """Escribe el código generado a un directorio temporal."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="m3_codigo_"))
    for modulo in modulos:
        (tmp_dir / modulo.filename).write_text(modulo.source_code, encoding="utf-8")
    return tmp_dir


def ejecutar_radon(code_dir: Path) -> dict:
    """Corre radon cc + mi y devuelve dict con resultados."""
    res_cc = subprocess.run(
        [sys.executable, "-m", "radon", "cc", "-j", str(code_dir)],
        capture_output=True, text=True,
    )
    cc_data = json.loads(res_cc.stdout) if res_cc.stdout.strip() else {}

    res_mi = subprocess.run(
        [sys.executable, "-m", "radon", "mi", "-j", str(code_dir)],
        capture_output=True, text=True,
    )
    mi_data = json.loads(res_mi.stdout) if res_mi.stdout.strip() else {}

    cc_normalizado = {Path(k).name: v for k, v in cc_data.items()}
    mi_normalizado = {Path(k).name: v for k, v in mi_data.items()}
    return {"cc": cc_normalizado, "mi": mi_normalizado}


def ejecutar_complexipy(code_dir: Path) -> dict:
    """Corre complexipy y devuelve CogC por función."""
    complexipy_cmd = shutil.which("complexipy")
    if not complexipy_cmd:
        scripts_dir = Path(sys.executable).parent
        complexipy_cmd = str(scripts_dir / "complexipy.exe")
        if not Path(complexipy_cmd).exists():
            complexipy_cmd = "complexipy"
    subprocess.run(
        [complexipy_cmd, "--output-format", "json", "--quiet", str(code_dir)],
        cwd=str(code_dir), capture_output=True, text=True,
    )
    resultados_path = code_dir / "complexipy-results.json"
    if not resultados_path.exists():
        return {}
    lista = json.loads(resultados_path.read_text(encoding="utf-8"))
    resultado: dict[str, dict[str, int]] = {}
    for item in lista:
        archivo = item["file_name"]
        funcion = item["function_name"]
        resultado.setdefault(archivo, {})[funcion] = item["complexity"]
    return resultado


def ejecutar_bandit(code_dir: Path) -> list:
    """Corre Bandit y devuelve hallazgos de seguridad."""
    from src.contract_c import SecurityFinding, SecuritySeverity

    bandit_cmd = shutil.which("bandit")
    if not bandit_cmd:
        scripts_dir = Path(sys.executable).parent
        bandit_cmd = str(scripts_dir / "bandit.exe")
        if not Path(bandit_cmd).exists():
            bandit_cmd = "bandit"
    res = subprocess.run(
        [bandit_cmd, "-r", "-f", "json", str(code_dir)],
        capture_output=True, text=True,
    )
    if not res.stdout.strip():
        return []
    data = json.loads(res.stdout)
    findings = []
    for issue in data.get("results", []):
        findings.append(SecurityFinding(
            test_id=issue["test_id"],
            severity=SecuritySeverity(issue["issue_severity"].lower()),
            module=Path(issue["filename"]).name,
            line_number=issue["line_number"],
            description=issue["issue_text"],
        ))
    return findings


def construir_metricas_funciones(radon_data: dict, complexipy_data: dict) -> list:
    """Construye lista de FunctionMetrics desde radon + complexipy."""
    from src.contract_c import ComplexityBand, FunctionMetrics

    metrics = []
    for archivo, entradas in radon_data.get("cc", {}).items():
        for entrada in entradas:
            if entrada.get("type") not in ("function", "method"):
                continue
            nombre = entrada["name"]
            cc = entrada["complexity"]
            try:
                banda = ComplexityBand(entrada["rank"])
            except ValueError:
                banda = ComplexityBand.E

            cogc = complexipy_data.get(archivo, {}).get(nombre, 0)
            exceeds = (cc >= 10) or (cogc >= 15)

            metrics.append(FunctionMetrics(
                function_name=nombre,
                module=archivo,
                cyclomatic_complexity=cc,
                cognitive_complexity=cogc,
                cc_band=banda,
                nesting_depth=0,
                exceeds_threshold=exceeds,
            ))
    return metrics


def clasificar_iso_25010(function_metrics: list, security_findings: list, maintainability_index: float | None) -> list:
    """Clasifica las 8 características ISO 25010."""
    from src.contract_c import (
        QualityCharacteristic, MeasurementStatus, QualityCharacteristicResult, SecuritySeverity,
    )

    exceeding = sum(1 for fm in function_metrics if fm.exceeds_threshold)
    high_findings = sum(1 for f in security_findings if f.severity == SecuritySeverity.HIGH)
    mi_ok = maintainability_index is not None and maintainability_index >= 20

    resultados = []

    if exceeding == 0 and mi_ok:
        mantenibilidad_verdict = f"pass: 0 funciones sobre umbral, MI={maintainability_index} >= 20"
    else:
        mantenibilidad_verdict = f"fail: {exceeding} funcion(es) sobre umbral, MI={maintainability_index}"
    resultados.append(QualityCharacteristicResult(
        characteristic=QualityCharacteristic.MAINTAINABILITY,
        status=MeasurementStatus.MEASURED,
        metrics_used=["radon cc", "complexipy", "radon mi"],
        verdict=mantenibilidad_verdict,
    ))

    if high_findings == 0 and len(security_findings) == 0:
        seg_verdict = "pass: sin hallazgos de Bandit"
    else:
        seg_verdict = f"fail: {len(security_findings)} hallazgo(s), {high_findings} de severidad HIGH"
    resultados.append(QualityCharacteristicResult(
        characteristic=QualityCharacteristic.SECURITY,
        status=MeasurementStatus.MEASURED,
        metrics_used=["bandit"],
        verdict=seg_verdict,
    ))

    resultados.append(QualityCharacteristicResult(
        characteristic=QualityCharacteristic.FUNCTIONAL_SUITABILITY,
        status=MeasurementStatus.REQUIRES_HUMAN_JUDGMENT,
        metrics_used=[],
        verdict="V3 no ejecuta los tests generados; pytest-cov lo cubre.",
    ))
    resultados.append(QualityCharacteristicResult(
        characteristic=QualityCharacteristic.RELIABILITY,
        status=MeasurementStatus.REQUIRES_HUMAN_JUDGMENT,
        metrics_used=[],
        verdict="Manejo de errores y casos limite requieren revision humana (V4).",
    ))
    resultados.append(QualityCharacteristicResult(
        characteristic=QualityCharacteristic.PERFORMANCE_EFFICIENCY,
        status=MeasurementStatus.NOT_APPLICABLE,
        metrics_used=[],
        verdict="Caracteristica de runtime; el analisis estatico no la mide.",
    ))
    resultados.append(QualityCharacteristicResult(
        characteristic=QualityCharacteristic.COMPATIBILITY,
        status=MeasurementStatus.NOT_APPLICABLE,
        metrics_used=[],
        verdict="Depende del entorno de integracion; fuera del alcance.",
    ))
    resultados.append(QualityCharacteristicResult(
        characteristic=QualityCharacteristic.PORTABILITY,
        status=MeasurementStatus.NOT_APPLICABLE,
        metrics_used=[],
        verdict="Depende del entorno destino; fuera del alcance.",
    ))
    resultados.append(QualityCharacteristicResult(
        characteristic=QualityCharacteristic.USABILITY,
        status=MeasurementStatus.NOT_APPLICABLE,
        metrics_used=[],
        verdict="Necesita usuarios reales; no se evalua sobre codigo backend.",
    ))
    return resultados


# --- V3: Trazabilidad + Coverage ---

MARKER_RE = re.compile(r'@pytest\.mark\.scenario\(["\']([^"\']+)["\']\)')


def extraer_markers_de_tests(tests: list) -> dict[str, list[str]]:
    """Extrae los scenario IDs de los tests generados."""
    resultado: dict[str, list[str]] = {}
    for test in tests:
        declarados = list(test.scenario_ids or [])
        en_codigo = MARKER_RE.findall(test.source_code or "")
        def limpiar(sid: str) -> str:
            return sid.strip().strip("[]")
        ids = {limpiar(s) for s in declarados + en_codigo if s and limpiar(s)}
        resultado[test.test_name] = sorted(ids)
    return resultado


def construir_matriz_trazabilidad(scenarios: dict[str, str], test_markers: dict[str, list[str]]):
    """Construye la matriz de trazabilidad bidireccional."""
    from src.contract_c import (
        TraceabilityMatrix, ScenarioTraceability, TestTraceability, TraceabilityStatus,
    )

    forward = []
    orphan_scenarios = []
    for sid, nombre in scenarios.items():
        cubriendo = sorted(t for t, ids in test_markers.items() if sid in ids)
        if cubriendo:
            estado = TraceabilityStatus.COVERED
        else:
            estado = TraceabilityStatus.ORPHAN_FORWARD
            orphan_scenarios.append(sid)
        forward.append(ScenarioTraceability(
            scenario_id=sid,
            scenario_name=nombre,
            covering_tests=cubriendo,
            status=estado,
        ))

    backward = []
    orphan_tests = []
    for test_name, ids in test_markers.items():
        justifican = sorted(s for s in ids if s in scenarios)
        if justifican:
            estado = TraceabilityStatus.COVERED
        else:
            estado = TraceabilityStatus.ORPHAN_BACKWARD
            orphan_tests.append(test_name)
        backward.append(TestTraceability(
            test_name=test_name,
            justifying_scenarios=justifican,
            status=estado,
        ))

    total_sc = len(scenarios) if scenarios else 1
    total_t = len(test_markers) if test_markers else 1
    req_cov = (total_sc - len(orphan_scenarios)) / total_sc * 100
    test_just = (total_t - len(orphan_tests)) / total_t * 100
    cmmi = (not orphan_scenarios) and (not orphan_tests)

    return TraceabilityMatrix(
        forward=forward,
        backward=backward,
        requirements_coverage_pct=round(req_cov, 2),
        tests_justified_pct=round(test_just, 2),
        orphan_scenarios=orphan_scenarios,
        orphan_tests=orphan_tests,
        cmmi_l3_compliant=cmmi,
    )


def medir_coverage(code_dir: Path, tests: list) -> object:
    """Corre pytest-cov y retorna CoverageReport."""
    from src.contract_c import CoverageReport

    for test in tests:
        nombre = test.test_name if test.test_name.startswith("test_") else f"test_{test.test_name}"
        if not nombre.endswith(".py"):
            nombre = f"{nombre}.py"
        wrapper = (
            "import sys\nfrom pathlib import Path\n"
            "sys.path.insert(0, str(Path(__file__).parent))\n\n"
            + test.source_code
        )
        (code_dir / nombre).write_text(wrapper, encoding="utf-8")

    (code_dir / "conftest.py").write_text(
        "def pytest_configure(config):\n"
        '    config.addinivalue_line("markers", "scenario(id): vincula un test a un escenario")\n',
        encoding="utf-8",
    )

    cov_json = code_dir / "coverage.json"
    subprocess.run(
        [sys.executable, "-m", "pytest", str(code_dir),
         f"--cov={code_dir}", "--cov-branch", "--cov-report=json:" + str(cov_json),
         "-q", "--tb=no"],
        capture_output=True, text=True, cwd=str(code_dir),
    )

    if not cov_json.exists():
        return CoverageReport(
            branch_coverage_pct=0.0, line_coverage_pct=0.0,
            meets_threshold=False, uncovered_modules=[],
        )
    data = json.loads(cov_json.read_text(encoding="utf-8"))
    totals = data.get("totals", {})
    line_pct = totals.get("percent_covered", 0.0)
    n_branches = totals.get("num_branches", 0)
    covered_branches = totals.get("covered_branches", 0)
    branch_pct = (covered_branches / n_branches * 100) if n_branches > 0 else line_pct

    uncovered = []
    for filepath, fdata in data.get("files", {}).items():
        f_totals = fdata.get("summary", {})
        f_branches = f_totals.get("num_branches", 0)
        f_covered = f_totals.get("covered_branches", 0)
        f_pct = (f_covered / f_branches * 100) if f_branches > 0 else f_totals.get("percent_covered", 0.0)
        if f_pct < 80:
            uncovered.append(Path(filepath).name)

    return CoverageReport(
        branch_coverage_pct=round(branch_pct, 2),
        line_coverage_pct=round(line_pct, 2),
        meets_threshold=branch_pct >= 80,
        uncovered_modules=uncovered,
    )


# --- Pipeline V3 completo ---

def pipeline_m3_completo(contract_b_data: dict, client: Groq) -> dict:
    """Ejecuta el pipeline completo M3 V1+V2+V3 y retorna Contract C."""
    from src.contract_c import (
        CodeGenerationResult, GeneratedCodeModule, GeneratedTest, QualityReport,
    )

    init_code_patterns_kb()

    # Sanitizar change_history: si alguna entrada no tiene reviewer,
    # lo rellena desde review.reviewer_name o "unknown"
    review_meta = contract_b_data.get("review", {})
    default_reviewer = review_meta.get("reviewer_name") or "unknown"
    for entry in review_meta.get("change_history", []):
        if not entry.get("reviewer"):
            entry["reviewer"] = default_reviewer
    contract_b_data["review"] = review_meta

    contract_b = GherkinTestSuite(**contract_b_data)

    todos_modulos: list[GeneratedCodeModule] = []
    todos_tests: list[GeneratedTest] = []

    # FASE V1: Generación de código con RAG
    for feature in contract_b.features:
        feature_dict = feature.model_dump()
        patrones = buscar_patrones_codigo(feature_dict, top_k=3)
        system_prompt, user_message = construir_prompt_codigo(feature_dict, patrones)
        raw_response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
            seed=42,
            max_tokens=6000,
        )
        try:
            modulos, tests = parsear_respuesta_codigo(
                raw_response.choices[0].message.content,
                feature.user_story_id,
            )
            todos_modulos.extend(modulos)
            todos_tests.extend(tests)
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"Error generando codigo para {feature.user_story_id}: {e}")
            continue

    if not todos_modulos:
        raise ValueError("No se pudo generar codigo para ninguna feature")

    # FASE V2: Análisis estático
    code_dir = volcar_codigo_a_disco(todos_modulos)
    radon_data = ejecutar_radon(code_dir)
    complexipy_data = ejecutar_complexipy(code_dir)
    security_findings = ejecutar_bandit(code_dir)
    function_metrics = construir_metricas_funciones(radon_data, complexipy_data)

    mi_values = [v["mi"] for v in radon_data.get("mi", {}).values()]
    maintainability_index = round(sum(mi_values) / len(mi_values), 2) if mi_values else None

    iso_coverage = clasificar_iso_25010(function_metrics, security_findings, maintainability_index)

    quality_report = QualityReport(
        function_metrics=function_metrics,
        maintainability_index=maintainability_index,
        security_findings=security_findings,
        iso_25010_coverage=iso_coverage,
        functions_exceeding_threshold=sum(1 for fm in function_metrics if fm.exceeds_threshold),
    )

    # FASE V3: Trazabilidad + Coverage
    scenarios = {}
    for feature in contract_b.features:
        for sc in feature.scenarios:
            scenarios[sc.acceptance_criterion_id] = sc.name

    test_markers = extraer_markers_de_tests(todos_tests)
    traceability_matrix = construir_matriz_trazabilidad(scenarios, test_markers)
    coverage_report = medir_coverage(code_dir, todos_tests)

    resultado = CodeGenerationResult(
        pipeline_run_id=f"v3-{uuid.uuid4().hex[:8]}",
        agent_version="0.3.0-v3-trazabilidad",
        source_contract_b_id=contract_b.pipeline_run_id,
        generated_code=todos_modulos,
        generated_tests=todos_tests,
        quality_report=quality_report,
        traceability_matrix=traceability_matrix,
        coverage_report=coverage_report,
        total_modules=len(todos_modulos),
        total_tests=len(todos_tests),
    )
    return resultado.model_dump(mode="json")


# ============================================================
# MÓDULO 3: CODE GENERATOR — Endpoints
# ============================================================

@app.route('/api/m3/generate-code', methods=['POST'])
def generate_code_m3():
    """Ejecuta el pipeline M3 completo (V1+V2+V3) y retorna Contract C."""
    api_key = get_groq_api_key()
    if not api_key:
        return jsonify({'error': 'API Key de Groq no configurada'}), 401

    client = Groq(api_key=api_key)

    try:
        datos = request.json
        contract_b_data = datos.get('contract_b')
        if not contract_b_data:
            return jsonify({'error': 'contract_b es requerido'}), 400

        contract_c = pipeline_m3_completo(contract_b_data, client)

        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True, parents=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"contract_c_v3_{timestamp}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(contract_c, f, ensure_ascii=False, indent=2)

        return jsonify({
            'success': True,
            'contract_c': contract_c,
            'output_file': str(output_file),
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


@app.route('/api/m3/review', methods=['POST'])
def review_contract_c():
    """Actualiza el estado HITL de un Contract C."""
    from src.contract_c import CodeGenerationResult, ReviewChange, ReviewStatus

    datos = request.json
    contract_c_data = datos.get('contract_c')
    reviewer = datos.get('reviewer', '').strip()
    action = datos.get('action', '').strip().lower()
    change_history_raw = datos.get('change_history', [])
    feedback = datos.get('feedback', '').strip()

    if not contract_c_data:
        return jsonify({'error': 'contract_c es requerido'}), 400
    if not reviewer:
        return jsonify({'error': 'reviewer es requerido'}), 400

    try:
        contract_c = CodeGenerationResult(**contract_c_data)
    except Exception as e:
        return jsonify({'error': f'Contract C invalido: {str(e)}'}), 400

    review = contract_c.review

    for entry in change_history_raw:
        cambio = ReviewChange(
            reviewer=reviewer,
            action=entry.get('action', 'comment_added'),
            target=entry.get('target'),
            notes=entry.get('notes'),
        )
        review.change_history.append(cambio)

    if action in ("approve", "approved", "aprobar"):
        review.review_status = ReviewStatus.APPROVED
        review.approved_by = reviewer
        review.approved_at = datetime.now()
        accion = "approved"
    elif action in ("reject", "rejected", "rechazar"):
        review.review_status = ReviewStatus.REJECTED
        accion = "rejected"
    else:
        review.review_status = ReviewStatus.NEEDS_CHANGES
        review.version += 1
        accion = "changes_requested"

    if feedback:
        review.reviewer_feedback = feedback

    review.change_history.append(ReviewChange(
        reviewer=reviewer,
        action=accion,
        notes=feedback,
    ))

    contract_c_data_actualizado = contract_c.model_dump(mode="json")
    return jsonify({
        'success': True,
        'contract_c': contract_c_data_actualizado,
        'message': f'Veredicto aplicado: {review.review_status.value}',
    })


if __name__ == '__main__':
    print("Iniciando QualityAI Web App...")
    init_models()
    print("Servidor listo en http://localhost:3000")
    app.run(debug=True, host='0.0.0.0', port=3000)
