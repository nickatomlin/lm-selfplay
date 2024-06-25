import time
import re

class WebNegotiationGame:
    """Tracks game state for the cooperative dialog game."""

    def __init__(
        self,
        item_counts=None,
        user_values=None,
        assistant_values=None,
        objective="self",
    ):
        # env_config should have hyperparameters that are not random

        if item_counts == None:
            self.item_counts = {"book": 1, "hat": 2, "ball": 3}
        else:
            self.item_counts = item_counts

        self.player_values = [None, None]
        if user_values == None:
            self.player_values[0] = {"book": 1, "hat": 3, "ball": 1}
        else:
            self.player_values[0] = user_values
            self.user_values = user_values

        if user_values == None:
            self.player_values[1] = {"book": 2, "hat": 1, "ball": 2}
        else:
            self.player_values[1] = assistant_values
            self.assistant_values = assistant_values


        self.proposals = [None, None]
        self.final_scores = [None, None]

        # flags that track game progression
        self.deal_proposed = False
        self.game_over = False

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
        
        # populate prompt with the prompt file
        with open(self.prompt_path, "r") as prompt_file:
            
            prompt_message = prompt_file.read()
            prompt_message = prompt_message.format(
                book_cnt=self.item_counts["book"],
                hat_cnt=self.item_counts["hat"],
                ball_cnt=self.item_counts["ball"],
                book_val=self.assistant_values["book"],
                hat_val=self.assistant_values["hat"],
                ball_val=self.assistant_values["ball"],
            )
        
        # for the web version
        self.assistant_system_prompt = prompt_message
            

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

    def receive_and_respond(self, user_msg, assistant_agent):
        # in the case of human generalization eval, this function takes in a user's message and returns a valid reply from a model
                
        if user_msg != None:
            # also checks for proposals
            # check for proposal
            if user_msg.strip().startswith("[propose]"):
                # we assume 0 is the user, 1 is the assistant
                self.proposals[0] = self.parse_proposal(user_msg)
                
                # check if this is the second proposal
                if self.deal_proposed == True:
                    self.game_over = True

                else:
                    # first proposal
                    self.deal_proposed = True

                assistant_agent.messages_json.append({
                    "role": "user",
                    "content": "[propose] Proposal made. You must now respond with a proposal of your own.\n",
                    "time": time.time()
                })

                assistant_agent.messages_log.append({
                    "role": "user",
                    "content": "[propose] Proposal made. You must now respond with a proposal of your own.\n"
                })
            
            else:
                # normal case
                # append to the assistant log
                
                assistant_agent.messages_json.append({
                    "role": "user",
                    "content": user_msg,
                    "time": time.time()
                })

                assistant_agent.messages_log.append({
                    "role": "user",
                    "content": user_msg
                })
                
            
        # default response text
        displayed_message = ""
        abort = False
            
        # generate answer ONLY if game is not over
        if not self.game_over:
            response_text = assistant_agent.respond()
            
            # append to your assistant messages
            assistant_agent.messages_json.append({
                "role": "assistant",
                "content": response_text,
                "time": time.time()
            })

            assistant_agent.messages_log.append({
                "role": "assistant",
                "content": response_text,
            })
            
            displayed_message = response_text.strip()
            
            # error check for agent
            # check for abort message
            if response_text.strip() == "[ABORT]":
                self.game_over = True
                abort = True
                displayed_message = "Model errored. Aborting game."

            # check for proposal
            if response_text.strip().startswith("[propose]"):
                # assume assistant is 1
                self.proposals[1] = self.parse_proposal(response_text)
                
                # check if this is the second proposal
                if self.deal_proposed == True:
                    self.game_over = True
                    displayed_message = "[propose] Proposal made."

                else:
                    # first proposal
                    self.deal_proposed = True
                    displayed_message = "[propose] Proposal made. You must now respond with a proposal of your own.\n"
        
        self.calculateFinalScores()
        
        # things to return: response message (if any)
        return {
            "message": displayed_message,
            "game_over": self.game_over,
            "final_scores": {
                "user_score": self.final_scores[0],
                "assistant_score": self.final_scores[1],
                "valid_deal": self.isValidDeal(),
                "abort": abort,
            },
            "user_proposal": self.proposals[0],
            "assistant_proposal": self.proposals[1],
            "message_log": assistant_agent.messages_json # for debugging purposes
        }
        