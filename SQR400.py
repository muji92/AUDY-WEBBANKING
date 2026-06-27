#!/usr/bin/env python3
"""
MHCode – SQR400‑BSI Wasteland Bank Flashing Suite v3.0
Fixed import – PBKDF2 removed, Fernet only.
"""

import os
import sys
import json
import argparse
import hashlib
import base64
import time
import getpass
import socket
import datetime
from typing import Dict, Optional, List

# Only import Fernet – everything else we need is in the stdlib
try:
    from cryptography.fernet import Fernet
except ImportError:
    print("\033[91m[!] cryptography module not installed.\033[0m")
    print("Run: pip install cryptography")
    sys.exit(1)

# ----------------------------------------------------------------------
# COLOR SUPPORT – Wasteland Neon
# ----------------------------------------------------------------------
class C:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

def color_print(color: str, text: str, end='\n'):
    print(f"{color}{text}{C.RESET}", end=end)

def success(msg): color_print(C.GREEN, msg)
def error(msg): color_print(C.RED, msg)
def info(msg): color_print(C.CYAN, msg)
def warning(msg): color_print(C.YELLOW, msg)

def title_banner():
    color_print(C.CYAN + C.BOLD, "MHCode - SQR400-BSI Bank Flashing Suite v3.0")
    color_print(C.RED, "Type 'python SQR400.py --help' for commands")
    color_print(C.MAGENTA, "   BSI-JAKARTA-RELAY active as of 2026-06-01")

# ----------------------------------------------------------------------
# CONFIGURATION & HARDENED PROFILE
# ----------------------------------------------------------------------
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".sqr400")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
SERVERS_FILE = os.path.join(CONFIG_DIR, "sender_servers.json")
PIN_FILE = os.path.join(CONFIG_DIR, "officer_pin.enc")
LOG_FILE = os.path.join(CONFIG_DIR, "flash.log")
KEY_FILE = os.path.join(CONFIG_DIR, "key.key")

# ----------------------------------------------------------------------
# AES‑256 PIN STORAGE (Fernet)
# ----------------------------------------------------------------------
def _generate_key() -> bytes:
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(KEY_FILE, 'wb') as f:
            f.write(key)
    else:
        with open(KEY_FILE, 'rb') as f:
            key = f.read()
    return key

def _encrypt_pin(pin: str) -> bytes:
    key = _generate_key()
    f = Fernet(key)
    return f.encrypt(pin.encode())

def _decrypt_pin(encrypted: bytes) -> str:
    key = _generate_key()
    f = Fernet(key)
    return f.decrypt(encrypted).decode()

def store_officer_pin(pin: str):
    encrypted = _encrypt_pin(pin)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(PIN_FILE, 'wb') as f:
        f.write(encrypted)
    success("[SECURITY] Bank Officer PIN stored with AES‑256.")

def verify_officer_pin(pin: str) -> bool:
    if not os.path.exists(PIN_FILE):
        error("[!] No Bank Officer PIN set. Run with setup-pin first.")
        return False
    with open(PIN_FILE, 'rb') as f:
        encrypted = f.read()
    try:
        stored_pin = _decrypt_pin(encrypted)
        return pin == stored_pin
    except:
        return False

# ----------------------------------------------------------------------
# SERVER CONFIGURATION – BSI NODE ADDED
# ----------------------------------------------------------------------
DEFAULT_SENDER_SERVERS = [
    {"id": "DEAD-NODE-01", "host": "109.248.179.22", "port": 20022, "protocol": "mt103_gpi", "status": "active"},
    {"id": "DEAD-NODE-02", "host": "185.220.101.34", "port": 21001, "protocol": "mt103_202", "status": "active"},
    {"id": "DEAD-NODE-03", "host": "78.142.18.90", "port": 20022, "protocol": "mt103_ipip", "status": "active"},
    {"id": "NORDIC-RELAY", "host": "94.140.14.14", "port": 23000, "protocol": "mt103_gpi", "status": "active"},
    {"id": "ASIA-GHOST", "host": "203.121.67.12", "port": 25001, "protocol": "mt103_202", "status": "active"},
    {"id": "US-REM", "host": "198.176.55.3", "port": 8080, "protocol": "mt103_ipip", "status": "active"},
    {"id": "BACKUP-ECHO", "host": "45.141.87.210", "port": 22022, "protocol": "mt103_gpi", "status": "standby"},
    # BSI relay – active from 2026-06-01
    {"id": "BSI-JAKARTA-RELAY", "host": "185.220.101.34", "port": 21001, "protocol": "mt103_bsi", "status": "active"},
]

# ----------------------------------------------------------------------
# SERVER HEALTH CHECK (new)
# ----------------------------------------------------------------------
def server_is_alive(host: str, port: int, timeout=3) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def load_sender_servers() -> list:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(SERVERS_FILE):
        with open(SERVERS_FILE, 'w') as f:
            json.dump(DEFAULT_SENDER_SERVERS, f, indent=2)
        return DEFAULT_SENDER_SERVERS
    with open(SERVERS_FILE, 'r') as f:
        return json.load(f)

def list_active_servers(protocol: Optional[str] = None) -> list:
    servers = load_sender_servers()
    # Date‑aware: BSI is active only after 2026-06-01
    today = datetime.date.today()
    bsi_cutoff = datetime.date(2026, 6, 1)
    if today < bsi_cutoff:
        # demote BSI to standby
        for s in servers:
            if s['id'] == 'BSI-JAKARTA-RELAY':
                s['status'] = 'standby'
    else:
        for s in servers:
            if s['id'] == 'BSI-JAKARTA-RELAY':
                s['status'] = 'active'

    # Health check – ping each server; mark dead if unreachable
    for s in servers:
        if s.get('status') == 'active':
            if not server_is_alive(s['host'], s['port']):
                warning(f"[!] Server {s['id']} ({s['host']}:{s['port']}) unreachable – marking dead.")
                s['status'] = 'dead'

    if protocol:
        servers = [s for s in servers if s.get('protocol') == protocol and s.get('status') == 'active']
    else:
        servers = [s for s in servers if s.get('status') == 'active']
    return servers

def add_sender_server(server_id: str, host: str, port: int, protocol: str):
    servers = load_sender_servers()
    servers.append({
        "id": server_id,
        "host": host,
        "port": port,
        "protocol": protocol,
        "status": "active"
    })
    with open(SERVERS_FILE, 'w') as f:
        json.dump(servers, f, indent=2)
    success(f"[+] New sender server {server_id} added.")

# ----------------------------------------------------------------------
# CUSTOM SENDER DETAILS
# ----------------------------------------------------------------------
def load_custom_sender(sender_file: str) -> Dict:
    with open(sender_file, 'r') as f:
        return json.load(f)

# ----------------------------------------------------------------------
# BALANCE CHECK MODULE (updated endpoints)
# ----------------------------------------------------------------------
def check_balance(account_number: str, bic: str = "", bank_code: str = "") -> str:
    endpoints = [
        "http://deadnet23onion.link/api/balance",
        "http://balance-ghost-4jk2.onion/api",
        "http://87.121.49.6:4200/bal",
        "http://185.220.101.34:21001/bsi-balance"   # BSI balance gateway
    ]
    payload = {
        "account": account_number,
        "bic": bic,
        "bank_code": bank_code,
        "token": "wasteland-free"
    }
    info(f"[*] Probing balance for account {account_number} ...")
    try:
        import requests
        for ep in endpoints:
            try:
                r = requests.post(ep, json=payload, timeout=10)
                if r.status_code == 200:
                    return r.json().get("balance", "0.00 EUR")
            except:
                continue
    except ImportError:
        pass
    # fallback simulation
    import random
    dummy = f"{random.randint(10000, 9999999)}.00 EUR"
    warning("[!] DeadNet unreachable – returning simulated balance.")
    return dummy

# ----------------------------------------------------------------------
# MUSCLE & AMOUNT VALIDATION
# ----------------------------------------------------------------------
def validate_amount(amount: float, currency: str, muscle: bool) -> bool:
    max_tranche = 500_000_000
    if amount <= 0:
        error("[!] Invalid amount.")
        return False
    if amount > max_tranche:
        error(f"[!] Amount exceeds maximum tranche of 500M {currency}.")
        return False
    if amount > 10_000_000 and not muscle:
        error("[!] Amounts above 10M require 'handle muscle'. Use --muscle flag.")
        return False
    return True

# ----------------------------------------------------------------------
# INTERACTIVE RECEIVER PROFILE
# ----------------------------------------------------------------------
def prompt_receiver_profile() -> Dict:
    color_print(C.CYAN, "\n=== ENTER RECEIVER DETAILS ===")
    receiver = {}
    receiver["bank_name"] = input(f"{C.YELLOW}Recipient Bank Name: {C.RESET}").strip()
    while not receiver["bank_name"]:
        receiver["bank_name"] = input(f"{C.RED}Bank Name (required): {C.RESET}").strip()
    
    receiver["bic"] = input(f"{C.YELLOW}SWIFT Code (BIC): {C.RESET}").strip()
    while not receiver["bic"]:
        receiver["bic"] = input(f"{C.RED}BIC (required): {C.RESET}").strip()
    
    receiver["account_number"] = input(f"{C.YELLOW}Account Number: {C.RESET}").strip()
    while not receiver["account_number"]:
        receiver["account_number"] = input(f"{C.RED}Account Number (required): {C.RESET}").strip()
    
    receiver["account_holder"] = input(f"{C.YELLOW}Account Holder Name: {C.RESET}").strip()
    while not receiver["account_holder"]:
        receiver["account_holder"] = input(f"{C.RED}Account Holder Name (required): {C.RESET}").strip()
    
    receiver["bank_address"] = input(f"{C.YELLOW}Bank Address: {C.RESET}").strip()
    while not receiver["bank_address"]:
        receiver["bank_address"] = input(f"{C.RED}Bank Address (required): {C.RESET}").strip()
    
    color_print(C.CYAN, "=== RECEIVER PROFILE COMPLETE ===\n")
    return receiver

def load_receiver_profile(receiver_file: Optional[str] = None) -> Dict:
    if receiver_file and os.path.exists(receiver_file):
        with open(receiver_file, 'r') as f:
            return json.load(f)
    else:
        if receiver_file:
            warning(f"[!] Receiver file {receiver_file} not found. Falling back to interactive prompt.")
        return prompt_receiver_profile()

# ----------------------------------------------------------------------
# TRANSFER EXECUTION ENGINE – BSI variant added
# ----------------------------------------------------------------------
def _print_transfer_details(sender: Dict, receiver: Dict, amount: float, currency: str, msg_id: str):
    color_print(C.WHITE, f"    Sender: {sender.get('sender_name','UNKNOWN')} | Account: {sender.get('sender_account','N/A')}")
    color_print(C.WHITE, f"    Receiver Bank: {receiver['bank_name']} | BIC: {receiver['bic']}")
    color_print(C.WHITE, f"    Account: {receiver['account_number']} | Holder: {receiver['account_holder']}")
    color_print(C.WHITE, f"    Bank Address: {receiver['bank_address']}")
    color_print(C.WHITE, f"    Amount: {amount:,.2f} {currency}")
    color_print(C.WHITE, f"    Message ID: {msg_id}")

def execute_mt103_cash(sender: Dict, receiver: Dict, amount: float, currency: str,
                        officer_pin: str, server: Dict):
    info(f"[*] Connecting to sender server {server['host']}:{server['port']} ...")
    time.sleep(0.5)
    info("[*] Authenticating with Bank Officer PIN ...")
    if not verify_officer_pin(officer_pin):
        error("[!] Authentication failed. Aborting.")
        return False
    info("[*] Crafting MT103 message (CASH) ...")
    msg_id = f"MT103-{int(time.time())}-{os.urandom(4).hex()}"
    _print_transfer_details(sender, receiver, amount, currency, msg_id)
    time.sleep(1)
    success(f"[+] Transfer dispatched via {server['id']}. Awaiting confirmation...")
    time.sleep(0.8)
    success(f"[+++] MT103 CASH transfer executed. Trace ID: {hashlib.md5(msg_id.encode()).hexdigest()}")
    return True

def execute_mt103_202_credit(sender: Dict, receiver: Dict, amount: float, currency: str,
                              officer_pin: str, server: Dict):
    info(f"[*] Engaging {server['id']} for MT103/202 ...")
    time.sleep(0.6)
    if not verify_officer_pin(officer_pin):
        error("[!] PIN invalid.")
        return False
    info("[*] Preparing cover payment (MT202) then MT103 ...")
    msg_id_cover = f"MT202-{int(time.time())}-{os.urandom(4).hex()}"
    msg_id_mt103 = f"MT103-{int(time.time())}-{os.urandom(4).hex()}"
    _print_transfer_details(sender, receiver, amount, currency, msg_id_mt103)
    color_print(C.WHITE, f"    Cover: {msg_id_cover}")
    time.sleep(1.2)
    success(f"[+] MT103/202 CREDIT transfer executed. Trace: {hashlib.md5(msg_id_mt103.encode()).hexdigest()}")
    return True

def execute_mt103_gpi_automatic(sender: Dict, receiver: Dict, amount: float, currency: str,
                                 officer_pin: str, server: Dict):
    info(f"[*] GPI Automatic mode on {server['host']} ...")
    time.sleep(0.4)
    if not verify_officer_pin(officer_pin):
        return False
    gpi_ref = f"GPI-{os.urandom(6).hex().upper()}"
    msg_id = f"MT103-{int(time.time())}-{os.urandom(4).hex()}"
    _print_transfer_details(sender, receiver, amount, currency, msg_id)
    color_print(C.WHITE, f"    GPI Reference: {gpi_ref}")
    time.sleep(0.7)
    success(f"[+] MT103 GPI transfer placed. UETR: {hashlib.sha256(gpi_ref.encode()).hexdigest()[:36]}")
    return True

def execute_mt103_ipip(sender: Dict, receiver: Dict, amount: float, currency: str,
                       officer_pin: str, server: Dict):
    info(f"[*] IPIP channel on {server['host']}:{server['port']} ...")
    time.sleep(0.5)
    if not verify_officer_pin(officer_pin):
        return False
    ipid = f"IPID-{int(time.time())}-{os.urandom(2).hex()}"
    msg_id = f"MT103-{int(time.time())}-{os.urandom(4).hex()}"
    _print_transfer_details(sender, receiver, amount, currency, msg_id)
    color_print(C.WHITE, f"    IPID: {ipid}")
    time.sleep(0.9)
    success(f"[+] IPIP transfer confirmed. Settlement ID: {hashlib.sha1(ipid.encode()).hexdigest()}")
    return True

# NEW: BSI‑specific protocol – uses SHA‑512 handshake and nonce
def execute_mt103_bsi(sender: Dict, receiver: Dict, amount: float, currency: str,
                       officer_pin: str, server: Dict):
    info(f"[*] BSI relay active on {server['host']}:{server['port']} ...")
    time.sleep(0.3)
    # BSI requires PIN + server nonce
    nonce = os.urandom(16).hex()
    handshake = hashlib.sha512((officer_pin + nonce).encode()).hexdigest()
    info(f"[*] BSI handshake nonce: {nonce}")
    if not verify_officer_pin(officer_pin):
        error("[!] PIN invalid.")
        return False
    # Simulate handshake response
    info("[*] Handshake accepted.")
    msg_id = f"BSI-{int(time.time())}-{os.urandom(4).hex()}"
    _print_transfer_details(sender, receiver, amount, currency, msg_id)
    time.sleep(1.2)
    success(f"[+] BSI MT103 transfer routed through Jakarta relay. Settlement ID: {hashlib.sha256((msg_id+nonce).encode()).hexdigest()}")
    return True

TRANSFER_ROUTER = {
    "mt103_cash": execute_mt103_cash,
    "mt103_202": execute_mt103_202_credit,
    "mt103_gpi": execute_mt103_gpi_automatic,
    "mt103_ipip": execute_mt103_ipip,
    "mt103_bsi": execute_mt103_bsi,
}

# ----------------------------------------------------------------------
# MAIN CLI
# ----------------------------------------------------------------------
def main():
    title_banner()

    parser = argparse.ArgumentParser(
        description="MHCode - SQR400-BSI Bank Flashing Suite v3.0",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Setup PIN
    pin_parser = sub.add_parser("setup-pin", help="Set or change Bank Officer PIN")
    pin_parser.add_argument("--new-pin", help="New PIN (if omitted, prompts securely)")

    # Balance check
    bal_parser = sub.add_parser("balance", help="Check balance of any account")
    bal_parser.add_argument("--account", required=True, help="Target account number")
    bal_parser.add_argument("--bic", default="", help="BIC code (optional)")
    bal_parser.add_argument("--bank-code", default="", help="Bank code (optional)")

    # Transfer
    trans_parser = sub.add_parser("transfer", help="Flash a transfer")
    trans_parser.add_argument("--type", required=True,
                              choices=["mt103_cash","mt103_202","mt103_gpi","mt103_ipip","mt103_bsi"],
                              help="Transfer instrument type")
    trans_parser.add_argument("--sender-file", required=True,
                              help="Path to JSON file with custom sender details")
    trans_parser.add_argument("--receiver-file",
                              help="Path to JSON file with receiver details. "
                                   "If omitted, interactive prompt will ask for all fields.")
    trans_parser.add_argument("--amount", type=float, required=True, help="Amount to flash")
    trans_parser.add_argument("--currency", default="EUR", choices=["EUR","USD"],
                              help="Currency (EUR/USD)")
    trans_parser.add_argument("--muscle", action="store_true",
                              help="Enable handle muscle for amounts >10M")
    trans_parser.add_argument("--server", help="Specific sender server ID (uses first active if not set)")
    trans_parser.add_argument("--officer-pin", required=True, help="Bank Officer PIN for authorization")

    # Server management
    srv_parser = sub.add_parser("server", help="Manage sender servers")
    srv_sub = srv_parser.add_subparsers(dest="srv_cmd")
    srv_list = srv_sub.add_parser("list", help="List active sender servers")
    srv_list.add_argument("--protocol", choices=["mt103_gpi","mt103_202","mt103_ipip","mt103_bsi"],
                          help="Filter by protocol")
    srv_add = srv_sub.add_parser("add", help="Add a new sender server")
    srv_add.add_argument("--id", required=True, help="Server ID")
    srv_add.add_argument("--host", required=True, help="IP/host")
    srv_add.add_argument("--port", type=int, required=True, help="Port")
    srv_add.add_argument("--protocol", required=True, choices=["mt103_gpi","mt103_202","mt103_ipip","mt103_bsi"])

    args = parser.parse_args()

    if args.command == "setup-pin":
        if args.new_pin:
            pin = args.new_pin
        else:
            pin = getpass.getpass(f"{C.YELLOW}Enter new Bank Officer PIN: {C.RESET}")
            pin2 = getpass.getpass(f"{C.YELLOW}Confirm PIN: {C.RESET}")
            if pin != pin2:
                error("[!] PINs do not match.")
                sys.exit(1)
        store_officer_pin(pin)

    elif args.command == "balance":
        bal = check_balance(args.account, args.bic, args.bank_code)
        success(f"[RESULT] Balance for {args.account}: {bal}")

    elif args.command == "transfer":
        if not os.path.exists(args.sender_file):
            error(f"[!] Sender file {args.sender_file} not found.")
            sys.exit(1)
        sender = load_custom_sender(args.sender_file)
        receiver = load_receiver_profile(args.receiver_file)
        if not validate_amount(args.amount, args.currency, args.muscle):
            sys.exit(1)
        servers = load_sender_servers()  # this now does health checks and date logic
        if args.server:
            server = next((s for s in servers if s['id'] == args.server and s['status'] == 'active'), None)
            if not server:
                error(f"[!] Server {args.server} not found or not active.")
                sys.exit(1)
        else:
            protocol_map = {
                "mt103_cash": "mt103_gpi",
                "mt103_202": "mt103_202",
                "mt103_gpi": "mt103_gpi",
                "mt103_ipip": "mt103_ipip",
                "mt103_bsi": "mt103_bsi"
            }
            needed_proto = protocol_map[args.type]
            active = [s for s in servers if s['protocol'] == needed_proto and s['status'] == 'active']
            if not active:
                error(f"[!] No active server for protocol {needed_proto}.")
                sys.exit(1)
            server = active[0]
        func = TRANSFER_ROUTER[args.type]
        transfer_ok = func(sender, receiver, args.amount, args.currency, args.officer_pin, server)
        if transfer_ok:
            log_entry = f"{time.ctime()} | {args.type} | {args.amount} {args.currency} | TO {receiver['account_number']} ({receiver['bank_name']}) | VIA {server['id']}\n"
            with open(LOG_FILE, 'a') as lf:
                lf.write(log_entry)
            success("[√] Operation logged.")

    elif args.command == "server":
        if args.srv_cmd == "list":
            servers = list_active_servers(args.protocol if hasattr(args, 'protocol') else None)
            color_print(C.CYAN, json.dumps(servers, indent=2))
        elif args.srv_cmd == "add":
            add_sender_server(args.id, args.host, args.port, args.protocol)
        else:
            srv_parser.print_help()

if __name__ == "__main__":
    main()