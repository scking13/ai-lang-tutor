document.addEventListener('DOMContentLoaded', () => {
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const chatMessagesDiv = document.getElementById('chat-messages');
    const feedbackContentDiv = document.getElementById('feedback-content');
    const nativeLangSelect = document.getElementById('native-lang');
    const targetLangSelect = document.getElementById('target-lang');
    const updateSettingsButton = document.getElementById('update-settings-button');

    const getDifficulty = () => document.querySelector('input[name="difficulty"]:checked').value;

    const BOT_ERROR_PLACEHOLDER = "Sorry, I can't respond right now. The AI service seems to be unavailable. Please try again later.";
    const FEEDBACK_ERROR_PLACEHOLDER = "No feedback available at the moment. The AI service might be temporarily down.";
    const SERVICE_NOT_CONFIGURED_CHAT_MESSAGE = "Sorry, I can't respond right now. The service is not configured.";
    const SERVICE_NOT_CONFIGURED_FEEDBACK_MESSAGE = "No feedback available at the moment. The service is not configured.";

    // Function to display a message in the chat area
    function displayMessage(sender, messageText, type = 'chat', isLoading = false) {
        const messageDiv = document.createElement('p');
        messageDiv.classList.add('message');
        if (isLoading) {
            messageDiv.classList.add('loading-message');
        }

        if (sender === 'user') {
            messageDiv.classList.add('user-message');
            messageDiv.textContent = `You: ${messageText}`;
        } else if (sender === 'bot') {
            messageDiv.classList.add('bot-message');
            messageDiv.textContent = `Bot: ${messageText}`;
            // Check for known error messages from backend to style them differently if needed
            if (messageText === BOT_ERROR_PLACEHOLDER || messageText === SERVICE_NOT_CONFIGURED_CHAT_MESSAGE) {
                messageDiv.classList.add('error-message'); // Add an error class for styling
            }
        } else if (type === 'feedback' && sender === 'feedback') { 
            messageDiv.classList.add('feedback-message'); 
            messageDiv.innerHTML = `<strong>Feedback:</strong><br>${messageText.replace(/\n/g, '<br>')}`;
            if (messageText === FEEDBACK_ERROR_PLACEHOLDER || messageText === SERVICE_NOT_CONFIGURED_FEEDBACK_MESSAGE) {
                messageDiv.classList.add('error-message');
            }
        }
        chatMessagesDiv.appendChild(messageDiv);
        chatMessagesDiv.scrollTop = chatMessagesDiv.scrollHeight;
        return messageDiv; // Return the element if it needs to be removed (e.g., loading message)
    }

    // Function to display feedback in the feedback panel
    function displayFeedback(feedbackText) {
        feedbackContentDiv.innerHTML = ''; // Clear previous feedback
        const feedbackP = document.createElement('p');
        feedbackP.innerHTML = feedbackText.replace(/\n/g, '<br>');
        if (feedbackText === FEEDBACK_ERROR_PLACEHOLDER || feedbackText === SERVICE_NOT_CONFIGURED_FEEDBACK_MESSAGE) {
            feedbackP.classList.add('error-message'); // Add an error class for styling
        }
        feedbackContentDiv.appendChild(feedbackP);
    }
    
    function displayLogEntry(item) {
        if (item.type === 'chat') {
            displayMessage('user', item.user);
            displayMessage('bot', item.bot);
        } else if (item.type === 'feedback') {
            // Feedback is now displayed in its own panel by /send_message response handling.
            // For history, we can choose to display it, or just ensure the latest feedback is shown.
            // For simplicity, the last feedback from history would set the feedback panel.
            displayFeedback(item.feedback);
        }
    }

    async function loadHistory() {
        let loadingMessage = displayMessage('bot', 'Loading history...', 'system', true);
        try {
            const response = await fetch('/get_history');
            chatMessagesDiv.removeChild(loadingMessage); // Remove loading message

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            
            chatMessagesDiv.innerHTML = ''; 
            feedbackContentDiv.innerHTML = '<p>Previous feedback will appear here.</p>';

            if (data.history && data.history.length > 0) {
                data.history.forEach(item => {
                    displayLogEntry(item);
                });
            } else {
                // Check gemini_configured status passed from server (available globally via script tag if needed)
                // For now, checking if the send button is disabled as a proxy
                if (sendButton.disabled) { // Assuming sendButton is disabled if Gemini not configured
                     displayMessage('bot', SERVICE_NOT_CONFIGURED_CHAT_MESSAGE);
                } else {
                     displayMessage('bot', "Welcome! Select your languages and difficulty, then send a message to begin.");
                }
            }

            if (data.settings) {
                nativeLangSelect.value = data.settings.native_lang || 'English';
                targetLangSelect.value = data.settings.target_lang || 'Spanish';
                document.querySelectorAll('input[name="difficulty"]').forEach(radio => {
                    radio.checked = radio.value === (data.settings.difficulty || 'Beginner');
                });
            }

        } catch (error) {
            console.error('Error loading history:', error);
            if (loadingMessage && chatMessagesDiv.contains(loadingMessage)) {
                chatMessagesDiv.removeChild(loadingMessage);
            }
            displayMessage('bot', 'Error loading chat history. Please refresh the page.');
        }
    }

    sendButton.addEventListener('click', async () => {
        const messageText = messageInput.value.trim();
        if (!messageText) return;

        const nativeLang = nativeLangSelect.value;
        const targetLang = targetLangSelect.value;
        const difficulty = getDifficulty();

        displayMessage('user', messageText);
        messageInput.value = ''; 
        
        sendButton.disabled = true;
        sendButton.textContent = 'Thinking...';
        let thinkingMessage = displayMessage('bot', 'Bot is thinking...', 'system', true);

        try {
            const response = await fetch('/send_message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: messageText,
                    native_lang: nativeLang,
                    target_lang: targetLang,
                    difficulty: difficulty,
                }),
            });

            if (thinkingMessage && chatMessagesDiv.contains(thinkingMessage)) {
                chatMessagesDiv.removeChild(thinkingMessage);
            }

            if (!response.ok) {
                // Try to parse error from backend, otherwise throw generic
                let errorMsg = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || errorMsg;
                } catch (e) { /* Ignore if response is not json */ }
                throw new Error(errorMsg);
            }

            const data = await response.json();

            if (data.error) { // Check for explicit error key from server (though current server.py doesn't use this)
                displayMessage('bot', data.error);
                displayFeedback('Error generating feedback.');
            } else {
                displayMessage('bot', data.bot_response);
                if (data.feedback) {
                    displayFeedback(data.feedback);
                } else {
                    displayFeedback(FEEDBACK_ERROR_PLACEHOLDER); // Or a "No feedback provided" message
                }
            }

        } catch (error) {
            console.error('Error sending message:', error);
            if (thinkingMessage && chatMessagesDiv.contains(thinkingMessage)) { // Ensure thinking message is removed on error too
                chatMessagesDiv.removeChild(thinkingMessage);
            }
            displayMessage('bot', BOT_ERROR_PLACEHOLDER); // Display standard bot error
            displayFeedback('Could not get feedback due to an error.'); // Display feedback error
        } finally {
            sendButton.disabled = false;
            sendButton.textContent = 'Send';
        }
    });
    
    messageInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter' && !sendButton.disabled) {
            event.preventDefault(); 
            sendButton.click();
        }
    });

    updateSettingsButton.addEventListener('click', async () => {
        const nativeLang = nativeLangSelect.value;
        const targetLang = targetLangSelect.value;
        const difficulty = getDifficulty();

        // You could add visual feedback for settings update too
        updateSettingsButton.textContent = 'Updating...';
        updateSettingsButton.disabled = true;

        try {
            const response = await fetch('/update_settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    native_lang: nativeLang,
                    target_lang: targetLang,
                    difficulty: difficulty,
                }),
            });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            // console.log('Settings updated:', data.settings);
            // Optionally, display a success message briefly
            alert('Settings updated successfully!'); // Simple alert for now
        } catch (error) {
            console.error('Error updating settings:', error);
            alert('Failed to update settings.'); // Simple alert for error
        } finally {
            updateSettingsButton.textContent = 'Update Settings';
            updateSettingsButton.disabled = false;
        }
    });

    loadHistory();
});
