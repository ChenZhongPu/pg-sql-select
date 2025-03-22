# PG-SQL-SELECT
用于数据库课程的只读SQL查询后端。

## 前置要求
1. 创建`mydb`数据库，并导入[数据](https://github.com/ChenZhongPu/db-swufe/tree/master/db-book)。
2. 创建`select_role`用户，并授权`mydb`数据库的`SELECT`权限，具体如下：

```sql
CREATE ROLE select_role WITH LOGIN PASSWORD 'swufe_password';
GRANT CONNECT ON DATABASE mydb TO select_role;
GRANT USAGE ON SCHEMA public TO select_role;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO select_role;
```
## 启动服务
推荐使用[uv](https://docs.astral.sh/uv/)：

```bash
$ uv sync
# windows: source .venv\Scripts\activate
$ source .venv/bin/activate
$ uv run main.py
```