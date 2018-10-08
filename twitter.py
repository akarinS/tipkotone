from typing import Dict
from requests_oauthlib import OAuth1Session
from config import CONSUMERKEY, CONSUMERSECRET, ACCESSTOKEN, ACCESSTOKENSECRET

def tweet(status: str, in_reply_to_status_id: str) -> None:
    api = OAuth1Session(CONSUMERKEY, CONSUMERSECRET, ACCESSTOKEN, ACCESSTOKENSECRET)
    url = 'https://api.twitter.com/1.1/statuses/update.json'
    params = {'status': status, 'in_reply_to_status_id': in_reply_to_status_id}

    api.post(url, params = params)

def dm(text: str, recipient_id: str) -> None:
    api = OAuth1Session(CONSUMERKEY, CONSUMERSECRET, ACCESSTOKEN, ACCESSTOKENSECRET)
    url = 'https://api.twitter.com/1.1/direct_messages/events/new.json'
    params = {'event': {'type': 'message_create', 'message_create': {'target': {'recipient_id': recipient_id}, 'message_data': {'text': text}}}}

    api.post(url, json = params)

def user(screen_name: str) -> Dict:
    api = OAuth1Session(CONSUMERKEY, CONSUMERSECRET, ACCESSTOKEN, ACCESSTOKENSECRET)
    url = 'https://api.twitter.com/1.1/users/show.json'
    params = {'screen_name': screen_name}

    response = api.get(url, params = params)

    return response.json()

def follow(user_id: str) -> None:
    api = OAuth1Session(CONSUMERKEY, CONSUMERSECRET, ACCESSTOKEN, ACCESSTOKENSECRET)
    url = 'https://api.twitter.com/1.1/friendships/create.json'
    params = {'user_id': user_id, 'follow': 'true'}

    api.post(url, params = params)

