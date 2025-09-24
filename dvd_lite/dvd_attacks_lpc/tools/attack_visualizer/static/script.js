document.addEventListener('DOMContentLoaded', async () => {
    const selector = document.getElementById('attack-selector');
    const mainContent = document.getElementById('main-content');
    const detailsContainer = document.getElementById('attack-details-container');

    // API 엔드포인트에서 파일 목록을 비동기적으로 가져옵니다.
    try {
        const response = await fetch('/api/attacks');
        const attackFiles = await response.json();

        // 드롭다운 메뉴 채우기
        attackFiles.forEach(file => {
            const option = document.createElement('option');
            option.value = file;
            option.textContent = file.replace(/_attack_tree\.json/g, '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            selector.appendChild(option);
        });
    } catch (error) {
        console.error("Failed to fetch attack list:", error);
        selector.innerHTML = '<option value="">Error loading attacks</option>';
    }
    
    // 선택 변경 이벤트 리스너
    selector.addEventListener('change', (event) => {
        const fileName = event.target.value;
        if (fileName) {
            loadAttackData(fileName);
        } else {
            mainContent.classList.add('hidden');
        }
    });

    // JSON 데이터 로드 및 파싱 함수 (이제 API를 호출)
    async function loadAttackData(fileName) {
        try {
            const response = await fetch(`/api/attacks/${fileName}`);
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            const data = await response.json();
            renderAttackTree(data.attack_tree);
            mainContent.classList.remove('hidden');
        } catch (error) {
            console.error("Could not load attack data:", error);
            detailsContainer.innerHTML = `<p style="color:red; text-align:center;"><b>Error loading ${fileName}.</b><br>${error.message}</p>`;
            mainContent.classList.remove('hidden');
        }
    }

    // 데이터를 HTML로 렌더링하는 함수 (이전과 동일)
    function renderAttackTree(tree) {
        if (!tree) {
            detailsContainer.innerHTML = `<p style="color:red; text-align:center;"><b>Invalid JSON structure.</b><br>The file does not contain a valid 'attack_tree' object.</p>`;
            return;
        }

        detailsContainer.innerHTML = `
            <div class="attack-header">
                <h2>${tree.name || 'N/A'} <span class="info-item" style="font-size: 1rem; background: #333; display: inline-block; padding: 5px 10px;">${tree.attack_id || 'N/A'}</span></h2>
                <p class="description">${tree.description || 'No description available.'}</p>
                <div class="info-grid">
                    <div class="info-item"><strong>Risk Level</strong> <span>${tree.risk_level || 'N/A'}</span></div>
                    <div class="info-item"><strong>Attack Type</strong> <span>${tree.attack_type || 'N/A'}</span></div>
                    <div class="info-item"><strong>Difficulty</strong> <span>${tree.technical_difficulty || 'N/A'}</span></div>
                    <div class="info-item"><strong>Overall Score</strong> <span>${tree.overall_risk_score || 'N/A'}</span></div>
                </div>
            </div>

            ${tree.prerequisites ? `
            <div class="attack-section" id="prerequisites-section">
                 <h3>Prerequisites</h3>
                 <div class="info-grid">
                    ${Object.entries(tree.prerequisites).map(([key, value]) => `
                        <div class="info-item">
                            <strong>${key.replace(/_/g, ' ')}</strong>
                            <span>${Array.isArray(value) ? value.join(', ') : value}</span>
                        </div>
                    `).join('')}
                 </div>
            </div>` : ''}
            
            <div class="attack-section">
                <h3>MITRE ATT&CK Tactics</h3>
                <div class="tactic-grid">
                    ${tree.attack_phases ? Object.entries(tree.attack_phases).map(([tacticKey, tactic]) => `
                        <div class="tactic-card" data-tactic="${tacticKey.toLowerCase()}">
                            <h3>
                                ${tactic.tactic_name}
                                <span class="tactic-id">${tactic.tactic_id}</span>
                            </h3>
                            ${(tactic.techniques || []).map(tech => `
                                <div class="technique">
                                    <h4>${tech.technique_name}</h4>
                                    <span class="technique-id">${tech.technique_id}</span>
                                    <div class="technique-details">
                                        <p><strong>Description:</strong> ${tech.description || 'N/A'}</p>
                                        <p><strong>Implementation:</strong> <code>${tech.implementation || 'N/A'}</code></p>
                                        ${tech.target_messages ? `<p><strong>Target Messages:</strong></p><ul class="tag-list">${tech.target_messages.map(msg => `<li>${msg}</li>`).join('')}</ul>` : ''}
                                        ${tech.target_endpoints ? `<p><strong>Target Endpoints:</strong></p><ul class="tag-list">${tech.target_endpoints.map(ep => `<li>${ep}</li>`).join('')}</ul>` : ''}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `).join('') : '<p>No attack phases defined.</p>'}
                </div>
            </div>
        `;
    }
});