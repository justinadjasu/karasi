from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
import numpy as np
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import re
import json

from helpers import login_required, text_process

PRONOUNS = ["he/him/his", "she/her/hers", "they/them/theirs", "xe/xim/xyrs"]
EXCEPT_CHS = [1]
# Configure application hi art
app = Flask(__name__)

# ensure auto reload
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# access database
db = SQL("sqlite:///apocalypse.db")

# homepage
@app.route("/", methods=["POST", "GET"])
@login_required
def index():
    if request.method == "GET":
        plays = db.execute("SELECT * FROM plays WHERE user_id = ?", session["user_id"])
        return render_template("index.html", plays=plays)
    else:
        # TODO: route user to appropriate chapter page when clicking continue
        # may have error if javascript hidden form not setup correctly
        return redirect("/")

# registration page
@app.route("/register", methods = ['POST', 'GET'])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        # check error conditions
        fields = ["username", "password", "confirmation"]
        for field in fields:
            if not request.form.get(field):
                message = (f"Please Enter a {field}.")
                flash(message, 'danger')
                return render_template("register.html")
        username = request.form.get(fields[0])
        password = request.form.get(fields[1])
        confirmation = request.form.get(fields[2])

        if password != confirmation:
            message = "Password does not match Confirmation."
            flash(message, 'danger')
            return render_template("register.html")
        taken = db.execute("SELECT * FROM users WHERE username = ?", username)
        if taken:
            message = "Username Taken."
            flash(message, 'danger')
            return render_template("register.html")

        # Add user to database of users
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, generate_password_hash(password))
        message = "Account Created Successfully!"
        flash(message, 'success')
        return redirect("/login")


# new story page
@app.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "GET":
        return render_template("new.html", pronouns = PRONOUNS)
    else:
        user_pronouns = request.form.get("pronouns")
        character_name = request.form.get("name")

        # Check username
        if not character_name:
            message = "Please enter your name."
            flash(message, 'danger')
            return render_template("new.html", pronouns = PRONOUNS)

        # check misuse
        if user_pronouns not in PRONOUNS:
            message = "Please select your pronouns."
            flash(message, 'danger')
            return render_template("new.html", pronouns = PRONOUNS)

        rows = db.execute("SELECT * FROM plays WHERE user_id = ? AND name = ? AND pronouns = ?", session["user_id"], character_name, user_pronouns)

        if len(rows) == 0:
            sim_number = 1
            db.execute("INSERT INTO plays (user_id, name, pronouns, sim_play) VALUES (?, ?, ?, ?)", session["user_id"], character_name, user_pronouns, sim_number)
        else:
            sim_number = rows[-1]["sim_play"]
            sim_number += 1
            db.execute("INSERT INTO plays (user_id, name, pronouns, sim_play) VALUES (?, ?, ?, ?)", session["user_id"], character_name, user_pronouns, sim_number)

        play_id = db.execute("SELECT id FROM plays WHERE user_id = ? AND name = ? AND pronouns = ? AND sim_play = ?", session['user_id'], character_name, user_pronouns, sim_number)[0]["id"]
        db.execute("INSERT INTO stories (play_id) VALUES (?)", play_id)
        return redirect(url_for('.chapters', play_id=play_id))


# chapters
# new story page
# Update so information from form is uploaded into decisions database
@app.route("/chapters", methods=["GET", "POST"])
@login_required
def chapters():
    if request.method == "GET":
        play_id = request.args.get('play_id')

        chandname = db.execute("SELECT ch_number, name FROM plays WHERE id = ?", play_id)[0]
        current_chapter = chandname["ch_number"]
        character_name = chandname["name"]

        chapter_route = "chapters/chapter" + str(current_chapter) + ".txt"
        with open(chapter_route, "r") as file:
            text = file.read()
        text = text.replace('{{ name }}', character_name.capitalize())

        chapter, title = text_process(text)

        if current_chapter in EXCEPT_CHS:
            chapter_template = "chapter" + str(current_chapter) + ".html"
        else:
            chapter_template = "chapters.html"

        return render_template(chapter_template, title=title, chapter=chapter, play_id=play_id)

    else:
        # process archetype based on choices
        play_id = request.form.get("play_id")
        chapter_number = db.execute("SELECT ch_number FROM plays WHERE id = ?", play_id)[0]["ch_number"]
        
        if chapter_number in DECISIONS: #Assuming decisions is a dict
            for ch_number in DECISIONS:
                decision_indices = DECISIONS[ch_number]
                for ind in decision_indices:
                    request.form.get("choice" + str(ind))
                    
        new_chapter_number = chapter_number + 1
        db.execute("UPDATE plays SET ch_number = ? WHERE id = ?", new_chapter_number, play_id)

        return redirect(url_for('.chapters', play_id=play_id))

# Make it so that going to previous chapter does not mess up current data in table,
# user should just be shown the generated story. Actually same thing needed for going forward I guess
@app.route("/previous", methods=["GET", "POST"])
@login_required
def previous():
    if request.method == "POST":
        play_id = request.form.get('play_id')
        current_chapter_number = db.execute("SELECT ch_number FROM plays WHERE id = ?", play_id)[0]["ch_number"]
        last_chapter_number = current_chapter_number - 1
        db.execute("UPDATE plays SET ch_number = ? WHERE id = ?", last_chapter_number, play_id)

        return redirect(url_for('.chapters', play_id=play_id))

# login page
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            message = "Please enter a valid username and password."
            flash(message, 'danger')
            return render_template("login.html")

        # Ensure password was submitted
        elif not request.form.get("password"):
            message = "Please enter a valid username and password."
            flash(message, 'danger')
            return render_template("login")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            message = "User does not exist. Please register if a new user."
            flash(message, 'danger')
            return render_template("login.html")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        # return redirect("/")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

# log out page
@app.route("/logout")
@login_required
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

# @app.route("/history")
# def history():


