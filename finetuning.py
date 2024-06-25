import utils as utils
import argparse

def main():
    # parse CLI for objective and for model
    parser = argparse.ArgumentParser(
        description="A script that demonstrates argparse usage"
    )

    # add arguments
    parser.add_argument("-d", "--dir", type=str, help="Data directory")
    parser.add_argument("-o", "--objective", type=str, help="Objective")
    parser.add_argument("-f", "--filter", type=str, help="Filter")
    parser.add_argument("-m", "--model_id", type=str, help="Model to train")
    parser.add_argument("-s", "--suffix", type=str, help="Output model suffix")

    parser.add_argument("-u", "--human", default=False, type=bool, help="human data")

    # parse the command-line arguments
    args = parser.parse_args()

    dir_path = args.dir
    filter = args.filter
    model_to_train = args.model_id
    model_suffix = args.suffix
    objective = args.objective

    if args.human == True:
        utils.create_finetuning_job(
            model_suffix, f"data/human_init_data/human_data.jsonl", model_to_train
        )
        return

    is_comp = objective == "comp"

    utils.concatenate(dir_path, filter, is_comp)
    utils.create_finetuning_job(
        model_suffix, f"{dir_path}/game_data.jsonl", model_to_train
    )


if __name__ == "__main__":
    main()
