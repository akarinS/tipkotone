import sys
import os
import sqlite3
import time
from coinrpc import CoinRPC
from decimal import Decimal
from config import rpcuser, rpcpassword, rpcport

class AccountWalletController(object):
    def __init__(self) -> None:
        self.rpc = CoinRPC(rpcuser, rpcpassword, rpcport)
        self.db_path = get_db_path()

        if not db_exists():
            init_db()

    def get_new_account_address(self, account: str) -> str:
        with sqlite3.connect(self.db_path, timeout = 60, isolation_level = 'EXCLUSIVE') as conn:
            try:
                address = self.rpc.call('getnewaddress')
                cursor = conn.cursor()
                cursor.execute('insert or ignore into account_wallet(account) values(?)', (account,))
                cursor.execute('insert into account_address(account, address) values(?, ?)', (account, address))

            except Exception as err:
                print('Error:', err)
                conn.rollback()

            else:
                conn.commit()

        return address if 'address' in locals() else ''

    def get_account_balance(self, account: str) -> Decimal:
        with sqlite3.connect(self.db_path, timeout = 60, isolation_level = 'EXCLUSIVE') as conn:
            try:
                cursor = conn.cursor()
                cursor.execute('insert or ignore into account_wallet(account) values(?)', (account,))
                cursor.execute('select balance from account_wallet where account == ?', (account,))

                balance = Decimal(str(cursor.fetchone()[0]))

            except Exception as err:
                print('Error:', err)
                conn.rollback()

            else:
                conn.commit()

        return balance if 'balance' in locals() else Decimal('0.0')

def get_db_path() -> str:
    return os.path.join(os.path.dirname(__file__), 'accountwallet.sqlite3')

def db_exists() -> bool:
    return os.path.exists(get_db_path())

def init_db() -> None:
    with sqlite3.connect(get_db_path(), timeout = 60, isolation_level = 'EXCLUSIVE') as conn:
        try:
            cursor = conn.cursor()
            cursor.execute('create table account_wallet(account text unique not null, balance real default 0.0 check(balance >= 0.0) not null)')
            cursor.execute('create table account_address(account text not null, address text unique not null)')
            cursor.execute('create table notified_txid(txid text unique not null, time integer not null, confirmed integer default 0 not null)')
            cursor.execute('create table withdrawal_request(account text not null, address text not null, amount real check(amount >= 0.1) not null, completed integer default 0 not null)')

        except Exception as err:
            print('Error:', err)
            conn.rollback()

        else:
            conn.commit()

def set_txid(txid: str) -> None:
    print(f'start set txid : {txid}')

    with sqlite3.connect(get_db_path(), timeout = 60, isolation_level = 'EXCLUSIVE') as conn:
        try:
            cursor = conn.cursor()
            print('insert txid')
            cursor.execute('insert or ignore into notified_txid(txid, time) values(?, ?)', (txid, int(time.time())))

        except Exception as err:
            print('Error:', err)
            conn.rollback()

        else:
            print('commit')
            conn.commit()

def check_txid(period: int = 3600) -> None:
    print('start check_txid')
    with sqlite3.connect(get_db_path(), timeout = 60, isolation_level = 'EXCLUSIVE') as conn:
        try:
            cursor = conn.cursor()
            cursor.execute('begin')
            cursor.execute('select txid from notified_txid where confirmed == 0 and time > ?', (int(time.time()) - period,))

            txids = [r[0] for r in cursor.fetchall()]

            rpc = CoinRPC(rpcuser, rpcpassword, rpcport)

            for txid in txids:
                print(f'checking {txid}')
                result = rpc.call('gettransaction', txid)

                if result is None or result.get('confirmations') < 10:
                    print('None or less than 10 conf')
                    continue

                print('getting rawtransaction')
                raw = rpc.call('getrawtransaction', txid)
                result = rpc.call('decoderawtransaction', raw)

                if raw is None or result is None:
                    print('None')
                    continue

                for vout in result.get('vout'):
                    address = vout.get('scriptPubKey').get('addresses')[0]
                    print(f'address is {address}')
                    cursor.execute('select account from account_address where address == ?', (address,))
                    account = cursor.fetchone()

                    if account is not None:
                        account = account[0]
                        print(f'{account} has the address')
                        cursor.execute('select balance from account_wallet where account == ?', (account,))

                        balance = Decimal(str(cursor.fetchone()[0]))
                        value = Decimal(str(vout.get('value')))
                        print(f'balance is {balance}')
                        print(f'value is {value}')
                 

                        balance = balance + value
                        print(f'new balance is {balance}')

                        cursor.execute('update account_wallet set balance = ? where account == ?', (float(balance), account))
                        print('update wallet')

                    else:
                        print('account not found')

                cursor.execute('update notified_txid set confirmed = 1 where txid == ?', (txid,))
                print('finish this txid')

        except Exception as err:
            print('Error:', err)
            conn.rollback()

        else:
            conn.commit()

    print('finish')

def exec_withdrawal() -> None:
    pass

def main() -> None:
    if not db_exists():
        init_db()

    if len(sys.argv) < 2:
        print('Argument is missing.')
        return

    if sys.argv[1] == 'set_txid':
        if len(sys.argv) < 3:
            print('Argument is missing.')
            return

        set_txid(sys.argv[2])
        return

    if sys.argv[1] == 'check_txid':
        if not len(sys.argv) < 3 and sys.argv[2].isdigit():
            check_txid(int(sys.argv[2]))
            return

        check_txid()
        return

    if sys.argv[1] == 'exec_withdrawal':
        exec_withdrawal()
        return

if __name__ == '__main__':
    main()

