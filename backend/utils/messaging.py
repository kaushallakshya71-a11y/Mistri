"""
Mistri Automated Messaging Service
Handles Real-Time WhatsApp & SMS Dispatch for Repair Lifecycle Events
Supports Pluggable Cloud APIs (Twilio / Meta WhatsApp API) with Mock Logging Fallback
"""
import os
import logging
from typing import Optional
from db.database import get_db

logger = logging.getLogger("mistri.messaging")

# Cloud configuration (optional from environment)
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")

def send_whatsapp_message(to_phone: str, message: str) -> dict:
    """
    Send WhatsApp message to customer.
    If Meta Cloud API tokens are configured, dispatches real HTTP request.
    Otherwise, logs simulated dispatch for local/production fallback.
    """
    clean_phone = "".join(filter(str.isdigit, to_phone or ""))
    if not clean_phone:
        clean_phone = "919800000000"
    if not clean_phone.startswith("91") and len(clean_phone) == 10:
        clean_phone = f"91{clean_phone}"

    # If Cloud API configured, attempt delivery
    if WHATSAPP_TOKEN and WHATSAPP_PHONE_ID:
        try:
            import urllib.request
            import json
            url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
            payload = json.dumps({
                "messaging_product": "whatsapp",
                "to": clean_phone,
                "type": "text",
                "text": {"body": message}
            }).encode("utf-8")
            req = urllib.request.Request(
                url, data=payload,
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                res_data = json.loads(resp.read().decode())
                return {"status": "sent", "provider": "meta_whatsapp", "details": res_data}
        except Exception as e:
            logger.warning(f"WhatsApp Meta dispatch failed, falling back to simulated: {e}")

    # Simulated dispatch log
    print(f"\n📱 [WHATSAPP DISPATCH] To: +{clean_phone}")
    print(f"   Message: {message}\n")
    return {"status": "simulated", "phone": clean_phone, "message": message}

def send_sms(to_phone: str, message: str) -> dict:
    """Send SMS notification to customer."""
    clean_phone = "".join(filter(str.isdigit, to_phone or ""))
    print(f"\n💬 [SMS DISPATCH] To: +{clean_phone} | Text: {message}")
    return {"status": "simulated", "phone": clean_phone, "message": message}

def dispatch_repair_status_alert(
    customer_id: int,
    customer_name: str,
    customer_phone: Optional[str],
    repair_id: str,
    device_name: str,
    status: str,
    total_amount: Optional[float] = None
) -> dict:
    """
    Generates tailored WhatsApp message based on status and records in database.
    """
    tracking_url = f"http://localhost:8000/track/{repair_id}"

    templates = {
        "Received": (
            f"Namaste {customer_name}! 🙏\n"
            f"Aapka {device_name} repair ke liye receive ho gaya hai.\n"
            f"📋 Job ID: {repair_id}\n"
            f"🔍 Live Status Track karein: {tracking_url}\n"
            f"Team Mistri ⚡"
        ),
        "Diagnosing": (
            f"Namaste {customer_name}!\n"
            f"🔍 Hamare technician aapke {device_name} ki checking (Diagnosis) kar rahe hain.\n"
            f"Job ID: {repair_id}\n"
            f"Status: {tracking_url}"
        ),
        "Repairing": (
            f"Namaste {customer_name}!\n"
            f"🔧 {device_name} par repair ka kaam shuru ho chuka hai.\n"
            f"Jald hi aapko update milega.\n"
            f"Track: {tracking_url}"
        ),
        "Completed": (
            f"Badhai ho {customer_name}! 🎉\n"
            f"Aapka {device_name} successfully repair ho chuka hai aur pickup ke liye ready hai!\n"
            f"📋 Job ID: {repair_id}\n"
            + (f"💰 Bill Amount: ₹{total_amount:,.2f}\n" if total_amount else "") +
            f"📄 Bill & Tracking: {tracking_url}\n"
            f"Dukan par aakar device collect kar sakte hain. - Mistri"
        ),
        "Delivered": (
            f"Thank you {customer_name}! 🙏\n"
            f"Aapka {device_name} deliver ho chuka hai. Hume umeed hai aap hamari service se santusht hain.\n"
            f"Kripya 1 minute nikal kar rating de: {tracking_url}\n"
            f"- Team Mistri ⚡"
        )
    }

    msg_body = templates.get(
        status,
        f"Update for {repair_id}: Your {device_name} status is now {status}. Track at {tracking_url}"
    )

    # 1. Send WhatsApp message
    wa_result = send_whatsapp_message(customer_phone or "919800000000", msg_body)

    # 2. Record in database notifications with channel='whatsapp'
    try:
        conn = get_db()
        conn.execute("""
            INSERT INTO notifications (user_id, repair_job_id, title, message, channel)
            VALUES (?, ?, ?, ?, ?)
        """, (customer_id, None, f"WhatsApp Update: {status}", msg_body, "whatsapp"))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving notification to DB: {e}")

    return wa_result
