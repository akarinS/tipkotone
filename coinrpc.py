from typing import Any
import json
import requests

class CoinRPC(object):
    def __init__(self, rpcuser: str, rpcpassword: str, rpcport: str) -> None:
        self.auth = (rpcuser, rpcpassword)
        self.url = f'http://localhost:{rpcport}'

    def call(self, method: str, *params: Any) -> Any:
        data = json.dumps({'jsonrpc': '1.0', 'id': '', 'method': method, 'params': params})
        response = requests.post(self.url, auth = self.auth, headers = {'content-type': 'text/plain'}, data = data)

        return response.json().get('result')

