from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    num_media = int(request.values.get("NumMedia", 0))
    incoming_msg = request.values.get("Body", "").strip()
    resp = MessagingResponse()
    msg = resp.message()

    if num_media > 0:
        media_type = request.values.get("MediaContentType0", "")
        media_url = request.values.get("MediaUrl0", "")

        if "image" in media_type:
            msg.body("Mast photo bheja re")
        elif "audio" in media_type:
            msg.body("Awaaz to bahaut sundar hai teri <3")
        else:
            msg.body("Kya bhej diya bhai, kuch samajh nahi aya")
    elif incoming_msg:
        msg.body("Kya re laude")  # Text message
    else:
        msg.body("Khaali message bhej diya kya?")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
