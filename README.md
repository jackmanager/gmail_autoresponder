# Gmail Auto-responder

A Python application that automatically responds to emails using ChatGPT.

## Features

- Automatically fetches new unread emails from Gmail
- Uses ChatGPT to draft replies
- Saves drafts in Gmail
- Provides a web interface to review, edit, send, or reject drafts
- Runs on a schedule to continuously check for new emails

## Prerequisites

- Python 3.11 or higher
- Google OAuth credentials (Client ID, Client Secret, Refresh Token)
- OpenAI API key

## Installation

1. Clone the repository or download the source code

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on the `.env.example` template and fill in your credentials:
```
# Google OAuth Credentials
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GMAIL_REFRESH_TOKEN=your_gmail_refresh_token

# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key

# Application Settings
APP_BASE_URL=http://localhost:8000
AUTH_USERNAME=admin
AUTH_PASSWORD=your_secure_password
SESSION_SECRET=your_session_secret
```

## Running the Application

1. Start the application:
```bash
cd gmail_autoresponder
uvicorn app.main:app --reload
```

2. Access the web interface at http://localhost:8000

3. Log in with the username and password specified in your `.env` file

## How It Works

1. The application polls your Gmail inbox every 5 minutes for new unread messages
2. For each unread message, it:
   - Extracts the content
   - Generates a reply using ChatGPT
   - Creates a draft in Gmail
   - Marks the original message as read
   - Stores the draft information in a local database

3. You can review all pending drafts at the `/drafts` endpoint
4. For each draft, you can:
   - Send it as-is
   - Edit it and then send
   - Reject it (deletes the draft)

## Deployment

For production deployment:

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your environment variables (either in a `.env` file or directly in your environment)

3. Run the application with a production ASGI server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

4. For a more robust setup, consider using Gunicorn with Uvicorn workers:
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
```

5. Set up a reverse proxy (like Nginx) to handle HTTPS and forward requests to your application

## Security Considerations

- The application uses basic authentication for the web interface
- Make sure to use a strong password
- Consider implementing more robust authentication for production use
- Keep your API keys and OAuth credentials secure
- The application stores draft information in a local SQLite database

## Customization

- You can modify the system prompt in `llm_service.py` to change how ChatGPT generates replies
- Adjust the polling interval in `scheduler.py` if you want to check for new emails more or less frequently
- Customize the HTML interface in `main.py` to match your preferences
