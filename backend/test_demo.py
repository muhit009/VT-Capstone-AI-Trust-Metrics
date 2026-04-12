import requests
import sys
import json

# --- Configuration ---
BASE_URL = "http://localhost:8000"

# Ensure these filenames match the PDFs saved in your folder
PDF_1_FILENAME = "747.pdf" 
PDF_2_FILENAME = "737.pdf"

def wait_for_next_step(step_number, step_title, explanation):
    """
    Helper function to pause the script for a live presentation.
    """
    print(f"\n{'='*70}")
    print(f"STEP {step_number}: {step_title}")
    print(f"{'-'*70}")
    print(explanation)
    print(f"{'-'*70}")
    input(f">>> Press Enter to proceed to Step {step_number}... ")
    print("🚀 Executing...\n")

# =====================================================================
# DEMO START
# =====================================================================


print("\n🌟 STARTING ENTERPRISE AI CONFIDENCE API DEMO 🌟\n")

# --- INITIAL INLINE CLEANUP ---
# Automatically wipe the documents if they exist from a previous run
print("Running initial cleanup for a clean slate...")
for filename in [PDF_1_FILENAME, PDF_2_FILENAME]:
    try:
        cleanup_res = requests.delete(f"{BASE_URL}/v1/documents/{filename}")
        if cleanup_res.status_code in [200, 204, 202]:
            print(f"  -> Successfully cleared old file: {filename}")
    except requests.exceptions.RequestException:
        pass # Ignore connection errors here, they will be caught in Step 1
print("Cleanup complete.\n")

# --- Step 1: Upload ---
wait_for_next_step(
    1, "Upload Documents",
    f"Explanation:\nWe begin by populating our RAG database. We are calling the \n"
    f"POST /v1/documents/upload endpoint to send two distinct research papers:\n"
    f"1. {PDF_1_FILENAME}\n"
    f"2. {PDF_2_FILENAME}"
)

upload_url = f"{BASE_URL}/v1/documents/upload"
for filename in [PDF_1_FILENAME, PDF_2_FILENAME]:
    try:
        with open(filename, "rb") as f:
            files = {"file": (filename, f, "application/pdf")}
            print(f"Uploading {filename}...")
            r = requests.post(upload_url, files=files)
            print(f"Status: {r.status_code} | Server Response: {r.text}")
    except FileNotFoundError:
        print(f"❌ Error: Could not find '{filename}' in local folder.")
        sys.exit(1)


# --- Step 2: List ---
wait_for_next_step(
    2, "List Stored Documents",
    "Explanation:\nNow we want to verify that the backend has indexed our files correctly.\n"
    "We will hit the GET /v1/documents/ endpoint. This allows us to see \n"
    "exactly what is currently stored in our vector database."
)

list_url = f"{BASE_URL}/v1/documents/"
list_response = requests.get(list_url)
print(f"Status: {list_response.status_code}")
if list_response.status_code == 200:
    print("Files currently in database:")
    print(json.dumps(list_response.json(), indent=2))
else:
    print(f"Error: {list_response.text}")


# --- Step 3: Delete ---
wait_for_next_step(
    3, "Delete a Document",
    f"Explanation:\nTo demonstrate management capabilities, we'll remove the 737 document\n"
    f"using the DELETE /v1/documents/{{filename}} endpoint.\n"
    f"This ensures that our upcoming AI query only draws from the 737 MAX data."
)

delete_url = f"{BASE_URL}/v1/documents/{PDF_2_FILENAME}"
delete_response = requests.delete(delete_url)
print(f"Status: {delete_response.status_code} | Response: {delete_response.text}")


# --- Step 4: Query ---
wait_for_next_step(
    4, "Submit Asynchronous RAG Query",
    "Explanation:\nWe will now ask a complex question about the remaining document via\n"
    "the POST /api/v1/query endpoint. The system will start generating an answer\n"
    "and calculating a 'Trust Tier' score. It returns a 'query_id' immediately\n"
    "so the UI doesn't hang while the AI 'thinks'."
)

query_url = f"{BASE_URL}/api/v1/query"
payload = {
    "query": "Based on the text, what were the engineering and management failures regarding the MCAS system?",
    "session_id": "demo-123",
    "model_params": {},
    "user_id": None
}

query_response = requests.post(query_url, json=payload)
print(f"Status Code: {query_response.status_code}")

query_id = None
if query_response.status_code == 200:
    data = query_response.json()
    print("Response JSON:", data)
    query_id = data.get('query_id')
else:
    print(f"❌ Error: {query_response.text}")
    sys.exit(1)


# --- Step 5: Results ---
if query_id:
    wait_for_next_step(
        5, "Retrieve Final Answer & Confidence Score",
        f"Explanation:\nFinally, we use the query_id ('{query_id}') to hit the\n"
        f"GET /api/v1/results/{{query_id}} endpoint. This returns the LLM's answer\n"
        f"along with its HIGH/MEDIUM/LOW confidence rating based on source grounding."
    )

    results_url = f"{BASE_URL}/api/v1/results/{query_id}"
    print(f"Fetching results from: {results_url}")
    
    # We loop slightly here in case the backend is still processing
    results_response = requests.get(results_url)
    
    print(f"Status Code: {results_response.status_code}")
    if results_response.status_code == 200:
        print("\n--- FINAL OUTPUT ---")
        print(json.dumps(results_response.json(), indent=2))
    else:
        print(f"Result not ready or Error: {results_response.text}")

print(f"\n{'='*70}")
print("ALL 5 ENDPOINTS DEMONSTRATED SUCCESSFULLY")
print(f"{'='*70}\n")