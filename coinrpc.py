from typing import Any
import json
import requests
from config import RPCUSER, RPCPASSWORD, RPCPORT

def call(method: str, *params: Any) -> Any:
    data = json.dumps({'jsonrpc': '1.0', 'id': '', 'method': method, 'params': params})
    response = requests.post(f'http://localhost:{RPCPORT}', auth = (RPCUSER, RPCPASSWORD), headers = {'content-type': 'text/plain'}, data = data)

    return response.json().get('result')

