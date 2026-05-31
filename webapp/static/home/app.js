// QualityAI Web App - JavaScript
const API_BASE = 'http://localhost:3000/api';

let currentAmbiguities = [];
let currentResolutions = [];
let currentContractA = null;

// Ejemplos de requerimientos
const examples = {
    1: "El sistema debe gestionar usuarios de forma segura y eficiente, permitiendo el registro y autenticación de usuarios",
    2: "Necesito que el reporte se genere automáticamente con buena calidad y se envíe periódicamente a los usuarios",
    3: "El sistema debe ser rápido y fácil de usar para los usuarios, permitiendo realizar consultas de forma intuitiva"
};

// Versión fija - siempre usa v4 (la mejor)
const AGENT_VERSION = 'v4';

// Inicialización
document.addEventListener('DOMContentLoaded', () => {
    checkApiKey();
    checkHealth();
    setupEventListeners();
    setupApiKeyToggle();
});

function setupEventListeners() {
    const input = document.getElementById('requirementInput');
    input.addEventListener('input', updateCharCount);
}

function updateCharCount() {
    const input = document.getElementById('requirementInput');
    const count = document.getElementById('charCount');
    count.textContent = `${input.value.length} caracteres`;
}

// ============================================================
// GESTIÓN DE API KEY
// ============================================================

function getApiHeaders(additionalHeaders = {}) {
    const apiKey = localStorage.getItem('groq_api_key');
    return {
        'Content-Type': 'application/json',
        'X-Groq-API-Key': apiKey || '',
        ...additionalHeaders
    };
}

function checkApiKey() {
    const apiKey = localStorage.getItem('groq_api_key');
    if (!apiKey) {
        document.getElementById('apiKeyModal').classList.remove('hidden');
    }
}

function openApiKeyModal() {
    const currentKey = localStorage.getItem('groq_api_key');
    if (currentKey) {
        document.getElementById('apiKeyInput').value = currentKey;
    }
    document.getElementById('apiKeyModal').classList.remove('hidden');
}

function setupApiKeyToggle() {
    const checkbox = document.getElementById('showApiKey');
    const input = document.getElementById('apiKeyInput');
    
    checkbox.addEventListener('change', () => {
        input.type = checkbox.checked ? 'text' : 'password';
    });
}

function saveApiKey() {
    const apiKey = document.getElementById('apiKeyInput').value.trim();
    
    if (!apiKey) {
        alert('Por favor ingresa una API Key válida');
        return;
    }
    
    if (!apiKey.startsWith('gsk_')) {
        alert('La API Key de Groq debe comenzar con "gsk_"');
        return;
    }
    
    // Guardar en localStorage
    localStorage.setItem('groq_api_key', apiKey);
    
    // Cerrar modal
    document.getElementById('apiKeyModal').classList.add('hidden');
    
    // Mostrar confirmación
    alert('✅ API Key guardada correctamente. Ya puedes usar QualityAI.');
    
    // Recargar health check
    checkHealth();
}

async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();
        
        if (data.kb_count) {
            document.getElementById('kbCount').textContent = `${data.kb_count} historias`;
        }
        
        const status = document.getElementById('healthStatus');
        if (data.status === 'ok' && data.groq_configured) {
            status.innerHTML = `
                <div class="w-3 h-3 bg-green-400 rounded-full pulse-animation"></div>
                <span class="text-sm">Sistema Activo</span>
            `;
        } else {
            status.innerHTML = `
                <div class="w-3 h-3 bg-red-400 rounded-full"></div>
                <span class="text-sm">Configuración Incompleta</span>
            `;
        }
    } catch (error) {
        console.error('Error checking health:', error);
        const status = document.getElementById('healthStatus');
        status.innerHTML = `
            <div class="w-3 h-3 bg-red-400 rounded-full"></div>
            <span class="text-sm">Servidor Desconectado</span>
        `;
    }
}

function switchTab(tab) {
    // Update tab buttons
    document.querySelectorAll('[id^="tab-"]').forEach(btn => {
        btn.classList.remove('tab-active');
    });
    document.getElementById(`tab-${tab}`).classList.add('tab-active');
    
    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.add('hidden');
    });
    document.getElementById(`content-${tab}`).classList.remove('hidden');
}

function loadExample(num) {
    document.getElementById('requirementInput').value = examples[num];
    updateCharCount();
}

function clearInput() {
    document.getElementById('requirementInput').value = '';
    updateCharCount();
}

async function startProcess() {
    const requirement = document.getElementById('requirementInput').value.trim();
    
    if (!requirement) {
        alert('Por favor ingrese un requerimiento');
        return;
    }
    
    // Paso 1: Analizar ambigüedades
    showLoading('Analizando ambigüedades...');
    
    try {
        const response = await fetch(`${API_BASE}/analyze-ambiguities`, {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify({ requirement_text: requirement })
        });
        
        const data = await response.json();
        currentAmbiguities = data.ambiguities || [];
        
        hideLoading();
        
        // Si NO hay ambigüedades, generar directamente
        if (currentAmbiguities.length === 0) {
            await refineRequirements(null);
            return;
        }
        
        // Si HAY ambigüedades, mostrar para resolución
        displayAmbiguities(data);
        document.getElementById('ambCount').textContent = data.total || 0;
        switchTab('ambiguities');
        
    } catch (error) {
        console.error('Error:', error);
        alert('Error al analizar: ' + error.message);
        hideLoading();
    }
}

function showLoading(message = 'Procesando...') {
    document.getElementById('loadingMessage').textContent = message;
    document.getElementById('loadingModal').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingModal').classList.add('hidden');
}

function displayAmbiguities(data) {
    const container = document.getElementById('ambiguitiesContainer');
    
    if (!data.ambiguities || data.ambiguities.length === 0) {
        container.innerHTML = `
            <div class="text-center py-12 text-green-600">
                <i class="fas fa-check-circle text-6xl mb-4"></i>
                <p class="text-lg font-semibold">¡No se detectaron ambigüedades!</p>
                <p class="text-sm text-gray-600">El requerimiento es suficientemente claro</p>
            </div>
        `;
        document.getElementById('resolutionPanel').classList.add('hidden');
        return;
    }
    
    const severityColors = {
        'alta': 'severity-alta',
        'media': 'severity-media',
        'baja': 'severity-baja'
    };
    
    const severityIcons = {
        'alta': 'fa-exclamation-circle',
        'media': 'fa-exclamation-triangle',
        'baja': 'fa-info-circle'
    };
    
    let html = `
        <div class="mb-6 p-4 bg-orange-50 border-l-4 border-orange-500 rounded">
            <div class="flex items-center mb-2">
                <i class="fas fa-chart-pie text-orange-600 mr-2"></i>
                <h3 class="font-bold text-gray-800">Resumen del Análisis</h3>
            </div>
            <div class="grid grid-cols-3 gap-4 mt-4">
                <div class="text-center p-3 bg-red-100 rounded-lg">
                    <div class="text-2xl font-bold text-red-700">${data.severity_count.alta}</div>
                    <div class="text-sm text-red-600">Alta Severidad</div>
                </div>
                <div class="text-center p-3 bg-orange-100 rounded-lg">
                    <div class="text-2xl font-bold text-orange-700">${data.severity_count.media}</div>
                    <div class="text-sm text-orange-600">Media Severidad</div>
                </div>
                <div class="text-center p-3 bg-green-100 rounded-lg">
                    <div class="text-2xl font-bold text-green-700">${data.severity_count.baja}</div>
                    <div class="text-sm text-green-600">Baja Severidad</div>
                </div>
            </div>
        </div>
        
        <div class="space-y-4">
    `;
    
    const severityTooltips = {
        'alta': 'Crítico - Afecta significativamente la claridad del requerimiento',
        'media': 'Moderado - Puede causar interpretaciones diferentes',
        'baja': 'Menor - Aclaración recomendada pero no crítica'
    };
    
    data.ambiguities.forEach((amb, index) => {
        html += `
            <div class="border-l-4 border-${amb.severity === 'alta' ? 'red' : amb.severity === 'media' ? 'orange' : 'green'}-500 bg-white p-4 rounded-lg shadow-sm">
                <div class="flex items-start justify-between mb-3">
                    <div class="flex items-center space-x-3">
                        <div class="${severityColors[amb.severity]} text-white w-10 h-10 rounded-full flex items-center justify-center">
                            <i class="fas ${severityIcons[amb.severity]}"></i>
                        </div>
                        <div>
                            <h4 class="font-bold text-gray-800 text-lg">"${amb.word}"</h4>
                            <span class="text-sm text-gray-500">${amb.category.replace(/_/g, ' ')}</span>
                        </div>
                    </div>
                    <span class="badge badge-${amb.severity === 'alta' ? 'critical' : amb.severity === 'media' ? 'high' : 'medium'}" title="${severityTooltips[amb.severity]}">
                        ${amb.severity.toUpperCase()}
                    </span>
                </div>
                
                <div class="space-y-2 text-sm">
                    <div class="flex items-start">
                        <i class="fas fa-quote-left text-gray-400 mr-2 mt-1"></i>
                        <div>
                            <span class="font-semibold text-gray-700">Contexto:</span>
                            <span class="text-gray-600">${amb.context}</span>
                        </div>
                    </div>
                    
                    <div class="flex items-start">
                        <i class="fas fa-lightbulb text-yellow-500 mr-2 mt-1"></i>
                        <div>
                            <span class="font-semibold text-gray-700">Sugerencia:</span>
                            <span class="text-gray-600">${amb.suggestion}</span>
                        </div>
                    </div>
                    
                    ${amb.ieee_830_violation ? `
                        <div class="flex items-start">
                            <i class="fas fa-book text-blue-500 mr-2 mt-1"></i>
                            <div>
                                <span class="font-semibold text-gray-700">IEEE 830:</span>
                                <span class="text-gray-600">${amb.ieee_830_violation}</span>
                            </div>
                        </div>
                    ` : ''}
                    
                    ${amb.iso_25010_category ? `
                        <div class="flex items-start">
                            <i class="fas fa-certificate text-purple-500 mr-2 mt-1"></i>
                            <div>
                                <span class="font-semibold text-gray-700">ISO 25010:</span>
                                <span class="text-gray-600">${amb.iso_25010_category}</span>
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
    
    // Siempre mostrar panel de resolución (v4)
    displayResolutionPanel(data.ambiguities);
}

function displayResolutionPanel(ambiguities) {
    const panel = document.getElementById('resolutionPanel');
    const container = document.getElementById('resolutionItems');
    
    currentResolutions = [];
    
    let html = '';
    ambiguities.forEach((amb, index) => {
        currentResolutions.push({
            word: amb.word,
            category: amb.category,
            analyst_resolution: '',
            status: 'pending'
        });
        
        html += `
            <div class="border-2 border-gray-200 rounded-lg p-4 bg-gray-50">
                <div class="flex items-center justify-between mb-3">
                    <h4 class="font-bold text-gray-800">"${amb.word}"</h4>
                    <span class="text-sm text-gray-500">${amb.category.replace(/_/g, ' ')}</span>
                </div>
                
                <p class="text-sm text-gray-600 mb-3">
                    <i class="fas fa-lightbulb text-yellow-500 mr-1"></i>
                    Sugerencia: ${amb.suggestion}
                </p>
                
                <div class="space-y-2">
                    <label class="flex items-center space-x-2 cursor-pointer">
                        <input type="radio" name="resolution-${index}" value="accept" class="text-purple-600" onchange="updateResolution(${index}, 'accept', '${amb.suggestion.replace(/'/g, "\\'")}')">
                        <span class="text-sm">Aceptar sugerencia</span>
                    </label>
                    
                    <label class="flex items-center space-x-2 cursor-pointer">
                        <input type="radio" name="resolution-${index}" value="custom" class="text-purple-600" onchange="toggleCustomInput(${index})">
                        <span class="text-sm">Proporcionar mi propia resolución</span>
                    </label>
                    
                    <div id="custom-input-${index}" class="hidden ml-6 mt-2">
                        <input type="text" 
                               id="custom-text-${index}"
                               class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-purple-500 focus:ring-2 focus:ring-purple-200"
                               placeholder="Escriba su resolución..."
                               onchange="updateResolution(${index}, 'custom', this.value)">
                    </div>
                    
                    <label class="flex items-center space-x-2 cursor-pointer">
                        <input type="radio" name="resolution-${index}" value="dismiss" class="text-purple-600" onchange="updateResolution(${index}, 'dismiss', '')">
                        <span class="text-sm">Descartar - no es ambiguo en este contexto</span>
                    </label>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
    panel.classList.remove('hidden');
}

function toggleCustomInput(index) {
    const customDiv = document.getElementById(`custom-input-${index}`);
    customDiv.classList.remove('hidden');
    document.getElementById(`custom-text-${index}`).focus();
}

function updateResolution(index, type, value) {
    if (type === 'accept') {
        currentResolutions[index] = {
            ...currentResolutions[index],
            analyst_resolution: value,
            status: 'resolved'
        };
    } else if (type === 'custom') {
        currentResolutions[index] = {
            ...currentResolutions[index],
            analyst_resolution: value,
            status: 'resolved'
        };
    } else if (type === 'dismiss') {
        currentResolutions[index] = {
            ...currentResolutions[index],
            analyst_resolution: '',
            status: 'dismissed'
        };
    }
}

function cancelResolutions() {
    currentResolutions = [];
    document.getElementById('resolutionPanel').classList.add('hidden');
    switchTab('input');
}

async function submitResolutions() {
    // Validate all resolutions are completed
    const pending = currentResolutions.filter(r => r.status === 'pending');
    if (pending.length > 0) {
        alert(`Por favor resuelva todas las ambigüedades (${pending.length} pendientes)`);
        return;
    }
    
    await refineRequirements(currentResolutions);
}

async function refineRequirements(resolutions = null) {
    const requirement = document.getElementById('requirementInput').value.trim();
    const version = AGENT_VERSION; // Siempre v4
    
    if (!requirement) {
        alert('Por favor ingrese un requerimiento');
        return;
    }
    
    showLoading('Refinando requerimientos con IA...');
    
    try {
        const payload = {
            requirement_text: requirement,
            version: version
        };
        
        if (resolutions) {
            payload.analyst_resolutions = resolutions;
        }
        
        const response = await fetch(`${API_BASE}/refine-requirements`, {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        displayResults(data.result);
        document.getElementById('storiesCount').textContent = data.result.user_stories.length;
        
        switchTab('results');
        hideLoading();
    } catch (error) {
        console.error('Error:', error);
        alert('Error al refinar requerimientos: ' + error.message);
        hideLoading();
    }
}

function displayResults(result) {
    const container = document.getElementById('resultsContainer');
    
    // Guardar Contract A para el módulo 2
    currentContractA = result;
    
    // Mostrar botón para continuar al módulo 2
    const continueBtn = document.getElementById('continueToModule2');
    if (continueBtn) {
        continueBtn.classList.remove('hidden');
    }
    
    if (!result.user_stories || result.user_stories.length === 0) {
        container.innerHTML = `
            <div class="text-center py-12 text-gray-500">
                <i class="fas fa-exclamation-circle text-6xl mb-4 text-gray-300"></i>
                <p class="text-lg">No se generaron historias de usuario</p>
            </div>
        `;
        return;
    }
    
    let html = `
        <!-- Summary -->
        <div class="mb-6 p-6 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg border border-purple-200">
            <h3 class="text-xl font-bold text-gray-800 mb-4">
                <i class="fas fa-chart-line text-purple-600 mr-2"></i>
                Resumen del Refinamiento
            </h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="text-center p-3 bg-white rounded-lg shadow-sm">
                    <div class="text-3xl font-bold text-purple-600">${result.user_stories.length}</div>
                    <div class="text-sm text-gray-600">Historias</div>
                </div>
                <div class="text-center p-3 bg-white rounded-lg shadow-sm">
                    <div class="text-3xl font-bold text-blue-600">${result.user_stories.reduce((sum, s) => sum + s.acceptance_criteria.length, 0)}</div>
                    <div class="text-sm text-gray-600">Criterios</div>
                </div>
                <div class="text-center p-3 bg-white rounded-lg shadow-sm">
                    <div class="text-3xl font-bold text-orange-600">${result.total_ambiguities_found}</div>
                    <div class="text-sm text-gray-600">Ambigüedades</div>
                </div>
                <div class="text-center p-3 bg-white rounded-lg shadow-sm" title="Número de decisiones que la IA tuvo que adivinar (0 es ideal)">
                    <div class="text-3xl font-bold ${result.total_assumptions_made === 0 ? 'text-green-600' : 'text-red-600'}">${result.total_assumptions_made}</div>
                    <div class="text-sm text-gray-600">Decisiones de IA</div>
                </div>
            </div>
            
            ${result.project_context ? `
                <div class="mt-4 p-4 bg-white rounded-lg">
                    <h4 class="font-semibold text-gray-700 mb-2">Contexto del Proyecto:</h4>
                    <p class="text-gray-600">${result.project_context}</p>
                </div>
            ` : ''}
        </div>
        
        <!-- User Stories -->
        <div class="space-y-6">
    `;
    
    result.user_stories.forEach((story, index) => {
        const priorityClass = {
            'critical': 'badge-critical',
            'high': 'badge-high',
            'medium': 'badge-medium',
            'low': 'badge-low'
        }[story.priority] || 'badge-medium';
        
        const priorityTooltip = {
            'critical': 'Urgente - Debe implementarse de inmediato',
            'high': 'Alta prioridad - Implementar pronto',
            'medium': 'Prioridad media - Planificar para próximas iteraciones',
            'low': 'Baja prioridad - Puede esperar'
        }[story.priority] || 'Prioridad media';
        
        const typeClass = {
            'functional': 'badge-functional',
            'non_functional': 'badge-non-functional',
            'technical': 'badge-technical'
        }[story.story_type] || 'badge-functional';
        
        const typeTooltip = {
            'functional': 'Funcionalidad visible para el usuario final',
            'non_functional': 'Requisito de calidad (rendimiento, seguridad, usabilidad)',
            'technical': 'Tarea técnica interna (refactorización, infraestructura)'
        }[story.story_type] || 'Funcionalidad del sistema';
        
        html += `
            <div class="story-card bg-white rounded-lg shadow-md p-6 fade-in">
                <div class="flex items-start justify-between mb-4">
                    <div>
                        <h3 class="text-xl font-bold text-gray-800">${story.id}: ${story.title}</h3>
                        <div class="flex items-center space-x-2 mt-2">
                            <span class="badge ${typeClass}" title="${typeTooltip}">${story.story_type.replace('_', ' ')}</span>
                            <span class="badge ${priorityClass}" title="${priorityTooltip}">${story.priority}</span>
                        </div>
                    </div>
                </div>
                
                <div class="bg-gray-50 rounded-lg p-4 mb-4">
                    <div class="space-y-2 text-sm">
                        <p><span class="font-semibold text-purple-600">Como</span> ${story.as_a}</p>
                        <p><span class="font-semibold text-purple-600">Quiero</span> ${story.i_want}</p>
                        <p><span class="font-semibold text-purple-600">Para que</span> ${story.so_that}</p>
                    </div>
                </div>
                
                <h4 class="font-bold text-gray-800 mb-3">
                    <i class="fas fa-check-square text-green-600 mr-2"></i>
                    Criterios de Aceptación (${story.acceptance_criteria.length})
                </h4>
                
                <div class="space-y-3">
        `;
        
        story.acceptance_criteria.forEach((criterion, cIndex) => {
            html += `
                <div class="criterion-card border border-gray-200 rounded-lg p-4">
                    <div class="flex items-start justify-between mb-2">
                        <h5 class="font-semibold text-gray-800">${criterion.id}: ${criterion.description}</h5>
                        ${criterion.is_negative_case ? '<span class="badge badge-critical" title="Verifica que el sistema rechace datos inválidos"><i class="fas fa-exclamation-triangle mr-1"></i>Prueba de Rechazo</span>' : ''}
                    </div>
                    
                    <div class="space-y-2 text-sm mt-3">
                        <div class="flex items-start">
                            <span class="font-semibold text-blue-600 w-20">GIVEN:</span>
                            <span class="text-gray-700 flex-1">${criterion.given}</span>
                        </div>
                        <div class="flex items-start">
                            <span class="font-semibold text-green-600 w-20">WHEN:</span>
                            <span class="text-gray-700 flex-1">${criterion.when}</span>
                        </div>
                        <div class="flex items-start">
                            <span class="font-semibold text-purple-600 w-20">THEN:</span>
                            <span class="text-gray-700 flex-1">${criterion.then}</span>
                        </div>
                    </div>
                    
                    ${criterion.test_data_examples && criterion.test_data_examples.length > 0 ? `
                        <div class="mt-3 p-3 bg-blue-50 rounded">
                            <h6 class="text-xs font-semibold text-blue-800 mb-2">Datos de Prueba:</h6>
                            <div class="space-y-1">
                                ${criterion.test_data_examples.map(ex => `
                                    <div class="text-xs text-blue-700">
                                        ${Object.entries(ex).map(([k, v]) => `<span class="font-mono">${k}: ${JSON.stringify(v)}</span>`).join(', ')}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                    
                    ${criterion.boundary_values && criterion.boundary_values.length > 0 ? `
                        <div class="mt-2">
                            <span class="text-xs font-semibold text-gray-600">Valores Límite:</span>
                            <span class="text-xs text-gray-600">${criterion.boundary_values.join(', ')}</span>
                        </div>
                    ` : ''}
                </div>
            `;
        });
        
        html += '</div>';
        
        // Ambiguities resolved
        if (story.ambiguities_resolved && story.ambiguities_resolved.length > 0) {
            html += `
                <div class="mt-4">
                    <h4 class="font-bold text-gray-800 mb-3">
                        <i class="fas fa-lightbulb text-yellow-500 mr-2"></i>
                        Ambigüedades Resueltas
                    </h4>
                    <div class="space-y-2">
            `;
            
            story.ambiguities_resolved.forEach(amb => {
                const badge = amb.assumption_made ? 
                    '<span class="badge badge-critical" title="La IA decidió esto por su cuenta"><i class="fas fa-robot mr-1"></i>Decidido por IA</span>' : 
                    '<span class="badge badge-low" title="Usted decidió esto"><i class="fas fa-user-check mr-1"></i>Decidido por Usted</span>';
                
                html += `
                    <div class="flex items-start space-x-3 text-sm p-3 bg-yellow-50 rounded-lg">
                        <div class="flex-1">
                            <p class="font-semibold text-gray-800">"${amb.original_text}"</p>
                            <p class="text-gray-600 mt-1">${amb.resolution}</p>
                        </div>
                        ${badge}
                    </div>
                `;
            });
            
            html += '</div></div>';
        }
        
        // Additional info
        const hasAdditionalInfo = story.business_rules?.length > 0 || 
                                  story.dependencies?.length > 0 || 
                                  story.ui_elements?.length > 0 || 
                                  story.api_endpoints?.length > 0;
        
        if (hasAdditionalInfo) {
            html += '<div class="mt-4 grid grid-cols-2 gap-4 text-sm">';
            
            if (story.business_rules?.length > 0) {
                html += `
                    <div>
                        <h5 class="font-semibold text-gray-700 mb-2">Reglas de Negocio:</h5>
                        <ul class="list-disc list-inside text-gray-600 space-y-1">
                            ${story.business_rules.map(rule => `<li>${rule}</li>`).join('')}
                        </ul>
                    </div>
                `;
            }
            
            if (story.dependencies?.length > 0) {
                html += `
                    <div>
                        <h5 class="font-semibold text-gray-700 mb-2">Dependencias:</h5>
                        <div class="flex flex-wrap gap-2">
                            ${story.dependencies.map(dep => `<span class="badge badge-medium">${dep}</span>`).join('')}
                        </div>
                    </div>
                `;
            }
            
            if (story.ui_elements?.length > 0) {
                html += `
                    <div>
                        <h5 class="font-semibold text-gray-700 mb-2">Elementos UI:</h5>
                        <div class="flex flex-wrap gap-2">
                            ${story.ui_elements.map(el => `<span class="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded">${el}</span>`).join('')}
                        </div>
                    </div>
                `;
            }
            
            if (story.api_endpoints?.length > 0) {
                html += `
                    <div>
                        <h5 class="font-semibold text-gray-700 mb-2">API Endpoints:</h5>
                        <div class="space-y-1">
                            ${story.api_endpoints.map(ep => `<code class="text-xs bg-gray-100 px-2 py-1 rounded block">${ep}</code>`).join('')}
                        </div>
                    </div>
                `;
            }
            
            html += '</div>';
        }
        
        html += '</div>';
    });
    
    html += `
        </div>
        
        <!-- Actions -->
        <div class="mt-8 flex justify-end space-x-4">
            <button onclick="downloadJSON()" class="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition-all shadow-md hover:shadow-lg">
                <i class="fas fa-download mr-2"></i>Descargar JSON
            </button>
            <button onclick="switchTab('input')" class="px-6 py-3 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700 transition-all shadow-md hover:shadow-lg">
                <i class="fas fa-plus mr-2"></i>Nuevo Requerimiento
            </button>
        </div>
    `;
    
    container.innerHTML = html;
}

function downloadJSON() {
    const container = document.getElementById('resultsContainer');
    if (!container.textContent.includes('Historias')) {
        alert('No hay resultados para descargar');
        return;
    }
    
    // This would need the actual result data stored
    alert('Funcionalidad de descarga - Los archivos se guardan automáticamente en la carpeta output/');
}

// ============================================================
// MÓDULO 2: TEST ARCHITECT - Generación de Escenarios Gherkin
// ============================================================

function startModule2() {
    if (!currentContractA) {
        alert('Error: No hay Contract A disponible. Primero genera las historias de usuario.');
        return;
    }
    
    // Guardar Contract A en localStorage para el módulo 2
    localStorage.setItem('contractA', JSON.stringify(currentContractA));
    
    // Redirigir a la página de generación de escenarios
    window.location.href = '/static/scenarios/';
}


