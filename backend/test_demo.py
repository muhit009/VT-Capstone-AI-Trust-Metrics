import requests
import sys

# --- Configuration ---
BASE_URL = "http://localhost:8000"

# Replace these with the actual filenames of the PDFs you downloaded
PDF_1_FILENAME = "boeing_747_pfd.pdf" 
PDF_2_FILENAME = "boeing_737_max.pdf"

def wait_for_next_step(step_title, explanation):
    """
    Helper function to pause the script for a live presentation.
    Prints the explanation and waits for user input.
    """
    print(f"\n{'='*60}")
    print(f"NEXT STEP: {step_title}")
    print(f"{'-'*60}")
    print(explanation)
    print(f"{'-'*60}")
    # Wait for the presenter to press Enter
    input(">>> Press Enter to execute this step... ")
    print("Executing...\n")

# =====================================================================
# DEMO START
# =====================================================================

print("\n🚀 STARTING ENTERPRISE AI CONFIDENCE API DEMO 🚀\n")

# --- Step 1: Upload Documents ---
wait_for_next_step(
    "Upload Documents to RAG Backend",
    f"Explanation:\nFirst, we need to populate our knowledge base. We will hit the \n"
    f"POST /v1/documents/upload endpoint twice to upload two different PDFs:\n"
    f"1. {PDF_1_FILENAME} (about the 747)\n"
    f"2. {PDF_2_FILENAME} (about the 737 MAX)."
)

upload_url = f"{BASE_URL}/v1/documents/upload"

for filename in [PDF_1_FILENAME, PDF_2_FILENAME]:
    try:
        with open(filename, "rb") as f:
            files = {"file": (filename, f, "application/pdf")}
            print(f"Uploading {filename}...")
            upload_response = requests.post(upload_url, files=files)
            print(f"Status: {upload_response.status_code} | Response: {upload_response.text}")
    except FileNotFoundError:
        print(f"❌ Error: Could not find '{filename}'. Please ensure it is in the same directory.")
        sys.exit(1)


# --- Step 2: Delete One Document ---
wait_for_next_step(
    "Delete a Document",
    f"Explanation:\nTo demonstrate database management, we will now remove the first document\n"
    f"({PDF_1_FILENAME}) using the DELETE /v1/documents/{{filename}} endpoint.\n"
    f"This ensures our upcoming query relies solely on the remaining 737 MAX document."
)

delete_url = f"{BASE_URL}/v1/documents/{PDF_1_FILENAME}"
delete_response = requests.delete(delete_url)
print(f"Status: {delete_response.status_code} | Response: {delete_response.text}")


# --- Step 3: Make the initial query ---
wait_for_next_step(
    "Submit Asynchronous RAG Query",
    f"Explanation:\nNow we ask a question specific to the remaining document.\n"
    f"We will hit the POST /api/v1/query endpoint.\n"
    f"Because AI generation and confidence scoring take time, this endpoint returns\n"
    f"a 'query_id' immediately, allowing the system to process the answer in the background."
)

query_url = f"{BASE_URL}/api/v1/query"
payload = {
    "query": "According to the document, what was the proximate cause of the Boeing 737 MAX disasters?",
    "session_id": "demo-session-123",
    "model_params": {},
    "user_id": None
}

print(f"Sending payload: {payload['query']}")
query_response = requests.post(query_url, json=payload)
print(f"Status Code: {query_response.status_code}")

query_id = None
if query_response.status_code == 200:
    response_data = query_response.json()
    print("Response Content:", response_data)
    query_id = response_data.get('query_id')
else:
    print("❌ Error during initial query:", query_response.text)
    sys.exit(1)


# --- Step 4: Retrieve the Results ---
if query_id:
    wait_for_next_step(
        "Retrieve Answer and Confidence Score",
        f"Explanation:\nFinally, we will take the query_id we just received ('{query_id}')\n"
        f"and pass it to the GET /api/v1/results/{{query_id}} endpoint.\n"
        f"This will return the final LLM response along with its calculated Trust Tier\n"
        f"(HIGH/MEDIUM/LOW) based on NLI grounding and log-probability."
    )

    results_url = f"{BASE_URL}/api/v1/results/{query_id}"
    print(f"Requesting URL: {results_url}")

    results_response = requests.get(results_url)

    print(f"Status Code: {results_response.status_code}")
    print("Final Results Content:")
    
    # Pretty print the final JSON response if successful
    if results_response.status_code == 200:
        import json
        print(json.dumps(results_response.json(), indent=2))
    else:
        print(results_response.text)

print(f"\n{'='*60}")
print("🎉 DEMO COMPLETE 🎉")
print(f"{'='*60}\n")
