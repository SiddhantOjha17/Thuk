from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# WhatsApp webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    resp = MessagingResponse()
    msg = resp.message()

    # Always send the same response
    msg.body("Kya re laude")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
