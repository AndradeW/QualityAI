const API_BASE = 'http://localhost:3000/api';

let currentContractC = null;
let reviewChanges = [];

function getApiHeaders(additional = {}) {
    const apiKey = localStorage.getItem('groq_api_key');
    return { 'Content-Type': 'application/json', 'X-Groq-API-Key': apiKey || '', ...additional };
}

// ============================================================
// TAB NAVIGATION
// ============================================================
function switchTab(tab) {
    ['code', 'quality', 'review'].forEach(t => {
        document.getElementById(`tab-${t}`).className = 'flex-1 px-6 py-4 text-center text-sm font-medium text-gray-500 hover:bg-gray-50 transition';
        document.getElementById(`content-${t}`).classList.add('hidden');
    });
    document.getElementById(`tab-${tab}`).className = 'tab-active flex-1 px-6 py-4 text-center text-sm font-medium hover:bg-gray-50 transition';
    document.getElementById(`content-${tab}`).classList.remove('hidden');
}

function showStatus(msg, show) {
    const bar = document.getElementById('statusBar');
    if (show) {
        document.getElementById('statusMessage').textContent = msg;
        bar.classList.remove('hidden');
    } else {
        bar.classList.add('hidden');
    }
}

// ============================================================
// GENERATE CODE
// ============================================================
async function generateCode() {
    const contractB = JSON.parse(localStorage.getItem('contractB'));
    if (!contractB) {
        alert('No hay Contract B disponible. Primero genera escenarios en el Modulo 2.');
        window.location.href = '/static/scenarios/';
        return;
    }

    document.getElementById('generateBtn').disabled = true;
    showStatus('Generando codigo... Esto puede tomar 30-60 segundos.', true);

    try {
        const res = await fetch(`${API_BASE}/m3/generate-code`, {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify({ contract_b: contractB })
        });
        const data = await res.json();

        if (!data.success) {
            throw new Error(data.error || 'Error al generar codigo');
        }

        currentContractC = data.contract_c;
        localStorage.setItem('contractC', JSON.stringify(currentContractC));

        displayCodeResults(currentContractC);
        displayQualityResults(currentContractC);
        setupReviewPanel(currentContractC);

        document.getElementById('noCodePlaceholder').classList.add('hidden');
        document.getElementById('codeResults').classList.remove('hidden');
        switchTab('code');

    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        document.getElementById('generateBtn').disabled = false;
        showStatus('', false);
    }
}

// ============================================================
// TAB 1: CODE RESULTS
// ============================================================
function displayCodeResults(contractC) {
    const container = document.getElementById('codeResults');
    let html = '';

    // Summary
    html += `
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div class="bg-indigo-50 rounded-lg p-4 text-center">
                <div class="text-3xl font-bold text-indigo-600">${contractC.total_modules}</div>
                <div class="text-sm text-gray-600">Modulos generados</div>
            </div>
            <div class="bg-green-50 rounded-lg p-4 text-center">
                <div class="text-3xl font-bold text-green-600">${contractC.total_tests}</div>
                <div class="text-sm text-gray-600">Tests generados</div>
            </div>
            <div class="bg-purple-50 rounded-lg p-4 text-center">
                <div class="text-sm font-mono text-purple-600 truncate">${contractC.pipeline_run_id}</div>
                <div class="text-sm text-gray-600">Pipeline Run ID</div>
            </div>
            <div class="bg-gray-50 rounded-lg p-4 text-center">
                <div class="text-sm font-semibold text-gray-700">v${contractC.agent_version}</div>
                <div class="text-sm text-gray-600">Version</div>
            </div>
        </div>`;

    // Modules
    html += '<h3 class="text-lg font-bold text-gray-800 mb-4"><i class="fas fa-file-code text-indigo-600 mr-2"></i>Modulos de Codigo</h3>';
    contractC.generated_code.forEach((mod, i) => {
        html += `
            <div class="mb-4 border border-gray-200 rounded-lg overflow-hidden">
                <div class="bg-gray-800 text-white px-4 py-2 flex justify-between items-center">
                    <span class="font-mono font-bold">${mod.filename}</span>
                    <span class="text-xs text-gray-400">${mod.user_story_id}</span>
                </div>
                <div class="p-0">
                    <pre>${escapeHtml(mod.source_code)}</pre>
                </div>
                <div class="bg-gray-50 px-4 py-2 text-sm text-gray-600">${mod.description}</div>
            </div>`;
    });

    // Tests
    html += '<h3 class="text-lg font-bold text-gray-800 mt-6 mb-4"><i class="fas fa-vial text-green-600 mr-2"></i>Tests Generados</h3>';
    contractC.generated_tests.forEach((test, i) => {
        html += `
            <div class="mb-4 border border-gray-200 rounded-lg overflow-hidden">
                <div class="bg-gray-800 text-white px-4 py-2 flex justify-between items-center">
                    <span class="font-mono font-bold">${test.test_name}</span>
                    <span class="text-xs text-gray-400">target: ${test.target_module} | scenarios: ${(test.scenario_ids || []).join(', ') || 'none'}</span>
                </div>
                <div class="p-0">
                    <pre>${escapeHtml(test.source_code)}</pre>
                </div>
            </div>`;
    });

    container.innerHTML = html;
}

// ============================================================
// TAB 2: QUALITY RESULTS
// ============================================================
function displayQualityResults(contractC) {
    const container = document.getElementById('qualityResults');
    const qr = contractC.quality_report;
    const tm = contractC.traceability_matrix;
    const cr = contractC.coverage_report;

    if (!qr && !tm && !cr) {
        document.getElementById('noQualityPlaceholder').classList.remove('hidden');
        return;
    }

    document.getElementById('noQualityPlaceholder').classList.add('hidden');
    container.classList.remove('hidden');

    let html = '';

    // Quality Report
    if (qr) {
        html += `
            <div class="bg-white border border-gray-200 rounded-lg p-6">
                <h3 class="text-lg font-bold text-gray-800 mb-4"><i class="fas fa-microchip text-indigo-600 mr-2"></i>Quality Report</h3>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div class="bg-blue-50 rounded p-3 text-center">
                        <div class="text-2xl font-bold text-blue-700">${qr.functions_exceeding_threshold}</div>
                        <div class="text-xs text-gray-600">Funciones sobre umbral</div>
                    </div>
                    <div class="bg-green-50 rounded p-3 text-center">
                        <div class="text-2xl font-bold text-green-700">${qr.maintainability_index || 'N/A'}</div>
                        <div class="text-xs text-gray-600">Maintainability Index</div>
                    </div>
                    <div class="bg-red-50 rounded p-3 text-center">
                        <div class="text-2xl font-bold text-red-700">${qr.security_findings.length}</div>
                        <div class="text-xs text-gray-600">Hallazgos de seguridad</div>
                    </div>
                    <div class="bg-purple-50 rounded p-3 text-center">
                        <div class="text-2xl font-bold text-purple-700">${qr.function_metrics.length}</div>
                        <div class="text-xs text-gray-600">Funciones medidas</div>
                    </div>
                </div>`;

        // Function metrics table
        if (qr.function_metrics.length > 0) {
            html += `
                <h4 class="font-bold text-gray-700 mb-2">Metricas por Funcion</h4>
                <div class="overflow-x-auto mb-4">
                    <table class="w-full text-sm border-collapse">
                        <thead>
                            <tr class="bg-gray-100">
                                <th class="border p-2 text-left">Funcion</th>
                                <th class="border p-2 text-left">Modulo</th>
                                <th class="border p-2 text-center">CC</th>
                                <th class="border p-2 text-center">CogC</th>
                                <th class="border p-2 text-center">Banda</th>
                                <th class="border p-2 text-center">Umbral</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${qr.function_metrics.map(fm => `
                                <tr class="${fm.exceeds_threshold ? 'bg-red-50' : 'bg-white'}">
                                    <td class="border p-2 font-mono">${fm.function_name}</td>
                                    <td class="border p-2">${fm.module}</td>
                                    <td class="border p-2 text-center">${fm.cyclomatic_complexity}</td>
                                    <td class="border p-2 text-center">${fm.cognitive_complexity}</td>
                                    <td class="border p-2 text-center"><span class="px-2 py-1 rounded text-xs font-bold ${fm.cc_band === 'A' || fm.cc_band === 'B' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">${fm.cc_band}</span></td>
                                    <td class="border p-2 text-center">${fm.exceeds_threshold ? '<span class="badge-fail px-2 py-1 rounded text-xs font-bold">EXCEDE</span>' : '<span class="badge-pass px-2 py-1 rounded text-xs font-bold">OK</span>'}</td>
                                </tr>`).join('')}
                        </tbody>
                    </table>
                </div>`;
        }

        // Security findings
        if (qr.security_findings.length > 0) {
            html += `
                <h4 class="font-bold text-gray-700 mb-2">Hallazgos de Seguridad (Bandit)</h4>
                <div class="overflow-x-auto mb-4">
                    <table class="w-full text-sm border-collapse">
                        <thead>
                            <tr class="bg-gray-100">
                                <th class="border p-2">ID</th>
                                <th class="border p-2">Severidad</th>
                                <th class="border p-2">Modulo</th>
                                <th class="border p-2">Linea</th>
                                <th class="border p-2 text-left">Descripcion</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${qr.security_findings.map(sf => `
                                <tr>
                                    <td class="border p-2 font-mono text-xs">${sf.test_id}</td>
                                    <td class="border p-2 text-center"><span class="px-2 py-1 rounded text-xs font-bold ${sf.severity === 'high' ? 'bg-red-100 text-red-800' : sf.severity === 'medium' ? 'bg-yellow-100 text-yellow-800' : 'bg-blue-100 text-blue-800'}">${sf.severity.toUpperCase()}</span></td>
                                    <td class="border p-2">${sf.module}</td>
                                    <td class="border p-2 text-center">${sf.line_number}</td>
                                    <td class="border p-2">${sf.description}</td>
                                </tr>`).join('')}
                        </tbody>
                    </table>
                </div>`;
        } else {
            html += `<p class="text-sm text-green-600 mb-4"><i class="fas fa-check-circle mr-1"></i>Sin hallazgos de seguridad</p>`;
        }

        // ISO 25010
        if (qr.iso_25010_coverage && qr.iso_25010_coverage.length > 0) {
            html += `
                <h4 class="font-bold text-gray-700 mb-2">Cobertura ISO 25010</h4>
                <div class="overflow-x-auto">
                    <table class="w-full text-sm border-collapse">
                        <thead>
                            <tr class="bg-gray-100">
                                <th class="border p-2 text-left">Caracteristica</th>
                                <th class="border p-2 text-center">Estado</th>
                                <th class="border p-2 text-left">Veredicto</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${qr.iso_25010_coverage.map(iso => `
                                <tr>
                                    <td class="border p-2 font-medium">${iso.characteristic.replace(/_/g, ' ')}</td>
                                    <td class="border p-2 text-center">
                                        <span class="px-2 py-1 rounded text-xs font-bold ${iso.status === 'measured' ? 'bg-green-100 text-green-800' : iso.status === 'requires_human_judgment' ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-600'}">${iso.status.replace(/_/g, ' ')}</span>
                                    </td>
                                    <td class="border p-2 text-xs">${iso.verdict || '-'}</td>
                                </tr>`).join('')}
                        </tbody>
                    </table>
                </div>`;
        }
        html += '</div>';
    }

    // Traceability Matrix
    if (tm) {
        const cmmiBadge = tm.cmmi_l3_compliant
            ? '<span class="badge-pass px-3 py-1 rounded font-bold"><i class="fas fa-check mr-1"></i>CMMI L3 COMPLIANT</span>'
            : '<span class="badge-fail px-3 py-1 rounded font-bold"><i class="fas fa-times mr-1"></i>NO COMPLIANT</span>';

        html += `
            <div class="bg-white border border-gray-200 rounded-lg p-6 mt-6">
                <h3 class="text-lg font-bold text-gray-800 mb-4"><i class="fas fa-project-diagram text-indigo-600 mr-2"></i>Matriz de Trazabilidad CMMI L3</h3>
                <div class="flex items-center space-x-4 mb-4">${cmmiBadge}</div>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div class="bg-green-50 rounded p-3 text-center">
                        <div class="text-2xl font-bold text-green-700">${tm.requirements_coverage_pct.toFixed(1)}%</div>
                        <div class="text-xs text-gray-600">Cobertura de requisitos</div>
                    </div>
                    <div class="bg-blue-50 rounded p-3 text-center">
                        <div class="text-2xl font-bold text-blue-700">${tm.tests_justified_pct.toFixed(1)}%</div>
                        <div class="text-xs text-gray-600">Tests justificados</div>
                    </div>
                    <div class="${tm.orphan_scenarios.length > 0 ? 'bg-red-50' : 'bg-green-50'} rounded p-3 text-center">
                        <div class="text-2xl font-bold ${tm.orphan_scenarios.length > 0 ? 'text-red-700' : 'text-green-700'}">${tm.orphan_scenarios.length}</div>
                        <div class="text-xs text-gray-600">Huerfanos forward</div>
                    </div>
                    <div class="${tm.orphan_tests.length > 0 ? 'bg-red-50' : 'bg-green-50'} rounded p-3 text-center">
                        <div class="text-2xl font-bold ${tm.orphan_tests.length > 0 ? 'text-red-700' : 'text-green-700'}">${tm.orphan_tests.length}</div>
                        <div class="text-xs text-gray-600">Huerfanos backward</div>
                    </div>
                </div>`;

        // Forward traceability
        html += `<h4 class="font-bold text-gray-700 mb-2">Forward: Escenarios -> Tests</h4>
            <div class="overflow-x-auto mb-4">
                <table class="w-full text-sm border-collapse">
                    <thead><tr class="bg-gray-100"><th class="border p-2">Escenario</th><th class="border p-2">Estado</th><th class="border p-2">Tests que cubren</th></tr></thead>
                    <tbody>${tm.forward.map(fw => `
                        <tr class="${fw.status === 'orphan_forward' ? 'bg-red-50' : 'bg-white'}">
                            <td class="border p-2 font-mono text-xs">${fw.scenario_id}: ${fw.scenario_name}</td>
                            <td class="border p-2 text-center"><span class="px-2 py-1 rounded text-xs font-bold ${fw.status === 'covered' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">${fw.status.replace(/_/g, ' ')}</span></td>
                            <td class="border p-2">${fw.covering_tests.join(', ') || '-'}</td>
                        </tr>`).join('')}
                    </tbody>
                </table>
            </div>`;

        // Backward traceability
        html += `<h4 class="font-bold text-gray-700 mb-2">Backward: Tests -> Escenarios</h4>
            <div class="overflow-x-auto">
                <table class="w-full text-sm border-collapse">
                    <thead><tr class="bg-gray-100"><th class="border p-2">Test</th><th class="border p-2">Estado</th><th class="border p-2">Escenarios que justifican</th></tr></thead>
                    <tbody>${tm.backward.map(bw => `
                        <tr class="${bw.status === 'orphan_backward' ? 'bg-red-50' : 'bg-white'}">
                            <td class="border p-2 font-mono">${bw.test_name}</td>
                            <td class="border p-2 text-center"><span class="px-2 py-1 rounded text-xs font-bold ${bw.status === 'covered' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">${bw.status.replace(/_/g, ' ')}</span></td>
                            <td class="border p-2">${bw.justifying_scenarios.join(', ') || '-'}</td>
                        </tr>`).join('')}
                    </tbody>
                </table>
            </div>`;
        html += '</div>';
    }

    // Coverage Report
    if (cr) {
        html += `
            <div class="bg-white border border-gray-200 rounded-lg p-6 mt-6">
                <h3 class="text-lg font-bold text-gray-800 mb-4"><i class="fas fa-percentage text-indigo-600 mr-2"></i>Coverage Report</h3>
                <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
                    <div class="${cr.meets_threshold ? 'bg-green-50' : 'bg-red-50'} rounded p-3 text-center">
                        <div class="text-2xl font-bold ${cr.meets_threshold ? 'text-green-700' : 'text-red-700'}">${cr.branch_coverage_pct.toFixed(1)}%</div>
                        <div class="text-xs text-gray-600">Branch coverage</div>
                    </div>
                    <div class="bg-blue-50 rounded p-3 text-center">
                        <div class="text-2xl font-bold text-blue-700">${cr.line_coverage_pct.toFixed(1)}%</div>
                        <div class="text-xs text-gray-600">Line coverage</div>
                    </div>
                    <div class="${cr.meets_threshold ? 'bg-green-50' : 'bg-red-50'} rounded p-3 text-center">
                        <div class="text-sm font-bold ${cr.meets_threshold ? 'text-green-700' : 'text-red-700'}">${cr.meets_threshold ? 'CUMPLE (>=80%)' : 'NO CUMPLE (<80%)'}</div>
                        <div class="text-xs text-gray-600">Umbral de calidad</div>
                    </div>
                </div>`;
        if (cr.uncovered_modules && cr.uncovered_modules.length > 0) {
            html += `<p class="text-sm text-red-600"><i class="fas fa-exclamation-triangle mr-1"></i>Modulos por debajo del umbral: ${cr.uncovered_modules.join(', ')}</p>`;
        } else {
            html += `<p class="text-sm text-green-600"><i class="fas fa-check-circle mr-1"></i>Todos los modulos cumplen el umbral de coverage</p>`;
        }
        html += '</div>';
    }

    container.innerHTML = html;
}

// ============================================================
// TAB 3: HITL REVIEW
// ============================================================
function setupReviewPanel(contractC) {
    const container = document.getElementById('reviewResults');
    document.getElementById('noReviewPlaceholder').classList.add('hidden');
    container.classList.remove('hidden');

    reviewChanges = [];

    let html = `
        <div class="bg-yellow-50 border-l-4 border-yellow-500 p-4 mb-6">
            <p class="text-sm text-yellow-800"><i class="fas fa-info-circle mr-2"></i>
            Las metricas miden lo objetivo (CC, CogC, cobertura, trazabilidad). Tu como desarrollador senior
            juzgas lo que ninguna herramienta mide: naming, design intent, code smells subjetivos y
            Functional Appropriateness.</p>
        </div>

        <div class="mb-6">
            <label class="block text-sm font-semibold text-gray-700 mb-2">Tu identificador (formato: nombre.apellido)</label>
            <input type="text" id="reviewerName" placeholder="ej: juan.perez" class="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:border-indigo-500 focus:outline-none">
        </div>`;

    // Module review
    contractC.generated_code.forEach((mod, i) => {
        html += `
            <div class="mb-6 border border-gray-200 rounded-lg overflow-hidden">
                <div class="bg-gray-800 text-white px-4 py-2 font-mono font-bold flex justify-between items-center">
                    <span>${mod.filename}</span>
                    <span id="review-status-${i}" class="text-xs px-2 py-1 rounded bg-gray-600 text-gray-300">Pendiente</span>
                </div>
                <div class="p-0">
                    <pre class="max-h-60 overflow-y-auto">${escapeHtml(mod.source_code)}</pre>
                </div>
                <div class="bg-gray-50 px-4 py-3">
                    <div class="flex items-center space-x-2 mb-2">
                        <input type="text" id="review-note-${i}" placeholder="Observacion (naming, smells, design intent...)" class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:border-indigo-500 focus:outline-none">
                        <button onclick="flagSmell(${i})" class="px-4 py-2 bg-orange-500 text-white rounded-lg text-sm font-semibold hover:bg-orange-600 transition"><i class="fas fa-flag mr-1"></i>Marcar smell</button>
                        <button onclick="acceptModule(${i})" class="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-semibold hover:bg-green-700 transition"><i class="fas fa-check mr-1"></i>Aceptar modulo</button>
                    </div>
                </div>
            </div>`;
    });

    // Final verdict
    html += `
        <div class="bg-white border border-gray-200 rounded-lg p-6 mt-6">
            <h3 class="text-lg font-bold text-gray-800 mb-4"><i class="fas fa-gavel mr-2"></i>Veredicto Final</h3>
            <div class="mb-4">
                <label class="block text-sm font-semibold text-gray-700 mb-2">Comentario sobre el Contract C completo</label>
                <textarea id="finalFeedback" rows="3" class="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:border-indigo-500 focus:outline-none"></textarea>
            </div>
            <div class="flex space-x-4">
                <button onclick="submitVerdict('approve')" class="flex-1 px-6 py-4 bg-gradient-to-r from-green-600 to-teal-600 text-white rounded-lg font-bold text-lg hover:from-green-700 hover:to-teal-700 transition shadow-lg"><i class="fas fa-check-circle mr-2"></i>Aprobar</button>
                <button onclick="submitVerdict('reject')" class="flex-1 px-6 py-4 bg-gradient-to-r from-red-600 to-pink-600 text-white rounded-lg font-bold text-lg hover:from-red-700 hover:to-pink-700 transition shadow-lg"><i class="fas fa-times-circle mr-2"></i>Rechazar</button>
                <button onclick="submitVerdict('changes_requested')" class="flex-1 px-6 py-4 bg-gradient-to-r from-yellow-500 to-orange-600 text-white rounded-lg font-bold text-lg hover:from-yellow-600 hover:to-orange-700 transition shadow-lg"><i class="fas fa-edit mr-2"></i>Solicitar cambios</button>
            </div>
        </div>

        <!-- Change history -->
        <div class="bg-white border border-gray-200 rounded-lg p-6 mt-6">
            <h3 class="text-lg font-bold text-gray-800 mb-4"><i class="fas fa-history mr-2"></i>Historial de revision (change_history)</h3>
            <div id="changeHistoryContainer" class="space-y-2">
                <p class="text-sm text-gray-500 text-center py-4">Aun no hay acciones registradas</p>
            </div>
        </div>`;

    container.innerHTML = html;
}

function flagSmell(index) {
    const note = document.getElementById(`review-note-${index}`).value.trim();
    if (!note) {
        alert('Escribe una observacion antes de marcar el smell.');
        return;
    }
    reviewChanges.push({
        target: currentContractC.generated_code[index].filename,
        action: 'smell_flagged',
        notes: note
    });
    document.getElementById(`review-status-${index}`).textContent = 'Smell marcado';
    document.getElementById(`review-status-${index}`).className = 'text-xs px-2 py-1 rounded bg-orange-600 text-white';
    document.getElementById(`review-note-${index}`).value = '';
    updateChangeHistory();
}

function acceptModule(index) {
    reviewChanges.push({
        target: currentContractC.generated_code[index].filename,
        action: 'comment_added',
        notes: 'Modulo aceptado por el revisor'
    });
    document.getElementById(`review-status-${index}`).textContent = 'Aceptado';
    document.getElementById(`review-status-${index}`).className = 'text-xs px-2 py-1 rounded bg-green-600 text-white';
    updateChangeHistory();
}

function updateChangeHistory() {
    const container = document.getElementById('changeHistoryContainer');
    if (reviewChanges.length === 0) {
        container.innerHTML = '<p class="text-sm text-gray-500 text-center py-4">Aun no hay acciones registradas</p>';
        return;
    }
    container.innerHTML = reviewChanges.map((c, i) => `
        <div class="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg">
            <span class="text-xs font-mono text-gray-500 mt-1">${i + 1}.</span>
            <div class="flex-1">
                <p class="text-sm"><span class="font-semibold">${c.target || 'Contract C'}</span>
                <span class="px-2 py-0.5 rounded text-xs font-bold ${c.action === 'smell_flagged' ? 'bg-orange-100 text-orange-800' : 'bg-green-100 text-green-800'} ml-2">${c.action.replace(/_/g, ' ')}</span></p>
                <p class="text-xs text-gray-600 mt-1">${c.notes}</p>
            </div>
        </div>`).join('');
}

async function submitVerdict(action) {
    const reviewer = document.getElementById('reviewerName').value.trim();
    const feedback = document.getElementById('finalFeedback').value.trim();

    if (!reviewer) {
        alert('Ingresa tu identificador (nombre.apellido) antes de emitir el veredicto.');
        return;
    }
    if (!currentContractC) {
        alert('No hay Contract C para revisar. Genera el codigo primero.');
        return;
    }

    // Inyectar reviewer en cada entrada del change_history
    for (const entry of reviewChanges) {
        if (!entry.reviewer) entry.reviewer = reviewer;
    }

    try {
        const res = await fetch(`${API_BASE}/m3/review`, {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify({
                contract_c: currentContractC,
                reviewer: reviewer,
                action: action,
                change_history: reviewChanges,
                feedback: feedback || null
            })
        });
        const data = await res.json();

        if (!data.success) {
            throw new Error(data.error || 'Error al guardar revision');
        }

        currentContractC = data.contract_c;
        localStorage.setItem('contractC', JSON.stringify(currentContractC));

        alert('Veredicto aplicado: ' + data.message);
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// ============================================================
// UTILITIES
// ============================================================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================
// INIT
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    const saved = localStorage.getItem('contractC');
    if (saved) {
        try {
            currentContractC = JSON.parse(saved);
            displayCodeResults(currentContractC);
            displayQualityResults(currentContractC);
            setupReviewPanel(currentContractC);
            document.getElementById('noCodePlaceholder').classList.add('hidden');
            document.getElementById('codeResults').classList.remove('hidden');
        } catch (e) {
            console.warn('Contract C previo invalido, se generara uno nuevo');
        }
    }
});
