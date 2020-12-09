from cs50 import SQL
from flask import redirect, render_template, request, session
from functools import wraps

# access database
db = SQL("sqlite:///apocalypse.db")

# globals
PRONOUNS = ["he/him/his", "she/her/hers", "they/them/theirs", "xe/xim/xyrs"]


# Decisions with following structure {
#     "number of a chapter with important decisions":[list of indices in chapter array where the optroute key gives choice that has important decision]
#     ex for ch3:
#     '3':[1] # index 1 corresponds to 2nd decision, which determines if Yafeu dies
# }
DECISIONS = {
    3: [1],
    6: [1]
}

EFFECTS = {
    "Disparage the robber": "yafeu_dead",
    "Talk her out of it": "parents_dead"
}

EXCEPT_CHS = [1, 5, 9]


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# process text file of chapter into form compatible with javascript code to analyze choices
def text_process(text, play_id):
    """

    Process chapter into sublists

    """
    main = []
    options = []
    routes = []
    archs = []
    cons = []
    cons_locs = []
    conditions = []

    # Split the main plot of the story into pieces
    text_main = text.split("||")

    # Split each of the indivdual choices throughout the chapter
    text_options = text.split("##")

    # Split all of the routes throughout the chapter
    text_routes = text.split("**")

    # Split all of the archetypes throughout the chapter
    text_archs = text.split("%%")

    # Split all of the conditional text throughout the chapter
    text_cons = text.split("&&")

    # Split all of the conditional locations throughout the chapter
    text_cons_locs = text.split("$$")  # $$"I sat and thought to myself."$$

    # Split all of the conditions
    text_conditions = text.split("@@")  # @@yafeu_dead@@ &&damn my dog alive//damn my dog dead&&

    # Get the chapter title
    title = text_main[0]

    # Section all of the separated portions into lists
    for i in range(len(text_main) - 2):
        main.append(text_main[i + 1])
    for i in range(len(text_options) - 2):
        options.append([text_options[i + 1]])
        routes.append([text_routes[i + 1]])
        archs.append([text_archs[i + 1]])

    # Section all of the separated conditionals into lists
    for i in range(len(text_cons) - 2):
        cons.append(text_cons[i + 1])
        cons_locs.append(text_cons_locs[i + 1])
        conditions.append(text_conditions[i + 1])

    # Subdivide each of the individual options, routes, and conditions
    options_sep = []
    routes_sep = []
    archs_sep = []
    optroute = []
    cons_sep = []

    # options_sep and routes_sep are both a list of lists. Each sub-list contains all of the choices and possible routes at a single point in the story.
    # Afterwards, these sub-lists are turned into dictionaries where option is the key and route is the value
    for i in range(len(options)):
        options_sep.append([y for x in options[i] for y in x.split('//')])
        routes_sep.append([y for x in routes[i] for y in x.split('//')])
        archs_sep.append([y for x in archs[i] for y in x.split('//')])

        j = 0
        optroute.append({})
        for key in (options_sep[i]):
            optroute[i][key] = [routes_sep[i][j], archs_sep[i][j]]
            j += 1

    # Subdivide all of the condition texts
    # Afterwards, put the conditionals and their text locations in a dictionary with key cons
    conditionals = {}
    cons_sep.append([y for x in cons for y in x.split('//')])
    i = 0
    for key in conditions:
        conditionals[key] = cons_sep[i] + [cons_locs[i]]
        i += 1

    # Combine main storylines and routes into one list of dictionaries
    chapter = []
    if len(main) == len(options):
        for i in range(len(main)):
            chapter.append({})
            chapter[i]["main"] = main[i]
            chapter[i]["optroute"] = optroute[i]

    elif len(main) == len(options) + 1:
        for i in range(len(options)):
            chapter.append({})
            chapter[i]["main"] = main[i]
            chapter[i]["optroute"] = optroute[i]
        chapter.append({})
        chapter[-1]["main"] = main[-1]
        chapter[-1]["optroute"] = {'': []}

    else:
        print("error loading chapter")

    # Adds conditions to the end of corresponding text
    decisions = db.execute("SELECT * FROM important_decisions WHERE play_id=?", play_id)[0]
    for key in conditionals:
        if key != '':
            condition = decisions[key]
            if condition == True:
                con_ind = 1
            else:
                con_ind = 0

            cond_text = conditionals[key][con_ind]
            cond_strloc = conditionals[key][2]
            for section in chapter:
                # find() returns first index where the value is. Outputs -1 if not found.
                if section["main"].find(cond_strloc) != -1:
                    pre_pos = section["main"].find(cond_strloc)
                    pos = pre_pos + len(cond_strloc) - 1
                    section["main"] = section["main"][:pos + 1] + " " + cond_text + " " + section["main"][pos + 1:]
                    break

    return chapter, title

# keeps track of choices for archetype and important story information
def process_decisions(chapter_number, character_name, play_id):
    # check if previous chapter has decisions to be made, if not move on to next chapter
    if chapter_number not in EXCEPT_CHS:

        # Update choice information from previous chapter playthrough
        # Open previous chapter
        if chapter_number != 4:
            chapter_route = "chapters/chapter" + str(chapter_number) + ".txt"
        else:
            current_conds = db.execute("SELECT * FROM important_decisions WHERE play_id = ?", play_id)[0]
            if current_conds["yafeu_dead"]:
                chapter_route = "chapters/chapter" + str(chapter_number) + "dead" + ".txt"
            else:
                return

        with open(chapter_route, "r") as file:
            text = file.read()
        text = text.replace('{{ name }}', character_name.capitalize())

        # Process previous chapter
        chapter, title = text_process(text, play_id)

        # Generate array of all archetype choices for user
        archetypes = []
        for i in range(len(chapter)):
            if (request.form.get("choice" + str(i+1))):
                archetypes.append(chapter[i]["optroute"][request.form.get("choice" + str(i + 1))][1])
            else:
                break

        # Update current archetype points in table
        for archetype in archetypes:
            points = 5 + db.execute("SELECT * FROM plays WHERE id = ?", play_id)[0][archetype.lower()]
            db.execute("UPDATE plays SET " + archetype.lower() + " = ? WHERE id = ?", points, play_id)

        # Get user decisions that will affect plot line
        if chapter_number in DECISIONS:
            decision_list = DECISIONS[chapter_number]
            decisions = []

            # stores choice user made for each important decision
            for ind in decision_list:
                decisions.append(request.form.get("choice" + str(ind + 1)))

            # checks if decision made is in EFFECTS
            for i in range(len(decisions)):
                if decisions[i] in EFFECTS:
                    db.execute("UPDATE important_decisions SET " + EFFECTS[decisions[i]] + " = ? WHERE play_id = ?", True, play_id)
    return

# adds user's new playthrough to database
def new_story(character_name, user_pronouns):
    rows = db.execute("SELECT * FROM plays WHERE user_id = ? AND name = ? AND pronouns = ?", session["user_id"], character_name, user_pronouns)

    if len(rows) == 0:
        sim_number = 1
        db.execute("INSERT INTO plays (user_id, name, pronouns, sim_play) VALUES (?, ?, ?, ?)", session["user_id"], character_name, user_pronouns, sim_number)
    else:
        # distiguish b/w plays with same name
        sim_number = rows[-1]["sim_play"]
        sim_number += 1
        db.execute("INSERT INTO plays (user_id, name, pronouns, sim_play) VALUES (?, ?, ?, ?)", session["user_id"], character_name, user_pronouns, sim_number)

    # add new playthrough to stories and important_decisions
    play_id = db.execute("SELECT id FROM plays WHERE user_id = ? AND name = ? AND pronouns = ? AND sim_play = ?", session['user_id'], character_name, user_pronouns, sim_number)[0]["id"]
    db.execute("INSERT INTO stories (play_id) VALUES (?)", play_id)
    db.execute("INSERT INTO important_decisions (play_id) VALUES (?)", play_id)

    return play_id

# breakdown user decisions at end of playthrough
def breakdown_play(play_id):

    # get archetype data of player
    players = db.execute("SELECT survivalist, prophet, antichrist, christ FROM plays WHERE id = ?", play_id)[0]

    # determine primary archetype
    primary = highest(players)
    del players[primary]

    # determine secondary archetype
    secondary = highest(players)

    pronoun_dict = {}

    # get each pronoun into list in proper form
    pronoun = db.execute("SELECT * FROM plays WHERE id = ?", play_id)[0]["pronouns"]
    pronoun_list = pronoun.split("/")


    # Process the text files relating to the archtypes
    types = [primary, secondary]
    text = []

    for i in range(len(types)):
        description = ""
        with open(f"breakdown/{types[i]}.txt", "r") as file:
            description = file.read()
        for i in range(len(pronoun_list)):
            description = description.replace(f"pronoun{i + 1}", pronoun_list[i])
            pronoun_list[i] = pronoun_list[i].capitalize()
            description = description.replace(f"Pronoun{i + 1}", pronoun_list[i])
        text.append(description)

    return primary, secondary, text

def get_arch(play_id):
    # get archetype data of player
    player = db.execute("SELECT survivalist, prophet, antichrist, christ FROM plays WHERE id = ?", play_id)[0]
    main_archetype = highest(player)
    return main_archetype

def highest(player):
    # In the event of a tie
    ranks = {'prophet': 4, 'survivalist': 3, 'antichrist': 2, 'christ': 1}

    # determine primary archetype
    idx = 0
    primary = ""

    # use copy of original dict to avoid making changes
    player_copy = player.copy()
    for archetype in player_copy:
        if player_copy[archetype] > idx:
            primary = archetype
            idx = player_copy[archetype]
    del player_copy[primary]

    ties = []
    ties.append(primary)

    # check if multiple archetypes have the max archetype value
    tied = False
    for archetype in player_copy:
        if player_copy[archetype] == idx:
            tied = True
            ties.append(archetype)

    # If a tie, determine primary based on
    if tied:
        score = 0
        main_archetype = ''
        for archetype in ties:
            if ranks[archetype] > score:
                main_archetype = archetype
                score = ranks[archetype]
    else:
        main_archetype = primary

    return main_archetype
