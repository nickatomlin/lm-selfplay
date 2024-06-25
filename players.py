from dotenv import load_dotenv
from openai import OpenAI
import os
import re

class HumanPlayer():

    def __init__(self, game, vals):
        self.game = game
        self.vals = vals
        self.messages_json = []
        self.messages_log = []

    def respond(self):
        response_text = input()
        return response_text


class LLMPlayer():
    def __init__(
        self,
        game,
        vals,
        log_filename,
        temperature=1,
        selfplay=True,
        prompt_path="prompts/dond.txt",
    ):

        self.game = game
        self.temperature = temperature
        self.selfplay = selfplay
        self.messages_json = []
        self.messages_log = []

        # logging
        self.player_log_filename = log_filename

        # write initial context to log
        value_context = "Books are worth {book_val} points, hats are worth {hat_val} points, and balls are worth {ball_val} points.\n"
        f = open(self.player_log_filename, "a")
        f.write(
            value_context.format(
                book_val=vals["book"],
                hat_val=vals["hat"],
                ball_val=vals["ball"],
            )
        )
        f.write("\n\n")
        f.close()

    def respond(self):
        # generate player output
        response_text = self.generate_response()
        
        # error checking loop
        is_valid_output, error_msg = self.is_valid_output(response_text)

        err_cnt = 0
        while not is_valid_output:
            # add intermediate text to the prompt (aka not the final message that gets sent, which happens in the game function)

            self.messages_json.append(
                {
                    "role": "assistant",
                    "content": response_text,
                }
            )

            self.messages_json.append(
                {
                    "role": "user",
                    "content": f"An error occurred. Please resend the previous message with the following correction, without indicating in any way that you have made a correction to a prior message: \n \"{error_msg}\" "
                }
            )

            # write the error message to the log
            f = open(self.player_log_filename, "a")
            f.write("Error: " + error_msg + "\n")
            f.close()

            # check for whether we abort or not
            err_cnt += 1
            if err_cnt >= 5:
                return "[ABORT]"

            # regenerate a response
            response_text = self.generate_response()
            is_valid_output, error_msg = self.is_valid_output(response_text)

        if not self.selfplay:
            if response_text.strip().startswith("[propose]"):
                print(
                    "[propose] Proposal made. You must now respond with a proposal of your own. If you've discussed that you should receive a certain combination of items, this proposal should reflect that. Keep in mind that you and your partner's proposals should be complementary.\n"
                )
            else:
                print(response_text)

        return response_text

    def is_valid_message(self, msg):
        # check for redundant message or propose
        if "[message]" in msg[10:] or "[propose]" in msg[10:]:
            return (
                False,
                "Do not include any mentions of [message] or [propose] after the initial prefix. Please just send a single message, beginning with [message].",
            )

        if not msg.strip().startswith("[message]"):
            return False, "Messages must begin with [message]."
        
        if self.game.deal_proposed:
            return (
                False,
                "Opponent's proposal must be followed by a proposal of your own. Please send a proposal, beginning with [propose].",
            )

        return True, ""

    def is_valid_proposal(self, msg):
        # check if any messages have been sent yet
        if len(self.messages_log) == 1:
            return (
                False,
                "Please begin the dialogue by discussing how you'll divide the items before submitting a private proposal.",
            )

        # what we want: "[propose] (1 books, 3 hats, 2 balls)"
        if not msg.strip().startswith("[propose]"):
            return (
                False,
                "Proposals must begin with [propose]. You may resubmit the exact same proposal but with [propose] as a prefix.",
            )

        proposal = msg.split("[propose]")[-1].strip()

        # assert that we refer to all of the items and in the correct order
        book_idx = proposal.find("book")
        hat_idx = proposal.find("hat")
        ball_idx = proposal.find("ball")

        # check that we found all indices and they are in the correct order
        if not (-1 < book_idx < hat_idx < ball_idx):
            return (
                False,
                "Item counts must be sequenced in the following order: books, hats, and then balls.",
            )

        # get the quantities as integers (not strings)
        quantities = [int(x) for x in re.findall(r"\d+", proposal)]

        # make sure we have only three integers in our proposal message
        if len(quantities) != 3:
            return (
                False,
                "There should only be counts for three items in your proposal: books, hats, and balls.",
            )

        # make sure the three quantities are within valid range, given the game item counts
        if not (
            0 <= quantities[0] <= self.game.item_counts["book"]
            and 0 <= quantities[1] <= self.game.item_counts["hat"]
            and 0 <= quantities[2] <= self.game.item_counts["ball"]
        ):
            return (
                False,
                "Item counts suggested are invalid based on game context; some of your proposal's item counts are greater than total items available.",
            )
        return True, ""

    def is_valid_output(self, response_text):
        is_valid, error_msg = True, ""
        if response_text.strip().startswith("[propose]"):
            is_valid, error_msg = self.is_valid_proposal(response_text)

        elif response_text.strip().startswith("[message]"):
            is_valid, error_msg = self.is_valid_message(response_text)
        else:
            return (
                False,
                "Your output should either begin with [message] or a [propose].",
            )
        return is_valid, error_msg


class ClosedSourceChatPlayer(LLMPlayer):
    def __init__(
        self,
        game,
        vals,
        log_filename,
        temperature=1,
        selfplay=True,
        model="gpt-3.5-turbo-0125",
        prompt_path="prompts/dond.txt",
    ):
        super().__init__(game, vals, log_filename, temperature, selfplay, prompt_path)
        self.model = model

    def generate_response(self):
        load_dotenv()
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            organization=os.getenv("OPENAI_ORG_ID"),
        )

        # generate output using API
        response = client.chat.completions.create(
            model=self.model,
            messages=self.messages_json,
            temperature=self.temperature,
            max_tokens=200,
        )

        full_output = response.choices[0].message.content.strip()

        # append full output to the log
        f = open(self.player_log_filename, "a")
        f.write(full_output + "\n")
        f.close()

        # truncate if any [END]'s were generated
        if "[END]" in full_output:
            response_text = full_output.split("[END]")[0].strip()
        elif "[end]" in full_output:
            response_text = full_output.split("[end]")[0].strip()
        else:
            response_text = full_output.strip()
            
        # if proposal, we cut off anything after the first line
        if response_text.strip().startswith("[propose]"):
            response_text = response_text.split("\n")[0]

        return response_text

