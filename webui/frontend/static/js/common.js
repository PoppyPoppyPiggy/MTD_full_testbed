// MTD 드론 보안 테스트베드 공통 JavaScript

// WebSocket 연결
let socket = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    initializeWebSocket();
    setupEventListeners();
});

// WebSocket 초기화
function initializeWebSocket() {
    if (socket) {
        socket.disconnect();
    }
    
    socket = io();
    
    socket.on('connect', function() {
        console.log('WebSocket 연결됨');
        updateConnectionStatus(true);
        reconnectAttempts = 0;
    });
    
    socket.on('disconnect', function() {
        console.log('WebSocket 연결 해제됨');
        updateConnectionStatus(false);
        attemptReconnect();
    });
    
    socket.on('metrics_broadcast', function(data) {
        handleMetricsUpdate(data);
    });
    
    socket.on('dvd_broadcast', function(data) {
        handleDVDUpdate(data);
    });
    
    socket.on('ns3_update', function(data) {
        handleNS3Update(data);
    });
    
    socket.on('error', function(error) {
        console.error('WebSocket 오류:', error);
        showNotification('WebSocket 연결 오류: ' + error.message, 'error');
    });
}

// 재연결 시도
function attemptReconnect() {
    if (reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        console.log(`재연결 시도 ${reconnectAttempts}/${maxReconnectAttempts}`);
        
        setTimeout(() => {
            initializeWebSocket();
        }, 3000 * reconnectAttempts); // 점진적 지연
    } else {
        showNotification('WebSocket 재연결 실패. 페이지를 새로고침하세요.', 'error');
    }
}

// 연결 상태 업데이트
function updateConnectionStatus(connected) {
    const statusIcon = document.getElementById('connection-status');
    const statusText = document.getElementById('connection-text');
    
    if (statusIcon && statusText) {
        if (connected) {
            statusIcon.className = 'fas fa-circle text-success';
            statusText.textContent = '연결됨';
        } else {
            statusIcon.className = 'fas fa-circle text-danger';
            statusText.textContent = '연결 해제됨';
        }
    }
}

// 이벤트 리스너 설정
function setupEventListeners() {
    // 전역 오류 처리
    window.addEventListener('error', function(event) {
        console.error('전역 오류:', event.error);
    });
    
    // 네비게이션 하이라이트
    highlightCurrentPage();
}

// 현재 페이지 하이라이트
function highlightCurrentPage() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

// 메트릭 업데이트 처리
function handleMetricsUpdate(data) {
    // 하위 페이지에서 구현
    if (typeof updateMetricsDisplay === 'function') {
        updateMetricsDisplay(data);
    }
}

// DVD 업데이트 처리
function handleDVDUpdate(data) {
    // 하위 페이지에서 구현
    if (typeof updateDVDDisplay === 'function') {
        updateDVDDisplay(data);
    }
}

// NS-3 업데이트 처리
function handleNS3Update(data) {
    // 하위 페이지에서 구현
    if (typeof updateNS3Display === 'function') {
        updateNS3Display(data);
    }
}

// 알림 표시
function showNotification(message, type = 'info', duration = 5000) {
    const alertClass = {
        'success': 'alert-success',
        'error': 'alert-danger',
        'warning': 'alert-warning',
        'info': 'alert-info'
    }[type] || 'alert-info';
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 80px; right: 20px; z-index: 9999; min-width: 300px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    // 자동 제거
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, duration);
}

// 로딩 스피너 표시/숨김
function showSpinner(message = '로딩 중...') {
    const spinner = document.createElement('div');
    spinner.id = 'loading-spinner';
    spinner.className = 'spinner-overlay';
    spinner.innerHTML = `
        <div class="text-center text-white">
            <div class="spinner-border spinner-border-lg mb-3" role="status">
                <span class="visually-hidden">로딩 중...</span>
            </div>
            <div>${message}</div>
        </div>
    `;
    
    document.body.appendChild(spinner);
}

function hideSpinner() {
    const spinner = document.getElementById('loading-spinner');
    if (spinner) {
        spinner.remove();
    }
}

// API 호출 래퍼
async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API 호출 오류:', error);
        showNotification('API 호출 실패: ' + error.message, 'error');
        throw error;
    }
}

// 데이터 포맷팅 유틸리티
function formatNumber(num, decimals = 1) {
    if (isNaN(num)) return '0';
    return Number(num).toFixed(decimals);
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatDuration(seconds) {
    if (seconds < 60) return `${seconds}초`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}분 ${seconds % 60}초`;
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}시간 ${minutes}분`;
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('ko-KR');
}

// 차트 색상 팔레트
const chartColors = {
    primary: '#007bff',
    secondary: '#6c757d',
    success: '#28a745',
    danger: '#dc3545',
    warning: '#ffc107',
    info: '#17a2b8',
    light: '#f8f9fa',
    dark: '#343a40'
};

const chartColorPalette = [
    '#007bff', '#28a745', '#dc3545', '#ffc107', '#17a2b8',
    '#6f42c1', '#e83e8c', '#fd7e14', '#20c997', '#6c757d'
];

// 차트 기본 옵션
function getDefaultChartOptions(title = '') {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            title: {
                display: !!title,
                text: title,
                font: {
                    size: 16,
                    weight: 'bold'
                }
            },
            legend: {
                position: 'top'
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: {
                    color: 'rgba(0,0,0,0.1)'
                }
            },
            x: {
                grid: {
                    color: 'rgba(0,0,0,0.1)'
                }
            }
        }
    };
}

// 테이블 업데이트 유틸리티
function updateTable(tableId, data, columns) {
    const tbody = document.querySelector(`#${tableId} tbody`);
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    if (!data || data.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = `<td colspan="${columns.length}" class="text-center">데이터가 없습니다.</td>`;
        tbody.appendChild(row);
        return;
    }
    
    data.forEach(item => {
        const row = document.createElement('tr');
        row.innerHTML = columns.map(col => {
            let value = item[col.field];
            if (col.formatter) {
                value = col.formatter(value, item);
            }
            return `<td>${value}</td>`;
        }).join('');
        tbody.appendChild(row);
    });
}

// 상태 배지 생성
function createStatusBadge(status) {
    const badges = {
        'running': 'bg-success',
        'stopped': 'bg-danger',
        'completed': 'bg-success',
        'failed': 'bg-danger',
        'pending': 'bg-warning',
        'active': 'bg-primary'
    };
    
    const badgeClass = badges[status] || 'bg-secondary';
    return `<span class="badge ${badgeClass}">${status}</span>`;
}

// 진행률 바 생성
function createProgressBar(percentage, className = '') {
    const color = percentage < 30 ? 'danger' : percentage < 70 ? 'warning' : 'success';
    return `
        <div class="progress ${className}">
            <div class="progress-bar bg-${color}" style="width: ${percentage}%">
                ${percentage.toFixed(1)}%
            </div>
        </div>
    `;
}

// 디바운스 유틸리티
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 실시간 데이터 요청
function requestRealtimeData(type) {
    if (socket && socket.connected) {
        socket.emit('request_data', { type: type });
    }
}

// 페이지 가시성 API
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        // 페이지가 숨겨졌을 때 업데이트 빈도 감소
        console.log('페이지 숨김 - 업데이트 빈도 감소');
    } else {
        // 페이지가 다시 보일 때 즉시 데이터 갱신
        console.log('페이지 표시 - 데이터 즉시 갱신');
        if (typeof refreshPageData === 'function') {
            refreshPageData();
        }
    }
});

// 에러 바운더리
window.addEventListener('unhandledrejection', function(event) {
    console.error('처리되지 않은 Promise 거부:', event.reason);
    showNotification('예상치 못한 오류가 발생했습니다.', 'error');
});

// 전역 유틸리티 함수들을 window 객체에 등록
window.MTDUtils = {
    showNotification,
    showSpinner,
    hideSpinner,
    apiCall,
    formatNumber,
    formatBytes,
    formatDuration,
    formatTimestamp,
    chartColors,
    chartColorPalette,
    getDefaultChartOptions,
    updateTable,
    createStatusBadge,
    createProgressBar,
    debounce,
    requestRealtimeData
};
