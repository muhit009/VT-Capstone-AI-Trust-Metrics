import requests
import uuid

# --- Step 1: Make the initial query to start the job ---

# Define the endpoint URL for the initial query
query_url = "http://localhost:8000/api/v1/query"

# Generate a UUID for user_id
user_id = None

# Define the payload
payload = {
    "query": "What is system engineering according to NASA?",
    "session_id": "abc123",
    "model_params": {},
    "user_id": user_id
}

print("--- Sending initial query... ---")
# Send a POST request to the endpoint
response = requests.post(query_url, json=payload)

# Print the response status code and content
print("Status Code (Initial Query):", response.status_code)

# It's good practice to check if the request was successful before continuing
if response.status_code == 200:
    # Get the JSON data from the response
    response_data = response.json()
    print("Response Content (Initial Query):", response_data)

    # --- Step 2: Use the query_id to get the results ---

    # Extract the query_id from the first response.
    # We use .get() which is safer than ['query_id'] as it won't crash if the key is missing.
    query_id = response_data.get('query_id')

    if query_id:
        print(f"\n--- Query ID '{query_id}' received. Fetching results... ---")

        # Construct the URL for the results endpoint
        results_url = f"http://localhost:8000/api/v1/results/{query_id}"
        print("Requesting URL:", results_url)

        # Send a GET request to the results endpoint
        results_response = requests.get(results_url)

        # Print the final results
        print("Status Code (Results):", results_response.status_code)
        print("Results Content:", results_response.json())
    else:
        print("\nError: 'query_id' not found in the initial response.")

else:
    print("Error during initial query:", response.text)
    