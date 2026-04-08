import requests
import time

def test():
    # 1. Post a safe message
    print("Submitting safe text...")
    r = requests.post("http://localhost:5000/api/moderate", json={"text": "hello nice world", "id": "1"})
    print("Safe Response:", r.json())

    # 2. Post a toxic message
    print("\nSubmitting toxic text...")
    r = requests.post("http://localhost:5000/api/moderate", json={"text": "kill murder stabbing", "id": "2"})
    print("Toxic Response:", r.json())
    
    # 3. Post a borderline message
    print("\nSubmitting borderline text...")
    r = requests.post("http://localhost:5000/api/moderate", json={"text": "hate", "id": "3"})
    print("Borderline Response:", r.json())
    
    if r.json().get("status") == "pending_review":
        rid = r.json().get("review_id")
        print("\nApproving review_id:", rid)
        r2 = requests.post(f"http://localhost:5000/api/review/{rid}", json={"decision": "approve"})
        print("Review Response:", r2.json())

if __name__ == "__main__":
    test()
