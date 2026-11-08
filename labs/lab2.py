#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
进阶本地靶场：SSRF / SSTI / 反序列化 / JWT 伪造 / XXE / 路径规范化绕过
仅监听 127.0.0.1:8898
"""
import base64
import hashlib
import hmac
import json
import os
import pickle
import pickletools
import re
import subprocess
import urllib.request
from flask import Flask, request, jsonify, Response

APP = Flask(__name__)

SECRET = "lab-secret-do-not-use-in-prod"


# ---------- 0. 首页 ----------
@APP.route("/")
def index():
    return """
    <h1>Advanced Local Lab</h1>
    <ul>
      <li>/jwt/issue?user=guest</li>
      <li>/jwt/admin  (需 role=admin)</li>
      <li>/ssrf?url=http://127.0.0.1:8898/internal</li>
      <li>/internal  (meta)</li>
      <li>/ssti?name={{7*7}}</li>
      <li>/pickle  (POST base64)</li>
      <li>/xxe  (POST xml)</li>
      <li>/upload  (POST file)</li>
    </ul>
    """


# ---------- 1. JWT：弱密钥 + 无 alg 校验 ----------
def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64u_dec(s):
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def make_jwt(payload):
    header = {"alg": "HS256", "typ": "JWT"}
    h = b64u(json.dumps(header, separators=(",", ":")).encode())
    p = b64u(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{b64u(sig)}"


@APP.route("/jwt/issue")
def jwt_issue():
    user = request.args.get("user", "guest")
    role = "admin" if user == "admin" else "guest"
    return jsonify(token=make_jwt({"user": user, "role": role}))


@APP.route("/jwt/admin")
def jwt_admin():
    """漏洞：同时接受 none 算法，且密钥可爆破"""
    tok = request.args.get("token", "")
    parts = tok.split(".")
    if len(parts) != 3:
        return jsonify(error="bad token"), 400
    h, p, s = parts
    try:
        header = json.loads(b64u_dec(h))
    except Exception:
        return jsonify(error="bad header"), 400

    # 漏洞 1：alg=none 直接信任
    if header.get("alg") == "none":
        try:
            payload = json.loads(b64u_dec(p))
        except Exception:
            return jsonify(error="bad payload"), 400
        ok = payload.get("role") == "admin"
        return jsonify(alg="none", payload=payload, admin=ok), (200 if ok else 403)

    # 漏洞 2：弱密钥 HS256
    expect = b64u(hmac.new(SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(s, expect):
        return jsonify(error="bad signature"), 403
    try:
        payload = json.loads(b64u_dec(p))
    except Exception:
        return jsonify(error="bad payload"), 400
    ok = payload.get("role") == "admin"
    return jsonify(alg="HS256", payload=payload, admin=ok), (200 if ok else 403)


# ---------- 2. SSRF ----------

@APP.route("/.dsh-verify-<path:tok>.txt")
def dsh_verify(tok):
    """归属校验文件的模拟端点：证明控制权"""
    return tok.replace("", ""), 200, {"Content-Type": "text/plain"}


@APP.route("/internal")
def internal():
    return jsonify(secret="INTERNAL_ONLY_FLAG{ssrf_reached_metadata}", path="/internal")


@APP.route("/ssrf")
def ssrf():
    """漏洞：无白名单直取 URL"""
    url = request.args.get("url", "")
    if not url:
        return jsonify(error="url required"), 400
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            body = r.read(4096)
        return Response(body, mimetype=r.headers.get_content_type())
    except Exception as e:
        return jsonify(error=str(e), url=url), 502


# ---------- 3. SSTI ----------
@APP.route("/ssti")
def ssti():
    """漏洞：把用户输入拼进模板源码"""
    name = request.args.get("name", "world")
    tpl = f"<h2>Hello {name}!</h2>"
    # 极简模板求值：只支持 {{ expr }}
    def ev(m):
        expr = m.group(1)
        try:
            return str(eval(expr, {"__builtins__": {"__import__": __import__}}, {}))
        except Exception as e:
            return f"[err {e}]"
    return re.sub(r"\{\{(.+?)\}\}", ev, tpl)


# ---------- 4. 反序列化 ----------
@APP.route("/pickle", methods=["POST"])
def unpickle():
    """漏洞：直接 pickle.loads 用户数据"""
    raw = request.get_data()
    try:
        data = base64.b64decode(raw)
        obj = pickle.loads(data)
        return jsonify(ok=True, result=str(obj)[:500])
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 400


# ---------- 5. XXE ----------
@APP.route("/xxe", methods=["POST"])
def xxe():
    """漏洞：lxml 默认会解析外部实体（XXE）"""
    from lxml import etree
    raw = request.get_data()
    try:
        parser = etree.XMLParser(load_dtd=True, resolve_entities=True, no_network=False)
        tree = etree.fromstring(raw, parser)
        return jsonify(ok=True, text=tree.text, result=etree.tostring(tree, encoding="unicode")[:800])
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 400


# ---------- 6. 路径规范化绕过 ----------
@APP.route("/files/<path:name>")
def files(name):
    """漏洞：先检查再拼接，可用 ../ 或 URL 编码绕过"""
    base = "/tmp/pentest-lab2/files"
    if ".." in name:
        return jsonify(error="blocked by naive check"), 403
    # 漏洞：解码后再拼，%2e%2e 能过第一道检查
    from urllib.parse import unquote
    real = os.path.join(base, unquote(name))
    try:
        with open(real, "r", errors="replace") as f:
            return Response(f.read(), mimetype="text/plain")
    except Exception as e:
        return jsonify(error=str(e), tried=real), 404


if __name__ == "__main__":
    os.makedirs("/tmp/pentest-lab2/files", exist_ok=True)
    with open("/tmp/pentest-lab2/files/hello.txt", "w") as f:
        f.write("lab file ok\n")
    APP.run(host="127.0.0.1", port=8898, debug=False)
