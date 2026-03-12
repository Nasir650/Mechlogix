import json
import os
import re
import secrets
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import fitz
import google.generativeai as genai
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database import (
    create_plan,
    create_user,
    delete_plan_for_user,
    get_dashboard_stats,
    get_or_create_google_user,
    get_plan_for_user,
    get_recent_plans,
    get_user_by_email,
    get_user_by_id,
    init_db,
    update_user,
)
from prompts import build_manufacturing_prompt


load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set in .env")

SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
GOOGLE_OAUTH_ENABLED = all(
    [GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI]
)

genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = SECRET_KEY

init_db()


def clean_gemini_response(text):
    text = (text or "").strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


def set_session_user(user, auth_source):
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["auth_source"] = auth_source


def extract_pdf_text(file_storage):
    pdf_bytes = file_storage.read()
    if not pdf_bytes:
        return ""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_parts = [page.get_text().strip() for page in doc]
    doc.close()
    return "\n".join(part for part in text_parts if part).strip()


def generate_plan_content(design_text):
    prompt = build_manufacturing_prompt(design_text)
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.2,
            "response_mime_type": "application/json",
        },
    )
    raw_text = clean_gemini_response(getattr(response, "text", ""))
    if not raw_text:
        raise ValueError("Gemini returned an empty response.")

    try:
        parsed = json.loads(raw_text)
        return raw_text, parsed, "completed"
    except json.JSONDecodeError:
        return raw_text, None, "raw_only"


def generate_title(parsed_json, input_text):
    if isinstance(parsed_json, dict):
        summary = (parsed_json.get("plan_summary") or "").strip()
        if summary:
            return summary[:80]

    compact_input = " ".join((input_text or "").split())
    if compact_input:
        return compact_input[:80]

    return f"Plan {datetime.now().strftime('%Y-%m-%d %H:%M')}"


def parse_json_field(plan):
    parsed_json = None
    if plan and plan.get("parsed_json"):
        try:
            parsed_json = json.loads(plan["parsed_json"])
        except json.JSONDecodeError:
            parsed_json = None
    return parsed_json


def humanize_input_type(input_type):
    return "PDF Upload" if input_type == "pdf" else "Text Input"


def badge_class(status):
    mapping = {
        "completed": "badge-success",
        "raw_only": "badge-warning",
        "failed": "badge-danger",
    }
    return mapping.get(status, "badge-warning")


def format_datetime(value):
    if not value:
        return "No activity yet"
    dt = datetime.fromisoformat(value)
    return dt.strftime("%b %d, %Y, %I:%M %p")


def time_ago(value):
    if not value:
        return "No activity"
    dt = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def clamp_percent(value):
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return 0


@app.before_request
def load_current_user():
    g.user = None
    if session.get("user_id"):
        g.user = get_user_by_id(session["user_id"])
        if g.user is None:
            session.clear()


@app.context_processor
def inject_globals():
    return {
        "current_user": g.user,
        "oauth_enabled": GOOGLE_OAUTH_ENABLED,
        "badge_class": badge_class,
        "format_datetime": format_datetime,
        "time_ago": time_ago,
        "humanize_input_type": humanize_input_type,
        "clamp_percent": clamp_percent,
        "theme_class": f"theme-{(g.user or {}).get('theme', 'dark')}",
    }


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/template-assets/<path:filename>")
def template_asset(filename):
    return send_from_directory(os.path.join(BASE_DIR, "templates"), filename)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        auth_action = request.form.get("auth_action", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if auth_action == "register":
            name = request.form.get("name", "").strip()
            if not name or not email or not password:
                flash("Name, email, and password are required to create an account.", "warning")
                return render_template("login.html", active_panel="create")

            if get_user_by_email(email):
                flash("An account with that email already exists.", "warning")
                return render_template("login.html", active_panel="create")

            password_hash = generate_password_hash(password)
            user_id = create_user(name=name, email=email, password_hash=password_hash)
            user = get_user_by_id(user_id)
            set_session_user(user, "password")
            flash("Account created successfully.", "success")
            return redirect(url_for("dashboard"))

        if not email or not password:
            flash("Email and password are required to sign in.", "warning")
            return render_template("login.html", active_panel="signin")

        user = get_user_by_email(email)
        if not user or not user["password_hash"] or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "warning")
            return render_template("login.html", active_panel="signin")

        set_session_user(user, "password")
        flash("Signed in successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html", active_panel="signin")


@app.route("/auth/google")
def google_login():
    if not GOOGLE_OAUTH_ENABLED:
        flash("Google sign-in is not configured for this deployment.", "warning")
        return redirect(url_for("login"))

    state = secrets.token_urlsafe(24)
    session["google_oauth_state"] = state
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return redirect(
        "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    )


@app.route("/auth/google/callback")
def google_callback():
    if not GOOGLE_OAUTH_ENABLED:
        flash("Google sign-in is not configured for this deployment.", "warning")
        return redirect(url_for("login"))

    if request.args.get("state") != session.pop("google_oauth_state", None):
        flash("Google sign-in failed due to an invalid state token.", "warning")
        return redirect(url_for("login"))

    if request.args.get("error"):
        flash("Google sign-in was cancelled or denied.", "warning")
        return redirect(url_for("login"))

    code = request.args.get("code")
    if not code:
        flash("Google sign-in did not return an authorization code.", "warning")
        return redirect(url_for("login"))

    try:
        token_payload = urlencode(
            {
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        ).encode("utf-8")
        token_request = Request(
            "https://oauth2.googleapis.com/token",
            data=token_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urlopen(token_request) as token_response:
            token_data = json.loads(token_response.read().decode("utf-8"))

        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("Missing access token")

        userinfo_request = Request(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urlopen(userinfo_request) as userinfo_response:
            profile = json.loads(userinfo_response.read().decode("utf-8"))

        email = profile.get("email")
        if not email:
            raise ValueError("Google account did not return an email address")

        user = get_or_create_google_user(
            name=profile.get("name", email.split("@")[0]),
            email=email,
        )
        set_session_user(user, "google")
        flash("Signed in with Google successfully.", "success")
        return redirect(url_for("dashboard"))
    except Exception:
        flash("Google sign-in could not be completed.", "warning")
        return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    stats = get_dashboard_stats(g.user["id"])
    recent_plans = get_recent_plans(g.user["id"], limit=5)
    return render_template("dashboard.html", stats=stats, recent_plans=recent_plans)


@app.route("/history")
@login_required
def history():
    plans = get_recent_plans(g.user["id"], limit=100)
    return render_template("history.html", plans=plans)


@app.route("/new-plan", methods=["GET", "POST"])
@login_required
def new_plan():
    if request.method == "POST":
        text_input = request.form.get("design_text", "").strip()
        input_mode = request.form.get("input_mode", "text")
        pdf_file = request.files.get("design_pdf")

        design_text = text_input
        input_type = "text"
        uploaded_pdf_name = ""

        if pdf_file and pdf_file.filename:
            uploaded_pdf_name = pdf_file.filename
            design_text = extract_pdf_text(pdf_file)
            input_type = "pdf"
            input_mode = "pdf"

            if not design_text:
                flash(
                    "The uploaded PDF does not contain extractable text. Please use a text-based PDF or paste the requirements manually.",
                    "warning",
                )
                return render_template(
                    "new-plan.html",
                    input_mode=input_mode,
                    design_text=text_input,
                    uploaded_pdf_name=uploaded_pdf_name,
                )

        if not design_text:
            flash("Please provide design text or upload a PDF.", "warning")
            return render_template(
                "new-plan.html",
                input_mode=input_mode,
                design_text=text_input,
                uploaded_pdf_name=uploaded_pdf_name,
            )

        try:
            raw_response, parsed_json, status = generate_plan_content(design_text)
            title = generate_title(parsed_json, design_text)
            plan_id = create_plan(
                user_id=g.user["id"],
                title=title,
                input_type=input_type,
                input_text=design_text,
                raw_response=raw_response,
                parsed_json=parsed_json,
                status=status,
            )
            if status == "raw_only":
                flash("Plan saved, but Gemini returned non-JSON output. Showing the raw response.", "warning")
            else:
                flash("Manufacturing plan generated successfully.", "success")
            return redirect(url_for("plan_detail", plan_id=plan_id))
        except Exception as exc:
            flash(f"Plan generation failed: {exc}", "warning")
            return render_template(
                "new-plan.html",
                input_mode=input_mode,
                design_text=text_input,
                uploaded_pdf_name=uploaded_pdf_name,
            )

    return render_template("new-plan.html", input_mode="text", design_text="", uploaded_pdf_name="")


@app.route("/plan/<int:plan_id>")
@login_required
def plan_detail(plan_id):
    plan = get_plan_for_user(plan_id, g.user["id"])
    if not plan:
        flash("Plan not found.", "warning")
        return redirect(url_for("dashboard"))

    parsed_json = parse_json_field(plan)
    active_tab = "manufacturing" if parsed_json else "raw"
    return render_template(
        "plan-detail.html",
        plan=plan,
        parsed_json=parsed_json,
        active_tab=active_tab,
    )


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        preferred_llm = request.form.get("preferred_llm", "Gemini").strip() or "Gemini"
        theme = request.form.get("theme", "dark").strip().lower()
        if theme not in {"dark", "light"}:
            theme = "dark"

        if not name or not email:
            flash("Name and email are required.", "warning")
            return render_template("settings.html")

        existing = get_user_by_email(email)
        if existing and existing["id"] != g.user["id"]:
            flash("That email address is already in use.", "warning")
            return render_template("settings.html")

        update_user(g.user["id"], name, email, preferred_llm, theme)
        session["user_name"] = name
        flash("Profile updated successfully.", "success")
        return redirect(url_for("settings"))

    return render_template("settings.html")


@app.route("/delete-plan/<int:plan_id>", methods=["POST"])
@login_required
def delete_plan(plan_id):
    deleted = delete_plan_for_user(plan_id, g.user["id"])
    if deleted:
        flash("Plan deleted.", "success")
    else:
        flash("Plan not found.", "warning")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
