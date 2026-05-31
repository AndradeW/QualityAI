# QualityAI - Aplicación Web

Interfaz web para el sistema QualityAI de refinamiento de requerimientos y generación automática de escenarios de prueba.

## 📋 Requisitos Previos

- **Python 3.8 o superior**
- **pip** (gestor de paquetes de Python)
- **Groq API Key** ([Obtener aquí](https://console.groq.com))

---

## 🚀 Instalación Rápida

### Paso 1: Verificar estructura del proyecto

Asegúrate de tener esta estructura en tu computador:

```
/tu-proyecto/
├── qualityai-modulo1/
├── qualityai-modulo2/
└── webapp/              ← Esta carpeta
```

### Paso 2: Instalar dependencias de los módulos (si no lo has hecho)

**Solo si es la primera vez que instalas:**

```bash
# Desde la raíz del proyecto
cd qualityai-modulo1
pip install -r requirements.txt
cd ..

cd qualityai-modulo2
pip install -r requirements.txt
cd ..
```

> **📝 Nota importante:** Si usas la interfaz web, **NO necesitas configurar API Key en los módulos 1 y 2**. La webapp los usa internamente y les pasa la API Key que configures en la interfaz.

### Paso 3: Instalar dependencias de la webapp

```bash
cd webapp
pip install -r requirements.txt
```

### Paso 4: Configurar API Key de Groq

**✨ NUEVO: Configuración desde la interfaz**

Ahora puedes configurar tu API Key directamente desde la interfaz web:

1. Abre la aplicación en tu navegador
2. Al iniciar, verás un modal solicitando tu API Key
3. Ingresa tu API Key de Groq (comienza con `gsk_`)
4. Haz clic en "Guardar y Continuar"
5. ¡Listo! Tu API Key se guardará en tu navegador

**Cambiar API Key:** Haz clic en el botón "API Key" en la esquina superior derecha.

---

**Opción alternativa - Variable de entorno:**

```bash
# En macOS/Linux:
export GROQ_API_KEY="tu_api_key_aqui"

# En Windows (CMD):
set GROQ_API_KEY=tu_api_key_aqui

# En Windows (PowerShell):
$env:GROQ_API_KEY="tu_api_key_aqui"
```

**Opción B - Archivo .env:**

Crea un archivo `.env` en la carpeta `webapp/` con:

```
GROQ_API_KEY=tu_api_key_aqui
```

### Paso 5: Ejecutar la aplicación

```bash
# Asegúrate de estar en la carpeta webapp
cd webapp
python3 app.py
```

### Paso 6: Abrir en el navegador

Abre tu navegador en: **http://localhost:3000**

---

## 📁 Estructura de la Webapp

```
webapp/
├── app.py                      # Servidor Flask
├── static/
│   ├── home/                   # Refinamiento de requerimientos
│   │   ├── index.html
│   │   └── app.js
│   ├── scenarios/              # Generación de escenarios
│   │   ├── index.html
│   │   └── scenarios.js
│   ├── review/                 # Revisión manual
│   │   ├── index.html
│   │   └── review.js
│   └── report/                 # Reporte ejecutivo
│       ├── index.html
│       └── report.js
└── requirements.txt
```

---

## 🔧 Solución de Problemas

### Error: "ModuleNotFoundError"

Instala las dependencias:

```bash
pip install -r requirements.txt
```

### Error: "GROQ_API_KEY no configurada"

Asegúrate de haber configurado la API Key (ver Paso 4).

### El puerto 3000 está en uso

Cambia el puerto en `app.py` (última línea):

```python
app.run(host='0.0.0.0', port=5000, debug=True)  # Cambiar 3000 por otro puerto
```

### Los modelos tardan en cargar

La primera vez descargará modelos de embeddings (~500MB). Es normal y solo sucede una vez.

---

## 📝 Dependencias Principales

- `flask` - Framework web
- `flask-cors` - CORS para API
- `groq` - Cliente para LLM
- `sentence-transformers` - Modelos de embeddings
- `chromadb` - Base de datos vectorial
- `pydantic` - Validación de datos

---

## 🎯 Flujo de Uso

1. **Ingresar requerimientos** → Página principal
2. **Analizar ambigüedades** → Detección automática
3. **Resolver ambigüedades** → Revisión manual
4. **Generar historias de usuario** → Refinamiento automático
5. **Generar escenarios de prueba** → Casos de prueba Gherkin
6. **Revisar escenarios** (Opcional) → Ajustes manuales
7. **Generar reporte** → Reporte ejecutivo final

---

## 📄 Notas Importantes

- La webapp requiere que los módulos 1 y 2 estén en la misma carpeta raíz
- Los archivos se sirven desde `/static/` con estructura organizada por carpetas
- El servidor corre en modo debug por defecto (no usar en producción)
- Los reportes se guardan en `qualityai-modulo2/output/`

---

**Versión**: 1.0.0  
**Última actualización**: Mayo 2026

## 💡 ¿Qué Hace?

Convierte ideas vagas en especificaciones técnicas profesionales:

**Tú escribes:**
```
"El sistema debe gestionar usuarios de forma segura"
```

**La app genera:**
- ✅ Historias de usuario estructuradas
- ✅ Criterios de aceptación Given/When/Then
- ✅ Datos de prueba concretos
- ✅ Sin suposiciones (tú decides todo)

## 🎯 Cómo Usar

1. **Ingresa tu requerimiento** en el área de texto
2. **Haz clic en "Generar Historias de Usuario"**
3. **Resuelve las ambigüedades** que el sistema detecte
4. **Revisa las historias generadas** con criterios verificables

## 🔧 Tecnologías

- **Backend**: Flask + Python
- **Frontend**: HTML5 + TailwindCSS + JavaScript
- **IA**: Groq (llama-3.3-70b-versatile)
- **Embeddings**: SentenceTransformers
- **Vector DB**: ChromaDB
- **Validación**: Pydantic

## � Estructura

```
webapp/
├── app.py              # Servidor Flask
├── requirements.txt    # Dependencias
├── start.bat          # Script de inicio (Windows)
└── static/
    ├── index.html     # Interfaz
    └── app.js         # Lógica
```

## 🐛 Solución de Problemas

**Error: "GROQ_API_KEY no configurada"**
→ Crea archivo `.env` con tu clave de Groq

**Error: "No module named 'flask'"**
→ Ejecuta: `pip install -r requirements.txt`

**Puerto 5000 ocupado**
→ Cambia el puerto en `app.py` línea final

## 📝 Notas

- Resultados se guardan en `../output/webapp_v4_*.json`
- Base de conocimiento se carga automáticamente
- Sistema usa Human-in-the-Loop (máxima calidad)
