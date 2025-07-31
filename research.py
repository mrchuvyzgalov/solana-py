import json
import random
import sys
import time

from constants import Role, Stage, Constants
from deserialize_service import DeserializeService
from main import choose_port, create_transfer_tx
from node import SolanaNode
from wallet import load_wallet, pubkey_to_address, get_public_key


def start_research(node: SolanaNode, addresses: list[str]) -> (int, float): # (amount of added txs, time)
    coins_to_send = 1

    amount_of_blocks_before = len(node.blockchain.blocks)
    amount_of_generated_blocks = 3

    amount_of_added_txs = 0
    start = time.time()

    while len(node.blockchain.blocks) - amount_of_blocks_before != amount_of_generated_blocks:
        if node.get_stage() != Stage.TX:
            continue

        tx = create_transfer_tx(node, random.choice(addresses), coins_to_send)
        if node.add_and_broadcast_tx(tx):
            amount_of_added_txs += 1

    return amount_of_added_txs, time.time() - start

def get_addresses() -> list[str]:
    wallet_files = [
        "research_files/user_wallet0.txt",
        "research_files/user_wallet1.txt",
        "research_files/user_wallet2.txt"
    ]

    pr_keys: list[str] = []

    for wallet_f in wallet_files:
        pr_keys.append(load_wallet(wallet_f))

    return [pubkey_to_address(get_public_key(pr_key)) for pr_key in pr_keys]

def prepare_leader(node: SolanaNode):
    with open("research_files/blockchain.json", "r") as f:
        blockchain_data = json.load(f)
        blocks = DeserializeService.deserialize_chain(blockchain_data)
        node.blockchain.try_to_update_chain(blocks)

def show_menu(node: SolanaNode):
    addresses: list[str] = get_addresses()

    while True:
        print("\n===== Menu =====")
        print("1. Start research")
        print("0. Exit")

        choice = input("Choice: ").strip()
        if choice == "1":
            print("Research started")
            tx_amount, sec = start_research(node, addresses)
            print("Amount of transactions: ", tx_amount)
            print("Time spent: ", sec / 60.0, " minutes")
            print("TPS: ", tx_amount / sec)

        elif choice == "0":
            node.disconnect()
            print("👋 Goodbye!")
            break
        else:
            print("⚠️ Incorrect input")

if __name__ == "__main__":
    Constants.TIME_TO_SLEEP = 0.4
    AMOUNT_OF_START_BLOCKS = 3000
    role = Role.USER
    wallet_file = "my_wallet.txt"

    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "leader":
            role = Role.LEADER
            wallet_file = "research_files/leader_wallet.txt"
        elif command == "user":
            role = Role.USER
            number_of_user = sys.argv[2]
            wallet_file = f"research_files/user_wallet{number_of_user}.txt"


    port = choose_port()
    node = SolanaNode("0.0.0.0", port, role, wallet_file)

    if role == Role.LEADER:
        print("Preparation started...")
        prepare_leader(node)
        print("Preparation finished")

    node.start()

    while True:
        time.sleep(2)
        if len(node.blockchain.blocks) >= AMOUNT_OF_START_BLOCKS:
            break

    print("❗❗❗You can start research...")
    show_menu(node)