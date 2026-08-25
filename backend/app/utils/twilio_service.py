"""Twilio service for SMS, OTP, IVR calls, and TTS voice alerts."""
import os
import hashlib
import time


class TwilioService:
    """Minimal Twilio wrapper — uses REST API directly (no SDK dependency)."""

    def __init__(self):
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.phone_number = os.environ.get("TWILIO_PHONE_NUMBER", "")
        self.verify_service = os.environ.get("TWILIO_VERIFY_SID", "")
        self._otp_store: dict[str, dict] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token)

    def send_sms(self, to: str, body: str) -> dict:
        """Send SMS via Twilio REST API."""
        if not self.is_configured:
            return {"status": "not_configured", "message": "Twilio credentials not set"}
        try:
            import httpx
            resp = httpx.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json",
                auth=(self.account_sid, self.auth_token),
                data={"From": self.phone_number, "To": to, "Body": body},
                timeout=10.0,
            )
            data = resp.json()
            return {"status": "sent" if resp.status_code < 300 else "failed", "sid": data.get("sid"), "error": data.get("message")}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def send_evacuation_alert(self, to: str, shelter_name: str, distance_km: float) -> dict:
        """Send formatted evacuation alert SMS."""
        body = (
            f"EMERGENCY ALERT — LocaTS\n\n"
            f"Evacuation recommended.\n"
            f"Nearest shelter: {shelter_name}\n"
            f"Distance: {distance_km}km\n"
            f"Follow marked routes. Help elderly first.\n"
            f"Helpline: 1070"
        )
        return self.send_sms(to, body)

    def send_otp(self, to: str, channel: str = "sms") -> dict:
        """Send OTP for family member verification."""
        if not self.verify_service:
            # Fallback: generate local OTP
            otp = str(int(hashlib.md5(f"{to}{time.time()}".encode()).hexdigest()[:6], 16) % 1000000).zfill(6)
            self._otp_store[to] = {"otp": otp, "ts": time.time()}
            return {"status": "local_otp", "otp": otp, "message": "OTP generated locally (Twilio Verify not configured)"}
        try:
            import httpx
            resp = httpx.post(
                f"https://verify.twilio.com/v2/Services/{self.verify_service}/Verifications",
                auth=(self.account_sid, self.auth_token),
                data={"To": to, "Channel": channel},
                timeout=10.0,
            )
            return {"status": "sent" if resp.status_code < 300 else "failed", "sid": resp.json().get("sid")}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def verify_otp(self, to: str, code: str) -> dict:
        """Verify an OTP code."""
        if not self.verify_service:
            stored = self._otp_store.get(to)
            if stored and stored["otp"] == code and (time.time() - stored["ts"]) < 300:
                del self._otp_store[to]
                return {"status": "verified", "valid": True}
            return {"status": "invalid", "valid": False}
        try:
            import httpx
            resp = httpx.post(
                f"https://verify.twilio.com/v2/Services/{self.verify_service}/VerificationChecks",
                auth=(self.account_sid, self.auth_token),
                data={"To": to, "Code": code},
                timeout=10.0,
            )
            data = resp.json()
            return {"status": "verified" if data.get("valid") else "invalid", "valid": data.get("valid", False)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def broadcast_sms(self, phone_numbers: list[str], message: str) -> dict:
        """Send SMS to multiple numbers."""
        results = []
        for number in phone_numbers:
            results.append(self.send_sms(number, message))
        return {"sent": len([r for r in results if r["status"] == "sent"]), "failed": len([r for r in results if r["status"] != "sent"]), "total": len(phone_numbers)}

    def create_ivr_flow(self, phone_number: str, message: str) -> dict:
        """Create a TwiML response for IVR call."""
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="en-IN">{message}</Say>
    <Pause length="2"/>
    <Say voice="alice" language="hi-IN">Kripya madad ke liye hamare helpline number 1070 par call karein.</Say>
    <Pause length="1"/>
    <Hangup/>
</Response>"""
        return {"status": "twiml_generated", "twiml": twiml, "phone_number": phone_number}

    def make_tts_call(self, to: str, message: str, language: str = "en-IN") -> dict:
        """Make a real TTS voice call via Twilio."""
        if not self.is_configured:
            return {"status": "not_configured", "message": "Twilio credentials not set"}
        try:
            import httpx
            # Create TwiML
            voice = "alice" if "hi" in language else "alice"
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{voice}" language="{language}">{message}</Say>
    <Pause length="2"/>
    <Hangup/>
</Response>"""
            # For real calls, we'd need a TwiML Bin URL or a webhook.
            # With free trial, we can make outbound calls.
            resp = httpx.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Calls.json",
                auth=(self.account_sid, self.auth_token),
                data={
                    "From": self.phone_number,
                    "To": to,
                    "Twiml": twiml,
                },
                timeout=10.0,
            )
            data = resp.json()
            return {"status": "initiated" if resp.status_code < 300 else "failed", "sid": data.get("sid"), "error": data.get("message")}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def send_voice_alert_broadcast(self, phone_numbers: list[str], message: str, language: str = "en-IN") -> dict:
        """Send TTS voice alerts to multiple numbers."""
        results = []
        for number in phone_numbers:
            results.append(self.make_tts_call(number, message, language))
        return {
            "initiated": len([r for r in results if r["status"] in ("initiated", "not_configured")]),
            "failed": len([r for r in results if r["status"] == "failed"]),
            "total": len(phone_numbers),
        }


twilio_service = TwilioService()
