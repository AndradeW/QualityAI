# QualityAI Web App v2

Interfaz web para refinamiento de requerimientos y generación automática de escenarios de prueba Gherkin.

---

## Requisitos Previos

- **Python 3.8 o superior**
- **Groq API Key** ([Obtener aquí](https://console.groq.com))

---

## Instalación

```bash
cd webapp
pip install -r requirements.txt
```

## Configurar API Key

### Opción A — Archivo `.env`

Crea el archivo `webapp/.env`:

```
GROQ_API_KEY=gsk_tu_api_key_aqui
```

### Opción B — Variable de entorno

```powershell
# PowerShell
$env:GROQ_API_KEY="gsk_tu_api_key_aqui"
```

### Opción C — Desde la interfaz web

Al abrir la app, un modal te pedirá la API Key. Se guarda en `localStorage` del navegador. Puedes cambiarla desde el botón "API Key" en la esquina superior derecha.

---

## Ejecutar

```bash
cd webapp
.\venv\Scripts\python.exe app.py
```

Abrir en: **http://localhost:3000**

> El primer arranque descarga modelos de embeddings (~50MB). Con `debug=True` hay un reinicio automático, la carga completa toma ~10-15s.

---

## Estructura

```
webapp/
├── app.py                      # Servidor Flask (API + static)
├── requirements.txt            # Dependencias Python
├── .env                        # API Key de Groq
├── src/
│   ├── ambiguity_detector.py   # Detección de ambigüedades
│   └── contract_a.py           # Modelos Pydantic (Contract A)
├── knowledge_base/
│   └── katary_stories.json     # 15 historias de referencia para RAG
├── knowledge_base_data/        # ChromaDB persistente (índice vectorial)
├── output/                     # Resultados generados (Contract A + B)
├── static/
│   ├── home/                   # Refinamiento de requerimientos (M1)
│   │   ├── index.html
│   │   └── app.js
│   ├── scenarios/              # Generación de escenarios (M2)
│   │   ├── index.html
│   │   └── scenarios.js
│   ├── review/                 # Revisión manual
│   │   ├── index.html
│   │   └── review.js
│   └── report/                 # Reporte ejecutivo
│       ├── index.html
│       └── report.js
└── venv/                       # Entorno virtual
```

---

## Endpoints de la API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/health` | Estado del servidor, KB count, modelos cargados |
| POST | `/api/analyze-ambiguities` | Analiza ambigüedades en un texto |
| POST | `/api/refine-requirements` | Genera historias de usuario (Contract A) |
| POST | `/api/m2/generate-scenarios` | Genera escenarios Gherkin (Contract B) |

Todas las rutas POST esperan `X-Groq-API-Key` en el header (o la variable de entorno).

---

## Flujo de Uso

1. **Ingresar requerimientos** → Página principal (`/`)
2. **Analizar ambigüedades** → Detección automática
3. **Resolver ambigüedades** → Revisión manual
4. **Generar historias de usuario** → Refinamiento automático
5. **Generar escenarios de prueba** → Casos Gherkin (`/scenarios`)
6. **Revisar escenarios** (opcional) → Ajustes manuales
7. **Generar reporte** → Reporte ejecutivo (`/report`)

---

## Solución de Problemas

| Error | Solución |
|-------|----------|
| `ModuleNotFoundError: No module named 'flask'` | `pip install -r requirements.txt` |
| `GROQ_API_KEY no configurada` | Configurar `.env` o variable de entorno |
| `Puerto 3000 en uso` | Cambiar a `port=5000` en el `__main__` de `app.py` |
| Los modelos tardan en cargar | La primera vez descarga embeddings (~50MB). Con `debug=True` se reinicia una vez. |

---

## Tecnologías

- **Backend**: Flask + Python
- **Frontend**: HTML5 + TailwindCSS + JavaScript
- **IA**: Groq (llama-3.3-70b-versatile)
- **Embeddings**: SentenceTransformers (all-MiniLM-L6-v2)
- **Vector DB**: ChromaDB
- **Validación**: Pydantic

---

**Versión**: 2.0.0
**Última actualización**: Mayo 2026
