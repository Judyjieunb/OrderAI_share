"""
Snowflake 연결 클라이언트

- lazy init: 첫 호출 시 연결, 이후 재사용
- credential 없으면 None 반환 (config_loader가 에러 처리)
- .env에서 SNOWFLAKE_* 환경변수 로드
"""

import os
import sys

import pandas as pd

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_BASE_DIR, ".env"))
except ImportError:
    pass

_conn = None


def _get_credentials():
    """환경변수에서 Snowflake credential 반환 (없으면 None)

    인증 방식:
    - SNOWFLAKE_AUTH=externalbrowser → SSO 브라우저 인증 (password 불필요)
    - 기본 → password 인증
    """
    account = os.environ.get("SNOWFLAKE_ACCOUNT", "").strip()
    user = os.environ.get("SNOWFLAKE_USER", "").strip()
    password = os.environ.get("SNOWFLAKE_PASSWORD", "").strip()
    warehouse = os.environ.get("SNOWFLAKE_WAREHOUSE", "").strip()
    role = os.environ.get("SNOWFLAKE_ROLE", "").strip()
    auth = os.environ.get("SNOWFLAKE_AUTH", "").strip().lower()

    use_sso = auth == "externalbrowser"

    if not all([account, user, warehouse]):
        return None
    if not use_sso and not password:
        return None

    creds = {
        "account": account,
        "user": user,
        "warehouse": warehouse,
        "role": role,
        "database": "FNF",
        "schema": "PRCS",
    }

    if use_sso:
        creds["authenticator"] = "externalbrowser"
    else:
        creds["password"] = password

    return creds


def get_connection():
    """Snowflake 커넥션 반환 (lazy init, 재사용)"""
    global _conn

    # 기존 커넥션 유효하면 재사용
    if _conn is not None:
        try:
            _conn.cursor().execute("SELECT 1")
            return _conn
        except Exception:
            _conn = None

    creds = _get_credentials()
    if not creds:
        print("[Snowflake] credential 미설정 (SNOWFLAKE_ACCOUNT 등)")
        return None

    try:
        import snowflake.connector
        _conn = snowflake.connector.connect(**creds)
        print(f"[Snowflake] 연결 성공 (warehouse={creds['warehouse']})")
        return _conn
    except Exception as e:
        print(f"[Snowflake] 연결 실패: {e}")
        return None


def execute_query(sql):
    """SQL 실행 → DataFrame 반환 (실패 시 None)

    Args:
        sql: 실행할 SQL 문자열

    Returns:
        pd.DataFrame or None
    """
    conn = get_connection()
    if conn is None:
        return None

    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            df = pd.read_sql(sql, conn)
        print(f"[Snowflake] 쿼리 완료: {len(df):,}행")
        return df
    except Exception as e:
        print(f"[Snowflake] 쿼리 실패: {e}")
        return None


def close():
    """커넥션 종료"""
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None
