from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
import psycopg2.extras
import re
import os
from typing import List, Dict, Any

app = FastAPI(title="SQL Learning API", description="一个用于学生学习SQL的只读API接口")

# 添加CORS支持，方便前端调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# 数据库连接配置
DB_CONFIG = {
    "dbname": os.environ.get("DB_NAME", "mydb"),
    "user": os.environ.get("DB_USER", "select_role"),
    "password": os.environ.get("DB_PASSWORD", "swufe_password"),
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432"),
}


# 请求模型
class SQLQuery(BaseModel):
    query: str


# 获取数据库连接
def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据库连接失败: {str(e)}")


# 检查SQL查询是否只包含SELECT语句
def is_select_query(query: str) -> bool:
    # 去除注释和多余空白
    clean_query = re.sub(r"--.*?(\n|$)", " ", query)
    clean_query = re.sub(r"/\*.*?\*/", " ", clean_query, flags=re.DOTALL)
    clean_query = clean_query.strip()

    # 检查是否以SELECT开头且不包含数据修改语句
    is_select = re.match(r"^\s*SELECT", clean_query, re.IGNORECASE) is not None
    has_modifying = (
        re.search(
            r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE)\b",
            clean_query,
            re.IGNORECASE,
        )
        is not None
    )

    return is_select and not has_modifying


# 获取数据库中所有表的信息
@app.get("/tables", response_model=List[Dict[str, Any]])
def get_tables():
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT 
                table_name, 
                (SELECT count(*) FROM information_schema.columns 
                 WHERE table_schema = 'public' AND table_name = t.table_name) as column_count
            FROM information_schema.tables t
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        return list(tables)
    finally:
        conn.close()


# 获取特定表的列信息
@app.get("/tables/{table_name}/columns", response_model=List[Dict[str, Any]])
def get_table_columns(table_name: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        """,
            (table_name,),
        )
        columns = cursor.fetchall()
        if not columns:
            raise HTTPException(status_code=404, detail=f"表 {table_name} 不存在")
        return list(columns)
    finally:
        conn.close()


# 执行SQL查询的API端点
@app.post("/execute-query", response_model=Dict[str, Any])
def execute_query(sql_query: SQLQuery):
    # 验证查询是否为SELECT语句
    if not is_select_query(sql_query.query):
        raise HTTPException(
            status_code=403, detail="只允许SELECT查询。禁止执行修改数据的操作。"
        )

    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 设置查询超时（5秒）
        cursor.execute("SET statement_timeout = 5000")

        try:
            import time

            start_time = time.time()
            cursor.execute(sql_query.query)
            end_time = time.time()
            execution_time = end_time - start_time
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"查询执行错误: {str(e)}")

        # 获取列名
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        # 获取结果
        rows = cursor.fetchall()

        # 限制返回的行数（防止过大结果）
        MAX_ROWS = 1000
        has_more = len(rows) > MAX_ROWS
        if has_more:
            rows = rows[:MAX_ROWS]

        return {
            "columns": columns,
            "rows": list(rows),
            "rowCount": len(rows),
            "hasMore": has_more,
            "executionTime": execution_time,
        }
    finally:
        conn.close()


# 获取数据库的一些统计信息
@app.get("/database-info", response_model=Dict[str, Any])
def get_database_info():
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT
                (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public') as table_count,
                pg_size_pretty(pg_database_size(current_database())) as database_size,
                version() as postgres_version
        """)
        info = cursor.fetchone()
        return dict(info)
    finally:
        conn.close()


# 健康检查端点
@app.get("/health")
def health_check():
    try:
        conn = get_db_connection()
        conn.close()
        return {"status": "healthy"}
    except Exception:
        raise HTTPException(status_code=503, detail="数据库连接失败")


# 示例查询端点，提供一些常用的SQL示例
@app.get("/example-queries", response_model=List[Dict[str, str]])
def get_example_queries():
    return [
        {"title": "简单SELECT查询", "query": "SELECT name FROM instructor"},
        {
            "title": "带WHERE条件的查询",
            "query": "SELECT name FROM instructor WHERE dept_name = 'Physics'",
        },
        {
            "title": "多表JOIN查询",
            "query": "SELECT DISTINCT T.name FROM instructor AS T, instructor AS S WHERE T.salary > S.salary AND S.dept_name = 'History'",
        },
    ]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8999)
