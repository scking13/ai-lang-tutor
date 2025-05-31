from flask import Flask, render_template, session, request, jsonify
import datetime # For timestamping feedback
import os
from threading import Thread
from simple_websocket_server import WebSocketServer, WebSocket
from app.llm import configure_gemini, generate_chat_response, generate_feedback, GEMINI_API_KEY_CONFIGURED, manage_gemini_live_connection
import asyncio
import json
import base64 # Added for encoding audio data
import traceback # For logging WebSocket server crashes

# --- WebSocket Speech Service Class ---
class SpeechServiceSocket(WebSocket):
    """
    Handles WebSocket connections for the real-time speech-to-speech service.

    Each instance of this class corresponds to a single client connection.
    It manages:
    - Receiving audio data from the client.
    - Forwarding that audio to the Gemini Live API via `manage_gemini_live_connection`.
    - Receiving responses (transcriptions, generated text/audio) from Gemini.
    - Formatting these responses and sending them back to the client.
    - Handling the lifecycle of the asyncio event loop for each connection.
    """
    def __init__(self, server, sock, address):
        # Record initialization time and address for the connection.
        self.connection_time = datetime.now()
        print(f"{self.connection_time} [WS-{address}] SpeechServiceSocket.__init__: Initializing for new connection.")
        super().__init__(server, sock, address)
        self.loop = None
        self.audio_queue = None
        self.gemini_loop_thread = None
        # Note: self.address is available after super().__init__
        print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.__init__: Super class initialized. Client address: {self.address}")

    def connected(self):
        """
        Called when a new WebSocket client connects.
        Sets up the necessary infrastructure for this connection:
        - An asyncio queue (`self.audio_queue`) for buffering audio from the client.
        - A new asyncio event loop (`self.loop`) to run async tasks for this client.
        - A separate thread (`self.gemini_loop_thread`) to run the event loop,
          which in turn runs `manage_gemini_live_connection`.
        """
        print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.connected: Client connected. Setting up audio queue and Gemini loop.")
        # Each client connection gets its own asyncio queue for audio data.
        self.audio_queue = asyncio.Queue()
        # Each client connection runs its Gemini interaction in a separate asyncio event loop.
        self.loop = asyncio.new_event_loop()

        async def output_callback_func(message_from_gemini):
            """
            Callback executed by `manage_gemini_live_connection` when messages are received from Gemini.
            This function processes the Gemini message, formats it into a simpler JSON structure
            suitable for the client-side JavaScript, and sends it back to the client.
            It runs within the `gemini_loop_thread`'s event loop, so sending messages to the
            WebSocket client (which is handled by the main WebSocket server thread) needs to be thread-safe.
            """
            client_message = None
            # Log message receipt from Gemini manager
            print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.output_callback_func: Received message from Gemini manager: {type(message_from_gemini)}")
            try:
                # Case 1: Handle status or error messages directly from `manage_gemini_live_connection`.
                # These are typically simple dictionaries like {'status': 'connected'} or {'error': '...'}
                if isinstance(message_from_gemini, dict) and 'status' in message_from_gemini:
                    client_message = {'type': 'status', 'data': message_from_gemini['status']}
                elif isinstance(message_from_gemini, dict) and 'error' in message_from_gemini:
                    client_message = {'type': 'error', 'data': message_from_gemini['error']}

                # Case 2: Process complex objects from the Gemini SDK.
                # The structure of `message_from_gemini` can vary. We attempt to extract relevant parts.
                # Note: Attribute names like `input_transcription`, `model_turn`, `parts`, `text`, `audio_data`
                # are based on anticipated Gemini API response structures and may need adjustment
                # if the actual SDK objects differ.

                # Attempt to extract input transcription.
                input_transcription_text = None
                # Check for direct 'input_transcription.text' attribute path.
                if hasattr(message_from_gemini, 'input_transcription') and \
                   hasattr(message_from_gemini.input_transcription, 'text') and \
                   message_from_gemini.input_transcription.text:
                    input_transcription_text = message_from_gemini.input_transcription.text
                # Fallback: Check for a common pattern in speech APIs (e.g., Google Cloud Speech-to-Text).
                elif hasattr(message_from_gemini, 'results'):
                    for result in message_from_gemini.results:
                        if hasattr(result, 'is_final') and result.is_final and \
                           hasattr(result, 'alternatives') and result.alternatives and \
                           hasattr(result.alternatives[0], 'transcript') and result.alternatives[0].transcript:
                            input_transcription_text = result.alternatives[0].transcript
                            break # Use the first final transcript found.

                if input_transcription_text:
                    client_message = {'type': 'input_transcription', 'data': input_transcription_text}

                # Attempt to extract model-generated text and audio.
                # A single Gemini message might contain both text and audio parts.
                model_text_response = None
                model_audio_response_b64 = None

                if hasattr(message_from_gemini, 'model_turn') and hasattr(message_from_gemini.model_turn, 'parts'):
                    for part in message_from_gemini.model_turn.parts:
                        # Extract text part, if not already found.
                        if hasattr(part, 'text') and part.text and not model_text_response:
                            model_text_response = part.text
                        # Extract audio part (as bytes), encode to Base64, if not already found.
                        if hasattr(part, 'audio_data') and part.audio_data and not model_audio_response_b64:
                            audio_bytes = part.audio_data
                            model_audio_response_b64 = base64.b64encode(audio_bytes).decode('utf-8')

                # If model text was found, prepare and send it as a 'bot_response_text' message.
                if model_text_response:
                    print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.output_callback_func: Sending bot_response_text: {model_text_response[:100]}...")
                    text_client_msg = {'type': 'bot_response_text', 'data': model_text_response}
                    serialized_msg = json.dumps(text_client_msg)
                    # Use call_soon_threadsafe because this callback runs in the Gemini loop's thread,
                    # but send_message needs to operate in the WebSocket server's main thread.
                    self.loop.call_soon_threadsafe(self.send_message, serialized_msg)
                    client_message = None # Message handled; clear client_message to prevent re-sending.

                # If model audio was found (and Base64 encoded), prepare and send it.
                if model_audio_response_b64:
                    print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.output_callback_func: Sending bot_response_audio (b64 snippet): {model_audio_response_b64[:100]}...")
                    audio_client_msg = {'type': 'bot_response_audio', 'data': model_audio_response_b64}
                    serialized_msg = json.dumps(audio_client_msg)
                    self.loop.call_soon_threadsafe(self.send_message, serialized_msg)
                    client_message = None # Message handled.

                # If `client_message` is still None here, and no text/audio parts were processed,
                # it means the message from Gemini was not a recognized status/error, transcription,
                # or model response. Log this for debugging.
                if client_message is None and not model_text_response and not model_audio_response_b64:
                    print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.output_callback_func: Unhandled/unknown message structure from Gemini: {type(message_from_gemini)}")
                    # Optionally, send a generic 'unknown' message type to client for debugging there.
                    # client_message = {'type': 'unknown', 'data': str(message_from_gemini)}
                elif client_message: # Log if there's a direct client_message to send (status, error, transcription)
                     print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.output_callback_func: Parsed client_message to send: {client_message}")


            except AttributeError as ae: # Errors from trying to access non-existent attributes on SDK objects.
                print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.output_callback_func: AttributeError processing message: {ae}. Message: {message_from_gemini}")
                client_message = {'type': 'error', 'data': f"Internal server error processing API response: {ae}"}
            except Exception as e: # Catch-all for other unexpected errors during processing.
                print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.output_callback_func: Exception processing message: {e}")
                client_message = {'type': 'error', 'data': f"Internal server error: {e}"}

            # If client_message was set (e.g. for status, error, or a single-part transcription), send it.
            # Text/audio messages are sent directly above to handle multi-part responses correctly.
            if client_message:
                try:
                    serialized_msg = json.dumps(client_message)
                    self.loop.call_soon_threadsafe(self.send_message, serialized_msg)
                except Exception as e: # Error during final serialization or send.
                    print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.output_callback_func: Error serializing/sending client_message: {e}")
                    fallback_error_msg = json.dumps({'type': 'error', 'message': 'Failed to send processed message to client.'})
                    self.loop.call_soon_threadsafe(self.send_message, fallback_error_msg)

        def loop_runner(loop, coro):
            """
            Helper function to run an asyncio event loop in a separate thread.
            This is used to run `manage_gemini_live_connection` for each WebSocket client.
            """
            print(f"Starting asyncio event loop in thread for {self.address}...")
            asyncio.set_event_loop(loop) # Associate the loop with this thread.
            try:
                loop.run_until_complete(coro) # Run the main async coroutine.
            except Exception as e:
                print(f"Exception in loop_runner for {self.address}: {e}")
            finally:
                print(f"Asyncio event loop for {self.address} finished.")
                loop.close() # Ensure the event loop is closed.

        # Prepare the main coroutine for managing the Gemini connection.
        gemini_coro = manage_gemini_live_connection(self.audio_queue, output_callback_func)

        # Start the event loop (and `gemini_coro`) in a new daemon thread.
        self.gemini_loop_thread = Thread(target=loop_runner, args=(self.loop, gemini_coro), name=f"GeminiLoopThread-{self.address}")
        self.gemini_loop_thread.daemon = True # Allows main program to exit even if thread is running.
        print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.connected: Starting Gemini Live connection thread {self.gemini_loop_thread.name} (ID: {self.gemini_loop_thread.ident}).")
        self.gemini_loop_thread.start()
        # Note: thread ident is only available after start() is called, so previous log uses name.
        # For more accurate ident logging here, would need to log after start or pass thread object itself to know its ident before start.

    def handle(self):
        """
        Called when the WebSocket receives a message from the client.
        This method expects raw audio data (bytes) from the client.
        It puts the received audio data into the `self.audio_queue` to be processed
        by `manage_gemini_live_connection` in the asyncio event loop.
        """
        data_size = len(self.data) if self.data else 0
        print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.handle: Received data from client (size: {data_size} bytes).")
        if self.audio_queue and self.loop and self.loop.is_running():
            try:
                # `self.data` contains the binary audio data from the client.
                # `put_nowait` is used as we are calling from the WebSocket server's thread
                # into an asyncio queue that is consumed by a different thread's event loop.
                # `call_soon_threadsafe` ensures this operation is scheduled correctly in the asyncio loop.
                self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, self.data)
                print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.handle: Putting data onto audio_queue.")
            except Exception as e: # Broad exception catch for queue errors.
                print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.handle: Error putting data into audio_queue: {e}")
        else:
            # This might happen if data is received before the connection is fully set up
            # or after it has started to close.
            print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.handle: Skipping data, audio_queue or event loop not ready.")

    def handle_close(self):
        """
        Called when the WebSocket connection with the client is closed.
        This method signals the `manage_gemini_live_connection` coroutine to terminate
        by putting a `None` sentinel into the `audio_queue`.
        It also handles cleanup of the asyncio loop and thread.
        """
        print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.handle_close: Connection closed by client.")
        if self.audio_queue and self.loop and self.loop.is_running():
            print(f"{datetime.now()} [WS-{self.address}] SpeechServiceSocket.handle_close: Signaling audio_queue with None.")
            # Send the `None` sentinel to the audio queue to stop the `send_audio_task`
            # in `manage_gemini_live_connection`. This is done thread-safely.
            self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, None)

        # The `gemini_loop_thread` is a daemon thread, so it will exit when the main
        # program exits. Explicitly joining can be done if necessary, but might block
        # the WebSocket server's handling of other clients if not handled carefully.
        if self.gemini_loop_thread and self.gemini_loop_thread.is_alive():
            print(f"Gemini Live connection thread for {self.address} is still alive; will be cleaned up by daemon property or loop closure.")
            # Example: self.gemini_loop_thread.join(timeout=5)

        # The asyncio event loop (`self.loop`) is closed within the `loop_runner`'s `finally` block
        # once `manage_gemini_live_connection` (and its tasks) complete.
        print(f"Cleanup for {self.address} initiated.")

# --- Application Setup ---
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_very_secret_key_for_development_fallback')

# Configure Gemini API at startup
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
configure_gemini(GEMINI_API_KEY)

# --- Helper Functions for Session Management (Conversation, Feedback, Settings) ---

def _get_session_list(key):
    if key not in session:
        session[key] = []
    return session[key]

def _get_session_dict(key, default_val=None):
    if default_val is None:
        default_val = {}
    if key not in session:
        session[key] = default_val
    return session[key]

def add_message_to_history(user_message, bot_message):
    """Adds a new user-bot exchange to the conversation history in the session."""
    history = _get_session_list('conversation_log')
    history.append({'type': 'chat', 'user': user_message, 'bot': bot_message, 'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    session.modified = True

def add_feedback_to_history(feedback_note, original_user_message):
    """Adds a feedback note to the history in the session."""
    history = _get_session_list('conversation_log')
    history.append({
        'type': 'feedback',
        'user_message': original_user_message, # The message on which feedback is given
        'feedback': feedback_note,
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    session.modified = True

def get_full_chat_log_for_display():
    """Retrieves and formats the full chat log (chats and feedback) for display."""
    return _get_session_list('conversation_log')

def update_session_settings(native_lang, target_lang, difficulty, tone=None):
    settings = get_session_settings() # Ensures defaults are loaded, including 'tone'
    
    settings['native_lang'] = native_lang
    settings['target_lang'] = target_lang
    settings['difficulty'] = difficulty
    if tone is not None:
        settings['tone'] = tone
    # If tone is None, it retains the value from get_session_settings()
    
    session['settings'] = settings
    session.modified = True
    return settings

def get_session_settings():
    # This ensures that 'tone' is always present in session settings.
    default_settings = {
        'native_lang': 'English',
        'target_lang': 'Spanish',
        'difficulty': 'Beginner',
        'tone': 'Serious' 
    }
    settings = _get_session_dict('settings', default_settings)
    # Ensure all keys are present, even if session had an older version of settings
    for key, value in default_settings.items():
        if key not in settings:
            settings[key] = value
    session['settings'] = settings # Save back to session if updated
    return settings

# --- Routes ---

@app.route('/')
def index():
  current_settings = get_session_settings() # Ensures settings are initialized
  return render_template('index.html', 
                         settings=current_settings,
                         gemini_configured=GEMINI_API_KEY_CONFIGURED)

@app.route('/send_message', methods=['POST'])
def send_message_route():
    data = request.json
    user_input = data.get('message')
    native_lang = data.get('native_lang')
    target_lang = data.get('target_lang')
    difficulty = data.get('difficulty')
    tone = data.get('tone') # Get tone from request

    current_settings = get_session_settings()
    if native_lang is None: native_lang = current_settings['native_lang']
    if target_lang is None: target_lang = current_settings['target_lang']
    if difficulty is None: difficulty = current_settings['difficulty']
    if tone is None: tone = current_settings['tone'] # Use session tone if not in request

    if not user_input: # Only user_input is strictly required from request body
        return jsonify({'error': 'Missing message'}), 400

    update_session_settings(native_lang, target_lang, difficulty, tone)
    
    # Retrieve current conversation history for the LLM
    # We pass the 'conversation_log' which contains both chat and feedback for context if needed,
    # but llm.py's generate_chat_response should be adapted to filter or use it appropriately.
    # For simplicity, let's assume generate_chat_response expects only user/bot pairs for now.
    chat_only_history = [item for item in get_full_chat_log_for_display() if item['type'] == 'chat']


    bot_response_text = generate_chat_response(user_input, chat_only_history, native_lang, target_lang, difficulty, tone)
    add_message_to_history(user_input, bot_response_text)

    last_exchange = {'user': user_input, 'bot': bot_response_text}
    feedback_text = generate_feedback(last_exchange, native_lang, target_lang, difficulty, tone)
    if feedback_text: 
        add_feedback_to_history(feedback_text, user_input)
        
    return jsonify({
        'user_message': user_input, 
        'bot_response': bot_response_text,
        'feedback': feedback_text
    })

@app.route('/get_history', methods=['GET'])
def get_history_route():
    history = get_full_chat_log_for_display()
    settings = get_session_settings()
    return jsonify({'history': history, 'settings': settings})

@app.route('/update_settings', methods=['POST']) # Kept for explicit settings updates if needed
def update_settings_route():
    data = request.json
    native_lang = data.get('native_lang')
    target_lang = data.get('target_lang')
    difficulty = data.get('difficulty')
    tone = data.get('tone') # Get tone from request
    
    current_settings = get_session_settings()
    if native_lang is None: native_lang = current_settings['native_lang']
    if target_lang is None: target_lang = current_settings['target_lang']
    if difficulty is None: difficulty = current_settings['difficulty']
    if tone is None: tone = current_settings['tone'] # Use session tone if not in request
        
    updated_settings = update_session_settings(native_lang, target_lang, difficulty, tone)
    return jsonify({'message': 'Settings updated successfully', 'settings': updated_settings})

@app.route('/speech_service_status')
def speech_service_status():
    """Confirms that the Speech Service WebSocket should be running."""
    return jsonify({'message': 'Speech Service WebSocket should be running on ws://localhost:8000/'})


if __name__ == '__main__':
  if not app.secret_key or app.secret_key == 'your_very_secret_key_for_development_fallback':
      print("Warning: FLASK_SECRET_KEY is not set or is using a default development key. Set a strong secret key in your environment for production.")
  if not GEMINI_API_KEY:
      print("Warning: GEMINI_API_KEY environment variable not found. LLM features will be disabled.")

  # Start WebSocket server for Speech Service in a separate thread.
  # The server listens on port 8000 and uses SpeechServiceSocket to handle connections.
  print("Attempting to start Speech Service WebSocket server...")
  # simple_websocket_server.WebSocketServer handles each client in a new thread by default.
  # Our SpeechServiceSocket class then manages an asyncio loop within that client-specific thread.
  speech_websocket_server = WebSocketServer(
      '0.0.0.0', # Listen on all available network interfaces.
      8000,      # Port for the WebSocket server.
      SpeechServiceSocket # Handler class for incoming WebSocket connections.
  )

  # The `serve_forever()` method is blocking, so it needs to run in its own thread
  # to avoid blocking the main Flask application.

  def websocket_server_runner(server_instance):
      """
      Wrapper function to run the WebSocket server's serve_forever() method
      and log any exceptions that cause it to crash.
      """
      try:
          thread_ident = Thread.get_ident()
          print(f"{datetime.now()} [WS-Runner-{thread_ident}] WebSocket server thread starting serve_forever()...")
          server_instance.serve_forever()
      except Exception as e:
          thread_ident = Thread.get_ident()
          print(f"{datetime.now()} [WS-Runner-{thread_ident}] !!! WebSocket server thread crashed: {e} !!!")
          print(traceback.format_exc())
      finally:
          thread_ident = Thread.get_ident()
          print(f"{datetime.now()} [WS-Runner-{thread_ident}] WebSocket server thread serve_forever() exited.")

  server_thread = Thread(target=websocket_server_runner, args=(speech_websocket_server,))
  server_thread.daemon = True
  server_thread.start()
  print(f"{datetime.now()} [MainThread] Speech Service WebSocket server started on port 8000 in a separate thread with error logging.")

  # Run the Flask web application.
  # `debug=False` and `use_reloader=False` are recommended for stability when managing
  # background threads like the WebSocket server and its asyncio loops.
  app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
