const contractB = JSON.parse(localStorage.getItem('contractB') || 'null');
const agentVersion = localStorage.getItem('agentVersion') || 'v4';

if (!contractB) {
    alert('No hay datos para revisar. Redirigiendo...');
    window.location.href = '/static/scenarios/';
}

let currentScenarioIndex = 0;
let allScenarios = [];
let reviewChanges = [];

// Aplanar todos los escenarios
contractB.features.forEach(feature => {
    feature.scenarios.forEach(scenario => {
        allScenarios.push({
            feature: feature.name,
            featureDesc: feature.description,
            scenario: scenario
        });
    });
});

function loadScenario(index) {
    if (index >= allScenarios.length) {
        showFinalDecision();
        return;
    }

    currentScenarioIndex = index;
    const item = allScenarios[index];
    const scenario = item.scenario;

    // Actualizar progreso
    document.getElementById('progress').textContent = `${index + 1} / ${allScenarios.length}`;
    const percentage = ((index + 1) / allScenarios.length) * 100;
    document.getElementById('progressBar').style.width = `${percentage}%`;

    // Mostrar escenario
    const typeColors = {
        'positive': 'green',
        'negative': 'red',
        'boundary': 'orange',
        'edge_case': 'yellow',
        'error_handling': 'purple'
    };
    const color = typeColors[scenario.scenario_type] || 'gray';

    document.getElementById('scenarioCard').innerHTML = `
        <div class="mb-4">
            <h3 class="text-sm text-gray-500 mb-1">Feature</h3>
            <h2 class="text-2xl font-bold text-gray-800">${item.feature}</h2>
            <p class="text-gray-600 mt-1">${item.featureDesc}</p>
        </div>

        <div class="border-t pt-4">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-xl font-bold text-gray-800">${scenario.name}</h3>
                <div class="flex gap-2">
                    <span class="px-3 py-1 bg-${color}-100 text-${color}-700 rounded-full text-sm font-semibold">
                        ${scenario.scenario_type}
                    </span>
                    ${scenario.quality_characteristic ? `
                        <span class="px-3 py-1 bg-indigo-100 text-indigo-700 rounded-full text-sm font-semibold">
                            ${scenario.quality_characteristic.replace(/_/g, ' ')}
                        </span>
                    ` : ''}
                </div>
            </div>

            <div class="bg-gray-50 p-6 rounded-lg font-mono text-sm space-y-2">
                ${scenario.steps.map(step => `
                    <div class="text-gray-800">
                        <span class="font-bold text-${color}-600">${step.keyword}</span> ${step.text}
                    </div>
                `).join('')}
            </div>

            ${scenario.tags && scenario.tags.length > 0 ? `
                <div class="mt-4 flex flex-wrap gap-2">
                    ${scenario.tags.map(tag => `<span class="px-2 py-1 bg-gray-200 text-gray-700 rounded text-xs">${tag}</span>`).join('')}
                </div>
            ` : ''}
        </div>
    `;

    // Cargar valores actuales en los selectores
    document.getElementById('qualityChar').value = scenario.quality_characteristic || 'functional_suitability';
    document.getElementById('scenarioType').value = scenario.scenario_type;
    document.getElementById('reviewNotes').value = '';
}

function acceptScenario() {
    const notes = document.getElementById('reviewNotes').value.trim();
    
    reviewChanges.push({
        scenario_index: currentScenarioIndex,
        scenario_name: allScenarios[currentScenarioIndex].scenario.name,
        action: 'accepted',
        notes: notes || 'Aceptado sin cambios',
        timestamp: new Date().toISOString()
    });

    loadScenario(currentScenarioIndex + 1);
}

function reclassifyScenario() {
    const newQuality = document.getElementById('qualityChar').value;
    const newType = document.getElementById('scenarioType').value;
    const notes = document.getElementById('reviewNotes').value.trim();

    if (!notes) {
        alert('Por favor justifica por qué estás reclasificando este escenario');
        return;
    }

    const scenario = allScenarios[currentScenarioIndex].scenario;
    const oldQuality = scenario.quality_characteristic || 'functional_suitability';
    const oldType = scenario.scenario_type;

    // Aplicar cambios
    scenario.quality_characteristic = newQuality;
    scenario.scenario_type = newType;

    reviewChanges.push({
        scenario_index: currentScenarioIndex,
        scenario_name: scenario.name,
        action: 'reclassified',
        old_quality_characteristic: oldQuality,
        new_quality_characteristic: newQuality,
        old_scenario_type: oldType,
        new_scenario_type: newType,
        notes: notes,
        timestamp: new Date().toISOString()
    });

    loadScenario(currentScenarioIndex + 1);
}

function skipScenario() {
    reviewChanges.push({
        scenario_index: currentScenarioIndex,
        scenario_name: allScenarios[currentScenarioIndex].scenario.name,
        action: 'skipped',
        notes: 'Escenario omitido en la revisión',
        timestamp: new Date().toISOString()
    });

    loadScenario(currentScenarioIndex + 1);
}

function showFinalDecision() {
    // Ocultar barra de progreso
    document.getElementById('progressSection').classList.add('hidden');
    
    // Ocultar tarjeta de escenario actual
    document.getElementById('scenarioCard').classList.add('hidden');
    
    // Ocultar sección de ajuste de clasificación
    document.getElementById('adjustmentSection').classList.add('hidden');
    
    // Mostrar decisión final
    document.getElementById('finalDecision').classList.remove('hidden');
    
    // Scroll al inicio
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function submitReview() {
    const reviewerName = document.getElementById('reviewerName').value.trim();
    const decision = document.getElementById('reviewDecision').value;
    const finalNotes = document.getElementById('finalNotes').value.trim();

    if (!reviewerName) {
        alert('Por favor ingresa tu nombre');
        return;
    }

    // Recalcular matriz de cobertura si hubo reclasificaciones
    if (reviewChanges.some(c => c.action === 'reclassified')) {
        recalculateCoverageMatrix();
    }

    // Agregar metadata de revisión
    contractB.review = {
        reviewer_name: reviewerName,
        review_status: decision,
        review_date: new Date().toISOString(),
        review_notes: finalNotes,
        change_history: reviewChanges,
        total_scenarios_reviewed: allScenarios.length,
        scenarios_accepted: reviewChanges.filter(c => c.action === 'accepted').length,
        scenarios_reclassified: reviewChanges.filter(c => c.action === 'reclassified').length,
        scenarios_skipped: reviewChanges.filter(c => c.action === 'skipped').length
    };

    // Guardar y continuar al reporte
    localStorage.setItem('contractB', JSON.stringify(contractB));
    localStorage.setItem('agentVersion', 'v4');
    window.location.href = '/static/report/';
}

function recalculateCoverageMatrix() {
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

    const coverage = {};
    characteristics.forEach(char => coverage[char] = 0);

    allScenarios.forEach(item => {
        const qc = item.scenario.quality_characteristic || 'functional_suitability';
        coverage[qc] = (coverage[qc] || 0) + 1;
    });

    contractB.coverage_by_characteristic = coverage;
}

// Iniciar revisión
loadScenario(0);
