document.addEventListener('DOMContentLoaded', () => {
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const chatMessagesDiv = document.getElementById('chat-messages');
    const feedbackContentDiv = document.getElementById('feedback-content');
    const nativeLangSelect = document.getElementById('native-lang');
    const targetLangSelect = document.getElementById('target-lang');
    const difficultySelect = document.getElementById('difficulty'); // Added for dropdown
    const toneSelect = document.getElementById('tone'); // Added for tone dropdown
    const updateSettingsButton = document.getElementById('update-settings-button');

    const getDifficulty = () => difficultySelect.value; // Updated to read from select
    const getTone = () => toneSelect.value; // Added to read from tone select

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
                difficultySelect.value = data.settings.difficulty || 'Beginner'; // Updated for dropdown
                toneSelect.value = data.settings.tone || 'Serious'; // Added for tone
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
        const currentTone = getTone(); // Get current tone

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
                    tone: currentTone, // Added tone to payload
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
        const currentTone = getTone(); // Get current tone

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
                    tone: currentTone, // Added tone to payload
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

    // --- Speech Recognition and WebSocket VUI Functions ---
    // This section handles client-side logic for:
    // 1. Accessing the user's microphone.
    // 2. Recording audio via MediaRecorder.
    // 3. Establishing a WebSocket connection to the speech service backend.
    // 4. Sending recorded audio chunks over the WebSocket.
    // 5. Receiving messages (transcriptions, bot responses, status, errors) from the backend.
    // 6. Updating the UI with transcriptions, bot text, and playing bot audio.
    // 7. Managing UI state (e.g., button text, feedback messages).

    // Global variables for speech functionality
    const speechToggleButton = document.getElementById('speech-toggle-button'); // Button to start/stop speech input.
    const liveTranscriptionDiv = document.getElementById('live-transcription'); // Div to display live transcription and status.
    const botAudioOutput = document.getElementById('bot-audio-output'); // Hidden <audio> element for playing bot's audio responses.

    let mediaRecorder;      // MediaRecorder instance for capturing audio.
    let audioChunks = [];   // Array to store audio chunks, though direct sending is prioritized.
    let speechWebSocket;    // WebSocket instance for communication with the speech service.
    let isRecording = false; // Boolean flag to track if audio recording is currently active.
    const SPEECH_WEBSOCKET_URL = `ws://${window.location.hostname}:8000/`; // URL for the speech WebSocket server.

    /**
     * Toggles the speech recognition state (starts or stops recording).
     * Manages UI updates for the speech toggle button.
     */
    function handleSpeechToggle() {
        console.log('[JS] handleSpeechToggle: Called. isRecording:', isRecording);
        if (!speechToggleButton) {
            console.error("[JS] handleSpeechToggle: Speech toggle button not found."); // Added prefix
            return;
        }
        if (isRecording) {
            stopSpeechRecognition();
        } else {
            startSpeechRecognition();
        }
    }

    /**
     * Initiates speech recognition:
     * 1. Requests microphone access.
     * 2. Establishes a WebSocket connection.
     * 3. Sets up MediaRecorder to capture and send audio.
     * 4. Defines handlers for WebSocket messages, errors, and closure.
     */
    async function startSpeechRecognition() {
        console.log('[JS] startSpeechRecognition: Attempting to start.');
        if (!liveTranscriptionDiv || !speechToggleButton) return;

        // Clear previous messages and indicate connection attempt.
        liveTranscriptionDiv.innerHTML = '';
        liveTranscriptionDiv.textContent = 'Requesting microphone access...';

        try {
            // Request access to the user's microphone.
            console.log('[JS] startSpeechRecognition: Requesting microphone access...');
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            console.log('[JS] startSpeechRecognition: Microphone access granted.');
            liveTranscriptionDiv.textContent = 'Microphone connected. Opening WebSocket...';

            // Initialize WebSocket connection to the speech service.
            console.log('[JS] startSpeechRecognition: Initializing WebSocket to:', SPEECH_WEBSOCKET_URL);
            speechWebSocket = new WebSocket(SPEECH_WEBSOCKET_URL);

            // --- WebSocket Event Handlers ---

            // Called when the WebSocket connection is successfully opened.
            speechWebSocket.onopen = () => {
                console.log('[JS] WebSocket.onopen: Connection established. MediaRecorder setup starting.');
                liveTranscriptionDiv.textContent = 'Speech service connected. Recording...';
                speechToggleButton.textContent = 'Stop Speech';
                isRecording = true;

                // Initialize MediaRecorder with the microphone stream.
                mediaRecorder = new MediaRecorder(stream);

                // Event handler for when MediaRecorder has new audio data available.
                mediaRecorder.ondataavailable = event => {
                    try {
                        console.log('[JS] MediaRecorder.ondataavailable: Audio data available (size:', event.data.size, 'bytes). Sending via WebSocket.');
                        if (event.data.size > 0 && speechWebSocket && speechWebSocket.readyState === WebSocket.OPEN) {
                            speechWebSocket.send(event.data); // Send audio data to backend via WebSocket.
                        }
                    } catch (error) {
                        console.error('[JS] MediaRecorder.ondataavailable: Error sending data via WebSocket.', error);
                    }
                };

                // Event handler for when MediaRecorder stops.
                mediaRecorder.onstop = () => {
                    console.log('[JS] MediaRecorder.onstop: Recording stopped. Microphone stream tracks will be stopped.');
                    // Stop all tracks on the stream to release the microphone.
                    if (stream) {
                        stream.getTracks().forEach(track => track.stop());
                        console.log("[JS] MediaRecorder.onstop: Microphone stream tracks stopped."); // Added prefix
                    }
                };

                audioChunks = []; // Clear any previously stored chunks.
                // Start recording, sending data in timeslices (e.g., every 1 second).
                mediaRecorder.start(1000);
                console.log('[JS] WebSocket.onopen: MediaRecorder started.');
            };

            // Called when a message is received from the WebSocket server.
            speechWebSocket.onmessage = event => {
                console.log('[JS] WebSocket.onmessage: Raw data received:', event.data);
                try {
                    const message = JSON.parse(event.data); // Expecting JSON messages.
                    console.log('[JS] WebSocket.onmessage: Parsed message:', message);

                    // Handle different types of messages from the backend.
                    if (message.type === 'input_transcription') {
                        console.log('[JS] WebSocket.onmessage: Handling input_transcription:', message.data);
                        liveTranscriptionDiv.textContent = `You said: ${message.data}`;
                    } else if (message.type === 'bot_response_text') {
                        console.log('[JS] WebSocket.onmessage: Handling bot_response_text:', message.data);
                        displayMessage('bot', message.data);
                        if (message.data && message.data.trim() !== "") {
                            const utterance = new SpeechSynthesisUtterance(message.data);
                            window.speechSynthesis.speak(utterance);
                        }
                    } else if (message.type === 'bot_response_audio') {
                        console.log('[JS] WebSocket.onmessage: Handling bot_response_audio. Base64 length:', message.data ? message.data.length : 'N/A');
                        const audioBase64 = message.data;
                        if (audioBase64) {
                            try {
                                const audioBlob = base64ToBlob(audioBase64, 'audio/mpeg'); // Assuming MPEG audio.
                                const audioUrl = URL.createObjectURL(audioBlob);
                                botAudioOutput.src = audioUrl;
                                console.log('[JS] WebSocket.onmessage: Playing bot audio response.');
                                botAudioOutput.play()
                                    .then(() => console.log("[JS] WebSocket.onmessage: Bot audio playback started.")) // Added prefix
                                    .catch(e => {
                                        console.error("[JS] WebSocket.onmessage: Error playing bot audio:", e); // Added prefix
                                        displayMessage('bot', '[Error playing audio response. Text response (if any) is above.]');
                                        liveTranscriptionDiv.textContent = 'Error playing bot audio.';
                                    });
                                displayMessage('bot', '[Playing audio response...]');
                            } catch (error) {
                                console.error('[JS] WebSocket.onmessage: Error processing/playing bot_response_audio:', error);
                                displayMessage('bot', '[Error playing audio response. Text response (if any) is above.]');
                                liveTranscriptionDiv.textContent = 'Error playing bot audio.';
                            }
                        }
                    } else if (message.type === 'status') {
                        console.log('[JS] WebSocket.onmessage: Handling status:', message.data);
                        if (message.data === 'disconnected' && isRecording) {
                           liveTranscriptionDiv.textContent = 'Speech service disconnected.';
                           stopSpeechRecognition();
                        } else if (message.data === 'connected') {
                            liveTranscriptionDiv.textContent = 'Speech service connected. Recording...';
                        } else {
                            liveTranscriptionDiv.textContent = `Status: ${message.data}`;
                        }
                    } else if (message.type === 'error') {
                        console.error('[JS] WebSocket.onmessage: Handling error:', message.data);
                        liveTranscriptionDiv.textContent = `Error: ${message.data}`;
                        if (isRecording) {
                            stopSpeechRecognition(); // Stop recording on error.
                        }
                    // Fallback for other text messages if server sends them without a specific type.
                    } else if (message.text && message.text.trim() !== "") {
                        console.log('[JS] WebSocket.onmessage: Handling generic text message:', message.text);
                        displayMessage('bot', message.text);
                         if (message.text && message.text.trim() !== "") {
                            const utterance = new SpeechSynthesisUtterance(message.text);
                            window.speechSynthesis.speak(utterance);
                        }
                    }
                } catch (e) { // Error parsing JSON or processing message.
                    console.error('[JS] WebSocket.onmessage: Error parsing JSON or processing message:', e);
                    liveTranscriptionDiv.textContent = 'Error processing server message.';
                }
            };

            // Called when a WebSocket error occurs.
            speechWebSocket.onerror = error => {
                console.error('[JS] WebSocket.onerror: WebSocket error occurred:', error);
                liveTranscriptionDiv.textContent = 'Speech service connection error. Please try again.';
            };

            // Called when the WebSocket connection is closed.
            speechWebSocket.onclose = event => {
                console.warn('[JS] WebSocket.onclose: WebSocket connection closed. Event:', event);
                let reason = 'Speech service disconnected.';
                if (event.code !== 1000 && event.code !== 1005 && event.code !== 1001 ) {
                    reason += ` (Code: ${event.code}, Reason: ${event.reason || 'N/A'})`;
                }

                if (isRecording) {
                    liveTranscriptionDiv.textContent = reason;
                } else if (event.code !== 1000 && event.code !== 1005 && event.code !== 1001) {
                    liveTranscriptionDiv.textContent = `Connection closed unexpectedly. ${reason}`;
                } else {
                     liveTranscriptionDiv.textContent = "Speech service session ended.";
                }
                stopSpeechRecognition();
            };

        } catch (error) { // Error during microphone access.
            console.error('[JS] startSpeechRecognition: Microphone access error:', error);
            liveTranscriptionDiv.textContent = 'Microphone access denied. Please check your browser settings and allow microphone access for this site.';
            if (isRecording) {
                stopSpeechRecognition();
            } else {
                 speechToggleButton.textContent = 'Start Speech';
                 isRecording = false;
            }
        }
    }

    /**
     * Stops speech recognition:
     * 1. Stops the MediaRecorder.
     * 2. Closes the WebSocket connection.
     * 3. Resets UI elements and state variables.
     */
    function stopSpeechRecognition() {
        console.log('[JS] stopSpeechRecognition: Attempting to stop.');
        // Stop MediaRecorder if it's currently recording.
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            console.log('[JS] stopSpeechRecognition: Stopping MediaRecorder.');
            mediaRecorder.stop();
        }
        // Note: Microphone stream tracks are stopped in mediaRecorder.onstop().

        // Close WebSocket connection if it's open.
        if (speechWebSocket && speechWebSocket.readyState === WebSocket.OPEN) {
            console.log('[JS] stopSpeechRecognition: Closing WebSocket.');
            speechWebSocket.close();
        }

        // Reset global variables.
        speechWebSocket = null;
        mediaRecorder = null;
        audioChunks = [];

        // Reset UI state for the toggle button and recording status.
        if (isRecording || speechToggleButton.textContent === 'Stop Speech') {
            speechToggleButton.textContent = 'Start Speech';
            isRecording = false;
        }
        // Update transcription display to indicate recording has stopped.
        // liveTranscriptionDiv.textContent = 'Speech recognition stopped.'; // This is often set by onclose.
        console.log('[JS] stopSpeechRecognition: Process completed.');
    }

    /**
     * Converts a Base64 encoded string to a Blob object.
     * Used for handling Base64 encoded audio data received from the server.
     * @param {string} base64 - The Base64 encoded string.
     * @param {string} [type='application/octet-stream'] - The MIME type of the content.
     * @returns {Blob} A Blob object representing the decoded data.
     */
    function base64ToBlob(base64, type = 'application/octet-stream') {
        console.log('[JS] base64ToBlob: Converting base64 string (length:', base64.length, ') to Blob of type:', type);
        const byteCharacters = atob(base64); // Decode Base64 string to binary string.
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers); // Create a typed array.
        return new Blob([byteArray], {type: type}); // Create Blob from typed array.
    }

    // --- Event Listeners & Initial UI Setup ---

    // Attach event listener to the speech toggle button.
    if (speechToggleButton) {
        speechToggleButton.addEventListener('click', handleSpeechToggle);
    } else {
        // Log a warning if the button isn't found, as speech functionality will be broken.
        console.warn("[JS] Initial Setup: Speech toggle button not found on page load. Speech functionality will be unavailable.");
    }

    // Set initial state for UI elements related to speech.
    if (liveTranscriptionDiv) {
        liveTranscriptionDiv.textContent = 'Click "Start Speech" to use voice input.';
    }
    // Disable speech button and provide feedback if the main service (Gemini API) is not configured.
    // This check relies on the sendButton's disabled state, which is set based on server-side configuration.
    if (speechToggleButton && sendButton) {
        if (sendButton.disabled) {
            speechToggleButton.disabled = true;
            speechToggleButton.title = 'Speech functionality disabled: Service not configured.';
            if (liveTranscriptionDiv) {
                liveTranscriptionDiv.textContent = 'Speech service unavailable (LLM not configured).';
            }
            console.warn('[JS] Initial Setup: Speech toggle button disabled due to service not configured.');
        }
    }

    loadHistory();
});
