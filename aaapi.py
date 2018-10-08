from flask import Flask, request
from config import CONSUMERKEY, CONSUMERSECRET, ACCESSTOKEN, ACCESSTOKENSECRET
import base64
import hashlib
import hmac
import json
import multiprocessing as mp
import tipbot

application = Flask('twitter-tipbot')

def sig(msg: bytes) -> str:
    sha256_hash_digest = hmac.new(CONSUMERSECRET.encode(), msg = msg, digestmod = hashlib.sha256).digest()
    return 'sha256=' + base64.b64encode(sha256_hash_digest).decode()

def validate(signature: str, data: bytes) -> bool:
    return hmac.compare_digest(signature, sig(data))

@application.route('/twitter', methods = ['GET'])
def get():
    if 'crc_token' in request.args and len(request.args.get('crc_token')) == 48:
        response_token = sig(request.args.get('crc_token').encode())
        response = {'response_token': response_token}

        return json.dumps(response), 200, {'Content-Type': 'application/json'}

    return '', 204, {'Content-Type': 'text/plain'}

@application.route('/twitter', methods = ['POST'])
def post():
    if 'X-Twitter-Webhooks-Signature' in request.headers:
        if validate(request.headers.get('X-Twitter-Webhooks-Signature'), request.data):
            data = request.json

            process = mp.Process(target = tipbot.main, args = (data,))
            process.start()

            return 'OK', 200, {'Content-Type': 'text/plain'}

    return '', 204, {'Content-Type': 'text/plain'}

