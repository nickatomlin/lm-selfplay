
document.addEventListener('DOMContentLoaded', (event) => {
    let mturkQueryString = window.location.href.slice(window.location.href.indexOf("?"));
    let queryParams = new URLSearchParams(mturkQueryString);
    let socket = io({ query: Object.fromEntries(queryParams.entries()) });

    const startGameButton = document.getElementById('start-game-button');
    const mainLayout = document.getElementById('main-layout');
    const itemsDisplayContainer = document.getElementById('items-display-container');
    const instructionsContainer = document.getElementById('instructions-container');
    const chatInterfaceContainer = document.getElementById('chat-interface-container');

    let counts = [0, 0, 0];
    let userVals = [0, 0, 0];
    let initialMessage = "";
    let gameStarted = true;
    let proposalMade = false;
    let gameMode = "";

    let messages = []

    socket.on('connect', () => {
        console.log('Connected to server');
    });

    socket.on('instructions', function(data) {
        // The HTML looks like this:
        // <div id="checkbox">
        //             <!-- Check this box to confirm you have read the instructions and are ready to start -->
        //             <input type="checkbox" id="instructions-checkbox">
        //             <label for="instructions-checkbox">I have read the instructions and am ready to begin playing.</label>
        //         </div>
        //         <button disabled id="start-game-button">Start Game</button>
        const checkbox = document.getElementById('instructions-checkbox');
        const startGameButton = document.getElementById('start-game-button');
        // Enable button on click:
        checkbox.addEventListener('click', () => {
            startGameButton.disabled = !startGameButton.disabled;
            startGameButton.style.opacity = startGameButton.disabled ? 0.5 : 1;
            startGameButton.style.cursor = startGameButton.disabled ? 'not-allowed' : 'pointer';
        });
    });

    socket.on('initialize', (data) => {
        console.log('Game initialized with data:', data);
        counts = data.counts;
        userVals = data.values;
        let gameNum = data.game_num;
        let maxGames = data.max_games;
        let earned = data.earned;
        gameMode = data.game_mode;
        console.log("GAME MODE ", gameMode);

        console.log(counts);
        console.log(userVals);
        startGameButton.style.display = 'none';
        mainLayout.style.display = 'block';
        renderItemsDisplay();
        renderInstructions(gameNum, maxGames, earned);
        renderChatInterface();
    });

    socket.on('response', (data) => {
        console.log('Response from server:', data);
        const newAssistantMessage = { text: data.message, user: 'assistant' };
        messages.push(newAssistantMessage);
        renderMessages();

        // check for proposal made
        if (data.message.includes("[propose]")) {
            proposalMade = true;
            // Disable send message button:
            const sendButton = document.getElementById('send-button');
            sendButton.disabled = true;
            // Add opacity:
            sendButton.style.opacity = 0.5;
            // Prevent clicks on chat textbox:
            const inputTextBox = document.getElementById('input-text-box');
            inputTextBox.disabled = true;
        }

        // check if game ended
        // if (data.game_over) {
        //     const modal = document.getElementById('results-modal');
        //     modal.style.display = 'block';

        //     // const userScoreSpan = document.getElementById('user-score');
        //     // const assistantScoreSpan = document.getElementById('assistant-score');
        //     const userScore = data.user_score;
        //     const assistantScore = data.assistant_score;

        //     let explanation = "";
        //     if (data.final_scores.abort) {
        //         explanation = "The model experienced an error, leading to both players achieving a score of 0."
        //     } else if (data.final_scores.valid_deal) {
        //         explanation = "Congrats! You were able to reach an agreement with your partner."
        //     } else {
        //         explanation = "The model experienced an error, leading to both players achieving a score of 0."
        //     }
    
        //     openResultsModal(userScore, assistantScore, explanation);
        // }
    });

    startGameButton.addEventListener('click', () => {
        console.log('Start game button clicked');
        gameStarted = true;
        // Hide landing page:
        const landingPage = document.getElementById('landing-page');
        landingPage.style.display = 'none';
        const appContainer = document.getElementById('App-header');
        // Set width to 800px:
        appContainer.style.width = '800px';
        socket.emit('initialize_game');
    });

    function renderItemsDisplay() {
        itemsDisplayContainer.innerHTML = `
            <div class="items-container">
                <div class="item-row">
                    ${Array.from({ length: counts[0] }).map(() => `<div class="item"><img src="../static/assets/book.png" alt="book" class="item-image" style="width: 30px; height: 30px;"></div>`).join('')}
                </div>
                <div class="item-row">
                    ${Array.from({ length: counts[1] }).map(() => `<div class="item"><img src="../static/assets/hat.jpeg" alt="hat" class="item-image" style="width: 30px; height: 30px;"></div>`).join('')}
                </div>
                <div class="item-row">
                    ${Array.from({ length: counts[2] }).map(() => `<div class="item"><img src="../static/assets/ball.png" alt="ball" class="item-image" style="width: 30px; height: 30px;"></div>`).join('')}
                </div>
            </div>
        `;
    }

    function renderInstructions(gameNum, maxGames, earned) {
        if (gameMode === "self") {
            reminderText = "Game mode <b style='color: blueviolet;'>competitive</b>. Try to maximize your own score to earn bonus pay!";
        } else if (gameMode === "coop") {
            reminderText = "Game mode: <b style='color: green;'>cooperative</b>. Try to maximize the sum of your and your partner's scores to earn bonus pay!";
        } else if (gameMode === "comp") {
            reminderText = "Game mode: <b style='color: mediumvioletred;'>competitive</b>. Try to maximize your own score while minimizing your partner's score!";
        }

        earned = earned.toFixed(2);
        instructionsContainer.innerHTML = `
            <div id="game-mode-reminder" class="context-item">
                <p id="game-mode-reminder-text">` + reminderText + `</p>
            </div>
            <div class="instructions context-item">
                <p>
                    <b>Your Values</b>
                    <br/><br/>
                    Books: ${userVals[0]}
                    <br/>
                    Hats: ${userVals[1]}
                    <br/>
                    Balls: ${userVals[2]}
                </p>
            </div>
            <div id="partner-value" class="context-item">
            <p>
                <b>Game #${gameNum}</b><br/>(Max Games: ${maxGames})<br/><br/>
                Earned so far: $${earned}
            </p>
            </div>
        `;
    }

    function renderMessages() {
        const chatBox = document.getElementById('chat-box');
        if (chatBox) {
            chatBox.innerHTML = '';
            messages.forEach((message) => {
                // Strip out the [message] and [propose] tags
                message.text = message.text.replace(/\[message\] /g, '');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${message.user === 'assistant' ? 'left' : 'right'}`;
                messageDiv.textContent = message.text;
                chatBox.appendChild(messageDiv);
            });
        }

        const proposeButton = document.getElementById('propose-button');
        // Disable propose button if no messages sent so far:
        proposeButton.disabled = messages.length < 2;
        proposeButton.style.opacity = proposeButton.disabled ? 0.5 : 1;
        proposeButton.style.cursor = proposeButton.disabled ? 'not-allowed' : 'pointer';
        // If disabled, add an explanation on hover:
        if (proposeButton.disabled) {
            proposeButton.title = "You must send a message before making a proposal.";
        }
    }

    function renderChatInterface() {
        console.log("RENDER CHAT INTERFACE");
        chatInterfaceContainer.innerHTML = `
            <div class="chat-container">
                <div class="chat-box" id="chat-box"></div>
                <form id="chat-form">
                    <div class="input-container">
                        <input class="input-text-box" type="text" id="input-text-box" placeholder="Type your message here..." />
                        <button class="chat-button" id="send-button" type="submit">Send</button>
                        <button class="chat-button" id="propose-button" type="button">Make a Proposal</button>
                    </div>
                </form>
            </div>
        `;

        const chatBox = document.getElementById('chat-box');
        const inputTextBox = document.getElementById('input-text-box');
        const sendButton = document.getElementById('send-button');
        const proposeButton = document.getElementById('propose-button');
        const chatForm = document.getElementById('chat-form');
        
        const submitButton = document.getElementById("submit-button");

        chatForm.addEventListener('submit', (event) => {
            console.log("CHATFORM LISTENER");
            event.preventDefault(); // Prevent the default form submission behavior
            const input = inputTextBox.value.trim();
            if (input) {
                const newUserMessage = { text: input, user: 'user' };
                messages.push(newUserMessage);
                socket.emit('user_message', "[message] " + input);

                inputTextBox.value = '';
                renderMessages();
            }
        });

        sendButton.addEventListener('click', () => {
            console.log("BUTTON!");
            // const modal = document.getElementById('propose-modal');
            // modal.style.display = 'block';
        });

        proposeButton.addEventListener('click', () => {
            const modal = document.getElementById('propose-modal');
            populateDropdowns();
            modal.style.display = 'block';
        });

        // Disable propose button if no messages sent so far:
        proposeButton.disabled = messages.length < 2;
        proposeButton.style.opacity = proposeButton.disabled ? 0.5 : 1;
        proposeButton.style.cursor = proposeButton.disabled ? 'not-allowed' : 'pointer';
        // If disabled, add an explanation on hover:
        if (proposeButton.disabled) {
            proposeButton.title = "You must send a message before making a proposal.";
        }

        // submitButton.addEventListener('click', () => {
        //     const newUserMessage = { 
        //         text: "[propose] Proposal made. You must now respond with a proposal of your own.\n", 
        //         user: 'user' 
        //     };
        //     messages.push(newUserMessage);
        //     socket.emit('user_message', "[message] " + input);
        // })

        if (initialMessage) {
            messages.push({ text: initialMessage, user: 'assistant' });
            renderMessages();
        }
    }
    // Populate dropdown options for the modal
    const modal = document.getElementById('propose-modal');
    const closeModal = document.getElementById('close-modal');
    const form = document.getElementById('propose-form');

    const booksSelect = document.getElementById('books-select');
    const hatsSelect = document.getElementById('hats-select');
    const ballsSelect = document.getElementById('balls-select');

    function createOptions(count) {
        const options = [];
        for (let i = 0; i <= count; i++) {
            const option = document.createElement('option');
            option.value = i;
            option.textContent = i;
            options.push(option);
        }
        return options;
    }

    function populateSelect(selectElement, count) {
        const options = createOptions(count);
        // Clear existing options
        selectElement.innerHTML = '';
        options.forEach(option => selectElement.appendChild(option));
    }

    function populateDropdowns() {
        console.log('Populating dropdowns...');

        const booksCount = counts[0]; // Example count, replace with dynamic data
        const hatsCount = counts[1]; // Example count, replace with dynamic data
        const ballsCount = counts[2]; // Example count, replace with dynamic data

        populateSelect(booksSelect, booksCount);
        populateSelect(hatsSelect, hatsCount);
        populateSelect(ballsSelect, ballsCount);
    }

    closeModal.addEventListener('click', () => {
        modal.style.display = 'none';
    });

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        const selectedBooks = Number(booksSelect.value);
        const selectedHats = Number(hatsSelect.value);
        const selectedBalls = Number(ballsSelect.value);

        const selections = {
            books: selectedBooks,
            hats: selectedHats,
            balls: selectedBalls
        };

        console.log('User selected:', selections);
        modal.style.display = 'none';
        // Call your onSubmit function here with selections

        // check if proposal already made
        let proposal_text = "[propose] Proposal made. You must now respond with a proposal of your own.\n";
        if (proposalMade) {
            proposal_text = "[propose] Proposal made.";
        }
        // for (let i = 0; i < messages.length; i++) {
        //     let message_text = messages[i]["text"];
        //     if (message_text.includes("[propose]")) {
        //         proposal_text = "[propose] Proposal made.";
        //         proposal_made = true;
        //     }
        // }


        const newUserMessage = { 
            text: proposal_text, 
            user: 'user' 
        };

        messages.push(newUserMessage);
        renderMessages();
        console.log("EMIT PROPOSAL");
        socket.emit('user_message', "[propose] (" + selectedBooks + " books, " + selectedHats + " hats, " + selectedBalls + " balls)");
    });

    // Function to open the modal
    function openModal() {
        modal.style.display = 'block';
        populateDropdowns();
    }

    // Example function to open the modal (replace with your own logic)
    // document.getElementById('propose-button').addEventListener('click', openModal);


    socket.on('game_over', (data) => {
        console.log("HELLO PLEASE");
        console.log(data);

        const userScore = data.final_scores.user_score;
        const assistantScore = data.final_scores.assistant_score;
        console.log("USER SCORE", userScore);
        console.log("ASSISTANT SCORE", assistantScore);

        let explanation = "";
        if (data.final_scores.abort) {
            explanation = "Unfortunately, the model encountered an error, so neither you or your partner received any points for this game. This happens occasionally and isn’t your fault — you will be paired with a different random model in the next game. "
        } else if (data.final_scores.valid_deal) {
            explanation = "Congrats! You were able to reach an agreement with your partner."
        } else {
            explanation = "You and your partner submitted non-complementary proposals (proposals that did not add up to exactly the item counts), so neither player scored points. Please make sure to discuss the complete details of your proposal with your partner in chat before submitting. If you’ve already done this, it’s possible that the model made a mistake and the error wasn’t your fault."
        }

        const bonusPay = data.bonus_pay;
        const gameBonus = data.game_bonus;

        const numGamesCompleted = data.num_games_completed;
        const maxGames = data.max_games;
        const maxGamesReached = numGamesCompleted >= maxGames;

        openResultsModal(userScore, assistantScore, explanation, gameBonus, bonusPay, numGamesCompleted, maxGamesReached);

        // Disable send message and proposal buttons:
        const sendButton = document.getElementById('send-button');
        const proposeButton = document.getElementById('propose-button');
        sendButton.disabled = true;
        proposeButton.disabled = true;
        // Add opacity:
        sendButton.style.opacity = 0.5;
        proposeButton.style.opacity = 0.5;
        // Prevent clicks on chat textbox:
        const inputTextBox = document.getElementById('input-text-box');
        inputTextBox.disabled = true;
    });

    function keepPlaying() {
        socket.emit('keep_playing');
        const resultsModal = document.getElementById('results-modal');
        resultsModal.style.display = 'none';
        messages = [];
    }

    window.keepPlaying = keepPlaying;

    function openResultsModal(userScore, assistantScore, explanation, gameBonus, bonusPay, numGamesCompleted, maxGamesReached) {
        const resultsModal = document.getElementById('results-modal');
        const userScoreSpan = document.getElementById('user-score');
        const assistantScoreSpan = document.getElementById('assistant-score');
        const explanationSpan = document.getElementById('explanation');

        console.log("Scores: ", userScore, assistantScore);
        userScoreSpan.textContent = userScore;
        assistantScoreSpan.textContent = assistantScore;
        bonusPay = bonusPay.toFixed(2);
        gameBonus = gameBonus.toFixed(2);
        const paymentText = "You received a total of $" + gameBonus + " for this game.";
        const statusText = "You have completed " + numGamesCompleted + " games and earned a total of $" + bonusPay;
        explanationSpan.innerHTML = explanation + " " + paymentText + "<br><br>" + statusText;
        
        // "You have completed " + numGamesCompleted +" games so far. Your current bonus payment for this HIT is $" + bonusPay + ".";

        resultsModal.style.display = 'block';
        // Results modal elements
        // const closeButton = document.getElementById('close-results-modal');
        // closeButton.addEventListener('click', () => {
        //     resultsModal.style.display = 'none';
        // });

        // Keep playing button:
        if (!maxGamesReached) {
            continue_button = `<button type="button" class="btn btn-primary modal-button" onClick="window.keepPlaying()">Keep Playing</button>`;
            explanationSpan.innerHTML += " so far. You can keep playing to earn more money, or end the HIT now. Once you complete the HIT, you should expect to receive bonus payments within 24 hours."
        } else {
            continue_button = "";
            explanationSpan.innerHTML += ". You have reached the maximum number of games for this HIT. Once you click the complete HIT button, you should expect to receive bonus payments within 24 hours. Thank you for participating in our research!"
            // Set left margin to 0 for modal-button class:
            // document.getElementById('end-game').style.marginLeft = "0px";
        }
        // Complete HIT button:
        end_button = `<div id="end-game">
            <form id="end-game-form" action=${queryParams.get('turkSubmitTo') + '/mturk/externalSubmit'} method="POST" >
            <input id="assignmentId" name="assignmentId" type="hidden" value=${queryParams.get('assignmentId')}>
            <input id="bonus" name="bonus" type="hidden" value=${bonusPay}>
            <input id="dummy" name="dummy" type="hidden" value="none">
            <button type="button" class="btn btn-primary modal-button" onClick="submitEndForm()">Complete HIT ($${bonusPay})</button>
            </form>
        </div>`;
        document.getElementById('close-results-modal').innerHTML = continue_button + end_button;
    }
});

function submitEndForm() {    
    // Manually submit form to mturk, send event to our socket first
    // let form = $("#end-game-form").serializeArray();
    // $("#end-game-form").submit();
    // Without jquery:
    let form = document.getElementById("end-game-form");
    form.submit();
}