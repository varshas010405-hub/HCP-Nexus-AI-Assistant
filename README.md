# 🏥 HCP Nexus AI Assistant

> **An AI-powered Healthcare CRM Assistant built with React, FastAPI, and LangGraph to simplify healthcare professional interactions through intelligent conversational workflows.**

![License](https://img.shields.io/badge/License-MIT-blue.svg)
![React](https://img.shields.io/badge/Frontend-React-61DAFB)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)
![LangGraph](https://img.shields.io/badge/AI-LangGraph-orange)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB)

---

## 📖 Overview

HCP Nexus AI Assistant is an AI-powered Healthcare Customer Relationship Management (CRM) platform designed for Medical Representatives and Healthcare Professionals.

Instead of manually entering doctor visit details into traditional CRM systems, users can simply describe their interactions using natural language. The LangGraph-powered assistant intelligently extracts structured information, records interactions, retrieves previous visit history, provides AI-generated insights, and recommends follow-up actions.

The project demonstrates how conversational AI can streamline healthcare workflows while reducing manual effort and improving data accuracy.

---

# ✨ Key Features

- 🤖 AI-powered conversational assistant
- 📝 Natural language interaction logging
- 🔍 Automatic healthcare entity extraction
- 🏥 Doctor & hospital interaction management
- 📅 Intelligent follow-up recommendations
- 📚 Interaction history search
- 📊 AI-generated summaries & insights
- 📋 Structured CRM form support
- ⚡ Responsive and intuitive user interface

---

# 🛠 Tech Stack

### Frontend
- React.js
- Vite
- Tailwind CSS
- Axios

### Backend
- FastAPI
- Python
- SQLAlchemy
- PostgreSQL / SQLite

### AI & LangGraph
- LangGraph
- LangChain
- Groq API
- Gemma 2 9B IT

---

# 🧠 LangGraph Workflow

The assistant uses five specialized LangGraph tools to automate CRM operations.

| Tool | Description |
|------|-------------|
| 🔍 Entity Extraction | Extracts doctor, hospital, products, specialty, visit date and summary from natural language. |
| 📝 Visit Logger | Saves structured interaction data into the CRM database. |
| 📚 Search Tool | Retrieves historical interactions using conversational queries. |
| 📊 Insights Tool | Generates summaries and analytics from interaction history. |
| 📅 Follow-up Assistant | Identifies pending follow-ups and recommends future actions. |

---

# 📂 Project Structure

```
hcp-nexus-ai
│
├── backend
│   ├── langgraph
│   ├── models
│   ├── routers
│   ├── schemas
│   ├── tests
│   ├── database.py
│   └── main.py
│
├── frontend
│   ├── src
│   ├── public
│   ├── package.json
│   └── vite.config.js
│
├── scripts
├── docker-compose.yml
├── requirements.txt
├── README.md
└── .env.example
```

---

# 🖥️ Application Workflow

```
User Interaction
        │
        ▼
React Frontend
        │
        ▼
FastAPI Backend
        │
        ▼
LangGraph Workflow
        │
 ┌──────┼──────────┐
 │      │          │
 ▼      ▼          ▼
Entity  Search   Insights
Extract  Tool      Tool
 │
 ▼
Visit Logger
 │
 ▼
Database
 │
 ▼
Frontend Response
```

---

# 📸 Application Screenshots

## Dashboard



```

```
<img width="1917" height="918" alt="Screenshot 2026-07-10 130202" src="https://github.com/user-attachments/assets/a7bb583f-c071-476a-8e0e-6dfd06d43107" />


---

## AI Assistant


```
screenshots/ai-assistant.png
```

<img width="1917" height="956" alt="Screenshot 2026-07-10 114749" src="https://github.com/user-attachments/assets/ba04df9c-7dd9-4b12-960f-bcad5cd3f94a" />
>

---

## Structured Form

> Manual CRM interaction entry.

```
screenshots/structured-form.png
```

<img width="1917" height="882" alt="Screenshot 2026-07-10 125045" src="https://github.com/user-attachments/assets/cefc0848-a26c-4004-84d6-0257049f700a" />
>

---

## Interaction History

> View and search previous healthcare interactions.

```
screenshots/history.png
```

<img width="1895" height="806" alt="Screenshot 2026-07-10 130646" src="https://github.com/user-attachments/assets/4e722644-a316-413f-a136-5f51c5c4a462" />


---

## Platform Settings

> User preferences and application configuration.

```
screenshots/settings.png
```

<img width="1906" height="796" alt="image" src="https://github.com/user-attachments/assets/3e7b7bfa-b21d-4e37-8c7f-0c506a7a70ed" />


---

# ⚙️ Installation

## Clone Repository

```bash
git clone https://github.com/Varsha-vk-05/hcp-nexus-ai.git

cd hcp-nexus-ai
```

---

## Backend Setup

```bash
python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

uvicorn backend.main:app --reload
```

---

## Frontend Setup

```bash
cd frontend

npm install

npm run dev
```

---

# 🔑 Environment Variables

Create a `.env` file in the project root.

```env
DATABASE_URL=postgresql://username:password@localhost:5432/hcp_nexus_db

GROQ_API_KEY=your_groq_api_key

GROQ_MODEL=gemma2-9b-it

HOST=0.0.0.0

PORT=8000
```

---

# 🎯 Project Objective

The objective of HCP Nexus AI Assistant is to modernize traditional healthcare CRM systems by integrating conversational AI with LangGraph workflows.

The application enables healthcare professionals to:

- Record doctor visits through natural language
- Automatically extract structured medical interaction details
- Maintain interaction history
- Generate actionable insights
- Receive intelligent follow-up recommendations

This approach significantly reduces manual data entry while improving operational efficiency and user experience.

---

# 🚀 Future Enhancements

- Voice-based interaction logging
- Multi-language support
- Calendar integration
- Email & notification reminders
- Analytics dashboard
- Mobile application
- Secure authentication & role management

---

# 👩‍💻 Author

### Varsha S

Android Application developer |Software Developer | AI & Full Stack Developer

- GitHub: https://github.com/Varsha-vk-05


---

## ⭐ If you found this project useful, consider giving it a star!
