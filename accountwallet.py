from typing import Any, Callable, List, Tuple
import sys
import os
import sqlite3
import time
from coinrpc import CoinRPC
from decimal import Decimal
from config import DBPATH
from config import RPCUSER, RPCPASSWORD, RPCPORT
from config import MINCONF


# decorator
def sql_decorator(sql_func: Callable) -> Callable:
    def new_sql_func(*args: Any, **kwargs: Any) -> Any:
        with sqlite3.connect(DBPATH, timeout = 60, isolation_level = 'EXCLUSIVE') as conn:
            for i in range(5):
                try:
                    cursor = conn.cursor()
                    cursor.execute('begin')

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
    cursor.execute('create table account_address(account text not null, address text unique not null)')
    cursor.execute('create table notified_tx(txid text not null, time integer not null, confirmed integer default 0 not null, account text, value real)')
    cursor.execute('create table withdrawal_req(account text not null, address text not null, amount real check(amount >= 0.1) not null, completed integer default 0 not null)')

@sql_decorator
def get_new_account_address(cursor: sqlite3.Cursor, account: str) -> str:
    address = rpc.call('getnewaddress')

    cursor.execute('insert or ignore into account_wallet(account) values(?)', (account,))
    cursor.execute('insert into account_address(account, address) values(?, ?)', (account, address))

    return address

@sql_decorator
def get_addresses_by_account(cursor: sqlite3.Cursor, account: str) -> List:
    cursor.execute('select address from account_address where account == ?', (account,))
    addresses = [r[0] for r in cursor.fetchall()]

    return addresses

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

def main() -> None:
    @sql_decorator
    def notify_tx(cursor: sqlite3.Cursor, txid: str) -> None:
        print()
        print('notify_tx')
        print(f'  txid : {txid}')

        cursor.execute('select * from notified_tx where txid == ?', (txid,))

        if cursor.fetchone() is not None:
            print('    already set')
            return

        try:
            result = rpc.call('decoderawtransaction', rpc.call('getrawtransaction', txid))

        except:
            result = None

        if result is None:
            print('    result is None')
            cursor.execute('insert into notified_tx(txid, time, confirmed) values(?, ?, ?)', (txid, int(time.time()), -1))
            print('    set confirmed = -1')
            return

        account_found = False

        for vout in result.get('vout'):
            for address in vout.get('scriptPubKey').get('addresses'):
                print(f'    address : {address}')
                cursor.execute('select account from account_address where address == ?', (address,))
                account = cursor.fetchone()

                if account is None:
                    print('      account not found')
                    continue

                account_found = True
                print('      account found')

                account = account[0]
                value = vout.get('value')

                cursor.execute('insert into notified_tx(txid, time, account, value) values(?, ?, ?, ?)', (txid, int(time.time()), account, value))
                print(f'      set confirmed = 0, account = {account}, value = {value}')
                continue

        if not account_found:
            cursor.execute('insert into notified_tx(txid, time, confirmed) values(?, ?, ?)', (txid, int(time.time()), 2))
            print('  set confirmed = 2')

    @sql_decorator
    def check_tx(cursor: sqlite3.Cursor) -> None:
        print()
        print('check_tx')
        cursor.execute('select txid from notified_tx where confirmed == 0 and time > ?', (int(time.time()) - 60 * MINCONF * 10,))

        txids = set([r[0] for r in cursor.fetchall()])

        if len(txids) == 0:
            print('no transaction')
            return

        for txid in txids:
            print(f'  txid : {txid}')
            result = rpc.call('gettransaction', txid)

            if result is None:
                print('    result is None')
                cursor.execute('update notified_tx set confirmed = -1 where txid == ?', (txid,))
                print('    set confirmed = -1')
                continue

            confirmations = result.get('confirmations')

            if confirmations < MINCONF:
                print(f'    confirmations is {confirmations} < {MINCONF}')
                continue

            cursor.execute('select account, value from notified_tx where txid == ?', (txid,))

            for account, value in cursor.fetchall():
                print(f'    account : {account}, value : {value}')
                cursor.execute('select balance from account_wallet where account == ?', (account,))

                balance = Decimal(str(cursor.fetchone()[0]))
                value = Decimal(str(value))
                print(f'       before balance = {balance}')

                balance = balance + value
                print(f'        after balance = {balance}')

                print('        update balance')
                cursor.execute('update account_wallet set balance = ? where account == ?', (float(balance), account))
                print('        success')

            cursor.execute('update notified_tx set confirmed = 1 where txid == ?', (txid,))

    def exec_withdrawal() -> None:
        pass

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


if not os.path.exists(DBPATH):
    init_db()

rpc = CoinRPC(RPCUSER, RPCPASSWORD, RPCPORT)


if __name__ == '__main__':
    main()

