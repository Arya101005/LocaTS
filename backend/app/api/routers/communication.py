"""
Communication Router
====================
IVR phone helpline, Twilio SMS/OTP/calls, TTS voice alerts,
and WhatsApp bot endpoints.

API Routes:
  POST /api/ivr/start            — Start IVR session
  POST /api/ivr/input            — Process IVR input
  GET  /api/ivr/demo             — IVR demo info
  POST /api/ivr/call             — Real IVR call via Twilio
  GET  /api/twilio/status        — Check Twilio config
  POST /api/twilio/send-sms      — Send SMS
  POST /api/twilio/evacuation-alert — Evacuation SMS
  POST /api/twilio/send-otp      — Send OTP
  POST /api/twilio/verify-otp    — Verify OTP
  POST /api/twilio/broadcast     — Broadcast SMS
  POST /api/tts/alert            — TTS voice alert
  POST /api/tts/broadcast        — TTS broadcast
  POST /api/whatsapp/message     — WhatsApp bot message
  POST /api/whatsapp/action      — WhatsApp quick action
"""

from __future__ import annotations
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.api.state import graph_data, crowd_reports, hazard_confidences
from backend.app.models.domain import CrowdReport, HazardType

router = APIRouter(tags=["communication"])


# --- IVR Flow Definitions ---

IVR_FLOWS = {
    "en": {
        "greeting": {"text": "Welcome to LocaTS Emergency Helpline. Press 1 to report a hazard. Press 2 for evacuation instructions. Press 3 to check on a family member.",
                      "options": {"1": "report", "2": "evacuate", "3": "family"}},
        "report": {"text": "Describe the hazard. Say flood, landslide, or earthquake.",
                    "options": {"flood": "flood_report", "landslide": "landslide_report", "earthquake": "seismic_report"}},
        "flood_report": {"text": "Your flood report has been logged. Stay on high ground.", "options": {}},
        "landslide_report": {"text": "Your landslide report has been logged. Move away from the hillside.", "options": {}},
        "seismic_report": {"text": "Your earthquake report has been logged. Drop, cover, hold on.", "options": {}},
        "evacuate": {"text": "Move to the nearest shelter. Follow marked routes. Help elderly first.", "options": {}},
        "family": {"text": "Visit the nearest shelter with their name, or use the LocaTS app.", "options": {}},
    },
    "hi": {
        "greeting": {"text": "LocaTS Aapat Seva. Khatre ki report ke liye 1. Niraasan ke liye 2. Parivar ke liye 3.",
                      "options": {"1": "report", "2": "evacuate", "3": "family"}},
        "report": {"text": "Baadh ke liye 1, Bhoo-khalboli ke liye 2.", "options": {"1": "flood_report", "2": "landslide_report"}},
        "flood_report": {"text": "Aapki baadh report darj ho gayi. Uunchi jagah par rahein.", "options": {}},
        "landslide_report": {"text": "Aapki bhoo-khalboli report darj ho gayi. Pahaad se door rahein.", "options": {}},
        "evacuate": {"text": "Nazdeeki shelter par jaayein. Nirdisht raaston par chalein.", "options": {}},
        "family": {"text": "Nazdeeki shelter par jaayein ya LocaTS app ka upyog karein.", "options": {}},
    },
}

# --- Schemas ---

class SMSAlert(BaseModel):
    phone_number: str
    message: str

class EvacuationSMS(BaseModel):
    phone_number: str
    shelter_name: str
    distance_km: float = 0.0

class OTPRequest(BaseModel):
    phone_number: str
    channel: str = "sms"

class OTPVerify(BaseModel):
    phone_number: str
    code: str

class BroadcastSMS(BaseModel):
    phone_numbers: list[str]
    message: str


# --- IVR Endpoints ---

@router.post("/api/ivr/start")
async def ivr_start(language: str = "en"):
    """Start a new IVR session."""
    sid = str(uuid.uuid4())[:8]
    flow = IVR_FLOWS.get(language, IVR_FLOWS["en"])
    session = {"session_id": sid, "language": language, "current_step": "greeting",
               "text": flow["greeting"]["text"], "options": flow["greeting"]["options"]}
    return session


@router.post("/api/ivr/input")
async def ivr_input(session_id: str, user_input: str):
    """Process user input in an IVR session."""
    # Sessions are ephemeral; re-create flow state
    flow = IVR_FLOWS.get("en", IVR_FLOWS["en"])
    # Simple stateless lookup — find the step matching input
    for step_name, step in flow.items():
        if user_input in step.get("options", {}):
            next_step = flow.get(step["options"][user_input], {})
            return {"session_id": session_id, "text": next_step.get("text", ""),
                    "options": next_step.get("options", {}), "done": not next_step.get("options")}
    return {"session_id": session_id, "text": "Sorry, please try again.", "options": {}, "done": False}


@router.get("/api/ivr/demo")
async def ivr_demo_page():
    """IVR demo info."""
    return {"message": "Web-based IVR demo", "languages": ["en", "hi"]}


@router.post("/api/ivr/call")
async def ivr_make_call(payload: dict):
    """Make a real IVR call via Twilio."""
    phone = payload.get("phone_number", "")
    lang = payload.get("language", "en")
    msg_type = payload.get("message_type", "evacuation")
    from backend.app.utils.twilio_service import twilio_service
    msgs = {
        "evacuation": {"en": "Emergency evacuation alert. Move to nearest shelter.", "hi": "Aapat niraasan alert. Nazdeeki shelter par jaayein."},
        "status": {"en": "All shelters operational. No immediate evacuation needed.", "hi": "Sabhi shelter chalu hain."},
        "help": {"en": "Help request received. Stay safe.", "hi": "Sahaayata request prapt."},
    }
    msg = msgs.get(msg_type, msgs["evacuation"]).get(lang, msgs["evacuation"]["en"])
    if phone and twilio_service.is_configured:
        result = twilio_service.make_tts_call(phone, msg, f"{lang}-IN")
        return {"status": "call_initiated", "result": result}
    elif phone:
        result = twilio_service.create_ivr_flow(phone, msg)
        return {"status": "twiml_generated", "twiml": result["twiml"]}
    return {"status": "web_demo", "message": msg}


# --- Twilio Endpoints ---

@router.get("/api/twilio/status")
async def twilio_status():
    from backend.app.utils.twilio_service import twilio_service
    return {"configured": twilio_service.is_configured,
            "phone_number": twilio_service.phone_number or "not set",
            "verify_service": bool(twilio_service.verify_service)}

@router.post("/api/twilio/send-sms")
async def send_sms(alert: SMSAlert):
    from backend.app.utils.twilio_service import twilio_service
    return twilio_service.send_sms(alert.phone_number, alert.message)

@router.post("/api/twilio/evacuation-alert")
async def send_evacuation_alert(alert: EvacuationSMS):
    from backend.app.utils.twilio_service import twilio_service
    return twilio_service.send_evacuation_alert(alert.phone_number, alert.shelter_name, alert.distance_km)

@router.post("/api/twilio/send-otp")
async def send_otp(req: OTPRequest):
    from backend.app.utils.twilio_service import twilio_service
    return twilio_service.send_otp(req.phone_number, req.channel)

@router.post("/api/twilio/verify-otp")
async def verify_otp(req: OTPVerify):
    from backend.app.utils.twilio_service import twilio_service
    return twilio_service.verify_otp(req.phone_number, req.code)

@router.post("/api/twilio/broadcast")
async def broadcast_sms(alert: BroadcastSMS):
    from backend.app.utils.twilio_service import twilio_service
    return twilio_service.broadcast_sms(alert.phone_numbers, alert.message)

@router.post("/api/twilio/call")
async def make_twilio_call(phone_number: str, message: str = "Emergency alert from LocaTS."):
    from backend.app.utils.twilio_service import twilio_service
    return twilio_service.create_ivr_flow(phone_number, message)


# --- TTS Endpoints ---

@router.post("/api/tts/alert")
async def tts_voice_alert(payload: dict):
    """Send TTS voice alert in Hindi or English."""
    phone = payload.get("phone_number", "")
    msg_hi = payload.get("message_hi", "")
    msg_en = payload.get("message_en", "")
    lang = payload.get("language", "en-IN")
    phones = payload.get("phone_numbers", [])
    from backend.app.utils.twilio_service import twilio_service
    msg = msg_hi if "hi" in lang else msg_en
    if phone:
        return {"status": "sent", "method": "twilio-call", "result": twilio_service.make_tts_call(phone, msg, lang)}
    elif phones:
        return {"status": "broadcast", "result": twilio_service.send_voice_alert_broadcast(phones, msg, lang)}
    return {"status": "web_tts", "message": msg, "language": lang}

@router.post("/api/tts/broadcast")
async def tts_broadcast(payload: dict):
    """Broadcast TTS alert to phone numbers."""
    msg_hi = payload.get("message_hi", "LocaTS alert. Turant shelter par jaayein.")
    msg_en = payload.get("message_en", "Evacuate immediately to nearest shelter.")
    lang = payload.get("language", "hi-IN")
    phones = payload.get("phone_numbers", [])
    from backend.app.utils.twilio_service import twilio_service
    msg = msg_hi if "hi" in lang else msg_en
    if phones and twilio_service.is_configured:
        return {"status": "broadcast", "result": twilio_service.send_voice_alert_broadcast(phones, msg, lang)}
    return {"status": "web_tts", "message": msg}


# --- WhatsApp Bot ---

@router.post("/api/whatsapp/message")
async def whatsapp_message(payload: dict):
    """Process WhatsApp-style messages."""
    msg = payload.get("message", "").strip().lower()
    session = payload.get("session", {})
    step = session.get("step", "main")

    if step == "main":
        if msg in ("1", "flood"):
            return {"reply": "Flood report selected.\n1. Minor\n2. Moderate\n3. Severe", "new_session": {"step": "report_type", "data": {"hazard_type": "flood"}}}
        elif msg in ("2", "shelter"):
            shelters = [f"{s.name}: {s.bed_capacity - s.beds_occupied} beds free" for s in (graph_data.shelters if graph_data else []) if s.is_active][:5]
            return {"reply": "Nearby Shelters:\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(shelters)), "new_session": session}
        elif msg in ("6", "help"):
            return {"reply": "EMERGENCY: Call 1070. Move to high ground if flooding.", "new_session": session}
        return {"reply": "Choose: 1. Report hazard  2. Find shelter  3. Help", "new_session": session}

    elif step == "report_type":
        sev = {"1": 0.3, "2": 0.6, "3": 0.9}.get(msg, 0.5)
        ht = session.get("data", {}).get("hazard_type", "flood")
        rid = f"wa-{len(crowd_reports)+1:05d}"
        crowd_reports.append(CrowdReport(id=rid, reporter_id="whatsapp-bot", hazard_type=HazardType(ht),
                                         severity_estimate=sev, description=f"WhatsApp: {ht}",
                                         location={"lat": 30.40, "lon": 79.33}, timestamp=datetime.utcnow()))
        return {"reply": f"Report submitted! ID: {rid}. Call 1070 if emergency.", "new_session": {"step": "main"}}
    return {"reply": "Please start over.", "new_session": {"step": "main"}}


@router.post("/api/whatsapp/action")
async def whatsapp_action(payload: dict):
    """Handle quick action buttons."""
    action = payload.get("action", "")
    mapping = {"report_flood": "1", "find_shelter": "2", "need_help": "6"}
    return await whatsapp_message({"message": mapping.get(action, action), "session": payload.get("session", {})})
