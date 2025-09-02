from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import requests
import re
import json

app = FastAPI()


SANITY_PROJECT_ID = "c2fi737m"
SANITY_DATASET = "production"
SANITY_API_TOKEN = "skYMFW4XjrYsRsJX7jaWWNna8G7ySnDfqTHtnVZgbLprv1wHZYUikkptv6jMcR2ZMSK3PoyOB0Sw5yCPT7cXUqGlraaqETGxRdqEz2AGN4u4cL504h18a4yNQ4bvn4ni7Xtt70mlo5aErl3uVDKKrzR6v5ifHOcW9LJiv0feIATA9qizID4w"

SANITY_API_URL = f"https://{SANITY_PROJECT_ID}.api.sanity.io/v2021-10-21/data/query/{SANITY_DATASET}"

def normalize_tracking_id(raw_id: str):
    """Remove all symbols/spaces, keep only letters & numbers, uppercase."""
    if not raw_id:
        return None
    return re.sub(r"[^A-Za-z0-9]", "", raw_id).upper()

def fetch_from_sanity(tracking_id: str):
    """Fetch delivery info from Sanity."""
    normalized_id = normalize_tracking_id(tracking_id)
    if not normalized_id:
        return []
    
    print(f"🔍 Normalized Tracking ID: {normalized_id}")


    query = f"""*[_type == 'delivery' && trackingNumber == '{normalized_id}']{{
        "tracking_id": trackingNumber,
        "status": status,
        "customerName": customerName,
        "customerPhone": customerPhone,
        "estimatedDelivery": estimatedDelivery,
        "issueMessage": issueMessage
    }}"""
    headers = {"Authorization": f"Bearer {SANITY_API_TOKEN}"}

    try:
        response = requests.get(SANITY_API_URL, params={"query": query}, headers=headers)
        response.raise_for_status()
        result = response.json().get("result", [])
        print(f"Sanity Result: {result}")
        return result
    except requests.exceptions.RequestException as e:
        print(f"Sanity API request failed: {e}")
        return []

@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        body = await request.json()
        print("📩 Incoming webhook:", json.dumps(body, indent=2))

        if body.get("message", {}).get("type") == "tool-calls":
            tool_calls = body["message"].get("toolCalls", [])
            tool_outputs = []

            for call in tool_calls:
                if call.get("type") == "function" and call["function"]["name"] == "delivery_tracker":
                    tool_call_id = call.get("id")
                    if not tool_call_id:
                        continue

                    arguments = call["function"].get("arguments", {})
                    try:
                        if isinstance(arguments, str):
                            arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        print("Error decoding arguments JSON string.")
                        arguments = {}

                    tracking_id = arguments.get("tracking_id")
                    
                    output_data = {}
                    if not tracking_id:
                        print("⚠️ tracking_id missing in arguments.")
                        output_data = {"error": "Tracking ID is missing."}
                    else:
                        deliveries = fetch_from_sanity(tracking_id)
                        if not deliveries:
                            output_data = {"status": "not_found", "message": f"No delivery found for tracking ID: {tracking_id}"}
                        else:
                            output_data = deliveries[0]
                    
                    
                    tool_outputs.append({
                        "tool_call_id": tool_call_id,
                        "output": output_data
                    })


            if tool_outputs:
                response_payload = {"tool_outputs": tool_outputs}
                print("✅ Responding to VAPI with:", json.dumps(response_payload, indent=2))
                return JSONResponse(content=response_payload)
            
        return JSONResponse(content={"status": "ignored", "reason": "Not a relevant tool-call."})

    except Exception as e:
        print(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

