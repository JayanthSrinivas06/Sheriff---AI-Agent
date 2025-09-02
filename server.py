from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import requests
import re
import json
import os # Import the 'os' module to handle environment variables

app = FastAPI()

# --- Best Practice: Load credentials from environment variables ---
# These should be set in your Vercel project settings, NOT hardcoded.
SANITY_PROJECT_ID = os.getenv("SANITY_PROJECT_ID")
SANITY_DATASET = os.getenv("SANITY_DATASET")
SANITY_API_TOKEN = os.getenv("SANITY_API_TOKEN")

# Check if the essential API token is available
if not SANITY_API_TOKEN:
    print("FATAL ERROR: SANITY_API_TOKEN environment variable is not set.")
    # In a real app, you might want to prevent the app from starting.

SANITY_API_URL = f"https://{SANITY_PROJECT_ID}.api.sanity.io/v2021-10-21/data/query/{SANITY_DATASET}"

@app.get("/")
def read_root():
    """Provides a simple health check endpoint."""
    return {"status": "ok", "message": "Delivery tracker webhook is running."}

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

                    # --- START OF IMPROVED, SAFER LOGIC ---
                    try:
                        arguments = call["function"].get("arguments", {})
                        if isinstance(arguments, str):
                            arguments = json.loads(arguments)
                        
                        tracking_id = arguments.get("tracking_id")
                        
                        if not tracking_id:
                            print("⚠️ tracking_id missing in arguments.")
                            output_data = {"error": "Tracking ID is missing."}
                        else:
                            # 1. Fetch data from Sanity first
                            deliveries = fetch_from_sanity(tracking_id)
                            
                            # 2. NOW, safely check if the result is empty before accessing it
                            if not deliveries:
                                print(f"🚚 No delivery found for ID: {tracking_id}")
                                output_data = {"status": "not_found", "message": f"No delivery found for tracking ID: {tracking_id}"}
                            else:
                                # This is now safe because we know 'deliveries' is not empty
                                output_data = deliveries[0]

                        tool_outputs.append({
                            "tool_call_id": tool_call_id,
                            "output": output_data
                        })

                    except json.JSONDecodeError:
                        print(f"Error decoding arguments for tool_call_id: {tool_call_id}")
                        continue # Skip this specific tool call if arguments are invalid
                    except Exception as e:
                        print(f"Error processing tool call {tool_call_id}: {e}")
                        # Return an error message to Vapi for this specific call
                        tool_outputs.append({
                            "tool_call_id": tool_call_id,
                            "output": {"error": "An internal server error occurred processing this request."}
                        })
                    # --- END OF IMPROVED LOGIC ---

            if tool_outputs:
                print("✅ Responding to VAPI with:", json.dumps(tool_outputs, indent=2))
                return JSONResponse(content=tool_outputs)

            
        return JSONResponse(content={"status": "ignored", "reason": "Not a relevant tool-call."})

    except Exception as e:
        print(f"CRITICAL Webhook error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
