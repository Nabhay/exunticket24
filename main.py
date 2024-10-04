from flask import request, redirect, Response
from monster import render, Flask, escapeString
import sys, json
import hashlib, base64
import resend, secrets_parser

app = Flask(__name__)

def make_response(data, mimetype=None, status=None):
    if type(data) in [str, int, float, bool, list, dict]:
        data = json.dumps(data)
    resp = Response(data, mimetype=mimetype, status=status)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

resend.api_key = secrets_parser.parse("variables.txt")["RESEND"]
salt = secrets_parser.parse("variables.txt")["SALT"]

def send_mail(to, subject, html, reply_to="exun@dpsrkp.net"):
    params = {
        "from": "Exun Clan <exun@exun.co>",
        "to": [to],
        "subject": subject,
        "html": html,
        "reply_to": reply_to
    }
    email = resend.Emails.send(params)
    return email

send_mail("aarav@dayal.org", "test", "<div>hi</div>")

daisyui = "<script>"+ open("public/pako.js").read()+ "</script>"+ """<script>
    function decompressGzippedString(base64String) {
        try {
            const binaryString = atob(base64String);
            const len = binaryString.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            const decompressedData = pako.inflate(bytes, { to: 'string' });
            return decompressedData;
        } catch (err) {
            console.error('An error occurred while decompressing the string:', err);
            return null;
        }
    }
    """+ f"""
    var daisycss="{open("public/daisyui.b64").read()}";
    var style=document.createElement("style");
    style.textContent=decompressGzippedString(daisycss);
    document.head.appendChild(style);
    </script>
    """

tailwind = "<script>eval(atob(`" + base64.b64encode(open("public/tailwind.js").read().encode()).decode() + "`))</script>"

def otp(a):
    if type(a) == str:
        a = a.encode()+salt.encode()
    hash_object = hashlib.sha256(a)
    hex_dig = hash_object.hexdigest()
    array = int(hex_dig[-6:], 16) % (10 ** 6)
    return [int(digit) for digit in str(array)]

@app.get("/")
def home():
    return render("index", locals() | globals())

@app.get("/login")
def login():
    return render("login", locals() | globals())

@app.get("/email")
def email_send():
    args=dict(request.args)
    key="".join([str(x) for x in otp(args["email"])])
    otp_render=open("components/mail/mail.html").read()
    for x in range(0, 6):
        otp_render=otp_render.replace(f"{{digit{x+1}}}", key[x])
    send_mail(args["email"], "Exun Registration Authentication OTP - "+key, otp_render)
    return make_response(key)

app.run(host="127.0.0.1", port=int(sys.argv[1]))