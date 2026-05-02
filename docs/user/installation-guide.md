# Installation Guide

## 1. Purpose

This guide explains how to install and launch the Boeing Aircraft Assistant locally so a user can access the interface and begin asking questions

This guide is for users and evaluators. It focuses on getting the application running, not on backend architecture or deployment internals.

---

## 2. What you need before starting

Before launching the application, make sure you have:

- access to the project repository
- Python installed
- Node.js and npm installed
- terminal or command prompt access
- permission to run both the frontend and backend locally

Depending on your environment, the backend may use one of two model paths:
- a local development path
- a VT ARC / HPC-backed path for the confidence engine

If your team is using the shared VT ARC model server, the confidence-engine setup guide indicates that teammates can run against an already hosted vLLM server instead of setting up the entire model pipeline locally. 

---

## 3. Project components

The application has two major parts:

### Frontend
The frontend is the user-facing React application that opens in the browser. It contains:
- the chat interface
- the conversation sidebar
- the settings page
- the confidence/evidence review panel

### Backend
The backend is the service that:
- receives user questions
- retrieves relevant documents
- generates answers
- computes confidence information
- returns citations and metadata

Both services must be available for full functionality.

---

## 4. Start the backend

Open a terminal in the backend directory.

Typical startup flow:
1. Create and activate a virtual environment
2. Install backend dependencies
3. Configure required environment values
4. Initialize the database (IF this is the first run)
5. Start the backend server

### Example startup sequence

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python init_db.py
python main.py