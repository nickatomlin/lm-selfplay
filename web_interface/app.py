from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit
from flask_cors import CORS


import sys
sys.path.append("..")

import os, time
import random
import json
import string
from games.web_negotiation import WebNegotiationGame
from players import ClosedSourceChatPlayer
import openai
import numpy as np
import boto3
import logging


max_games = 40

api_key = os.environ.get('OPENAI_API_KEY')
org_id = os.environ.get('OPENAI_ORG_ID')

if not api_key:
    raise ValueError("OPENAI_API_KEY is not set")
if not org_id:
    raise ValueError("OPENAI_ORG_ID is not set")

current_model = ["original", "human", "after", ""]

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Optional code for logging games to S3 bucket:
# s3 = boto3.client('s3')
# bucket_name = "PLACEHOLDER"

def generate_random_string(length):
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for _ in range(length))

def mturk_params(req_params):
    keys = ("assignmentId", "hitId", "turkSubmitTo", "workerId")
    return {k: req_params.get(k) for k in keys}

def parse_context(ctx):
    ctx = ctx.split()
    cnts = [int(n) for n in ctx[0::2]]
    vals = [int(v) for v in ctx[1::2]]
    return cnts, vals

with open("data/selfplay.txt", "r") as file:
    lines = [line.strip() for line in file]

# Check and set OpenAI API key
api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY is not set")

# Optional: Check and set OpenAI Organization ID
org_id = os.environ.get('OPENAI_ORG_ID')

# Initialize OpenAI client
openai.api_key = api_key
if org_id:
    openai.organization = org_id

# Maintain game objects:
current_games = {}
user_data = {}
mturk_users = {}

def update_session_id(session_id):
    mturk_info = mturk_params(request.args)
    if mturk_info is None:
        return session_id
    if mturk_info["workerId"] in mturk_users and mturk_info["workerId"] != "debug" and mturk_info["workerId"] is not None:
        return mturk_users[mturk_info["workerId"]]
    return session_id

def new_game(user_id, mturk_info):
    # Replace this code based on finetuned model IDs:
    current_model[0] = np.random.choice(["original", "cooperative", "competitive"])
    current_model[1] = 0
    current_model[2] = "gpt-3.5-turbo"
    current_model[3] = "gpt-3.5-turbo"
    
    print("User: {} | Current model: {}".format(user_id, current_model))

    random_index = np.random.randint(0, 4085)
    cnts, p0_vals = parse_context(lines[random_index * 2])
    _, p1_vals = parse_context(lines[random_index * 2 + 1])

    if current_model[0] == "original":
        objective = "self"
        instr_path = "instructions/original.txt"
    elif current_model[0] == "cooperative":
        objective = "coop"
        instr_path = "instructions/cooperative.txt"
    elif current_model[0] == "competitive":
        objective = "comp"
        instr_path = "instructions/competitive.txt"
    else:
        raise Exception("Invalid objective")

    game = WebNegotiationGame(
        item_counts={
            "book": cnts[0],
            "hat": cnts[1],
            "ball": cnts[2],
        },
        user_values={
            "book": p0_vals[0],
            "hat": p0_vals[1],
            "ball": p0_vals[2],
        },
        assistant_values={
            "book": p1_vals[0],
            "hat": p1_vals[1],
            "ball": p1_vals[2],
        },
        objective=objective
    )

    assistant = ClosedSourceChatPlayer(
        game=game,
        vals=game.assistant_values,
        model=current_model[2],
        log_filename="test"
    )
    
    game.assistant = assistant

    assistant.messages_json = [{
        "role": "system",
        "content": game.assistant_system_prompt
    }]
    
    assistant.messages_log = [{
        "role": "system",
        "content": game.assistant_system_prompt
    }]
    
    current_games[user_id] = {
        "game": game,
        "assistant": assistant,
        "item_counts": game.item_counts,
        "user_values": game.user_values,
        "assistant_values": game.assistant_values,
        "model_id": assistant.model,
        "objective": objective,
        "start_time": time.time(),
        "mturk_info": mturk_info,
    }
    print("Game initialized for user: ", user_id)
        
    emit("instructions", {})

# On connection, randomly select a context from the dataset
@socketio.on('connect')
def handle_connect():
    bonus_pay = 0.00

    mturk_info = mturk_params(request.args)
    if mturk_info is None:
        mturk_info = {"assignmentId": "debug", "hitId": "debug", "turkSubmitTo": "debug", "workerId": "debug"}
    print("Connected: ", mturk_info)

    # Check if user has already played a game:
    if mturk_info["workerId"] in mturk_users and mturk_info["workerId"] != "debug" and mturk_info["workerId"] is not None:
        user_id = mturk_users[mturk_info["workerId"]]
    else:
        user_id = session.get('user_id')
        if user_id is None:
            user_id = generate_random_string(10)
            session['user_id'] = user_id

        mturk_info["user_cookie"] = user_id
        user_data[user_id] = {
            "mturk_info": mturk_info,
            "bonus_pay": bonus_pay,
            "num_games_completed": 0
        }
        mturk_users[mturk_info["workerId"]] = user_id
    new_game(user_id, mturk_info)

@socketio.on('keep_playing')
def handle_keep_playing():
    user_id = session.get('user_id')
    mturk_info = mturk_params(request.args)
    user_id = update_session_id(user_id)
    new_game(user_id, mturk_info)
    emit('initialize', {
        'counts': list(current_games[user_id]["item_counts"].values()),
        'values': list(current_games[user_id]["user_values"].values()),
        'game_num': user_data[user_id]["num_games_completed"]+1,
        'max_games': max_games,
        'earned': user_data[user_id]["bonus_pay"],
        'game_mode': current_games[user_id]["objective"]
    })

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('initialize_game')
def handle_initialize_game():
    user_id = session.get('user_id')
    user_id = update_session_id(user_id)
    game = current_games[user_id]["game"]
    assistant = current_games[user_id]["assistant"]
    emit('initialize', {
        'counts': list(game.item_counts.values()),
        'values': list(game.user_values.values()),
        'game_num': user_data[user_id]["num_games_completed"]+1,
        'max_games': max_games,
        'earned': user_data[user_id]["bonus_pay"],
        'game_mode': current_games[user_id]["objective"]
    })

    # Half the time, the assistant goes first:
    if random.random() < 0.5:
        response = game.receive_and_respond(None, assistant)
        emit('response', response)

@socketio.on('user_message')
def receive_and_respond(user_message):
    user_id = session.get('user_id')
    user_id = update_session_id(user_id)
    game = current_games[user_id]["game"]
    assistant = current_games[user_id]["assistant"]
    response = game.receive_and_respond(user_message, assistant)
    
    print("User {}: {}".format(user_id, user_message.split("]")[-1]))
    print("Model: {}".format(response["message"]))

    if response["game_over"]:
        user_data[user_id]["num_games_completed"] += 1
        
        # this is where we would save the games to a JSON
        current_games[user_id]["user_score"] = response["final_scores"]["user_score"]
        current_games[user_id]["user_proposal"] = response["user_proposal"]
        current_games[user_id]["assistant_score"] = response["final_scores"]["assistant_score"]
        current_games[user_id]["assistant_proposal"] = response["assistant_proposal"]
        current_games[user_id]["message_log"] = game.assistant.messages_json
        current_games[user_id]["disconnect"] = False        

        # Update bonus pay and add to response object
        # $0.10 per point in cooperative, and $0.20 per point in original
        bonus_pay = 0.00

        if response["final_scores"]["abort"]:
            bonus_pay = 0.25
        elif response["final_scores"]["user_score"] == 0:
            bonus_pay = 0.10
        elif current_model[0] == "original":
            bonus_pay = 0.10 + response["final_scores"]["user_score"] * 0.20
        elif current_model[0] == "cooperative":
            bonus_pay = 0.10 + response["final_scores"]["user_score"] * 0.10
        elif current_model[0] == "competitive":
            bonus_pay = 0.10 + max(response["final_scores"]["user_score"] * 0.30, 0.0)
        user_data[user_id]["bonus_pay"] += bonus_pay
        response["bonus_pay"] = user_data[user_id]["bonus_pay"]
        response["num_games_completed"] = user_data[user_id]["num_games_completed"]
        response["max_games"] = max_games
        response["game_bonus"] = bonus_pay
        response["num_games_completed"] = user_data[user_id]["num_games_completed"]

        current_games[user_id]["game_bonus"] = bonus_pay
        current_games[user_id]["bonus_so_far"] = user_data[user_id]["bonus_pay"]

        del current_games[user_id]['game']
        del current_games[user_id]['assistant']

        game_num = "game" + str(user_data[user_id]["num_games_completed"])
        random_index = str(random.randint(0, 1000000))
        key = "{}-{}-{}.json".format(user_id, game_num, random_index)
        # Log to S3:
        # s3.put_object(Bucket=bucket_name, Key=key, Body=json.dumps(current_games[user_id]))
        # print("Logged game from {} to S3".format(user_id))
        
        del current_games[user_id]
        
        print("Game over for user: {} (User: {}, Partner: {})".format(user_id, response["final_scores"]["user_score"], response["final_scores"]["assistant_score"]))
        emit('game_over', response)
        
    emit('response', response)

@socketio.on('disconnect')
def handle_disconnect():
    user_id = session.get('user_id')
    user_id = update_session_id(user_id)
    print("Disconnecting user: ", user_id)
    if user_id is not None:
        try:
            game = current_games[user_id]["game"]
            assistant = current_games[user_id]["assistant"]
            current_games[user_id]["user_score"] = 0
            current_games[user_id]["user_proposal"] = None
            current_games[user_id]["assistant_score"] = 0
            current_games[user_id]["assistant_proposal"] = None
            current_games[user_id]["message_log"] = game.assistant.messages_json
            current_games[user_id]["disconnect"] = True

            current_games[user_id]["game_bonus"] = 0.00
            current_games[user_id]["bonus_so_far"] = user_data[user_id]["bonus_pay"]
            
            del current_games[user_id]['game']
            del current_games[user_id]['assistant']
            
            game_num = "game" + str(user_data[user_id]["num_games_completed"])
            random_index = str(random.randint(0, 1000000))
            key = "{}-{}-{}.json".format(user_id, game_num, random_index)
            # Log to S3:
            # s3.put_object(Bucket=bucket_name, Key=key, Body=json.dumps(current_games[user_id]))
            # print("Logged game from {} to S3 after disconnect".format(user_id))
            del current_games[user_id]
        except KeyError:
            print("No game found for user")
        
if __name__ == '__main__':
    print("RUN")
    socketio.run(app)