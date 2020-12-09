from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import json

from helpers import login_required, text_process, process_decisions, new_story, get_arch

PRONOUNS = ["he/his/him", "she/her/hers", "they/theirs/them", "xe/xyrs/xim"]
EXCEPT_CHS = [1, 5, 9]

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
@app.route("/", methods=['POST', 'GET'])
@login_required
def index():
    if request.method == "GET":
        plays = db.execute("SELECT * FROM plays WHERE user_id = ?", session["user_id"])
        for play in plays:
            if db.execute("SELECT * FROM stories WHERE play_id = ?", play["id"])[0]["ch10"] and play["ch_number"] == 10:
                play["word"] = "View"
            else:
                play["word"] = "Continue"
        return render_template("index.html", plays=plays)
    else:
        # TODO: route user to appropriate chapter page when clicking continue
        # Check if deleting or continuing
        if request.form.get("continue"):
            return redirect(url_for('chapters', play_id=request.form.get("continue")))
        else:
            # delete selected playthrough
            play_id = request.form.get("delete")
            db.execute("DELETE FROM plays WHERE id = ?", play_id)
            db.execute("DELETE FROM important_decisions WHERE play_id = ?", play_id)
            db.execute("DELETE FROM stories WHERE play_id = ?", play_id)

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
        # restrict users to 5 total plays
        num_plays = len(db.execute("SELECT * FROM plays WHERE user_id = ?", session["user_id"]))
        if num_plays > 4:
            message = "Too many active plays, please delete one or more playthroughs before starting another."
            flash(message, 'danger')
            return render_template("new.html", pronouns = PRONOUNS)

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

        if not character_name.isalpha():
            message = "Please enter a name consisting only of letters"
            flash(message, 'danger')
            return render_template("new.html", pronouns = PRONOUNS)

        play_id = new_story(character_name.capitalize(), user_pronouns) # removed db from argument

        return redirect(url_for('chapters', play_id=play_id))


# chapters
# new story page
# Update so information from form is uploaded into decisions database
@app.route("/chapters", methods=["GET", "POST"])
@login_required
def chapters():
    if request.method == "GET":
        if request.form.get('play_id'):
            play_id = request.form.get('play_id')
        else:
            play_id = request.args.get('play_id')

        # Select character name and current chapter from database
        play_data = db.execute("SELECT * FROM plays WHERE id = ?", play_id)[0]
        current_chapter = play_data["ch_number"]
        character_name = play_data["name"]

        #process end of story
        if current_chapter == 11:
            return redirect(url_for('breakdown', play_id = play_id))

        # Check if new chapter has been played through already, if so load that
        chx = "ch" + str(current_chapter)
        loaded = db.execute("SELECT * FROM stories WHERE play_id = ?", play_id)[0][chx]
        # IF the chapter has been played through, load the text
        if loaded:
            title = db.execute("SELECT * FROM chapters WHERE chapter_number = ?", current_chapter)[0]["chapter_title"]
            return render_template('played.html', title=title, loaded=loaded, play_id=play_id)

        # open and process text for chosen chapter. Exception for chapter 4 which has two text files
        if current_chapter == 4:
            current_conds = db.execute("SELECT * FROM important_decisions WHERE play_id = ?", play_id)[0]
            if current_conds["yafeu_dead"] == True:
                chapter_route = "chapters/chapter" + str(current_chapter) + "dead" + ".txt"
            else:
                chapter_route = "chapters/chapter" + str(current_chapter) + "alive" + ".txt"
        else:
            chapter_route = "chapters/chapter" + str(current_chapter) + ".txt"

        print(chapter_route)
        with open(chapter_route, "r") as file:
            text = file.read()
        text = text.replace('{{ name }}', character_name.capitalize())
        chapter, title = text_process(text, play_id)

        # If chapter has no decisions use other template
        if current_chapter in EXCEPT_CHS or chapter_route == "chapters/chapter4alive.txt":
            chapter_template = "chapter_simple.html"
        else:
            chapter_template = "chapters.html"

        print(chapter_template)

        archetype = get_arch(play_id)
        # print(archetype)

        return render_template(chapter_template, title=title, chapter=chapter, play_id=play_id, archetype=archetype)

@app.route("/forward", methods=["GET", "POST"])
@login_required
def forward():
    if request.method == "POST":

        if request.form.get('play_id'):
            play_id = request.form.get('play_id')
        else:
            play_id = request.args.get('play_id')

        # Get current chapter information
        chandname = db.execute("SELECT * FROM plays WHERE id = ?", play_id)[0]
        chapter_number = chandname["ch_number"]
        character_name = chandname["name"]

        # Change current chapter number
        new_chapter_number = chapter_number + 1
        db.execute("UPDATE plays SET ch_number = ? WHERE id = ?", new_chapter_number, play_id)

        # Check if new chapter has been played through already, if so load that
        chx = "ch" + str(new_chapter_number)
        if new_chapter_number <= 10:
            loaded = db.execute("SELECT * FROM stories WHERE play_id = ?", play_id)[0][chx]
        else:
            return redirect(url_for('chapters', play_id=play_id))

        # If the chapter has been played through, load the text
        if loaded:
            title = db.execute("SELECT * FROM chapters WHERE chapter_number = ?", new_chapter_number)[0]["chapter_title"]
            return render_template('played.html', title=title, loaded=loaded, play_id=play_id)

        # If the new chapter has not been loaded/played through
        else:
            # if the previous chapter has not been loaded, then save it and process decisions. Do this for all chapters except 10
            if not db.execute("SELECT * FROM stories WHERE play_id = ?", play_id)[0]["ch" + str(chapter_number)]:
                story = request.form.get("story")
                db.execute("UPDATE stories SET ch" + str(chapter_number) + "  = ? WHERE play_id = ?", story, play_id)
                if chapter_number != 10:
                    process_decisions(chapter_number, character_name, play_id)

        return redirect(url_for('chapters', play_id=play_id))

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
        return redirect(url_for('previouschapter', play_id=play_id))

@app.route("/previouschapter", methods=["GET", "POST"])
@login_required
def previouschapter():
    play_id = request.args.get("play_id")
    last_chapter_number = db.execute("SELECT ch_number FROM plays WHERE id = ?", play_id)[0]["ch_number"]
    chx = "ch" + str(last_chapter_number)
    loaded = db.execute("SELECT * FROM stories WHERE play_id = ?", play_id)[0][chx]
    title = db.execute("SELECT * FROM chapters WHERE chapter_number = ?", last_chapter_number)[0]["chapter_title"]
    return render_template('played.html', title=title, loaded=loaded, play_id=play_id)

# handle the archetype breakdown page for the end of the chapter
@app.route("/breakdown", methods=["GET", "POST"])
@login_required
def breakdown():
    if request.method == "GET":
        play_id = request.args.get("play_id")
        primary, secondary, text = breakdown_play(play_id)
        render_template("breakdown.html", play_id=play_id, primary=primary, secondary=secondary, text=text)
    return

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


