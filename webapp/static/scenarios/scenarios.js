const API_BASE = 'http://localhost:3000/api';
let currentContractB = null;

// Traducciones
const SCENARIO_TYPES_ES = {
    'positive': 'Positivo',
    'negative': 'Negativo',
    'boundary': 'Límite',
    'edge_case': 'Caso Extremo',
    'error_handling': 'Manejo de Errores'
};

const QUALITY_CHARACTERISTICS_ES = {
    'functional_suitability': 'Idoneidad Funcional',
    'performance_efficiency': 'Eficiencia de Desempeño',
    'security': 'Seguridad',
    'usability': 'Usabilidad',
    'reliability': 'Fiabilidad',
    'compatibility': 'Compatibilidad',
    'maintainability': 'Mantenibilidad',
    'portability': 'Portabilidad'
};

function translateScenarioType(type) {
    return SCENARIO_TYPES_ES[type] || type;
}

function translateQualityCharacteristic(qc) {
    return QUALITY_CHARACTERISTICS_ES[qc] || qc;
}

// Obtener Contract A del localStorage (pasado desde módulo 1)
let contractA = null;
try {
    contractA = JSON.parse(localStorage.getItem('contractA') || 'null');
    console.log('Contract A cargado:', contractA);
} catch (e) {
    console.error('Error al cargar Contract A:', e);
}

if (!contractA) {
    console.warn('No hay Contract A disponible');
    alert('No hay Contract A disponible. Redirigiendo al Módulo 1...');
    window.location.href = '/';
}

async function generateScenarios() {
    console.log('=== INICIANDO GENERACIÓN DE ESCENARIOS ===');
    console.log('Contract A:', contractA);
    
    if (!contractA) {
        alert('Error: No hay Contract A disponible');
        return;
    }
    
    showLoading('Analizando historias y generando escenarios de prueba...');
    
    try {
        console.log('Enviando petición a:', `${API_BASE}/m2/generate-scenarios`);
        
        const response = await fetch(`${API_BASE}/m2/generate-scenarios`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Groq-API-Key': localStorage.getItem('groq_api_key') || ''
            },
            body: JSON.stringify({
                contract_a: contractA,
                version: 'v3'  // Siempre genera V3 (incluye V1 y V2)
            })
        });
        
        console.log('Respuesta recibida, status:', response.status);
        
        let data;
        try {
            data = await response.json();
            console.log('Datos recibidos:', data);
        } catch (jsonError) {
            console.error('Error al parsear JSON:', jsonError);
            const text = await response.text();
            console.error('Respuesta del servidor:', text);
            hideLoading();
            alert('Error al parsear respuesta del servidor. Ver consola para detalles.');
            return;
        }
        
        hideLoading();
        
        if (data.success) {
            console.log('✅ Escenarios generados exitosamente');
            currentContractB = data.contract_b;
            displayResults(data.contract_b);
        } else {
            console.error('❌ Error en la generación:', data);
            alert('Error al generar escenarios:\n' + (data.error || 'Error desconocido') + 
                  (data.traceback ? '\n\nVer consola para más detalles' : ''));
            if (data.traceback) {
                console.error('Traceback:', data.traceback);
            }
        }
    } catch (error) {
        console.error('❌ Error de conexión:', error);
        hideLoading();
        alert('Error de conexión: ' + error.message);
        console.error(error);
    }
}

function displayResults(contractB) {
    document.getElementById('resultsSection').classList.remove('hidden');
    
    // Métricas
    displayMetrics(contractB);
    
    // Escenarios
    displayScenarios(contractB);
    
    // Matriz de cobertura (siempre se muestra en V3)
    displayCoverageMatrix(contractB);
    
    // Scroll suave
    document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
}

function displayMetrics(contractB) {
    const html = `
        <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div class="text-center p-4 bg-blue-50 rounded-lg">
                <div class="text-4xl font-bold text-blue-600">${contractB.total_scenarios}</div>
                <div class="text-sm text-gray-600 mt-1">Escenarios Totales</div>
            </div>
            <div class="text-center p-4 bg-green-50 rounded-lg">
                <div class="text-4xl font-bold text-green-600">${contractB.total_positive || 0}</div>
                <div class="text-sm text-gray-600 mt-1">Positivos</div>
            </div>
            <div class="text-center p-4 bg-red-50 rounded-lg">
                <div class="text-4xl font-bold text-red-600">${contractB.total_negative || 0}</div>
                <div class="text-sm text-gray-600 mt-1">Negativos</div>
            </div>
            <div class="text-center p-4 bg-orange-50 rounded-lg">
                <div class="text-4xl font-bold text-orange-600">${contractB.total_boundary || 0}</div>
                <div class="text-sm text-gray-600 mt-1">Valores Límite</div>
            </div>
            <div class="text-center p-4 bg-purple-50 rounded-lg">
                <div class="text-4xl font-bold text-purple-600">${contractB.features.length}</div>
                <div class="text-sm text-gray-600 mt-1">Funcionalidades</div>
            </div>
        </div>
    `;
    document.getElementById('metricsContent').innerHTML = html;
}

function displayScenarios(contractB) {
    let html = '';
    
    contractB.features.forEach((feature, idx) => {
        html += `
            <div class="mb-6 border border-gray-200 rounded-lg overflow-hidden">
                <div class="bg-gradient-to-r from-purple-600 to-indigo-600 text-white p-4">
                    <h4 class="text-xl font-bold">Feature: ${feature.name}</h4>
                    <p class="text-purple-100 text-sm mt-1">${feature.description}</p>
                </div>
                <div class="p-4 bg-white space-y-4">
        `;
        
        feature.scenarios.forEach((scenario) => {
            const typeColors = {
                'positive': 'green',
                'negative': 'red',
                'boundary': 'orange',
                'edge_case': 'yellow',
                'error_handling': 'purple'
            };
            const color = typeColors[scenario.scenario_type] || 'gray';
            
            html += `
                <div class="p-4 border-l-4 border-${color}-500 bg-gray-50 rounded">
                    <div class="flex items-center justify-between mb-2">
                        <h5 class="font-bold text-gray-800">${scenario.name}</h5>
                        <div class="flex gap-2">
                            <span class="text-xs px-3 py-1 bg-${color}-100 text-${color}-700 rounded-full font-semibold">${translateScenarioType(scenario.scenario_type)}</span>
                            ${scenario.quality_characteristic ? `<span class="text-xs px-3 py-1 bg-indigo-100 text-indigo-700 rounded-full font-semibold">${translateQualityCharacteristic(scenario.quality_characteristic)}</span>` : ''}
                        </div>
                    </div>
                    <div class="font-mono text-sm space-y-1 mt-3">
            `;
            
            scenario.steps.forEach(step => {
                html += `<div class="text-gray-700"><span class="font-bold text-${color}-600">${step.keyword}</span> ${step.text}</div>`;
            });
            
            if (scenario.tags && scenario.tags.length > 0) {
                html += `
                    <div class="mt-3 flex flex-wrap gap-1">
                        ${scenario.tags.map(tag => `<span class="text-xs px-2 py-1 bg-gray-200 rounded">${tag}</span>`).join('')}
                    </div>
                `;
            }
            
            html += `
                    </div>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    });
    
    document.getElementById('scenariosContent').innerHTML = html;
}

function displayCoverageMatrix(contractB) {
    if (!contractB.coverage_by_characteristic) {
        return;
    }
    
    document.getElementById('coverageSection').classList.remove('hidden');
    
    const characteristics = [
        'functional_suitability',
        'performance_efficiency',
        'security',
        'usability',
        'reliability',
        'compatibility',
        'maintainability',
        'portability'
    ];
    
    let html = `
        <table class="w-full">
            <thead class="bg-gray-100">
                <tr>
                    <th class="px-4 py-3 text-left">Característica ISO 25010</th>
                    <th class="px-4 py-3 text-center">Escenarios</th>
                    <th class="px-4 py-3 text-center">Estado</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    characteristics.forEach(char => {
        const count = contractB.coverage_by_characteristic[char] || 0;
        let estado = '';
        let estadoClass = '';
        
        if (count === 0) {
            estado = 'No cubierto';
            estadoClass = 'text-red-600 bg-red-50';
        } else if (count < 5) {
            estado = 'Ligero';
            estadoClass = 'text-yellow-600 bg-yellow-50';
        } else {
            estado = 'Robusto';
            estadoClass = 'text-green-600 bg-green-50';
        }
        
        html += `
            <tr class="border-b">
                <td class="px-4 py-3 font-semibold">${translateQualityCharacteristic(char)}</td>
                <td class="px-4 py-3 text-center font-bold">${count}</td>
                <td class="px-4 py-3 text-center">
                    <span class="px-3 py-1 rounded-full text-sm font-semibold ${estadoClass}">${estado}</span>
                </td>
            </tr>
        `;
    });
    
    html += `
            </tbody>
            <tfoot class="bg-gray-100 font-bold">
                <tr>
                    <td class="px-4 py-3">TOTAL</td>
                    <td class="px-4 py-3 text-center">${contractB.total_scenarios}</td>
                    <td class="px-4 py-3"></td>
                </tr>
            </tfoot>
        </table>
    `;
    
    document.getElementById('coverageContent').innerHTML = html;
}

function startReview() {
    if (!currentContractB) {
        alert('No hay datos para revisar');
        return;
    }
    
    localStorage.setItem('contractB', JSON.stringify(currentContractB));
    window.location.href = '/static/review/';
}

function generateReport() {
    if (!currentContractB) {
        alert('No hay datos para generar el reporte');
        return;
    }
    
    // Ir directo al reporte sin revisión
    localStorage.setItem('contractB', JSON.stringify(currentContractB));
    localStorage.setItem('agentVersion', 'v3');
    window.location.href = '/static/report/';
}

function startModule3() {
    if (!currentContractB) {
        alert('No hay datos para continuar al Code Generator');
        return;
    }
    localStorage.setItem('contractB', JSON.stringify(currentContractB));
    window.location.href = '/static/code/';
}

function showLoading(message) {
    document.getElementById('loadingMessage').textContent = message;
    document.getElementById('loadingModal').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingModal').classList.add('hidden');
}
