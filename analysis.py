import argparse
import json
import numpy as np
import re
import os
import csv
import utils as utils

def calculate_avg_score(dir_path, filter_zeros=False):
    # collect all scores from both players
    with open(f"{dir_path}/p0_scores", "r") as p0_scores, open(
        f"{dir_path}/p1_scores", "r"
    ) as p1_scores:
        p0_array = [int(line.strip()) for line in p0_scores]
        p1_array = [int(line.strip()) for line in p1_scores]

    full_scores = p0_array + p1_array

    # check whether we are including zero-scoring games
    if filter_zeros:
        full_scores_filtered = [x for x in full_scores if x > 0]
        return np.mean(full_scores_filtered)
    else:
        return np.mean(full_scores)


def analyze(dir_path, verbose=True, objective="orig"):
    # collect all scores from both players
    with open(f"{dir_path}/p0_scores", "r") as p0_scores, open(
        f"{dir_path}/p1_scores", "r"
    ) as p1_scores:
        p0_array = [int(line.strip()) for line in p0_scores]
        p1_array = [int(line.strip()) for line in p1_scores]

    full_scores = p0_array + p1_array

    # calculate all scores
    unfiltered_mean = np.mean(full_scores)
    unfiltered_median = np.median(full_scores)

    # initialize arrays to store indices of games with agreements, token counts, and message counts
    agreement_indices = []
    token_counts = []
    msg_counts = []

    # track number of aborts
    num_aborts = 0

    # iterate through game indices
    for i in range(len(p0_array)):
        index = ("000" + str(i))[-3:]

        # retrieve results JSON
        results_filename = f"{dir_path}/results/{index}.json"
        with open(results_filename, "r") as results_file:
            result = json.load(results_file)

        # check for valid indices
        if result["is_valid_deal"]:
            agreement_indices.append(i)

        # append token and message counts
        token_counts.append(result["token_count"])
        msg_counts.append(result["message_count"])

        # open text file to check for aborts
        text_filename = f"{dir_path}/text_logs/{index}_full.txt"
        with open(text_filename, "r") as text_file:
            text = text_file.read()
        if "[ABORT]" in text:
            num_aborts += 1

    # calculate agreement rate
    agreement_scores_p0 = [p0_array[i] for i in agreement_indices]
    agreement_scores_p1 = [p1_array[i] for i in agreement_indices]
    agreement_scores = agreement_scores_p0 + agreement_scores_p1
    proportion_agreement = len(agreement_scores) / len(full_scores)

    # gather total statistics
    total_stats = {
        "mean": unfiltered_mean,
        "median": unfiltered_median,
        "length_in_msgs": np.mean(msg_counts),
        "length_in_tkns": np.mean(token_counts),
        "abort_rate": num_aborts / len(p0_array),
    }
    
    ############################
    # AGREEMENT STATS #
    ############################

    agreement_mean = np.mean(agreement_scores)
    agreement_median = np.median(agreement_scores)

    if verbose:
        print("TOTAL:")
        print(f"total mean: {unfiltered_mean}")
        print(f"total median: {unfiltered_median}")
        print(f"total average length (msgs): {np.mean(msg_counts)}")
        print(f"total average length (tokens): {np.mean(token_counts)}")
        print(f"rate of abort: {num_aborts / len(p0_array)}")

    # extract message/token counts of games ending in agreement
    agreement_message_counts = [msg_counts[i] for i in agreement_indices]
    agreement_token_counts = [token_counts[i] for i in agreement_indices]

    # calculate the proportion of pareto-optimal results
    num_optimal = 0
    for filename in os.listdir(f"{dir_path}/results"):

        # retrieve results JSON
        results_filename = os.path.join(f"{dir_path}/results", filename)
        with open(results_filename, "r") as results_file:
            result = json.load(results_file)

        # use game index to retrieve the score that we got
        game_index = int(filename[:3])
        p0_score, p1_score = p0_array[game_index], p1_array[game_index]

        try:
            # determine whether game reached pareto-optimality
            is_optimal = utils.isParetoOptimal(
                p0_score,
                p1_score,
                result["counts"],
                result["p0_values"],
                result["p1_values"],
                objective=objective,
            )
            if is_optimal:
                num_optimal += 1

        except:
            print(game_index)
            print(result)

    # gather agreement statistics
    agreement_stats = {
        "mean": agreement_mean,
        "median": agreement_median,
        "length_in_msgs": np.mean(agreement_message_counts),
        "length_in_tkns": np.mean(agreement_token_counts),
        "proportion_agreement": proportion_agreement,
        "proportion_pareto_opt": num_optimal / len(p0_array),
    }

    if verbose:
        print("AGREEMENT:")
        print(f"proportion of agreement: {proportion_agreement}")
        print(f"agreement mean: {agreement_mean}")
        print(f"agreement median: {agreement_median}")
        print(f"agreement average length (msgs): {np.mean(agreement_message_counts)}")
        print(f"agreement average length (tokens): {np.mean(agreement_token_counts)}")
        print(f"proportion of pareto optimal games: {num_optimal / len(p0_array)}")

    ############################
    # ABOVE AVERAGE GAME STATS #
    ############################

    # determine average score
    cutoff = np.mean(p0_array + p1_array)

    # collect the games indices of the games from both players that scored above average
    p0_good_games_indices, p1_good_games_indices = [], []
    for i in range(len(p0_array)):
        if p0_array[i] > cutoff:
            p0_good_games_indices.append(i)

        if p1_array[i] > cutoff:
            p1_good_games_indices.append(i)

    # collect scores based on above avg indices
    p0_above_avg_scores = [p0_array[i] for i in p0_good_games_indices]
    p1_above_avg_scores = [p1_array[i] for i in p1_good_games_indices]

    # calculate statistics
    all_above_avg_scores = p0_above_avg_scores + p1_above_avg_scores
    above_avg_mean = np.mean(all_above_avg_scores)
    above_avg_median = np.median(all_above_avg_scores)

    # calculate proportion of games above avg
    proportion_above_avg = len(all_above_avg_scores) / len(full_scores)

    # extract msg/token lengths
    above_avg_message_counts = [msg_counts[i] for i in agreement_indices]
    above_avg_token_counts = [token_counts[i] for i in agreement_indices]

    # gather above avg statistics
    above_avg_stats = {
        "mean": above_avg_mean,
        "median": above_avg_median,
        "length_in_msgs": np.mean(above_avg_message_counts),
        "length_in_tkns": np.mean(above_avg_token_counts),
        "proportion_above_avg": proportion_above_avg,
    }

    if verbose:
        print("ABOVE AVG:")
        print(f"above avg mean: {above_avg_mean}")
        print(f"above avg median: {above_avg_median}")
        print(f"above avg average length (msgs): {np.mean(above_avg_message_counts)}")
        print(f"above avg average length (tokens): {np.mean(above_avg_token_counts)}")
        print(f"proportion above avg: {proportion_above_avg}")

    # return all of the gathered statistics
    return {
        "total": total_stats,
        "agreement": agreement_stats,
        "above_avg": above_avg_stats,
    }


# code that extracts the context from logs and turns it into a JSON
def parse_game_context(text):
    # dictionary to store the results
    result = {}

    # extracting item counts
    counts_match = re.search(r"Item counts: there are ([\d\s\w,]+)\.", text)
    if counts_match:
        counts_text = counts_match.group(1)
        counts = re.findall(r"(\d+) (\w+)", counts_text)

        # convert count values from strings to integers
        result["counts"] = {item: int(count) for count, item in counts}

    # extracting values for player 0
    p0_values_match = re.search(r"Player 0 values: ([\w\s,]+)\.", text)
    if p0_values_match:
        p0_values_text = p0_values_match.group(1)
        p0_values = dict(re.findall(r"(\w+) are worth (\d+)", p0_values_text))

        # convert point values from strings to integers
        result["p0_values"] = {item: int(value) for item, value in p0_values.items()}

    # extracting values for player 1
    p1_values_match = re.search(r"Player 1 values: ([\w\s,]+)\.", text)
    if p1_values_match:
        p1_values_text = p1_values_match.group(1)
        p1_values = dict(re.findall(r"(\w+) are worth (\d+)", p1_values_text))

        # convert point values from strings to integers
        result["p1_values"] = {item: int(value) for item, value in p1_values.items()}

    return result


def generate_game_contexts(dir_path):
    # takes the path to an iteration's data and generates a directory of game contexts

    # create the folder
    if not os.path.exists(f"{dir_path}/contexts"):
        os.makedirs(f"{dir_path}/contexts")

    # iterate through the full text files
    for filename in os.listdir(f"{dir_path}/text_logs"):
        filepath = os.path.join(f"{dir_path}/text_logs", filename)

        # check if it's a "full.txt",
        if filepath.endswith("full.txt"):
            # get the first 3 lines to get the game context
            with open(filepath, "r") as text_log:
                context_str = "".join([next(text_log) for _ in range(3)])

            # pass into the context parsing function, get a JSON back
            context_json = parse_game_context(context_str)

            # write the JSON to a file in the new folder with the correct name
            index = filename[:3]
            with open(f"{dir_path}/contexts/{index}.json", "w") as context_file:
                json.dump(context_json, context_file)


def create_csv(objective, output_path):
    original_iterations = [
        "data/original/gpt-4",
        "data/original/9DNgwMlN",
        "data/original/9PKMibHw",
        "data/original/9PMs4x7S",
        "data/original/9POn9NJZ",
        "data/original/9PaMUea6",
        "data/original/9PbPTeHK",
    ]

    human_iterations = [
        "data/human/9Oz63Fnh",
        "data/human/9P0ZKcST",
        "data/human/9P2L5ZJB",
        "data/human/9P4MWWOv",
        "data/human/9PaOW5rD",
        "data/human/9PbQfBu5",
    ]

    coop_iterations = [
        "data/cooperative/gpt-4",
        "data/cooperative/9PvRpiad",
        "data/cooperative/9PxbGFd4",
        "data/cooperative/9Pz8kevY",
        "data/cooperative/9Q0sxpON",
    ]

    human_coop_iterations = [
        "data/human_coop/9Oz63Fnh",
        "data/human_coop/9Q4UFafd",
        "data/human_coop/9Q6zHBm4",
        "data/human_coop/9Q8j5r5o",
    ]

    if objective == "orig":
        iterations = original_iterations
    elif objective == "coop":
        iterations = coop_iterations
    elif objective == "human":
        iterations = human_iterations
    elif objective == "human_coop":
        iterations = human_coop_iterations

    data = []

    # iterate through all iterations and append aggregated data to the list
    for iteration_path in iterations:
        results = analyze(iteration_path)

        model_id = iteration_path.split("/")[-1]
        data.append(
            {
                "model id": model_id,
                "total mean": round(results["total"]["mean"], 4),
                "total median": results["total"]["median"],
                "total avg length in tokens": round(
                    results["total"]["length_in_tkns"], 4
                ),
                "total avg length in msgs": round(
                    results["total"]["length_in_msgs"], 4
                ),
                "agreement proportion": round(
                    results["agreement"]["proportion_agreement"], 4
                ),
                "pareto-optimal proportion": round(
                    results["agreement"]["proportion_pareto_opt"], 4
                ),
                "filtered mean": round(results["above_avg"]["mean"], 4),
                "filtered median": round(results["above_avg"]["median"], 4),
                "filtered length in tokens": round(
                    results["above_avg"]["length_in_tkns"], 4
                ),
                "filtered length in msgs": round(
                    results["above_avg"]["length_in_msgs"], 4
                ),
                "proportion filtered": round(
                    results["above_avg"]["proportion_above_avg"], 4
                ),
            }
        )

    # compile in a CSV
    field_names = [
        "model id",
        "total mean",
        "total median",
        "total avg length in tokens",
        "total avg length in msgs",
        "agreement proportion",
        "pareto-optimal proportion",
        "filtered mean",
        "filtered median",
        "filtered length in tokens",
        "proportion filtered",
        "filtered length in msgs",
    ]

    with open(output_path, mode="w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=field_names)
        writer.writeheader()
        for entry in data:
            writer.writerow(entry)


def main():
    parser = argparse.ArgumentParser(description="for generating a CSV of statistics")

    # add arguments
    parser.add_argument("-p", "--path", type=str, help="model to analyze")
    parser.add_argument("-o", "--objective", type=str, help="Game objective")

    # parse the command-line arguments
    args = parser.parse_args()
    
    analyze(args.path, objective=args.objective)


if __name__ == "__main__":
    main()
