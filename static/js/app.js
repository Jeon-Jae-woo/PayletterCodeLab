/**
 * PGAnalyzer 공통 앱 JS
 * [GR-4.1] 4-State(Idle/Loading/Error/Empty) 전환 유틸리티
 * [PR-8] CDN 참조 없음 — 로컬 로드 전용
 */

/**
 * 컴포넌트의 4-State 표시 상태를 전환한다.
 * data-state 속성을 이용해 CSS 클래스 기반 상태 토글 수행.
 *
 * @param {string|HTMLElement} component - 상태를 전환할 컨테이너 선택자 또는 DOM 요소
 * @param {'idle'|'loading'|'error'|'empty'} state - 전환할 대상 상태
 */
function switchState(component, state) {
    const VALID_STATES = ['idle', 'loading', 'error', 'empty'];
    if (!VALID_STATES.includes(state)) {
        console.warn(`[switchState] 알 수 없는 상태: "${state}". 허용값: ${VALID_STATES.join(', ')}`);
        return;
    }

    const el = typeof component === 'string' ? document.querySelector(component) : component;
    if (!el) {
        console.warn(`[switchState] 대상 요소를 찾을 수 없습니다: ${component}`);
        return;
    }

    el.dataset.state = state;
}

/**
 * 현재 URL 경로를 기반으로 사이드바 활성 네비게이션 링크를 표시한다.
 */
function initActiveNavLink() {
    const currentPath = window.location.pathname;
    const navItems = document.querySelectorAll('.nav-item[data-route]');

    navItems.forEach(function (item) {
        const route = item.dataset.route;
        // 현재 경로에 route 식별자가 포함되면 active 처리
        const isActive = currentPath.includes(route) ||
            (route === 'setup' && (currentPath === '/' || currentPath === '/setup'));
        item.classList.toggle('active', isActive);
    });
}

// DOM 로드 완료 후 네비게이션 활성화
document.addEventListener('DOMContentLoaded', initActiveNavLink);
