import json
import os
import re
import secrets
from datetime import date
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)
from mysql.connector import IntegrityError

import database as db
from records import COLUMNS, FIELDS, LABELS, SELECT, SINGULAR, STAGES

load_dotenv()
app = Flask(__name__)
app.config.update(SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_hex(32),
                  MAX_CONTENT_LENGTH=256 * 1024, SESSION_COOKIE_SAMESITE="Lax")
app.teardown_appcontext(db.close)
app.jinja_env.filters["from_json"] = json.loads


def skills(text):
    unique = {}
    for token in re.split(r"[,\n]", text):
        token = " ".join(token.split())
        if token:
            unique.setdefault(token.casefold(), token)
    return list(unique.values())


def match_jobs(jobs, supplied):
    known = {s.casefold() for s in skills(supplied)}
    ranked = []
    for job in jobs:
        required = skills(", ".join(json.loads(job["requirements"] or "[]")))
        matched = [s for s in required if s.casefold() in known]
        missing = [s for s in required if s.casefold() not in known]
        fraction = len(matched) / len(required) if required else None
        ranked.append(dict(job, matched=matched, missing=missing, total=len(required),
                           fraction=fraction, percent=round(100 * fraction) if required else None))
    return sorted(ranked, key=lambda j: (-(j["fraction"] if j["total"] else -1),
                                          j["job_title"].casefold(), j["job_id"]))


@app.before_request
def protect_forms():
    if request.method == "POST" and (
        not session.get("token") or request.form.get("token") != session["token"]
    ):
        abort(400, "Your form expired. Reload the page and try again.")
    if "token" not in session:
        session["token"] = secrets.token_hex(24)


@app.context_processor
def shared():
    return dict(singular=SINGULAR, labels=LABELS, columns=COLUMNS, stages=STAGES)


def primary(kind):
    if kind not in FIELDS:
        abort(404)
    return SINGULAR[kind] + "_id"


def record(kind, rid, lock=False):
    key = primary(kind)
    sql = SELECT[kind] + f" WHERE {kind}.{key}=%s"
    rows = db.rows(sql + (" FOR UPDATE" if lock else ""), (rid,))
    if not rows:
        abort(404)
    return rows[0]


@app.get("/")
def dashboard():
    counts = {k: db.rows(f"SELECT COUNT(*) AS n FROM {k}")[0]["n"] for k in FIELDS}
    pipeline = {r["status"]: r["n"] for r in db.rows(
        "SELECT status, COUNT(*) AS n FROM applications GROUP BY status")}
    recent = db.rows(SELECT["applications"] + " ORDER BY application_date DESC, application_id DESC LIMIT 5")
    return render_template("dashboard.html", counts=counts, pipeline=pipeline, recent=recent)


@app.get("/<kind>/")
def listing(kind):
    key = primary(kind)
    rows = db.rows(SELECT[kind] + f" ORDER BY {kind}.{key} DESC")
    return render_template(f"{kind}.html", kind=kind, rows=rows)


@app.get("/<kind>/<int:rid>")
def detail(kind, rid):
    row = record(kind, rid)
    return render_template("detail.html", kind=kind, row=row, rid=rid, fields=FIELDS[kind])


def options_for(fields):
    options = {}
    for f in fields:
        if f.kind == "companies":
            options[f.key] = db.rows("SELECT company_id AS id, company_name AS label FROM companies ORDER BY label, id")
        elif f.kind == "jobs":
            options[f.key] = db.rows("""SELECT job_id AS id, CONCAT(job_title, ' / ', company_name) AS label
                                        FROM jobs JOIN companies USING(company_id) ORDER BY label, id""")
    return options


def reject_nonstandard_number(value):
    raise ValueError(f"Invalid JSON number: {value}")


def validate(fields, form, options):
    values, errors = {}, {}
    for f in fields:
        raw = form.get(f.key, "").strip()
        value = raw or None
        try:
            if f.required and not raw:
                raise ValueError("This field is required.")
            if f.limit and len(raw) > f.limit:
                raise ValueError(f"Use at most {f.limit} characters.")
            if f.kind == "textarea" and len(raw.encode()) > 65535:
                raise ValueError("Shorten the notes to fit the database.")
            if f.kind == "skills":
                value = json.dumps(skills(raw))
            elif f.kind == "checkbox":
                value = int(raw == "on")
            elif f.kind == "json" and raw:
                try:
                    parsed = json.loads(raw, parse_constant=reject_nonstandard_number)
                    if not isinstance(parsed, dict):
                        raise ValueError
                    value = json.dumps(parsed, allow_nan=False, ensure_ascii=False)
                    value.encode("utf-8")
                except (ValueError, RecursionError):
                    raise ValueError('Enter a JSON object, for example {"location": "Zoom"}.')
            elif raw and f.kind == "number":
                if not raw.isascii() or not raw.isdecimal() or len(raw) > 10 or int(raw) > 2147483647:
                    raise ValueError("Enter a whole number from 0 to 2147483647.")
                value = int(raw)
            elif raw and f.kind == "date":
                try:
                    value = date.fromisoformat(raw)
                    if value.year < 1000:
                        raise ValueError
                except ValueError:
                    raise ValueError("Enter a valid date with a year of 1000 or later.")
            elif raw and f.kind == "url":
                url = urlsplit(raw)
                if url.scheme not in ("http", "https") or not url.hostname or any(c.isspace() for c in raw):
                    raise ValueError("Enter a full http or https URL.")
            elif raw and f.kind == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", raw):
                raise ValueError("Enter a valid email address.")
            elif raw and f.choices and raw not in f.choices:
                raise ValueError("Choose one of the listed options.")
            elif f.key in options and raw not in {str(o["id"]) for o in options[f.key]}:
                raise ValueError("Select an existing record.")
        except ValueError as exc:
            errors[f.key] = str(exc)
        values[f.key] = value
    low, high = values.get("salary_min"), values.get("salary_max")
    if isinstance(low, int) and isinstance(high, int) and high < low:
        errors["salary_max"] = "Maximum salary must be at least the minimum salary."
    return values, errors


@app.route("/<kind>/new", methods=["GET", "POST"])
@app.route("/<kind>/<int:rid>/edit", methods=["GET", "POST"])
def form(kind, rid=None):
    key = primary(kind)
    fields = FIELDS[kind]
    values = record(kind, rid, request.method == "POST") if rid is not None else {}
    if request.method == "GET":
        if values.get("requirements"):
            values["requirements"] = ", ".join(json.loads(values["requirements"]))
        if rid is None and kind == "applications":
            values.update(status="Applied", application_date=date.today())
    options = options_for(fields)
    errors = {}
    if request.method == "POST":
        values = request.form.to_dict()
        cleaned, errors = validate(fields, values, options)
        if not errors:
            try:
                if rid is None:
                    names = ", ".join(cleaned)
                    placeholders = ", ".join(["%s"] * len(cleaned))
                    rid = db.write(f"INSERT INTO {kind} ({names}) VALUES ({placeholders})", tuple(cleaned.values()))
                else:
                    assignments = ", ".join(f"{name}=%s" for name in cleaned)
                    db.write(f"UPDATE {kind} SET {assignments} WHERE {key}=%s", (*cleaned.values(), rid))
                flash("Record saved.")
                return redirect(url_for("detail", kind=kind, rid=rid), code=303)
            except IntegrityError:
                errors["form"] = "A linked record changed. Reload the form and select it again."
    return render_template("form.html", kind=kind, fields=fields, values=values, options=options,
                           errors=errors, rid=rid), 422 if errors else 200


@app.route("/<kind>/<int:rid>/delete", methods=["GET", "POST"])
def remove(kind, rid):
    row = record(kind, rid, request.method == "POST")
    error = None
    if request.method == "POST":
        try:
            db.write(f"DELETE FROM {kind} WHERE {primary(kind)}=%s", (rid,))
            flash("Record deleted.")
            return redirect(url_for("listing", kind=kind), code=303)
        except IntegrityError:
            error = "Other records link here. Edit or delete those records first."
    return render_template("delete.html", kind=kind, row=row, rid=rid, error=error), 409 if error else 200


@app.get("/job-match")
def job_match():
    supplied = request.args.get("skills", "")
    submitted = "skills" in request.args
    ranked = match_jobs(db.rows(SELECT["jobs"]), supplied) if skills(supplied) else []
    return render_template("job_match.html", supplied=supplied, submitted=submitted, has_skills=bool(skills(supplied)), ranked=ranked)


if __name__ == "__main__":
    app.run()
