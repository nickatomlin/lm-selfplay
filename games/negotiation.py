import re
import numpy as np
from transformers import GPT2Tokenizer

class NegotiationGame:
    """Tracks game state for the cooperative dialog game."""

    def __init__(
        self,
        game_index,
        item_counts=None,
        p1_values=None,
        p2_values=None,
        game_log_filename=None,
        objective="self",
    ):
        # env_config should have hyperparameters that are not random
        self.game_index = game_index

        if item_counts == None:
            self.item_counts = {"book": 1, "hat": 2, "ball": 3}
        else:
            self.item_counts = item_counts

        self.player_values = [None, None]
        if p1_values == None:
            self.player_values[0] = {"book": 1, "hat": 3, "ball": 1}
        else:
            self.player_values[0] = p1_values

        if p2_values == None:
            self.player_values[1] = {"book": 2, "hat": 1, "ball": 2}
        else:
            self.player_values[1] = p2_values

        self.proposals = [None, None]
        self.final_scores = [None, None]

        # flags that track game progression
        self.deal_proposed = False
        self.game_over = False

        # logging
        self.game_log_filename = game_log_filename

        # system prompt
        self.objective = objective
        if self.objective == "self":
            self.prompt_path = "prompts/dond.txt"
        elif self.objective == "coop":
            self.prompt_path = "prompts/coop_dond.txt"
        elif self.objective == "comp":
            self.prompt_path = "prompts/comp_dond.txt"
        else:
            raise Exception("invalid objective")

        # write the initial context to the game log
        item_context = "Item counts: there are {book_cnt} books, {hat_cnt} hats, and {ball_cnt} balls.\n"
        value_context = "Player {player_index} values: books are worth {book_val} points, hats are worth {hat_val} points, and balls are worth {ball_val} points.\n"

        f = open(self.game_log_filename, "a")
        f.write(
            item_context.format(
                book_cnt=self.item_counts["book"],
                hat_cnt=self.item_counts["hat"],
                ball_cnt=self.item_counts["ball"],
            )
        )
        f.write(
            value_context.format(
                player_index=0,
                book_val=self.player_values[0]["book"],
                hat_val=self.player_values[0]["hat"],
                ball_val=self.player_values[0]["ball"],
            )
        )
        f.write(
            value_context.format(
                player_index=1,
                book_val=self.player_values[1]["book"],
                hat_val=self.player_values[1]["hat"],
                ball_val=self.player_values[1]["ball"],
            )
        )
        f.write("\n\n")
        f.close()

    def isValidDeal(self):
        p1_cnts = self.proposals[0]
        p2_cnts = self.proposals[1]

        if p1_cnts == None or p2_cnts == None:
            return False

        for k in p1_cnts.keys():
            if p1_cnts[k] + p2_cnts[k] != self.item_counts[k]:
                return False
        return True

    def calculateFinalScores(self):
        # check if proposals are compatible
        if not self.isValidDeal():
            # both players get 0
            self.final_scores = [0, 0]

        else:
            # inner product of a player's value
            p0_score = self.calculateScore(self.player_values[0], self.proposals[0])
            p1_score = self.calculateScore(self.player_values[1], self.proposals[1])

            if self.objective == "self":
                self.final_scores[0] = p0_score
                self.final_scores[1] = p1_score
            elif self.objective == "coop":
                self.final_scores[0] = p0_score + p1_score
                self.final_scores[1] = p0_score + p1_score
            elif self.objective == "comp":
                self.final_scores[0] = p0_score - p1_score
                self.final_scores[1] = p1_score - p0_score

        return

    def calculateScore(self, player_values, player_cnts):
        return sum(x * y for x, y in zip(player_values.values(), player_cnts.values()))

    def isParetoOptimal(self, p1_values, p2_values, p1_cnts, p2_cnts):
        # checks for pareto optimality of proposal given the players' values
        # iterate through all possible allocations
        allocations = []
        for i in range(self.item_counts["book"] + 1):
            for j in range(self.item_counts["hat"] + 1):
                for k in range(self.item_counts["ball"] + 1):
                    allocations.append({"book": i, "hat": j, "ball": k})

        p1_current_utility = self.calculateScore(p1_values, p1_cnts)
        p2_current_utility = self.calculateScore(p2_values, p2_cnts)

        for allocation in allocations:
            isAsGood = False
            isBetter = False

            # decide player counts based on allocation
            p1_cnts = allocation
            p2_cnts = {k: self.item_counts[k] - p1_cnts[k] for k in p1_cnts.keys()}

            # calculate utilities based on allocation
            p1_new_utility = self.calculateScore(self.player_values[0], p1_cnts)
            p2_new_utility = self.calculateScore(self.player_values[0], p1_cnts)

            # check if there is a configuration where both players do as good and at least one player does better
            if (
                p1_new_utility >= p1_current_utility
                and p2_new_utility >= p2_current_utility
            ):
                isAsGood = True
            if p1_new_utility > p1_new_utility or p2_new_utility > p2_current_utility:
                isBetter = True

            if isAsGood and isBetter:
                return False

        # if we don't find a single better allocation
        return True

    def parse_proposal(self, text):
        # assume it looks like (x, y, z)
        # use regex
        counts = re.findall(r"\d+", text)

        return {"book": int(counts[0]), "hat": int(counts[1]), "ball": int(counts[2])}

    def play_game(self, player_agents):

        # turn player chosen uniformly randomly
        turn = 0 if np.random.rand() > 0.5 else 1

        player_prompts = [
            player_agents[0].messages_json,
            player_agents[1].messages_json,
        ]
        logs = [player_agents[0].messages_log, player_agents[1].messages_log]
        messages = []

        # first, append the prefix message
        with open(self.prompt_path, "r") as system_prompt_file:
            system_text = system_prompt_file.read()

        player_prompts[0].append(
            {
                "role": "system",
                "content": system_text.format(
                    book_cnt=self.item_counts["book"],
                    hat_cnt=self.item_counts["hat"],
                    ball_cnt=self.item_counts["ball"],
                    book_val=self.player_values[0]["book"],
                    hat_val=self.player_values[0]["hat"],
                    ball_val=self.player_values[0]["ball"],
                ),
            }
        )

        player_prompts[1].append(
            {
                "role": "system",
                "content": system_text.format(
                    book_cnt=self.item_counts["book"],
                    hat_cnt=self.item_counts["hat"],
                    ball_cnt=self.item_counts["ball"],
                    book_val=self.player_values[1]["book"],
                    hat_val=self.player_values[1]["hat"],
                    ball_val=self.player_values[1]["ball"],
                ),
            }
        )

        logs[0].append(
            {
                "role": "system",
                "content": system_text.format(
                    book_cnt=self.item_counts["book"],
                    hat_cnt=self.item_counts["hat"],
                    ball_cnt=self.item_counts["ball"],
                    book_val=self.player_values[0]["book"],
                    hat_val=self.player_values[0]["hat"],
                    ball_val=self.player_values[0]["ball"],
                ),
            }
        )

        logs[1].append(
            {
                "role": "system",
                "content": system_text.format(
                    book_cnt=self.item_counts["book"],
                    hat_cnt=self.item_counts["hat"],
                    ball_cnt=self.item_counts["ball"],
                    book_val=self.player_values[1]["book"],
                    hat_val=self.player_values[1]["hat"],
                    ball_val=self.player_values[1]["ball"],
                ),
            }
        )

        while not self.game_over:
            # assign turn player and other player
            turn_player = player_agents[turn]
            other_player = player_agents[1 - turn]

            # response should be of the format [message] <text>
            response_text = turn_player.respond()
            messages.append(response_text.strip())

            # append to files

            with open(self.game_log_filename, "a") as full_log:
                full_log.write("Player " + str(turn) + ": " + response_text + "\n")

            # check for abort message
            if response_text.strip() == "[ABORT]":
                self.game_over = True

            # check for proposal
            if response_text.strip().startswith("[propose]"):
                # check if this is the second proposal
                if self.deal_proposed == True:
                    self.proposals[turn] = self.parse_proposal(response_text)
                    self.game_over = True


                else:
                    # first proposal
                    self.proposals[turn] = self.parse_proposal(response_text)
                    self.deal_proposed = True

                assistant_message = response_text.strip()
                user_message = "[propose] Proposal made. You must now respond with a proposal of your own. If you've discussed that you should receive a certain combination of items, this proposal should reflect that. Keep in mind that you and your partner's proposals should be complementary – when added, the elementwise sum should exactly equal the total item counts.\n"

            else:
                # update prompts of each player normally, since this is a regular message
                assistant_message = response_text.strip()
                user_message = response_text.strip()

            player_prompts[turn].append(
                {"role": "assistant", "content": assistant_message}
            )
            player_prompts[1 - turn].append({"role": "user", "content": user_message})

            logs[turn].append({"role": "assistant", "content": assistant_message})
            logs[1 - turn].append({"role": "user", "content": user_message})

            # check if conversation is too long
            if len(messages) >= 50:
                self.game_over = True

            # update turn player
            turn = 1 - turn

        self.calculateFinalScores()

        with open(self.game_log_filename, "a") as full_log:
            full_log.write(f"Player 0 FINAL SCORE: {self.final_scores[0]} \n")
            full_log.write(f"Player 1 FINAL SCORE: {self.final_scores[1]} \n")

        print("Player 1 FINAL SCORE:", self.final_scores[0])
        print("Player 2 FINAL SCORE:", self.final_scores[1])
        print()
        print()

        # track token and message counts
        token_cnt = 0
        tokenizer = GPT2Tokenizer.from_pretrained("gpt2")

        for message in messages:
            tokens = tokenizer.encode(message)
            token_cnt += len(tokens)

        game_outcome = {
            "p0_score": self.final_scores[0],
            "p1_score": self.final_scores[1],
            "p0_log": logs[0],
            "p1_log": logs[1],
            "is_valid_deal": self.isValidDeal(),
            "msg_cnt": len(messages),
            "token_cnt": token_cnt,
        }

        return game_outcome
