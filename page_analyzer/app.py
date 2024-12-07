import os
from datetime import datetime
from urllib.parse import urlparse

import psycopg2
import requests
import validators
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from requests import RequestException

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    " AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 YaBrowser/24.10.0.0 Safari/537.36"
}


@app.route("/")
def main():
    return render_template("index.html")


@app.errorhandler(422)
def handle_422_error(error):
    return render_template("index.html"), 422


@app.post("/urls")
def check_urls():
    url = urlparse(request.form["url"])
    normalized_url = f"{url.scheme}://{url.hostname}"

    if len(normalized_url) > 255:
        flash("URL слишком длинный " "(максимум 255 символов)", "danger")
        abort(422)

    if not validators.url(normalized_url):
        flash("Некорректный URL-адрес", "danger")
        abort(422)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO urls (name)" " VALUES (%s) RETURNING id;", (normalized_url,)
        )
        url_item = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        flash("Страница успешно добавлена", "info")
    except Exception:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, created_at" " FROM urls WHERE name = %s",
            (normalized_url,),
        )
        url_item = cur.fetchone()
        cur.close()
        conn.close()
        flash("Страница уже существует", "info")
    return redirect(url_for("info_url", id=url_item[0]))


@app.get("/urls")
def get_urls():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT u.id, u.name, u.created_at, uc.status_code
        FROM urls u
        LEFT JOIN url_checks uc ON u.id = uc.url_id
        AND uc.created_at = (SELECT MAX(created_at)
         FROM url_checks WHERE url_id = u.id)
        ORDER BY u.created_at DESC;
    """
    )
    urls = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("urls.html", urls=urls)


@app.route("/urls/<int:id>")
def info_url(id):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("SELECT id, name, created_at" " FROM urls WHERE id = %s;", (id,))
    url_item = cur.fetchone()

    cur.execute(
        """
        SELECT id, status_code, h1,
         title, description, created_at
        FROM url_checks
        WHERE url_id = %s
        ORDER BY created_at DESC;
        """,
        (id,),
    )
    checks = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("url_id.html", url_item=url_item, checks=checks)


@app.route("/urls/<int:id>/checks", methods=["POST"])
def create_check(id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT name FROM urls WHERE id = %s;", (id,))
        url_item = cur.fetchone()
        url = url_item[0]
        cur.close()
        conn.close()

        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        h1_tag = soup.find("h1")
        title_tag = soup.find("title")
        meta_description_tag = soup.find("meta", attrs={"name": "description"})

        h1_text = h1_tag.get_text() if h1_tag else None
        title_text = title_tag.get_text() if title_tag else None
        meta_description_text = (
            meta_description_tag["content"] if meta_description_tag else None
        )
        status_code = response.status_code

        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO url_checks (url_id, "
            "status_code, created_at, h1, title, description)"
            " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;",
            (
                id,
                status_code,
                datetime.now(),
                h1_text,
                title_text,
                meta_description_text,
            ),
        )
        cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        flash("Страница успешно проверена", "success")
    except RequestException:
        flash("Произошла ошибка при проверке", "danger")

    return redirect(url_for("info_url", id=id))
