import google.generativeai as genai
import os

GEMINI_API_KEY_CONFIGURED = False
API_KEY_WARNING_PRINTED = False # To avoid spamming console if key is missing

# Standardized error messages
CHAT_ERROR_MESSAGE = "Sorry, I can't respond right now. The AI service seems to be unavailable. Please try again later."
FEEDBACK_ERROR_MESSAGE = "No feedback available at the moment. The AI service might be temporarily down."
SERVICE_NOT_CONFIGURED_CHAT_MESSAGE = "Sorry, I can't respond right now. The service is not configured."
SERVICE_NOT_CONFIGURED_FEEDBACK_MESSAGE = "No feedback available at the moment. The service is not configured."

def configure_gemini(api_key):
    """Configures the genai module with the API key."""
    global GEMINI_API_KEY_CONFIGURED, API_KEY_WARNING_PRINTED
    if api_key:
        try:
            genai.configure(api_key=api_key)
            GEMINI_API_KEY_CONFIGURED = True
            print("Gemini API key configured successfully.")
        except Exception as e:
            print(f"Error configuring Gemini API: {e}") # Log specific error
            GEMINI_API_KEY_CONFIGURED = False
    else:
        if not API_KEY_WARNING_PRINTED:
            print("Warning: GEMINI_API_KEY environment variable not found. LLM features will be disabled.")
            API_KEY_WARNING_PRINTED = True
        GEMINI_API_KEY_CONFIGURED = False

def generate_chat_response(user_input, conversation_history, native_lang, target_lang, difficulty):
    """
    Generates a chat response using the Gemini model, incorporating language and difficulty settings.
    """
    global GEMINI_API_KEY_CONFIGURED, API_KEY_WARNING_PRINTED
    if not GEMINI_API_KEY_CONFIGURED:
        if not API_KEY_WARNING_PRINTED: 
            print("Warning: GEMINI_API_KEY not configured. Cannot generate chat response.")
            API_KEY_WARNING_PRINTED = True
        return SERVICE_NOT_CONFIGURED_CHAT_MESSAGE

    try:
        model = genai.GenerativeModel('gemini-pro')
        
        system_prompt = f"""You are a language learning tutor.
        The user's native language is {native_lang}.
        The user wants to learn {target_lang}.
        The user's current learning difficulty is {difficulty}.
        Keep your responses concise and helpful for a {difficulty} learner of {target_lang}.
        Engage in a conversation in {target_lang}. If the user speaks in {native_lang}, gently guide them to use {target_lang}.
        """

        chat_history_for_model = []
        # Prepend system instructions if no history or as a general behavior model
        # For Gemini, it's often good to include system context in the chat history itself
        # or as part of the first user message if the API doesn't have a dedicated system role.
        # Let's try to add a system-like message at the beginning of the history if it's empty.
        
        if not conversation_history:
            # This is a way to give initial instructions to the model.
            # Note: The 'gemini-pro' model via `start_chat` expects alternating user/model roles.
            # A true system prompt is better handled with `generate_content` if sending a single complex prompt,
            # or by structuring the initial history carefully.
            # For now, we will ensure the prompt for the current message includes the learning context.
             pass # System prompt will be prepended to user_input if history is empty.


        for exchange in conversation_history:
            if 'user' in exchange and 'bot' in exchange:
                 chat_history_for_model.append({"role": "user", "parts": [exchange['user']]})
                 chat_history_for_model.append({"role": "model", "parts": [exchange['bot']]})

        chat = model.start_chat(history=chat_history_for_model)
        
        contextual_user_input = user_input
        # If this is the very first user message, prepend the system prompt.
        if not chat_history_for_model: 
             contextual_user_input = f"{system_prompt}\n\nUser: {user_input}\nAssistant (in {target_lang}):"
        
        response = chat.send_message(contextual_user_input)
        return response.text
    except Exception as e:
        print(f"Error generating chat response from Gemini: {e}") # Log specific error
        return CHAT_ERROR_MESSAGE

def generate_feedback(last_exchange, native_lang, target_lang, difficulty):
    """
    Generates feedback on the user's part of the last exchange, 
    considering language and difficulty.
    """
    global GEMINI_API_KEY_CONFIGURED, API_KEY_WARNING_PRINTED
    if not GEMINI_API_KEY_CONFIGURED:
        if not API_KEY_WARNING_PRINTED:
            print("Warning: GEMINI_API_KEY not configured. Cannot generate feedback.")
            API_KEY_WARNING_PRINTED = True
        return SERVICE_NOT_CONFIGURED_FEEDBACK_MESSAGE

    try:
        model = genai.GenerativeModel('gemini-pro')
        user_message = last_exchange.get('user')
        
        if not user_message:
            return "No user message found in the last exchange to provide feedback on."

        prompt = f"""
        The user's native language is {native_lang}.
        They are trying to learn {target_lang} at a {difficulty} level.
        The user's message was: "{user_message}"
        
        Please provide constructive feedback on the user's message. 
        Address the following:
        1.  Grammar: Identify errors and provide corrections. Briefly explain for a {difficulty} learner.
        2.  Vocabulary: Suggest more natural or appropriate words if applicable.
        3.  Phrasing: Offer alternative phrasings for better fluency or politeness in {target_lang}.
        4.  Positive Reinforcement: Begin with encouragement.
        
        Deliver the feedback in {native_lang}. Keep it concise and easy to understand for a {difficulty} learner.
        If the user's message is grammatically correct and appropriate for their level, acknowledge this.
        
        Example of feedback format (translate to {native_lang} if different from English):
        "Great try! Here are a few pointers:
        *   Instead of 'X', you might say 'Y'. 'Y' is used because... (briefly).
        *   The word 'ABC' is good, but 'DEF' could sound more natural in this context."
        
        User's message in {target_lang} (or attempted {target_lang}): "{user_message}"
        Your feedback (in {native_lang}):
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating feedback from Gemini: {e}") # Log specific error
        return FEEDBACK_ERROR_MESSAGE

if os.environ.get("GEMINI_API_KEY") and not GEMINI_API_KEY_CONFIGURED:
    configure_gemini(os.environ.get("GEMINI_API_KEY"))
