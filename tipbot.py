from typing import Dict, Optional
import accountwallet as aw
import re
import twitter
from config import BOTSCREENNAME
import random
import string
from decimal import Decimal
import coinrpc

def get_command(text: str) -> Dict:
    text = re.sub(' +', ' ', re.sub('(\n+| +|　+)', ' ', text))
    words = text.split(' ')

    while f'@{BOTSCREENNAME}' in words:
        words = words[words.index(f'@{BOTSCREENNAME}') + 1:]

        if len(words) == 0:
            break

        if re.match('^(tip|投げ銭|投銭|send|送金)$', words[0].lower()):
            return {'method': 'tip', 'params': words[1:]}

        if re.match('^(balance|残高.*)$', words[0].lower()):
            return {'method': 'balance'}

        if re.match('^(deposit|入金.*)$', words[0].lower()):
            return {'method': 'deposit'}

        if re.match('^(withdraw|出金)$', words[0].lower()):
            return {'method': 'withdraw', 'params': words[1:]}

        if re.match('^(help|ヘルプ)$', words[0].lower()):
            return {'method': 'help'}

        if re.match('^(followme|フォローミー|フォローして)', ''.join([word.lower() for word in words])):
            return {'method': 'follow'}

    return {'method': None}

def get_message(text: str, *screen_names: str) -> str:
    for screen_name in screen_names[::-1]:
        text = f'@{screen_name} ' + text

    return '\n'.join([text, '', ''.join([random.choice(string.ascii_letters) for i in range(4)])])

def Decimal_to_str(d: Decimal) -> str:
    reverse_s = f'{d:.8f}'[::-1]
    return_s = reverse_s

    for s in reverse_s:
        if s == '0':
            return_s = return_s[1:]
            continue

        if s == '.':
            return_s = return_s[1:]

        break

    return_s = return_s[::-1]

    return return_s

def execute(text: str, user_id: str, screen_name: str, name: str, from_tweet: bool) -> Optional[str]:
    account = 'twitter-' + user_id
    name = name.split('@')[0] if not name.startswith('@') else name
    command = get_command(text)

    if command['method'] == None:
        return None

    if command['method'] == 'tip':
        if len(command['params']) < 2:
            text = 'tipkotoneの使い方をご確認ください！ https://github.com/akarinS/tipkotone/blob/master/README.md'

            return get_message(text, screen_name) if from_tweet else get_message(text)

        if re.match('^@', command['params'][0]):
            to_screen_name = command['params'][0][1:]
            str_amount = command['params'][1]

        elif re.match('^@', command['params'][1]):
            to_screen_name = command['params'][1][1:]
            str_amount = command['params'][0]

        else:
            text = '宛先が間違っています・・・'

            return get_message(text, screen_name) if from_tweet else get_message(text)

        if to_screen_name == BOTSCREENNAME:
            to_account = 'FREE'

        else:
            to_user = twitter.user(to_screen_name)

            if to_user.get('error') is not None:
                text = '宛先が見つかりませんでした・・・'

                return get_message(text, screen_name) if from_tweet else get_message(text)

            to_user_id = to_user['id_str']
            to_account = 'twitter-' + to_user_id
            to_name = to_user['name']
            to_name = to_name.split('@')[0] if not to_name.startswith('@') else name

        result = aw.move(account, to_account, str_amount)

        if result == 'wrong':
            text = '不正な金額です・・・'

            return get_message(text, screen_name) if from_tweet else get_message(text)

        elif result == 'few':
            text = '金額が小さすぎです・・・'

            return get_message(text, screen_name) if from_tweet else get_message(text)

        elif result == 'insufficient':
            text = '残高が足りません・・・'

            return get_message(text, screen_name) if from_tweet else get_message(text)

        amount = Decimal_to_str(result)

        if to_screen_name == BOTSCREENNAME:
            text = f'{amount}KOTO 寄付していただきありがとうございます！'

            return get_message(text, screen_name) if from_tweet else get_message(text)

        text = f'{name}さんから {to_name}さんへ お心付けです！ {amount}KOTO'

        return get_message(text, screen_name, to_screen_name) if from_tweet else get_message(text)

    if command['method'] == 'balance':
        balance, confirming_balance = aw.get_account_balance(account)

        balance = Decimal_to_str(balance)

        if confirming_balance == 0:
            text = f'{name}さんの残高は {balance}KOTO です！'

        else:
            confirming_balance = Decimal_to_str(confirming_balance)
            text = f'{name}さんの残高は {balance}KOTO (+{confirming_balance}KOTO 承認中) です！'

        return get_message(text, screen_name) if from_tweet else get_message(text)

    if command['method'] == 'deposit':
        address = aw.get_account_address(account)

        text = f'{address} に送金してください！'

        return get_message(text, screen_name) if from_tweet else get_message(text)

    if command['method'] == 'withdraw':
        if len(command['params']) < 2:
            text = 'tipkotoneの使い方をご確認ください！ https://github.com/akarinS/tipkotone/blob/master/README.md'

            return get_message(text, screen_name) if from_tweet else get_message(text)

        if re.match('^(k|jz)', command['params'][0]):
            address = command['params'][0]
            str_amount = command['params'][1]

        elif re.match('^(k|jz)', command['params'][1]):
            address = command['params'][1]
            str_amount = command['params'][0]

        else:
            text = 'アドレスが間違っています・・・'

            return get_message(text, screen_name) if from_tweet else get_message(text)

        if not coinrpc.call('validateaddress', address)['isvalid']:
            text = 'アドレスが間違っています・・・'

            return get_message(text, screen_name) if from_tweet else get_message(text)

        result = aw.add_withdrawal_request(account, address, str_amount)

        if result == 'wrong':
            text = '不正な金額です・・・'

            return get_message(text, screen_name) if from_tweet else get_message(text)

        elif result == 'few':
            text = '金額が小さすぎです・・・'

            return get_message(text, screen_name) if from_tweet else get_message(text)

        elif result == 'insufficient':
            text = '残高が足りません・・・'

            return get_message(text, screen_name) if from_tweet else get_message(text)

        amount = Decimal_to_str(result)
        text = f'{amount}KOTO の出金リクエストを受け付けました！'

        return get_message(text, screen_name) if from_tweet else get_message(text)

    if command['method'] == 'help':
        text = 'tipkotoneの使い方はこちらです！ https://github.com/akarinS/tipkotone/blob/master/README.md'

        return get_message(text, screen_name) if from_tweet else get_message(text)

    if command['method'] == 'follow':
        twitter.follow(user_id)
        text = 'フォローしました！'

        return get_message(text, screen_name) if from_tweet else get_message(text)

    return None

def main(data: Dict) -> None:
    if 'tweet_create_events' in data:
        for event in data['tweet_create_events']:
            text = event['text']
            user_id = event['user']['id_str']
            screen_name = event['user']['screen_name']
            name = event['user']['name']
            status_id = event['id_str']

            if screen_name == BOTSCREENNAME:
                continue

            if re.match('(^RT |^QT |.* RT |.* QT ).*', text):
                continue

            message = execute(text, user_id, screen_name, name, True)

            if message is not None:
                twitter.tweet(message[:140], status_id)

    if 'direct_message_events' in data:
        for event in [event for event in data['direct_message_events'] if event['type'] == 'message_create']:
            text = '@tipkotone ' + event['message_create']['message_data']['text']
            user_id = event['message_create']['sender_id']
            screen_name = data['users'][user_id]['screen_name']
            name = data['users'][user_id]['name']

            if screen_name == BOTSCREENNAME:
                continue

            message = execute(text, user_id, screen_name, name, False)

            if message is not None:
                twitter.dm(message, user_id)

