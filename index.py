import subprocess
import sys
import os
from flask import Flask, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

app = Flask(__name__)

@app.route('/flash', methods=['POST'])
def flash_transfer():
    data = request.get_json()
    cmd = [
        "python", "SQR400.py", "transfer",
        "--type", data.get("type", "mt103_bsi"),
        "--sender-file", data.get("sender_file", "sender.json"),
        "--amount", str(data.get("amount", 50000)),
        "--currency", data.get("currency", "USD"),
        "--officer-pin", data.get("pin", "123456"),
        "--muscle"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)) + '/..', timeout=30)
        return jsonify({
            "status": "success", 
            "output": result.stdout + result.stderr, 
            "trace": "BSI-2026-LIVE",
            "receiver": {
                "bank": data.get("bank_name"),
                "bic": data.get("bic"),
                "account": data.get("account_number"),
                "holder": data.get("account_holder")
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@app.route('/')
def home():
    return "Muji Hardiansyah SQR400 BSI Flash v3.3 - Live June 2026 | Receiver Enabled"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)