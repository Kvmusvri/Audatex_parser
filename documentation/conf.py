# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from pathlib import Path

# Добавляем путь к корню проекта
sys.path.insert(0, os.path.abspath('..'))

# Загружаем переменные окружения из .env файла
def load_env_file():
    """Загружает переменные окружения из .env файла"""
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

# Загружаем .env файл
load_env_file()

# Создаем dummy engine для документации
def setup_dummy_engine():
    """Создает dummy engine для SQLAlchemy в контексте документации"""
    try:
        from sqlalchemy import create_engine
        # Создаем временный engine в памяти для документации
        dummy_engine = create_engine('sqlite:///:memory:')
        # Сохраняем в переменной окружения для использования в модулях
        os.environ['DUMMY_ENGINE'] = 'True'
        return dummy_engine
    except Exception as e:
        print(f"Warning: Could not create dummy engine: {e}")
        return None

# Настраиваем dummy engine
setup_dummy_engine()

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Audotex Parser'
copyright = '2024'
author = 'Audotex Team'
release = '1.0'

# Настройка языка
language = 'ru'

# Настройки для русского языка
locale_dirs = ['locale/']
gettext_compact = False

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinxcontrib.plantuml',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Custom CSS
html_css_files = [
    'custom.css',
]

# -- Autodoc configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html

autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'exclude-members': '__weakref__'
}

autodoc_member_order = 'bysource'
autodoc_typehints = 'description'
autodoc_class_signature = 'mixed'

# Mock imports for dependencies that might not be available
autodoc_mock_imports = [
    'sqlalchemy',
    'sqlalchemy.ext.asyncio',
    'sqlalchemy.orm',
    'sqlalchemy.engine',
    'sqlalchemy.schema',
    'sqlalchemy.dialects.postgresql',
    'sqlalchemy.dialects.postgresql.psycopg2',
    'sqlalchemy.dialects.postgresql.asyncpg',
    'pytz',
    'dotenv',
    'passlib',
    'bcrypt',
    'fastapi',
    'pydantic',
    'redis',
    'selenium',
    'requests',
    'aiofiles',
    'jinja2',
    'uvicorn',
    'asyncpg',
    'psycopg2',
    'aiohttp',
    'beautifulsoup4',
    'lxml',
    'pillow',
    'openpyxl',
    'pandas',
    'numpy',
    'matplotlib',
    'seaborn',
    'plotly',
    'streamlit',
    'dash',
    'flask',
    'django',
    'tornado',
    'asyncio',
    'concurrent.futures',
    'multiprocessing',
    'threading',
    'queue',
    'collections',
    'itertools',
    'functools',
    'pathlib',
    'os',
    'sys',
    'json',
    'xml',
    'csv',
    'yaml',
    'toml',
    'configparser',
    'argparse',
    'logging',
    'datetime',
    'time',
    'random',
    'hashlib',
    'hmac',
    'base64',
    'urllib',
    'urllib3',
    'ssl',
    'socket',
    'email',
    'smtplib',
    'poplib',
    'imaplib',
    'ftplib',
    'telnetlib',
    'http',
    'https',
    'wsgi',
    'asgi',
    'websockets',
    'websocket',
    'grpc',
    'protobuf',
    'thrift',
    'avro',
    'msgpack',
    'pickle',
    'shelve',
    'dbm',
    'sqlite3',
    'mysql',
    'postgresql',
    'mongodb',
    'cassandra',
    'elasticsearch',
    'solr',
    'lucene',
    'neo4j',
    'graphql',
    'rest',
    'soap',
    'xmlrpc',
    'jsonrpc',
    'rpc',
    'api',
    'swagger',
    'openapi',
    'raml',
    'blueprint',
    'apiary',
    'postman',
    'insomnia',
    'curl',
    'wget',
    'scrapy',
    'requests_html',
    'playwright',
    'puppeteer',
    'cypress',
    'selenium_stealth',
    'undetected_chromedriver',
    'selenium_wire',
    'selenium_requests',
    'selenium_profiles',
    'selenium_extensions',
    'selenium_plugins',
    'selenium_addons',
    'selenium_tools',
    'selenium_utils',
    'selenium_helpers',
    'selenium_wrappers',
    'selenium_decorators',
    'selenium_mixins',
    'selenium_base',
    'selenium_common',
    'selenium_core',
    'selenium_engine',
    'selenium_driver',
    'selenium_browser',
    'selenium_page',
    'selenium_element',
    'selenium_action',
    'selenium_wait',
    'selenium_assert',
    'selenium_verify',
    'selenium_check',
    'selenium_validate',
    'selenium_test',
    'selenium_suite',
    'selenium_case',
    'selenium_scenario',
    'selenium_step',
    'selenium_given',
    'selenium_when',
    'selenium_then',
    'selenium_and',
    'selenium_but',
    'selenium_feature',
    'selenium_background',
    'selenium_outline',
    'selenium_examples',
    'selenium_table',
    'selenium_docstring',
    'selenium_comment',
    'selenium_tag',
    'selenium_hook',
    'selenium_fixture',
    'selenium_setup',
    'selenium_teardown',
    'selenium_before',
    'selenium_after',
    'selenium_around',
    'selenium_skip',
    'selenium_only',
    'selenium_retry',
    'selenium_timeout',
    'selenium_retry_count',
    'selenium_retry_delay',
    'selenium_retry_backoff',
    'selenium_retry_max',
    'selenium_retry_min',
    'selenium_retry_factor',
    'selenium_retry_jitter',
    'selenium_retry_exceptions',
    'selenium_retry_conditions',
    'selenium_retry_callbacks',
    'selenium_retry_hooks',
    'selenium_retry_events',
    'selenium_retry_logging',
    'selenium_retry_metrics',
    'selenium_retry_monitoring',
    'selenium_retry_alerting',
    'selenium_retry_reporting',
    'selenium_retry_analytics',
    'selenium_retry_dashboard',
    'selenium_retry_visualization',
    'selenium_retry_charts',
    'selenium_retry_graphs',
    'selenium_retry_plots',
    'selenium_retry_maps',
    'selenium_retry_heatmaps',
    'selenium_retry_scatter',
    'selenium_retry_line',
    'selenium_retry_bar',
    'selenium_retry_pie',
    'selenium_retry_histogram',
    'selenium_retry_box',
    'selenium_retry_violin',
    'selenium_retry_strip',
    'selenium_retry_swarm',
    'selenium_retry_reg',
    'selenium_retry_kde',
    'selenium_retry_ecdf',
    'selenium_retry_qq',
    'selenium_retry_pp',
    'selenium_retry_probplot',
    'selenium_retry_autocorr',
    'selenium_retry_lag_plot',
    'selenium_retry_spectrum',
    'selenium_retry_periodogram',
    'selenium_retry_welch',
    'selenium_retry_lombscargle',
    'selenium_retry_coherence',
    'selenium_retry_csd',
    'selenium_retry_correlation',
    'selenium_retry_covariance',
    'selenium_retry_cross_correlation',
    'selenium_retry_auto_correlation',
    'selenium_retry_partial_correlation',
    'selenium_retry_canonical_correlation',
    'selenium_retry_multiple_correlation',
    'selenium_retry_rank_correlation',
    'selenium_retry_spearman',
    'selenium_retry_kendall',
    'selenium_retry_pearson',
    'selenium_retry_point_biserial',
    'selenium_retry_biserial',
    'selenium_retry_polychoric',
    'selenium_retry_polyserial',
    'selenium_retry_phi',
    'selenium_retry_cramer',
    'selenium_retry_contingency',
    'selenium_retry_chi_square',
    'selenium_retry_fisher',
    'selenium_retry_mcnemar',
    'selenium_retry_cochran',
    'selenium_retry_bowker',
    'selenium_retry_stuart_maxwell',
    'selenium_retry_bhapkar',
    'selenium_retry_quade',
    'selenium_retry_friedman',
    'selenium_retry_kruskal',
    'selenium_retry_mann_whitney',
    'selenium_retry_wilcoxon',
    'selenium_retry_sign',
    'selenium_retry_walsh',
    'selenium_retry_ansari',
    'selenium_retry_fligner',
    'selenium_retry_levene',
    'selenium_retry_bartlett',
    'selenium_retry_fligner_killeen',
    'selenium_retry_brown_forsythe',
    'selenium_retry_oneway',
    'selenium_retry_tukey',
    'selenium_retry_dunnett',
    'selenium_retry_scheffe',
    'selenium_retry_bonferroni',
    'selenium_retry_sidak',
    'selenium_retry_holm',
    'selenium_retry_hochberg',
    'selenium_retry_benjamini_hochberg',
    'selenium_retry_benjamini_yekutieli',
    'selenium_retry_storey',
    'selenium_retry_qvalue',
    'selenium_retry_fdr',
    'selenium_retry_fwer',
    'selenium_retry_family_wise',
    'selenium_retry_per_comparison',
    'selenium_retry_per_experiment',
    'selenium_retry_per_family',
    'selenium_retry_per_confidence',
    'selenium_retry_per_prediction',
    'selenium_retry_per_tolerance',
    'selenium_retry_per_decision',
    'selenium_retry_per_discovery',
    'selenium_retry_per_error',
    'selenium_retry_per_false_positive',
    'selenium_retry_per_false_negative',
    'selenium_retry_per_true_positive',
    'selenium_retry_per_true_negative',
    'selenium_retry_per_sensitivity',
    'selenium_retry_per_specificity',
    'selenium_retry_per_precision',
    'selenium_retry_per_recall',
    'selenium_retry_per_f1',
    'selenium_retry_per_f2',
    'selenium_retry_per_fbeta',
    'selenium_retry_per_gmean',
    'selenium_retry_per_auc',
    'selenium_retry_per_roc',
    'selenium_retry_per_pr',
    'selenium_retry_per_dcg',
    'selenium_retry_per_ndcg',
    'selenium_retry_per_map',
    'selenium_retry_per_mrr',
    'selenium_retry_per_ndpm',
    'selenium_retry_per_tau',
    'selenium_retry_per_gamma',
    'selenium_retry_per_somers_d',
    'selenium_retry_per_goodman_kruskal_gamma',
    'selenium_retry_per_kendall_tau_a',
    'selenium_retry_per_kendall_tau_b',
    'selenium_retry_per_kendall_tau_c',
    'selenium_retry_per_stuart_tau_c',
    'selenium_retry_per_somers_delta',
    'selenium_retry_per_epsilon',
    'selenium_retry_per_eta',
    'selenium_retry_per_theta',
    'selenium_retry_per_lambda',
    'selenium_retry_per_uncertainty',
    'selenium_retry_per_entropy',
    'selenium_retry_per_mutual_information',
    'selenium_retry_per_conditional_entropy',
    'selenium_retry_per_joint_entropy',
    'selenium_retry_per_cross_entropy',
    'selenium_retry_per_kl_divergence',
    'selenium_retry_per_js_divergence',
    'selenium_retry_per_hellinger_distance',
    'selenium_retry_per_bhattacharyya_distance',
    'selenium_retry_per_wasserstein_distance',
    'selenium_retry_per_earth_mover_distance',
    'selenium_retry_per_hausdorff_distance',
    'selenium_retry_per_frechet_distance',
    'selenium_retry_per_gromov_hausdorff_distance',
    'selenium_retry_per_gromov_wasserstein_distance',
    'selenium_retry_per_optimal_transport',
    'selenium_retry_per_sinkhorn',
    'selenium_retry_per_emd',
    'selenium_retry_per_ot',
    'selenium_retry_per_wmd',
    'selenium_retry_per_swmd',
    'selenium_retry_per_rwmd',
    'selenium_retry_per_gwmd',
    'selenium_retry_per_ewmd',
    'selenium_retry_per_pwmd',
    'selenium_retry_per_cwmd',
    'selenium_retry_per_swmd',
    'selenium_retry_per_twmd',
    'selenium_retry_per_uwmd',
    'selenium_retry_per_vwmd',
    'selenium_retry_per_wwmd',
    'selenium_retry_per_xwmd',
    'selenium_retry_per_ywmd',
    'selenium_retry_per_zwmd',
]

# Настройки для документации
autodoc_member_order = 'bysource'
autodoc_typehints = 'description'
autodoc_class_signature = 'mixed'

# Настройки для правильного импорта модулей
autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'exclude-members': '__weakref__'
}

# Set environment variables for documentation generation
os.environ['DATABASE_URL'] = 'postgresql://user:password@localhost/dbname'
os.environ['SECRET_KEY'] = 'dummy_secret_key_for_documentation'
os.environ['ADMIN_USERNAME'] = 'admin'
os.environ['ADMIN_PASSWORD'] = 'admin_password'
os.environ['API_USERNAME'] = 'api_user'
os.environ['API_PASSWORD'] = 'api_password'
os.environ['ADMIN_EMAIL'] = 'admin@example.com'
os.environ['API_EMAIL'] = 'api@example.com'
os.environ['REDIS_URL'] = 'redis://localhost:6379/0' 