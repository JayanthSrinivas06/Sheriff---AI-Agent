from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
import requests
import re
import json
import os

app = FastAPI()

# --- Environment variables ---
SANITY_PROJECT_ID = os.getenv("SANITY_PROJECT_ID")
SANITY_DATASET = os.getenv("SANITY_DATASET")
SANITY_API_TOKEN = os.getenv("SANITY_API_TOKEN")

if not SANITY_API_TOKEN:
    print("FATAL ERROR: SANITY_API_TOKEN environment variable is not set.")

SANITY_API_URL = f"https://{SANITY_PROJECT_ID}.api.sanity.io/v2021-10-21/data/query/{SANITY_DATASET}"

# --- Root endpoint ---
@app.get("/")
def read_root():
    return {"status": "ok", "message": "Delivery tracker webhook is running."}

# --- Helper: normalize tracking ID ---
def normalize_tracking_id(raw_id: str):
    if not raw_id:
        return None
    return re.sub(r"[^A-Za-z0-9]", "", raw_id).upper()

# --- Helper: fetch delivery from Sanity ---
def fetch_from_sanity(tracking_id: str):
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

# --- Main webhook handler ---
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

                    try:
                        # Parse arguments
                        arguments = call["function"].get("arguments", {})
                        if isinstance(arguments, str):
                            arguments = json.loads(arguments)
                        tracking_id = arguments.get("tracking_id")

                        # Fetch delivery info
                        if not tracking_id:
                            output_data = {"error": "Tracking ID is missing."}
                            message_text = "Please provide a valid tracking ID."
                        else:
                            deliveries = fetch_from_sanity(tracking_id)
                            if not deliveries:
                                output_data = {
                                    "status": "not_found",
                                    "message": f"No delivery found for tracking ID: {tracking_id}"
                                }
                                message_text = output_data["message"]
                            else:
                                output_data = deliveries[0]
                                message_text = (
                                    f"I've found your delivery details:\n"
                                    f"Customer Name: {output_data.get('customerName')}\n"
                                    f"Phone: {output_data.get('customerPhone')}\n"
                                    f"Status: {output_data.get('status')}\n"
                                    + (f"Estimated Delivery: {output_data['estimatedDelivery']}\n" if output_data.get('estimatedDelivery') else "")
                                    + (f"Issue: {output_data['issueMessage']}" if output_data.get('issueMessage') else "")
                                )

                        # Append response for VAPI
                        tool_outputs.append({
                            "tool_call_id": tool_call_id,
                            "output": {
                                "status": "success" if deliveries else output_data.get("status", "not_found"),
                                "message": message_text,
                                "deliveryDetails": output_data
                            }
                        })

                    except json.JSONDecodeError:
                        print(f"Error decoding arguments for tool_call_id: {tool_call_id}")
                        tool_outputs.append({
                            "tool_call_id": tool_call_id,
                            "output": {"status": "error", "message": "Invalid JSON arguments."}
                        })
                    except Exception as e:
                        print(f"Error processing tool call {tool_call_id}: {e}")
                        tool_outputs.append({
                            "tool_call_id": tool_call_id,
                            "output": {"status": "error", "message": "Internal server error processing request."}
                        })

            if tool_outputs:
                print("✅ Responding to VAPI with:", json.dumps(tool_outputs, indent=2))
                return Response(
                    content=json.dumps(tool_outputs),
                    media_type="application/json"
                )

        # Not a tool-call
        return Response(
            content=json.dumps({"status": "ignored", "reason": "Not a relevant tool-call."}),
            media_type="application/json"
        )

    except Exception as e:
        print(f"CRITICAL Webhook error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
