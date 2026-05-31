const API_BASE = 'http://localhost:3000/api';

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

const contractB = JSON.parse(localStorage.getItem('contractB') || 'null');
const agentVersion = localStorage.getItem('agentVersion') || 'v1';

if (!contractB) {
    alert('No hay datos para generar el reporte. Redirigiendo...');
    window.location.href = '/static/scenarios/';
}

// Configurar canvas para firma
const canvas = document.getElementById('signaturePad');
const ctx = canvas.getContext('2d');
let isDrawing = false;
let hasSignature = false;

canvas.addEventListener('mousedown', startDrawing);
canvas.addEventListener('mousemove', draw);
canvas.addEventListener('mouseup', stopDrawing);
canvas.addEventListener('mouseout', stopDrawing);

// Touch events para móviles
canvas.addEventListener('touchstart', (e) => {
    e.preventDefault();
    const touch = e.touches[0];
    const mouseEvent = new MouseEvent('mousedown', {
        clientX: touch.clientX,
        clientY: touch.clientY
    });
    canvas.dispatchEvent(mouseEvent);
});

canvas.addEventListener('touchmove', (e) => {
    e.preventDefault();
    const touch = e.touches[0];
    const mouseEvent = new MouseEvent('mousemove', {
        clientX: touch.clientX,
        clientY: touch.clientY
    });
    canvas.dispatchEvent(mouseEvent);
});

canvas.addEventListener('touchend', (e) => {
    e.preventDefault();
    const mouseEvent = new MouseEvent('mouseup', {});
    canvas.dispatchEvent(mouseEvent);
});

function startDrawing(e) {
    isDrawing = true;
    hasSignature = true;
    const rect = canvas.getBoundingClientRect();
    ctx.beginPath();
    ctx.moveTo(e.clientX - rect.left, e.clientY - rect.top);
}

function draw(e) {
    if (!isDrawing) return;
    const rect = canvas.getBoundingClientRect();
    ctx.lineTo(e.clientX - rect.left, e.clientY - rect.top);
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.stroke();
}

function stopDrawing() {
    isDrawing = false;
}

function clearSignature() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    hasSignature = false;
}

// Mostrar información del analista QA
function displayQAReviewInfo() {
    const review = contractB.review;
    
    // Mostrar sección
    document.getElementById('qaReviewSection').classList.remove('hidden');
    
    // Mapear decisiones a texto legible
    const decisionText = {
        'approved': '✅ APROBADO - Los escenarios están listos para producción',
        'changes_requested': '⚠️ CAMBIOS SOLICITADOS - Se requieren ajustes antes de continuar',
        'rejected': '❌ RECHAZADO - Los escenarios no cumplen con los criterios de calidad'
    };
    
    const decisionColor = {
        'approved': 'text-green-700 bg-green-100 border-green-500',
        'changes_requested': 'text-yellow-700 bg-yellow-100 border-yellow-500',
        'rejected': 'text-red-700 bg-red-100 border-red-500'
    };
    
    const reviewDate = new Date(review.review_date).toLocaleDateString('es-ES', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
    
    let html = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
                <p class="text-sm text-gray-600 mb-1">Analista de QA:</p>
                <p class="text-lg font-bold text-gray-800">${review.reviewer_name}</p>
            </div>
            <div>
                <p class="text-sm text-gray-600 mb-1">Fecha de revisión:</p>
                <p class="text-lg font-semibold text-gray-800">${reviewDate}</p>
            </div>
        </div>
        
        <div class="mb-4 p-4 rounded-lg border-2 ${decisionColor[review.review_status]}">
            <p class="text-sm font-semibold mb-1">Decisión:</p>
            <p class="text-lg font-bold">${decisionText[review.review_status]}</p>
        </div>
        
        <div class="mb-4">
            <p class="text-sm font-semibold text-gray-700 mb-2">Estadísticas de revisión:</p>
            <div class="grid grid-cols-3 gap-3 text-center">
                <div class="bg-green-50 p-3 rounded">
                    <div class="text-2xl font-bold text-green-600">${review.scenarios_accepted || 0}</div>
                    <div class="text-xs text-gray-600">Aprobados</div>
                </div>
                <div class="bg-orange-50 p-3 rounded">
                    <div class="text-2xl font-bold text-orange-600">${review.scenarios_reclassified || 0}</div>
                    <div class="text-xs text-gray-600">Reclasificados</div>
                </div>
                <div class="bg-gray-50 p-3 rounded">
                    <div class="text-2xl font-bold text-gray-600">${review.scenarios_skipped || 0}</div>
                    <div class="text-xs text-gray-600">Omitidos</div>
                </div>
            </div>
        </div>
    `;
    
    if (review.review_notes) {
        html += `
            <div class="bg-white border-2 border-gray-300 rounded-lg p-4">
                <p class="text-sm font-semibold text-gray-700 mb-2">Comentarios del analista:</p>
                <p class="text-gray-800 italic">"${review.review_notes}"</p>
            </div>
        `;
    }
    
    document.getElementById('qaReviewInfo').innerHTML = html;
}

// Generar contenido del reporte
function generateReport() {
    // Fecha del reporte
    const now = new Date();
    document.getElementById('reportDate').textContent = 
        `Generado el ${now.toLocaleDateString('es-ES', { 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        })}`;
    
    // Mostrar información del analista QA si existe (V4)
    if (contractB.review) {
        displayQAReviewInfo();
    }
    
    // Resumen Ejecutivo
    const totalStories = contractB.features.length;
    const totalCriteria = contractB.coverage_matrix.length;
    const avgScenariosPerCriteria = (contractB.total_scenarios / totalCriteria).toFixed(1);
    
    // Analizar qué se prueba y qué no
    const whatIsTested = [];
    const whatIsNotTested = [];
    
    contractB.features.forEach(feature => {
        feature.scenarios.forEach(scenario => {
            whatIsTested.push({
                feature: feature.name,
                scenario: scenario.name,
                type: scenario.scenario_type,
                quality: scenario.quality_characteristic
            });
        });
    });
    
    // Identificar gaps de cobertura
    if (agentVersion === 'v3' || agentVersion === 'v4') {
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
        
        characteristics.forEach(char => {
            const count = contractB.coverage_by_characteristic[char] || 0;
            if (count === 0) {
                whatIsNotTested.push({
                    characteristic: translateQualityCharacteristic(char),
                    reason: 'No se generaron escenarios para esta característica de calidad'
                });
            } else if (count < 3) {
                whatIsNotTested.push({
                    characteristic: translateQualityCharacteristic(char),
                    reason: `Cobertura insuficiente (solo ${count} escenario${count > 1 ? 's' : ''})`
                });
            }
        });
    }
    
    // Identificar tipos de escenarios faltantes
    if (contractB.total_negative === 0) {
        whatIsNotTested.push({
            characteristic: 'Casos negativos',
            reason: 'No se generaron escenarios de prueba para casos de error o validaciones negativas'
        });
    }
    
    if (contractB.total_boundary === 0) {
        whatIsNotTested.push({
            characteristic: 'Valores límite',
            reason: 'No se generaron escenarios para probar límites y valores extremos'
        });
    }
    
    document.getElementById('executiveSummary').innerHTML = `
        <p class="text-gray-700 leading-relaxed mb-4">
            Se ha completado exitosamente la generación de escenarios de prueba utilizando el 
            <strong>Agente ${agentVersion.toUpperCase()}</strong> de QualityAI Test Architect.
        </p>
        <p class="text-gray-700 leading-relaxed mb-4">
            El sistema procesó <strong>${totalStories} historias de usuario</strong> con un total de 
            <strong>${totalCriteria} criterios de aceptación</strong>, generando 
            <strong>${contractB.total_scenarios} escenarios de prueba</strong> en formato Gherkin (BDD).
        </p>
        <p class="text-gray-700 leading-relaxed mb-4">
            Los escenarios generados cubren múltiples tipos de prueba incluyendo casos positivos, 
            negativos, valores límite y manejo de errores.
        </p>
        
        <div class="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="bg-green-50 border-l-4 border-green-500 p-4 rounded">
                <h4 class="font-bold text-green-800 mb-2">✅ Lo que SÍ se va a probar:</h4>
                <ul class="text-sm text-green-700 space-y-1">
                    <li>• ${contractB.total_positive} escenarios de casos positivos (happy path)</li>
                    <li>• ${contractB.total_negative} escenarios de casos negativos</li>
                    <li>• ${contractB.total_boundary} escenarios de valores límite</li>
                    <li>• ${totalCriteria} criterios de aceptación cubiertos</li>
                </ul>
            </div>
            
            <div class="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded">
                <h4 class="font-bold text-yellow-800 mb-2">⚠️ Gaps de cobertura identificados:</h4>
                ${whatIsNotTested.length > 0 ? `
                    <ul class="text-sm text-yellow-700 space-y-1">
                        ${whatIsNotTested.slice(0, 5).map(gap => `<li>• ${gap.characteristic}: ${gap.reason}</li>`).join('')}
                        ${whatIsNotTested.length > 5 ? `<li class="font-semibold">• Y ${whatIsNotTested.length - 5} gaps adicionales...</li>` : ''}
                    </ul>
                ` : '<p class="text-sm text-green-700">✅ No se identificaron gaps significativos de cobertura</p>'}
            </div>
        </div>
    `;
    
    // Métricas Clave
    document.getElementById('keyMetrics').innerHTML = `
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="bg-blue-50 p-4 rounded-lg text-center">
                <div class="text-3xl font-bold text-blue-600">${contractB.total_scenarios}</div>
                <div class="text-sm text-gray-600 mt-1">Escenarios Totales</div>
            </div>
            <div class="bg-green-50 p-4 rounded-lg text-center">
                <div class="text-3xl font-bold text-green-600">${contractB.total_positive || 0}</div>
                <div class="text-sm text-gray-600 mt-1">Casos Positivos</div>
            </div>
            <div class="bg-red-50 p-4 rounded-lg text-center">
                <div class="text-3xl font-bold text-red-600">${contractB.total_negative || 0}</div>
                <div class="text-sm text-gray-600 mt-1">Casos Negativos</div>
            </div>
            <div class="bg-orange-50 p-4 rounded-lg text-center">
                <div class="text-3xl font-bold text-orange-600">${contractB.total_boundary || 0}</div>
                <div class="text-sm text-gray-600 mt-1">Valores Límite</div>
            </div>
        </div>
        <div class="mt-6 grid grid-cols-2 gap-4">
            <div class="bg-purple-50 p-4 rounded-lg text-center">
                <div class="text-3xl font-bold text-purple-600">${totalStories}</div>
                <div class="text-sm text-gray-600 mt-1">Features Generadas</div>
            </div>
            <div class="bg-indigo-50 p-4 rounded-lg text-center">
                <div class="text-3xl font-bold text-indigo-600">${avgScenariosPerCriteria}</div>
                <div class="text-sm text-gray-600 mt-1">Escenarios por Criterio (promedio)</div>
            </div>
        </div>
    `;
    
    // Matriz de Cobertura (solo V3+)
    if ((agentVersion === 'v3' || agentVersion === 'v4') && contractB.coverage_by_characteristic) {
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
        
        let html = '<table class="w-full border-collapse"><thead><tr class="bg-gray-100">';
        html += '<th class="border p-3 text-left">Característica ISO 25010</th>';
        html += '<th class="border p-3 text-center">Escenarios</th>';
        html += '<th class="border p-3 text-center">Cobertura</th>';
        html += '</tr></thead><tbody>';
        
        characteristics.forEach(char => {
            const count = contractB.coverage_by_characteristic[char] || 0;
            const percentage = ((count / contractB.total_scenarios) * 100).toFixed(1);
            let status = count === 0 ? '❌ No cubierto' : count < 5 ? '⚠️ Ligero' : '✅ Robusto';
            
            html += `
                <tr>
                    <td class="border p-3 font-semibold">${translateQualityCharacteristic(char)}</td>
                    <td class="border p-3 text-center font-bold">${count}</td>
                    <td class="border p-3 text-center">${percentage}% ${status}</td>
                </tr>
            `;
        });
        
        html += `
            <tr class="bg-gray-100 font-bold">
                <td class="border p-3">TOTAL</td>
                <td class="border p-3 text-center">${contractB.total_scenarios}</td>
                <td class="border p-3 text-center">100%</td>
            </tr>
        </tbody></table>`;
        
        document.getElementById('coverageMatrix').innerHTML = html;
    }
    
    // Detalle de escenarios
    generateScenariosDetail();
    
    // Recomendaciones
    generateRecommendations();
}

function generateScenariosDetail() {
    let html = '<div class="space-y-4">';
    
    contractB.features.forEach((feature, idx) => {
        html += `
            <div class="border border-gray-300 rounded-lg overflow-hidden">
                <div class="bg-gradient-to-r from-indigo-600 to-purple-600 text-white p-4">
                    <h4 class="text-lg font-bold">${idx + 1}. ${feature.name}</h4>
                    <p class="text-sm text-purple-100 mt-1">${feature.description}</p>
                </div>
                <div class="bg-white p-4">
                    <table class="w-full text-sm">
                        <thead class="bg-gray-100">
                            <tr>
                                <th class="border p-2 text-left">Escenario</th>
                                <th class="border p-2 text-center">Tipo</th>
                                ${(agentVersion === 'v3' || agentVersion === 'v4') ? '<th class="border p-2 text-center">Característica</th>' : ''}
                                <th class="border p-2 text-left">Pasos</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        
        feature.scenarios.forEach((scenario, sIdx) => {
            const typeColors = {
                'positive': 'green',
                'negative': 'red',
                'boundary': 'orange',
                'edge_case': 'yellow',
                'error_handling': 'purple'
            };
            const color = typeColors[scenario.scenario_type] || 'gray';
            
            html += `
                <tr class="border-b">
                    <td class="border p-2 font-semibold">${sIdx + 1}. ${scenario.name}</td>
                    <td class="border p-2 text-center">
                        <span class="px-2 py-1 bg-${color}-100 text-${color}-700 rounded text-xs font-semibold">
                            ${translateScenarioType(scenario.scenario_type)}
                        </span>
                    </td>
                    ${(agentVersion === 'v3' || agentVersion === 'v4') ? `
                        <td class="border p-2 text-center text-xs font-semibold">
                            ${scenario.quality_characteristic ? translateQualityCharacteristic(scenario.quality_characteristic) : 'N/A'}
                        </td>
                    ` : ''}
                    <td class="border p-2">
                        <div class="font-mono text-xs space-y-1">
                            ${scenario.steps.map(step => `
                                <div><span class="font-bold text-${color}-600">${step.keyword}</span> ${step.text}</div>
                            `).join('')}
                        </div>
                    </td>
                </tr>
            `;
        });
        
        html += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    document.getElementById('scenariosDetail').innerHTML = html;
}

function generateRecommendations() {
    let recommendations = [];
    
    // Análisis basado en métricas
    const positiveRatio = (contractB.total_positive / contractB.total_scenarios) * 100;
    const negativeRatio = (contractB.total_negative / contractB.total_scenarios) * 100;
    
    if (positiveRatio > 70) {
        recommendations.push('✅ Excelente cobertura de casos positivos (happy path).');
    }
    
    if (negativeRatio < 20) {
        recommendations.push('⚠️ Considere agregar más escenarios de casos negativos para mejorar la robustez.');
    }
    
    if (contractB.total_boundary < 5) {
        recommendations.push('⚠️ Se recomienda agregar más casos de prueba de valores límite.');
    }
    
    // Recomendaciones por versión
    if (agentVersion === 'v1') {
        recommendations.push('💡 Considere usar el Agente V2 para aplicar heurísticas formales (EP, BVA, Decision Tables) y generar más escenarios por criterio.');
    } else if (agentVersion === 'v2') {
        recommendations.push('💡 Considere usar el Agente V3 para clasificar escenarios según ISO/IEC 25010 y obtener matriz de cobertura por características de calidad.');
    } else if (agentVersion === 'v3') {
        recommendations.push('💡 Considere usar el Agente V4 para incluir revisión humana (HITL) antes de aprobar los escenarios.');
    }
    
    recommendations.push('📋 Implemente los escenarios generados en su framework de testing (Cucumber, Behave, SpecFlow, etc.).');
    recommendations.push('🔄 Mantenga los escenarios sincronizados con los cambios en los requisitos.');
    
    document.getElementById('recommendations').innerHTML = `
        <ul class="space-y-2">
            ${recommendations.map(rec => `<li class="flex items-start"><span class="mr-2">•</span><span>${rec}</span></li>`).join('')}
        </ul>
    `;
}

function submitApproval() {
    const clientName = document.getElementById('clientName').value.trim();
    const clientPosition = document.getElementById('clientPosition').value.trim();
    const approved = document.getElementById('approvalCheckbox').checked;
    
    if (!clientName) {
        alert('Por favor ingrese el nombre del cliente');
        return;
    }
    
    if (!clientPosition) {
        alert('Por favor ingrese el cargo del cliente');
        return;
    }
    
    if (!hasSignature) {
        alert('Por favor firme el documento');
        return;
    }
    
    if (!approved) {
        alert('Por favor marque la casilla de aprobación');
        return;
    }
    
    // Guardar aprobación
    const approval = {
        clientName,
        clientPosition,
        signature: canvas.toDataURL(),
        timestamp: new Date().toISOString(),
        contractB: contractB,
        agentVersion: agentVersion
    };
    
    localStorage.setItem('approval', JSON.stringify(approval));
    
    // Mostrar confirmación
    const now = new Date();
    document.getElementById('approvalTimestamp').textContent = 
        `Firmado el ${now.toLocaleString('es-ES')} por ${clientName} (${clientPosition})`;
    document.getElementById('approvalConfirmation').classList.remove('hidden');
    
    // Deshabilitar edición
    document.getElementById('clientName').disabled = true;
    document.getElementById('clientPosition').disabled = true;
    document.getElementById('approvalCheckbox').disabled = true;
    canvas.style.pointerEvents = 'none';
    
    alert('✅ Reporte aprobado y firmado exitosamente');
}

function downloadPDF() {
    window.print();
}

// Generar reporte al cargar
generateReport();
