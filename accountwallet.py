from typing import Any, Callable, List, Tuple, Union
import sys
import os
import sqlite3
import time
import coinrpc
from decimal import Decimal, ROUND_DOWN
from config import WALLETDBPATH, MINCONF


# decorator
def sql_decorator(sql_func: Callable) -> Callable:
    def new_sql_func(*args: Any, **kwargs: Any) -> Any:
        with sqlite3.connect(WALLETDBPATH, timeout = 60, isolation_level = 'EXCLUSIVE') as conn:
            for i in range(5):
                try:
                    cursor = conn.cursor()
                    cursor.execute('begin EXCLUSIVE')

                    r = sql_func(cursor, *args, **kwargs)

                except Exception as err:
                    print('Error:', err)
                    print('retry')
                    conn.rollback()
                    e = err
                    continue

                else:
                    conn.commit()
                    return r

            raise e

    return new_sql_func

@sql_decorator
def init_db(cursor: sqlite3.Cursor) -> None:
    cursor.execute('create table account_wallet(account text unique not null, balance real default 0.0 check(balance >= 0.0) not null)')
    cursor.execute('create table account_address(account text not null, address text unique not null, time integer not null)')
    cursor.execute('create table notified_tx(txid text not null, time integer not null, confirmed integer default 0 not null, account text, value real)')
    cursor.execute('create table withdrawal_req(account text not null, address text not null, amount real check(amount >= 0.01) not null, completed integer default 0 not null)')

@sql_decorator
def get_account_balance(cursor: sqlite3.Cursor, account: str) -> Tuple[Decimal, Decimal]:
    cursor.execute('insert or ignore into account_wallet(account) values(?)', (account,))

    cursor.execute('select balance from account_wallet where account == ?', (account,))
    balance = Decimal(str(cursor.fetchone()[0]))

    cursor.execute('select value from notified_tx where account == ? and confirmed == 0 and time > ?', (account, int(time.time()) - 60 * MINCONF * 10))
    values = [Decimal(str(r[0])) for r in cursor.fetchall()]

    confirming_balance = Decimal('0.0')
    for value in values:
        confirming_balance = confirming_balance + value

    return (balance, confirming_balance)

@sql_decorator
def get_account_address(cursor: sqlite3.Cursor, account: str) -> str:
    cursor.execute('insert or ignore into account_wallet(account) values(?)', (account,))

    cursor.execute('select address from account_address where account == ? and time > ?', (account, int(time.time()) - 60 * 60 * 24 * 7))
    address = cursor.fetchone()

    if address is None:
        address = coinrpc.call('getnewaddress')
        cursor.execute('insert into account_address(account, address, time) values(?, ?, ?)', (account, address, int(time.time())))

    else:
        address = address[0]

    return address

def is_amount(str_amount: str) -> bool:
    if str_amount.lower() in {'all', '全額'}:
        return True

    try:
        Decimal(str_amount)

    except:
        return False

    return True

def get_amount(str_amount: str, balance: Decimal) -> Decimal:
    if str_amount.lower() in {'all', '全額'}:
        return balance

    return Decimal(str_amount).quantize(Decimal('1e-8'), rounding = ROUND_DOWN)

@sql_decorator
def move(cursor: sqlite3.Cursor, from_account: str, to_account: str, str_amount: str) -> Union[str, Decimal]:
    cursor.execute('insert or ignore into account_wallet(account) values(?)', (from_account,))
    cursor.execute('insert or ignore into account_wallet(account) values(?)', (to_account,))

    if from_account == to_account:
        return 'self'

    if not is_amount(str_amount):
        return 'wrong'

    cursor.execute('select balance from account_wallet where account == ?', (from_account,))
    from_balance = Decimal(str(cursor.fetchone()[0]))

    cursor.execute('select balance from account_wallet where account == ?', (to_account,))
    to_balance = Decimal(str(cursor.fetchone()[0]))

    amount = get_amount(str_amount, from_balance)

    if amount <= 0:
        return 'few'

    if from_balance < amount:
        return 'insufficient'

    from_balance = from_balance - amount
    to_balance = to_balance + amount

    cursor.execute('update account_wallet set balance = ? where account == ?', (float(from_balance), from_account))
    cursor.execute('update account_wallet set balance = ? where account == ?', (float(to_balance), to_account))

    return amount

@sql_decorator
def add_withdrawal_request(cursor: sqlite3.Cursor, account: str, address: str, str_amount: str) -> Union[str, Decimal]:
    cursor.execute('insert or ignore into account_wallet(account) values(?)', (account,))

    if not is_amount(str_amount):
        return 'wrong'

    cursor.execute('select balance from account_wallet where account == ?', (account,))
    balance = Decimal(str(cursor.fetchone()[0]))

    amount = get_amount(str_amount, balance)

    if amount < Decimal('0.01'):
        return 'few'

    if balance < amount:
        return 'insufficient'

    balance = balance - amount

    cursor.execute('update account_wallet set balance = ? where account == ?', (float(balance), account))
    cursor.execute('insert into withdrawal_req(account, address, amount) values(?, ?, ?)', (account, address, float(amount)))

    return amount

def main() -> None:
    @sql_decorator
    def notify_tx(cursor: sqlite3.Cursor, txid: str) -> None:
        cursor.execute('select * from notified_tx where txid == ?', (txid,))

        if cursor.fetchone() is not None:
            return

        try:
            result = coinrpc.call('decoderawtransaction', coinrpc.call('getrawtransaction', txid))

        except:
            result = None

        if result is None:
            cursor.execute('insert into notified_tx(txid, time, confirmed) values(?, ?, ?)', (txid, int(time.time()), -1))
            return

        account_found = False

        for vout in result.get('vout'):
            for address in vout.get('scriptPubKey').get('addresses'):
                cursor.execute('select account from account_address where address == ?', (address,))
                account = cursor.fetchone()

                if account is None:
                    continue

                account_found = True

                account = account[0]
                value = vout.get('value')

                cursor.execute('insert into notified_tx(txid, time, account, value) values(?, ?, ?, ?)', (txid, int(time.time()), account, value))
                continue

        if not account_found:
            cursor.execute('insert into notified_tx(txid, time, confirmed) values(?, ?, ?)', (txid, int(time.time()), 2))

    @sql_decorator
    def check_tx(cursor: sqlite3.Cursor) -> None:
        cursor.execute('select txid from notified_tx where confirmed == 0 and time > ?', (int(time.time()) - 60 * MINCONF * 10,))

        txids = {r[0] for r in cursor.fetchall()}

        if len(txids) == 0:
            return

        for txid in txids:
            result = coinrpc.call('gettransaction', txid)

            if result is None:
                cursor.execute('update notified_tx set confirmed = -1 where txid == ?', (txid,))
                continue

            confirmations = result.get('confirmations')

            if confirmations < MINCONF:
                continue

            cursor.execute('select account, value from notified_tx where txid == ?', (txid,))

            for account, value in cursor.fetchall():
                cursor.execute('select balance from account_wallet where account == ?', (account,))

                balance = Decimal(str(cursor.fetchone()[0]))
                value = Decimal(str(value))

                balance = balance + value
                cursor.execute('update account_wallet set balance = ? where account == ?', (float(balance), account))

            cursor.execute('update notified_tx set confirmed = 1 where txid == ?', (txid,))

    @sql_decorator
    def exec_withdrawal(cursor: sqlite3.Cursor) -> None:
        cursor.execute('select address from withdrawal_req where completed == 0')
        addresses = {r[0] for r in cursor.fetchall()}

        if len(addresses) == 0:
            return

        params = {}

        for address in addresses:
            cursor.execute('select amount from withdrawal_req where address == ? and completed == 0', (address,))
            req_amounts = [Decimal(str(r[0])) for r in cursor.fetchall()]

            amount = Decimal('0.0')
            for req_amount in req_amounts:
                amount = amount + req_amount

            params[address] = float(amount)

        try:
            txid = coinrpc.call('sendmany', '', params, MINCONF, '', list(addresses))

        except:
            txid = None

        if txid is None:
            cursor.execute('select account, value from withdrawal_req where completed == 0')
            for req in cursor.fetchall():
                account = req[0]
                value = Decimal(str(req[1]))

                cursor.execute('select balance from account_wallet where account == ?', (account,))
                balance = Decimal(str(cursor.fetchone()[0]))

                balance = balance + value

                cursor.execute('update account_wallet set balance = ? where account == ?', (float(balance), account))

            cursor.execute('update withdrawal_req set completed = -1 where completed == 0')
            return

        cursor.execute('update withdrawal_req set completed = 1 where completed == 0')

    if len(sys.argv) < 2:
        print('Argument is missing.')
        return

    if sys.argv[1] == 'notify_tx':
        if len(sys.argv) < 3:
            print('Argument is missing.')
            return

        notify_tx(sys.argv[2])
        return

    if sys.argv[1] == 'check_tx':
        check_tx()
        return

    if sys.argv[1] == 'exec_withdrawal':
        exec_withdrawal()
        return


if not os.path.exists(WALLETDBPATH):
    init_db()


if __name__ == '__main__':
    main()

