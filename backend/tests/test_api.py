import requests

# The URL of your local FastAPI server
url = "http://localhost:8000/v1/predict"

# The data we want to send
payload = {
    "prompt": "Explain why databases are important for AI trust.",
    "max_new_tokens": 150,
    "temperature": 0.7,
    "repetition_penalty": 1.1,
    "no_repeat_ngram_size": 3
}

print("Sending request to AI Server...")

try:
    # Send the POST request
    response = requests.post(url, json=payload)
    
    # Check if it was successful
    if response.status_code == 200:
        data = response.json()
        print("\n--- AI RESPONSE ---")
        print(f"Text: {data['generated_text']}")
        print(f"Confidence: {data['confidence']['score']}")
        print("\nSuccess!")
    else:
        print(f"Failed with status code: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Could not connect to server: {e}")