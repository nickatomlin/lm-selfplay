from openai import OpenAI
import json
import numpy as np
import re

import os
from dotenv import load_dotenv

def check_agreement_validity(game_text):
    """
    Check if the proposals in the game text match the total item counts specified at the beginning.

    Args:
    game_text (str): The game text containing item counts and proposals.

    Returns:
    dict: A dictionary containing the results of compatibility check for books, hats, and balls, and overall compatibility.
    """

    # Extract the item counts from the first line
    item_counts = re.search(
        r"Item counts: there are (\d+) books, (\d+) hats, and (\d+) balls.", game_text
    )

    # Extract the proposals
    proposals = re.findall(
        r"\[propose\] \((\d+) books, (\d+) hats, (\d+) balls\)", game_text
    )

    if item_counts:
        total_books, total_hats, total_balls = map(int, item_counts.groups())
    else:
        return {"error": "Item counts not found in the provided text"}

    # initialize sum counters for the proposals
    sum_books, sum_hats, sum_balls = 0, 0, 0

    # sum the proposed amounts
    for proposal in proposals:
        sum_books += int(proposal[0])
        sum_hats += int(proposal[1])
        sum_balls += int(proposal[2])

    is_valid_deal = (
        sum_books == total_books and sum_hats == total_hats and sum_balls == total_balls
    )

    return is_valid_deal

def calculateScore(player_values, player_cnts):
    return sum(x * y for x, y in zip(player_values.values(), player_cnts.values()))

def calculateFinalScore(
    player_values, player_cnts, opponent_values, opponents_cnts, objective
):
    player_score = calculateScore(player_values, player_cnts)
    opponent_score = calculateScore(opponent_values, opponents_cnts)
    
    if objective == "self":
        return player_score
    elif objective == "coop":
        return player_score + opponent_score
    elif objective == "comp":
        return player_score - opponent_score
    else:
        raise Exception()


def isParetoOptimal(p0_score, p1_score, cnts, p0_values, p1_values, objective):
    # checks for pareto optimality of proposal given the players' values
    # iterate through all possible allocations
    assert objective in ["self", "coop", "comp"]
    
    allocations = []
    for i in range(cnts["book"] + 1):
        for j in range(cnts["hat"] + 1):
            for k in range(cnts["ball"] + 1):
                allocations.append({"book": i, "hat": j, "ball": k})

    for allocation in allocations:
        isAsGood = False
        isBetter = False

        # decide player counts based on allocation
        p0_cnts = allocation
        p1_cnts = {k: cnts[k] - p0_cnts[k] for k in p0_cnts.keys()}

        # calculate utilities based on allocation
        p0_new_score = calculateFinalScore(
            p0_values, p0_cnts, p1_values, p1_cnts, objective
        )
        p1_new_score = calculateFinalScore(
            p1_values, p1_cnts, p0_values, p0_cnts, objective
        )

        # check if there is a configuration where both players do as good and at least one player does better
        if p0_new_score >= p0_score and p1_new_score >= p1_score:
            isAsGood = True
        if p0_new_score > p0_score or p1_new_score > p1_score:
            isBetter = True

        if isAsGood and isBetter:
            return False

    # if we don't find a single better allocation
    return True


def calculate_maximum_collective_score(cnts, p0_values, p1_values, objective):
    allocations = []
    for i in range(cnts["books"] + 1):
        for j in range(cnts["hats"] + 1):
            for k in range(cnts["balls"] + 1):
                allocations.append({"books": i, "hats": j, "balls": k})

    best_combined_score = 0
    for allocation in allocations:
        # decide player counts based on allocation
        p0_cnts = allocation
        p1_cnts = {k: cnts[k] - p0_cnts[k] for k in p0_cnts.keys()}

        # calculate utilities based on allocation
        p0_new_score = calculateScore(p0_values, p0_cnts)
        p1_new_score = calculateScore(p1_values, p1_cnts)

        best_combined_score = max(best_combined_score, p0_new_score + p1_new_score)
        
    # return best score we saw from any allocation
    if objective == "self":
        return best_combined_score / 2
    elif objective == "coop":
        return best_combined_score
    else:
        raise Exception()


def calculate_dataset_ceiling_performance(dir_path, objective):

    best_combined_scores = []
    for filename in os.listdir(f"{dir_path}/results"):
        filepath = os.path.join(f"{dir_path}/results", filename)

        with open(filepath, "r") as results_file:
            results_json = json.load(results_file)

        # check maximum collective score
        best_combined_score = calculate_maximum_collective_score(
            results_json["counts"],
            results_json["p0_values"],
            results_json["p1_values"],
            objective,
        )

        best_combined_scores.append(best_combined_score)

    return np.mean(best_combined_scores)


def extract_final_scores(game_text):
    score_pattern = r"Player (\d) FINAL SCORE: (\d+)"

    # find all matches of the score pattern
    scores = re.findall(score_pattern, game_text)

    # convert scores to a dictionary
    score_dict = {int(player): int(score) for player, score in scores}

    # return the scores for Player 0 and Player 1
    return score_dict[0], score_dict[1]

def calculate_avg_score(path):
    with open(path, "r") as scores_file:
        scores = [int(line.strip()) for line in scores_file]
    return np.mean(scores)

def concatenate(dir_path, filter="above_avg", is_comp=False):
    with open(f"{dir_path}/p0_scores", "r") as p0_scores, open(
        f"{dir_path}/p1_scores", "r"
    ) as p1_scores:
        p0_array = [int(line.strip()) for line in p0_scores]
        p1_array = [int(line.strip()) for line in p1_scores]

    # determine the average score for cutoff
    if filter == "above_avg":
        cutoff = np.mean(p0_array + p1_array)
    elif filter == "nonzero":
        cutoff = 0
    elif filter == "all":
        cutoff = -100
    else:
        raise Exception("")

    print("cutoff", cutoff)

    # determine the games that satisfy the cutoff
    p0_good_games, p1_good_games = [], []
    for i in range(len(p0_array)):

        include = False
        if is_comp and p0_array[i] == 0 and p1_array[i] == 0:
            # use results json
            index = ("000" + str(i))[-3:]
            file_name = f"{dir_path}/results/{index}.json"

            with open(file_name, "r") as results_file:
                results = json.load(results_file)

            if results["is_valid_deal"]:
                include = True

        if p0_array[i] > cutoff or include:
            p0_good_games.append(i)

        if p1_array[i] > cutoff or include:
            p1_good_games.append(i)

    print(len(p0_good_games) + len(p1_good_games))

    # create the fine-tuning JSON
    with open(f"{dir_path}/game_data.jsonl", "a") as final_file:
        for i in p0_good_games:
            index = ("000" + str(i))[-3:]
            file_name = f"{dir_path}/json_logs/{index}_p0.json"

            # load the game log as a JSON
            with open(file_name, "r") as game_file:
                game_log = json.load(game_file)

            # dump the json into the jsonl, and then append a new line
            json.dump({"messages": game_log}, final_file)
            final_file.write("\n")

        for i in p1_good_games:
            index = ("000" + str(i))[-3:]
            file_name = f"{dir_path}/json_logs/{index}_p1.json"

            # load the game log as a JSON
            with open(file_name, "r") as game_file:
                game_log = json.load(game_file)

            # dump the json into the jsonl, and then append a new line
            json.dump({"messages": game_log}, final_file)
            final_file.write("\n")


def create_finetuning_job(model_suffix, jsonl_path=None, model_name="turbo"):
    
    # load API keys
    load_dotenv()
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        organization=os.getenv("OPENAI_ORG_ID"),
    )

    # creating a file with the API to train on
    file = open(jsonl_path, "rb")
    training_file = client.files.create(file=file, purpose="fine-tune")
    
    model = model_name

    # job response
    job_response = client.fine_tuning.jobs.create(
        model=model,
        training_file=training_file.id,
        hyperparameters={"n_epochs": 3, "batch_size": 1, "learning_rate_multiplier": 8},
        suffix=model_suffix,
    )
