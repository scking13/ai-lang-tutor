from flask import Flask, render_template, session, request, jsonify
import datetime # For timestamping feedback
import os
from app.llm import configure_gemini, generate_chat_response, generate_feedback, GEMINI_API_KEY_CONFIGURED

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

def update_session_settings(native_lang, target_lang, difficulty):
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


if __name__ == '__main__':
  if not app.secret_key or app.secret_key == 'your_very_secret_key_for_development_fallback':
      print("Warning: FLASK_SECRET_KEY is not set or is using a default development key. Set a strong secret key in your environment for production.")
  if not GEMINI_API_KEY:
      print("Warning: GEMINI_API_KEY environment variable not found. LLM features will be disabled.")
  app.run(host='0.0.0.0', port=5000, debug=True)
