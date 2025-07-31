import sys
import socket
import random
import os
import json

from constants import Role, Stage
from node import SolanaNode
from transaction import Transaction, Instruction, AccountMeta
from wallet import save_wallet, generate_keypair

WALLET_FILE = os.getenv("WALLET_FILE", "my_wallet.txt")

def ensure_wallet():
    if not os.path.exists(WALLET_FILE):
        print("🔐 Wallet not found. Generate a new one...")
        priv, _ = generate_keypair()
        save_wallet(WALLET_FILE, priv)
        print("✅ The wallet is saved in", WALLET_FILE)

def choose_port(default=5000, max_attempts=100):
    for _ in range(max_attempts):
        port = default + random.randint(0, 1000)
        try:
            s = socket.socket()
            s.bind(("127.0.0.1", port))
            s.close()
            return port
        except:
            continue
    raise Exception("❌ Failed to select a free port")

def show_menu(node: SolanaNode):
    while True:
        print("\n===== Menu =====")
        print("1. Show address")
        print("2. Show balance")
        print("3. Send SOL")
        print("4. Show blockchain")
        print("5. Show peers")
        print("0. Exit")

        choice = input("Choice: ").strip()
        if choice == "1":
            print("🏠 Address:", node.address)
        elif choice == "2":
            acc = node.blockchain.accounts.get(node.address)
            if acc:
                print(f"💰 Balance: {acc.get('balance', 0)} SOL")
            else:
                print("💰 Balance: 0 SOL")
        elif choice == "3":
            if node.stage != Stage.TX:
                print("⏳ Wait until block is finalized")
                continue
            to = input("Recipient address: ").strip()
            amt = input("Amount: ").strip()
            try:
                amt = int(amt)
                tx = create_transfer_tx(node, to, amt)
                if tx and node.add_and_broadcast_tx(tx):
                    print("📤 Transaction sent!")
            except:
                print("❌ Invalid input")
        elif choice == "4":
            node.blockchain.print_chain()
        elif choice == "5":
            print("🔗 Connected peers:")
            for peer in node.peers:
                print(" -", peer)
        elif choice == "0":
            node.disconnect()
            print("👋 Goodbye!")
            break
        else:
            print("⚠️ Incorrect input")

def create_transfer_tx(node: SolanaNode, to_address: str, amount: int) -> Transaction:
    acc = node.blockchain.accounts.get(node.address)
    if not acc or acc.get("balance", 0) < amount:
        print("❌ Not enough SOL")
        return None

    instr = Instruction(
        program_id="SystemProgram",
        accounts=[
            AccountMeta(pubkey=node.address, is_signer=True, is_writable=True),
            AccountMeta(pubkey=to_address, is_signer=False, is_writable=True)
        ],
        data=json.dumps({"type": "transfer", "amount": amount})
    )

    recent_blockhash = node.blockchain.get_last_block().hash()
    tx = Transaction([instr], recent_blockhash)
    tx.sign(node.private_key)
    return tx

if __name__ == "__main__":
    role = Role.USER

    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "leader":
            role = Role.LEADER

    ensure_wallet()
    port = choose_port()
    node = SolanaNode("0.0.0.0", port, role)
    node.start()

    show_menu(node)
