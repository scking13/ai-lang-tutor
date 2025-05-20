# Language Learning Chat Application

## Project Overview

This web-based language learning chat application allows users to practice a target language by conversing with an AI tutor powered by Google's Gemini model. Users can select their native and target languages, set a difficulty level, and receive real-time feedback on their grammar, vocabulary, and phrasing. The application maintains a conversation history for the current session.

## Features

-   **Interactive AI Chat**: Engage in conversations with an AI (Google Gemini Pro) to practice your target language.
-   **Language Selection**: Choose your native language and the language you want to learn.
-   **Difficulty Levels**: Adjust the difficulty (Beginner, Intermediate, Advanced) to match your learning stage.
-   **Real-time Feedback**: Receive instant feedback on your messages, including grammar corrections, vocabulary suggestions, and phrasing improvements, provided in your native language.
-   **Persistent Session History**: Your conversation and feedback history are saved within your current browser session.
-   **User-Friendly Interface**: Simple and intuitive chat interface with separate panels for settings, chat, and feedback.

## Setup and Installation

Follow these steps to set up and run the application locally:

1.  **Clone the Repository (if applicable)**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create a Virtual Environment**
    It's highly recommended to use a virtual environment to manage project dependencies.

    *   On macOS and Linux:
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   On Windows:
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```

3.  **Install Dependencies**
    Install all required Python packages using the `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Environment Variables**
    This application requires two environment variables to be set:

    *   **`FLASK_SECRET_KEY`**: This key is used by Flask to encrypt session cookies and other security-sensitive data.
        *   **Purpose**: Ensures the security of user session data.
        *   **How to generate**: You can generate a strong secret key using Python:
            ```bash
            python -c 'import os; print(os.urandom(24).hex())'
            ```
        *   **How to set**:
            *   Linux/macOS: `export FLASK_SECRET_KEY="your_generated_secret_key"`
            *   Windows (PowerShell): `$env:FLASK_SECRET_KEY="your_generated_secret_key"`
            *   Windows (CMD): `set FLASK_SECRET_KEY="your_generated_secret_key"`
            *   Alternatively, you can create a `.env` file in the project root (ensure `.env` is in your `.gitignore`) with the line: `FLASK_SECRET_KEY="your_generated_secret_key"` (The application currently uses a fallback if this is not set for development, but setting it is best practice).

    *   **`GEMINI_API_KEY`**: This API key is required to use the Google Gemini model for chat responses and feedback.
        *   **Purpose**: Authenticates your application with the Google AI services.
        *   **Where to get it**: You can obtain an API key from Google AI Studio. Visit [https://aistudio.google.com/](https://aistudio.google.com/) to create an API key.
        *   **How to set**: Follow the same methods as for `FLASK_SECRET_KEY` (e.g., `export GEMINI_API_KEY="your_gemini_api_key"` or add to `.env` file).

## Running the Application

Once you have completed the setup and installation steps:

1.  **Ensure your virtual environment is activated.**
2.  **Make sure the `GEMINI_API_KEY` and `FLASK_SECRET_KEY` environment variables are set.**
3.  **Navigate to the project's root directory** (if you aren't already there).
4.  **Run the application using the following command:**
    ```bash
    python -m app.main
    ```
    *Note: Using `python -m app.main` ensures that Python treats the `app` directory as a package, allowing relative imports within the application (like `from app.llm import ...`) to work correctly when running from the project root.*

5.  The application will start, and you should see output similar to this in your terminal:
    ```
    * Serving Flask app 'app.server' (lazy loading)
    * Environment: development
    * Debug mode: on
    * Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)
    ```
    (Note: If `GEMINI_API_KEY` is not found, a warning will be printed, and AI features will be disabled.)

6.  Open your web browser and go to: `http://127.0.0.1:5000/`

## Project Structure

The project is organized as follows:

-   `app/`: Main application directory.
    -   `__init__.py`: Makes the `app` directory a Python package.
    -   `main.py`: Entry point to run the Flask application. It imports and runs the Flask app instance from `server.py`.
    -   `server.py`: Contains the Flask application logic, including route definitions (`/`, `/send_message`, `/get_history`, `/update_settings`), session management, and interaction with the LLM module.
    -   `llm.py`: Handles all interactions with the Google Gemini API. This includes configuring the API key, generating chat responses, and generating feedback.
    -   `static/`: Contains static assets.
        -   `css/style.css`: Stylesheets for the web interface.
        -   `js/main.js`: Client-side JavaScript for handling user interactions, API calls to the Flask backend, and dynamic UI updates.
    -   `templates/`: Contains HTML templates.
        -   `index.html`: The main HTML page for the chat interface.
-   `requirements.txt`: Lists the Python dependencies for the project (e.g., Flask, google-generativeai).
-   `.gitignore`: Specifies intentionally untracked files that Git should ignore (e.g., virtual environment, `.env` files, `__pycache__`).
-   `README.md`: This file, providing an overview and instructions for the project.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.
(Further details can be added here if specific contribution guidelines are established.)
