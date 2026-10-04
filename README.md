# NB 🤖

**NB** is an AI-powered Facebook bot designed to automatically interact with users through **Messenger and Page comments**.

It combines language detection, intent analysis, conversation history and AI-generated responses to provide contextual interactions while maintaining analytics and anti-spam mechanisms.

## ✨ Features

* 💬 Automatic Messenger responses
* 🗨️ Automatic replies to Facebook comments
* 👍 Reaction handling
* 🌍 French / English / Malagasy language detection
* 🧠 User intent analysis
* 💾 Conversation history
* 📊 Interaction analytics
* 🚫 Spam detection
* 🔁 Duplicate-message protection
* ⏱️ Human-like response delays
* 🔄 Polling fallback for missed comments
* 📅 Automated daily analytics reports
* 🔐 Facebook webhook signature verification
* 🚨 External alert endpoint

## 🧠 How it works

A typical interaction follows this pipeline:

```text
Facebook Messenger / Comment
            ↓
       Language Detection
            ↓
       Intent Analysis
            ↓
        Spam Filter
            ↓
    Conversation History
            ↓
       AI Response
            ↓
       Facebook Reply
            ↓
        Analytics
```

The bot adapts its behavior according to the detected language and intention of the user.

## 🌍 Multilingual support

NB can detect:

* 🇫🇷 French
* 🇬🇧 English
* 🇲🇬 Malagasy

The detected language is stored with the conversation and interaction data.

## 🧠 Intent analysis

NB classifies incoming messages into several categories, including:

* Professional questions
* Requests for help
* Thanks
* Positive / negative feedback
* Small talk
* Short answers
* Conversation-ending signals
* Spam

This allows the AI responder to adapt its response instead of treating every message identically.

## 💾 Conversation memory

NB uses **Supabase** to store:

* User messages
* Bot responses
* Conversation history
* Detected languages
* Interaction types
* User intentions
* Response times

The system retrieves recent conversation history to provide contextual responses.

## 📊 Analytics

Interactions are logged and can be analyzed by:

* Interaction type
* Language
* User intention
* Response time
* Post

A daily report can summarize the previous 24 hours of activity.

## 🔄 Reliability

NB includes several mechanisms designed to make the bot more reliable:

* Webhook signature verification
* Duplicate-message protection
* Reaction deduplication
* API timeouts
* Error handling
* Polling fallback
* Automatic retry handling for missed comments

## 🌐 API

The backend is built with **FastAPI**.

### Health / Webhook

The application exposes Facebook webhook endpoints:

```text
GET  /webhook
POST /webhook
```

It also exposes an alert endpoint for external integrations.

## 🛠️ Technologies

* **Python**
* **FastAPI**
* **Facebook Graph API**
* **Supabase**
* **httpx**
* **Requests**
* **Uvicorn**
* **Docker**
* **Railway**
* **GitHub Actions**

## 🚀 Installation

Clone the repository:

```bash
git clone https://github.com/nyavorakotomavo/NB.git
cd NB
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the required environment variables for Facebook, Supabase and the AI providers.

The application can then be started with:

```bash
uvicorn bot.server:app --host 0.0.0.0 --port 8080
```

## 🔐 Configuration

Sensitive credentials are loaded through environment variables rather than being hard-coded into the application.

Main configuration areas include:

```text
Facebook Graph API
Supabase
AI providers
Webhook verification
External alerts
```

**Never commit API keys, access tokens or other secrets to the repository.**

## ☁️ Deployment

NB includes configuration for deployment with:

* **Docker**
* **Railway**
* **GitHub Actions**

GitHub Actions are also used for background tasks such as checking missed conversations and generating daily analytics reports.

## 📁 Project structure

```text
NB/
├── bot/
│   ├── server.py
│   ├── config.py
│   ├── fb_client.py
│   ├── ai_responder.py
│   ├── language_detector.py
│   ├── intent_analyzer.py
│   ├── conversation_store.py
│   ├── analytics.py
│   └── poller.py
│
├── polling/
│   ├── check_missed.py
│   └── daily_report.py
│
├── .github/
│   └── workflows/
│
├── Dockerfile
├── railway.json
└── requirements.txt
```

## 🎯 Project goal

NB was built to experiment with a complete **AI-powered customer interaction system**, combining social-media APIs, conversational AI, persistent memory, analytics and automated deployment.

The project focuses on building a bot that can handle real-world interactions rather than simply generating isolated AI responses.

## 📌 Status

🚧 **Experimental / active development**

NB is a personal development project and may evolve with new AI capabilities, integrations and improvements.

## 👨‍💻 Author

**Nyavo Rakotomavo**

GitHub: https://github.com/nyavorakotomavo
