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

        # --- Case 1: VAPI tool-call style ---
        if body.get("message", {}).get("type") == "tool-calls":
            tool_calls = body["message"].get("toolCalls", [])
            tool_outputs = []

            for call in tool_calls:
                if call.get("type") == "function":
                    func_name = call["function"]["name"]  # dynamic
                    tool_call_id = call.get("id")
                    if not tool_call_id:
                        continue

                    try:
                        arguments = call["function"].get("arguments", {})
                        if isinstance(arguments, str):
                            arguments = json.loads(arguments)
                        tracking_id = arguments.get("tracking_id")

                        if not tracking_id:
                            output_data = {"error": "Tracking ID is missing."}
                        else:
                            deliveries = fetch_from_sanity(tracking_id)
                            if not deliveries:
                                output_data = {
                                    "status": "not_found",
                                    "message": f"No delivery found for tracking ID: {tracking_id}"
                                }
                            else:
                                delivery = deliveries[0]
                                output_data = {
                                    "status": "success",
                                    "message": (
                                        f"I've found your delivery details:\n"
                                        f"Customer Name: {delivery.get('customerName')}\n"
                                        f"Phone: {delivery.get('customerPhone')}\n"
                                        f"Status: {delivery.get('status')}\n"
                                        + (f"Estimated Delivery: {delivery['estimatedDelivery']}\n" if delivery.get('estimatedDelivery') else "")
                                        + (f"Issue: {delivery['issueMessage']}" if delivery.get('issueMessage') else "")
                                    ),
                                    "deliveryDetails": delivery
                                }

                        tool_outputs.append({
                            "tool_call_id": tool_call_id,
                            "output": output_data
                        })

                    except Exception as e:
                        print(f"Error processing tool call {tool_call_id}: {e}")
                        tool_outputs.append({
                            "tool_call_id": tool_call_id,
                            "output": {"error": "Internal server error processing request."}
                        })

            if tool_outputs:
                assistant_messages = []
                for t in tool_outputs:
                    if t["output"].get("message"):
                        assistant_messages.append({
                            "role": "assistant",
                            "content": t["output"]["message"]
                        })

                response_data = {
                    "toolCallResults": [
                        {"toolCallId": t["tool_call_id"], "output": t["output"]} for t in tool_outputs
                    ],
                    "messages": assistant_messages
                }

                print("✅ Responding to VAPI with:", json.dumps(response_data, indent=2))
                return Response(content=json.dumps(response_data), media_type="application/json")

        # --- Case 2: Direct POST with tracking_id (your tool definition sends this) ---
        if "tracking_id" in body:
            tracking_id = body["tracking_id"]
            deliveries = fetch_from_sanity(tracking_id)

            if not deliveries:
                response_data = {
                    "status": "not_found",
                    "message": f"No delivery found for tracking ID: {tracking_id}"
                }
            else:
                delivery = deliveries[0]
                response_data = {
                    "status": "success",
                    "tracking_id": delivery.get("tracking_id"),
                    "customerName": delivery.get("customerName"),
                    "customerPhone": delivery.get("customerPhone"),
                    "statusText": delivery.get("status"),
                    "estimatedDelivery": delivery.get("estimatedDelivery"),
                    "issueMessage": delivery.get("issueMessage")
                }

            print("✅ Responding to direct request with:", json.dumps(response_data, indent=2))
            return Response(content=json.dumps(response_data), media_type="application/json")

        # --- If neither format matched ---
        return Response(
            content=json.dumps({"status": "ignored", "reason": "Not a relevant request."}),
            media_type="application/json"
        )

    except Exception as e:
        print(f"CRITICAL Webhook error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
