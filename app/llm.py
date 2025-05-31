import google.generativeai as genai
import os
import asyncio
import google.generativeai.types as genai_types

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

def generate_chat_response(user_input, conversation_history, native_lang, target_lang, difficulty, tone="Serious"): # Added tone
    """
    Generates a chat response using the Gemini model, incorporating language, difficulty, and tone settings.
    """
    global GEMINI_API_KEY_CONFIGURED, API_KEY_WARNING_PRINTED
    if not GEMINI_API_KEY_CONFIGURED:
        if not API_KEY_WARNING_PRINTED: 
            print("Warning: GEMINI_API_KEY not configured. Cannot generate chat response.")
            API_KEY_WARNING_PRINTED = True
        return SERVICE_NOT_CONFIGURED_CHAT_MESSAGE

    try:
        model = genai.GenerativeModel('gemini-2.0-flash') 
        
        system_prompt = f"""You are a language learning tutor.
        The user's native language is {native_lang}.
        The user wants to learn {target_lang}.
        The user's current learning difficulty is {difficulty}.
        Adapt your responses to a {tone} tone.
        Keep your responses concise and helpful for a {difficulty} learner of {target_lang}.
        Engage in a conversation in {target_lang}. If the user speaks in {native_lang}, gently guide them to use {target_lang}.
        """

        chat_history_for_model = []
        
        # Populate history for the model
        if conversation_history: 
            for exchange in conversation_history:
                if 'user' in exchange and 'bot' in exchange: 
                     chat_history_for_model.append({"role": "user", "parts": [str(exchange['user'])]}) 
                     chat_history_for_model.append({"role": "model", "parts": [str(exchange['bot'])]})

        chat = model.start_chat(history=chat_history_for_model)
        
        contextual_user_input = user_input
        if not chat_history_for_model: 
             contextual_user_input = f"{system_prompt}\n\nUser: {user_input}\nAssistant (in {target_lang}):"
        
        response = chat.send_message(contextual_user_input)
        return response.text
    except Exception as e:
        print(f"Error generating chat response from Gemini: {e}") 
        return CHAT_ERROR_MESSAGE

def generate_feedback(last_exchange, native_lang, target_lang, difficulty, tone="Serious"): # Added tone
    """
    Generates feedback on the user's part of the last exchange, 
    considering language, difficulty, and tone.
    """
    global GEMINI_API_KEY_CONFIGURED, API_KEY_WARNING_PRINTED
    if not GEMINI_API_KEY_CONFIGURED:
        if not API_KEY_WARNING_PRINTED:
            print("Warning: GEMINI_API_KEY not configured. Cannot generate feedback.")
            API_KEY_WARNING_PRINTED = True
        return SERVICE_NOT_CONFIGURED_FEEDBACK_MESSAGE

    try:
        model = genai.GenerativeModel('gemini-2.0-flash') 
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
        
        Deliver the feedback in {native_lang}. Adapt your feedback to a {tone} tone, while still being constructive.
        Keep it concise and easy to understand for a {difficulty} learner.
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
        print(f"Error generating feedback from Gemini: {e}") 
        return FEEDBACK_ERROR_MESSAGE

if os.environ.get("GEMINI_API_KEY") and not GEMINI_API_KEY_CONFIGURED:
    configure_gemini(os.environ.get("GEMINI_API_KEY"))


async def manage_gemini_live_connection(audio_input_queue: asyncio.Queue, output_callback_func):
    """
    Manages a bidirectional session with the Gemini Live API for streaming audio
    and receiving transcribed text and generated responses (text and audio).

    This function handles:
    - Setting up the connection with specified model and configurations.
    - Concurrently sending audio chunks from an input queue.
    - Concurrently receiving messages (like transcriptions, model responses) from Gemini.
    - Passing received messages to a callback function for further processing.
    - Graceful shutdown and error handling.

    Args:
        audio_input_queue (asyncio.Queue): A queue from which audio chunks (bytes) are read
                                           and sent to Gemini. A `None` value in this queue
                                           acts as a sentinel to signal the end of audio input
                                           and initiate graceful shutdown of the sending task.
        output_callback_func (async callable): An asynchronous function that will be invoked
                                               with messages received from Gemini. These messages
                                               can be SDK objects representing transcriptions,
                                               model responses, or status/error dictionaries
                                               generated by this manager.
    """
    global GEMINI_API_KEY_CONFIGURED, API_KEY_WARNING_PRINTED
    if not GEMINI_API_KEY_CONFIGURED:
        if not API_KEY_WARNING_PRINTED:
            print("Warning: GEMINI_API_KEY not configured. Cannot start Gemini Live session.")
            API_KEY_WARNING_PRINTED = True
        await output_callback_func({"error": "Gemini API not configured"})
        return

    client = None
    try:
        # Initialize the GenerativeServiceClient, which provides the interface for live connections.
        client = genai.GenerativeServiceClient()

        # --- Configuration for the Gemini Live session ---
        # model: Specifies the Gemini model to use (e.g., 'gemini-1.5-flash-latest').
        # generation_config:
        #   response_modalities: Defines the types of responses expected (AUDIO and TEXT).
        # input_audio_transcription: Enables transcription of the audio sent from the client.
        # output_audio_transcription: Enables generation of audio by Gemini for its responses.
        # speech_config (optional): Could be used to specify audio encoding, sample rate, etc.
        session_config = genai_types.LiveConnectRequest(
            model="models/gemini-1.5-flash-latest",
            config=genai_types.LiveConfig(
                generation_config=genai_types.GenerationConfig(
                    response_modalities=[
                        genai_types.ResponseModality.AUDIO,
                        genai_types.ResponseModality.TEXT
                    ]
                ),
                input_audio_transcription=genai_types.InputAudioTranscriptionConfig(),
                output_audio_transcription=genai_types.OutputAudioTranscriptionConfig()
            )
        )
        print("Attempting to connect to Gemini Live API...")

        # `client.aio.live.connect()` establishes the WebSocket-like bidirectional stream.
        # It's an async context manager, ensuring the session is properly closed on exit.
        async with client.aio.live.connect(config=session_config) as session:
            print("Successfully connected to Gemini Live API.")
            # Notify the caller (WebSocket handler) that the connection is established.
            await output_callback_func({"status": "connected", "session_id": session.session_id})

            # --- Concurrent Tasks for Sending Audio and Receiving Messages ---

            async def send_audio_task():
                """
                This task continuously reads audio chunks from `audio_input_queue`
                and sends them to the Gemini API via `session.send_audio()`.
                It stops when a `None` sentinel is received from the queue.
                """
                print("Audio sending task started.")
                while True:
                    try:
                        chunk = await audio_input_queue.get()
                        if chunk is None:  # `None` is the sentinel for stopping.
                            print("Received sentinel, stopping audio sending.")
                            break
                        if chunk: # Ensure there's data to send.
                            await session.send_audio(chunk)
                    except asyncio.CancelledError:
                        print("Audio sending task cancelled.")
                        break
                    except Exception as e:
                        print(f"Error in send_audio_task: {e}")
                        await output_callback_func({"error": f"Error sending audio: {e}"})
                        break
                    finally:
                        # Important for asyncio.Queue if `join()` is ever used on the queue elsewhere.
                        if 'chunk' in locals() and chunk is not None:
                            audio_input_queue.task_done()
                print("Audio sending task finished.")

            async def receive_messages_task():
                """
                This task continuously listens for messages from the Gemini API via
                `session.receive()`. Each received message is passed to the
                `output_callback_func` for processing by the WebSocket handler.
                """
                print("Message receiving task started.")
                try:
                    async for message in session.receive():
                        await output_callback_func(message)
                except asyncio.CancelledError:
                    print("Message receiving task cancelled.")
                except Exception as e:
                    print(f"Error in receive_messages_task: {e}")
                    await output_callback_func({"error": f"Error receiving message: {e}"})
                finally:
                    print("Message receiving task finished.")
                    # If the receiving task ends (e.g., server closes connection),
                    # try to unblock the sending task by putting a sentinel in its queue,
                    # in case it's stuck waiting on an empty queue.
                    if audio_input_queue.empty():
                         await audio_input_queue.put(None)

            # `asyncio.gather` runs both tasks concurrently. If one task fails,
            # `gather` will (by default) cancel the other and propagate the exception.
            # `return_exceptions=True` can be used to change this behavior if needed.
            send_task = asyncio.create_task(send_audio_task())
            receive_task = asyncio.create_task(receive_messages_task())

            await asyncio.gather(send_task, receive_task) # Wait for both to complete
            print("Both send and receive tasks have completed.")

    # --- Error Handling for Connection and Session ---
    except genai_types.RpcError as rpc_error: # Specific gRPC errors from the API
        print(f"Gemini Live API RPC Error: {rpc_error.reason} (Code: {rpc_error.code})")
        await output_callback_func({"error": f"Gemini Live API RPC Error: {rpc_error.reason}", "code": str(rpc_error.code)})
    except Exception as e: # Catch other potential exceptions during setup or connection
        print(f"Error in manage_gemini_live_connection: {e}")
        await output_callback_func({"error": f"Failed to connect or manage Gemini Live session: {e}"})
    finally:
        # This block executes regardless of whether an exception occurred or not.
        print("Gemini Live session manager finished.")
        # Notify the caller that the session is disconnected.
        await output_callback_func({"status": "disconnected"})
        # The `async with client.aio.live.connect(...)` ensures the session is closed.
        # `GenerativeServiceClient` itself doesn't usually need explicit closing for gRPC.
