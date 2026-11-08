#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地靶场：故意包含漏洞的演示应用（仅供本地 127.0.0.1 训练）
覆盖：SQLi / 反射型XSS / 命令注入 / 路径穿越 / 未授权IDOR / 越权
"""
import os
import sqlite3
import subprocess
from flask import Flask, request, g, jsonify

APP = Flask(__name__)
DB = "/tmp/pentest-demo/target.db"


def init_db():
    conn = sqlite3.connect(DB)
    conn.executescript("""
    DROP TABLE IF EXISTS users;
    CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT, email TEXT);
    INSERT INTO users VALUES(1,'admin','admin123','admin','admin@local');
    INSERT INTO users VALUES(2,'alice','alice123','user','alice@local');
    INSERT INTO users VALUES(3,'bob','bob123','user','bob@local');
    """)
    conn.commit()
    conn.close()


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
    return g.db


@APP.teardown_appcontext
def close_db(exc):
    d = g.pop("db", None)
    if d:
        d.close()


@APP.route("/")
def index():
    return """
    <h1>Local Vuln Lab</h1>
    <ul>
      <li>/login?u=admin&p=admin123</li>
      <li>/search?q=test</li>
      <li>/ping?host=127.0.0.1</li>
      <li>/read?file=readme.txt</li>
      <li>/api/user/1</li>
    </ul>
    """


# ---------- 漏洞1：SQL 注入（字符串拼接） ----------
@APP.route("/login")
def login():
    u = request.args.get("u", "")
    p = request.args.get("p", "")
    sql = f"SELECT id,username,role FROM users WHERE username='{u}' AND password='{p}'"
    try:
        rows = db().execute(sql).fetchall()
    except Exception as e:
        return jsonify(error=str(e), sql=sql), 500
    return jsonify(sql=sql, result=rows)


# ---------- 漏洞2：反射型 XSS（未转义输出） ----------
@APP.route("/search")
def search():
    q = request.args.get("q", "")
    return f"<html><body><h2>Results for: {q}</h2></body></html>"


# ---------- 漏洞3：命令注入 ----------
@APP.route("/ping")
def ping():
    host = request.args.get("host", "127.0.0.1")
    try:
        out = subprocess.check_output(
            f"ping -c 1 {host}", shell=True, stderr=subprocess.STDOUT, timeout=10
        ).decode(errors="replace")
    except subprocess.CalledProcessError as e:
        out = e.output.decode(errors="replace")
    return f"<pre>{out}</pre>"


# ---------- 漏洞4：路径穿越 ----------
@APP.route("/read")
def read():
    fn = request.args.get("file", "readme.txt")
    path = os.path.join("/tmp/pentest-demo/files", fn)
    try:
        with open(path, "r", errors="replace") as f:
            return f"<pre>{f.read()}</pre>"
    except Exception as e:
        return jsonify(error=str(e), path=path), 404


# ---------- 漏洞5：未授权 IDOR（无鉴权直读用户） ----------
@APP.route("/api/user/<int:uid>")
def api_user(uid):
    row = db().execute("SELECT id,username,role,email FROM users WHERE id=?", (uid,)).fetchone()
    if not row:
        return jsonify(error="not found"), 404
    return jsonify(id=row[0], username=row[1], role=row[2], email=row[3])


if __name__ == "__main__":
    os.makedirs("/tmp/pentest-demo/files", exist_ok=True)
    with open("/tmp/pentest-demo/files/readme.txt", "w") as f:
        f.write("local lab readme\n")
    init_db()
    APP.run(host="127.0.0.1", port=8899, debug=False)
