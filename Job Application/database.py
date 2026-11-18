"""One MySQL connection per Flask request, with explicit transaction boundaries."""
import os
import mysql.connector
from flask import g


def connection():
    if "db" not in g:
        g.db = mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "tracker_app"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "job_tracker"),
            charset="utf8mb4",
        )
    return g.db


def rows(sql, params=()):
    with connection().cursor(dictionary=True) as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def write(sql, params=()):
    db = connection()
    try:
        with db.cursor() as cursor:
            cursor.execute(sql, params)
            inserted = cursor.lastrowid
        db.commit()
        return inserted
    except mysql.connector.Error:
        db.rollback()
        raise


def close(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
