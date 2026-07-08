"""
페이지 라우트 — Jinja2 HTML 템플릿 렌더링 전용

각 라우트는 해당 화면 템플릿을 렌더링만 한다.
데이터는 클라이언트 JS가 /api/* 엔드포인트에서 fetch하여 바인딩.
"""
from flask import Blueprint, render_template

page_bp = Blueprint('page_bp', __name__)


@page_bp.route('/')
@page_bp.route('/setup')
def setup():
    """소스 연결 설정 화면 — [M1.F1]"""
    return render_template('setup.html')


@page_bp.route('/dashboard')
def dashboard():
    """통합 대시보드 화면 — [M1.F7]"""
    return render_template('dashboard.html')


@page_bp.route('/complexity')
def complexity():
    """복잡도 상세 화면 — [M1.F2]"""
    return render_template('complexity.html')


@page_bp.route('/search')
def search():
    """전역 검색 화면 — [M1.F3]"""
    return render_template('search.html')


@page_bp.route('/dependency')
def dependency():
    """의존성 흐름도 화면 — [M1.F4]"""
    return render_template('dependency.html')


@page_bp.route('/flow-graph')
def flow_graph():
    """호출 흐름도 화면 — [M1.F5]"""
    return render_template('flow.html')


@page_bp.route('/sp-flow')
def sp_flow():
    """SP 흐름도 화면 — [M1.F6]"""
    return render_template('sp_flow.html')
