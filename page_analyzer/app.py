import os
from datetime import datetime
from urllib.parse import urlparse

import psycopg2
import validators
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")


@app.route("/")
def main():
    return render_template("index.html")


@app.post("/urls")
def check_urls():
    url = urlparse(request.form["url"])
    normalized_url = f"{url.scheme}://{url.hostname}"

    # Проверка длины URL
    if len(normalized_url) > 255:
        flash("URL слишком длинный (максимум 255 символов)")
        return redirect(url_for("main"))

    # Проверка валидности URL
    if not validators.url(normalized_url):
        flash("Некорректный URL-адрес")
        return redirect(url_for("main"))

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO urls (name) VALUES (%s) RETURNING id;", (normalized_url,)
        )
        url_item = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, created_at FROM urls WHERE name = %s", (normalized_url,)
        )
        url_item = cur.fetchone()
        cur.close()
        conn.close()
    return redirect(url_for("info_url", id=url_item[0]))


@app.get("/urls")
def get_urls():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("SELECT id, name, created_at FROM urls ORDER BY created_at DESC;")
    urls = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("urls.html", urls=urls)


@app.route("/urls/<int:id>")
def info_url(id):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute(f"SELECT id, name, created_at FROM urls WHERE id = %s;", (id,))
    url_item = cur.fetchone()

    cur.execute("""
        SELECT id, status_code, h1, title, description, created_at 
        FROM url_checks 
        WHERE url_id = %s
        ORDER BY created_at DESC;
    """, (id,))
    checks = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("url_id.html", url_item=url_item, checks=checks)

@app.route("/urls/<int:id>/checks", methods=["POST"])
def create_check(id):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO url_checks (url_id, created_at) VALUES (%s, %s) RETURNING url_id;",
        (id, datetime.now())
    )
    check_item = cur.fetchone()
    conn.commit()
    flash(f"Страница успешно проверена")
    cur.close()
    conn.close()
    return redirect(url_for('info_url', id=check_item[0]))
