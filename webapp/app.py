"""
Aplicación Web Unificada para QualityAI
Servidor Flask que expone los servicios de ambos módulos:
- Módulo 1: Requirements Refiner (análisis de ambigüedades)
- Módulo 2: Test Architect (generación de escenarios Gherkin)
"""

import json
import os
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

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("ADVERTENCIA: No se encontró GROQ_API_KEY en .env")

modelo = None
collection = None
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

        # Serializar
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(test_suite, f, ensure_ascii=False, indent=2, default=str)

        return jsonify({
            'success': True,
            'contract_b': test_suite,
            'output_file': str(output_file),
            'version': version
        })

    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


def generar_escenarios_v3_completo(
        contract_a: RefinedRequirements,
        client: Groq
):
    """Genera escenarios Gherkin usando V3: heurísticas EP/BVA/DT + clasificación ISO 25010"""
    features = []
    coverage_matrix = []

    for story in contract_a.user_stories:
        scenarios = []

        for ac in story.acceptance_criteria:
            # Buscar patrones similares en KB (RAG)
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

            # Construir contexto RAG
            contexto_kb = "## PATRONES DE TESTING SIMILARES\n"
            for i, p in enumerate(patrones_similares, 1):
                contexto_kb += f"Patrón {i}: {p['domain']} (similitud: {p['similitud']:.2f})\n"
                contexto_kb += f"Técnicas: {p['techniques']}\n\n"

            # Prompt V3 completo con heurísticas + ISO 25010
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
                '      "heuristic_applied": "EP" | "BVA" | "DT" | "general",\n'
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

            # Llamar a Groq
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                seed=42,
                max_tokens=2500,  # Aumentado para V3 (múltiples escenarios)
            )

            raw_text = response.choices[0].message.content
            print(f"\n{'=' * 60}")
            print(f"Respuesta del LLM para AC {ac.id}:")
            print(f"{'=' * 60}")
            print(raw_text[:500] + "..." if len(raw_text) > 500 else raw_text)
            print(f"{'=' * 60}\n")

            # Parsear JSON
            text = raw_text.strip()
            if "```json" in text:
                text = text.split("```json", 1)[1].rsplit("```", 1)[0]
            elif "```" in text:
                text = text.split("```", 1)[1].rsplit("```", 1)[0]

            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == 0:
                print(f"No se encontró JSON válido en la respuesta")
                print(f"Texto procesado: {text[:200]}")
                continue  # Saltar este AC si no hay JSON

            json_str = text[start:end]
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"Error al parsear JSON: {e}")
                print(f"JSON string: {json_str[:200]}")
                continue  # Saltar este AC si el JSON es inválido

            # V3 retorna LISTA de escenarios
            escenarios_generados = data.get("scenarios", [data])  # Fallback si retorna un solo escenario

            scenario_names = []
            coverage_types = []
            quality_chars = []

            for esc_data in escenarios_generados:
                # Crear escenario con clasificación ISO 25010
                scenario = {
                    "name": esc_data["name"],
                    "scenario_type": esc_data.get("scenario_type", "positive"),
                    "quality_characteristic": esc_data.get("quality_characteristic", "functional_suitability"),
                    "heuristic_applied": esc_data.get("heuristic_applied", "general"),
                    "tags": esc_data.get("tags", []),
                    "steps": esc_data["steps"],
                    "acceptance_criterion_id": ac.id,
                    "user_story_id": story.id
                }
                scenarios.append(scenario)

                scenario_names.append(scenario["name"])
                coverage_types.append(scenario["scenario_type"])
                quality_chars.append(scenario["quality_characteristic"])

            # Agregar a cobertura (una entrada por AC con todos sus escenarios)
            coverage_matrix.append({
                "user_story_id": story.id,
                "criterion_id": ac.id,
                "scenario_names": scenario_names,
                "coverage_type": coverage_types,
                "quality_characteristics_covered": quality_chars
            })

        # Crear feature
        feature = {
            "name": story.title,
            "description": f"Como {story.as_a}, quiero {story.i_want}, para {story.so_that}",
            "scenarios": scenarios,
            "user_story_id": story.id
        }
        features.append(feature)

    # Construir test suite
    all_scenarios = [s for f in features for s in f["scenarios"]]
    total_positive = sum(1 for s in all_scenarios if s["scenario_type"] == "positive")
    total_negative = sum(1 for s in all_scenarios if s["scenario_type"] == "negative")
    total_boundary = sum(1 for s in all_scenarios if s["scenario_type"] == "boundary")

    # Calcular cobertura por característica
    coverage_by_characteristic = {
        "functional_suitability": 0,
        "performance_efficiency": 0,
        "security": 0,
        "usability": 0,
        "reliability": 0,
        "compatibility": 0,
        "maintainability": 0,
        "portability": 0
    }
    for s in all_scenarios:
        qc = s.get("quality_characteristic", "functional_suitability")
        coverage_by_characteristic[qc] = coverage_by_characteristic.get(qc, 0) + 1

    test_suite = {
        "pipeline_run_id": f"webapp-m2-{uuid.uuid4().hex[:8]}",
        "agent_version": "0.3.0-v3-iso25010",
        "features": features,
        "coverage_matrix": coverage_matrix,
        "total_scenarios": len(all_scenarios),
        "total_positive": total_positive,
        "total_negative": total_negative,
        "total_boundary": total_boundary,
        "coverage_by_characteristic": coverage_by_characteristic
    }

    return test_suite


if __name__ == '__main__':
    print("Iniciando QualityAI Web App...")
    init_models()
    print("Servidor listo en http://localhost:3000")
    app.run(debug=True, host='0.0.0.0', port=3000)
