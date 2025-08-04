import json
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from constants import Role, Stage, Constants
from deserialize_service import DeserializeService
from main import choose_port, create_transfer_tx
from node import SolanaNode
from wallet import load_wallet, pubkey_to_address, get_public_key


def start_research(node: SolanaNode, addresses: list[str]) -> None:
    # time_of_work, amount of transactions, tps, transaction latency

    coins_to_send = 1

    amount_of_blocks_before = len(node.blockchain.blocks)
    amount_of_generated_blocks = 3

    tx_submit_time = {}
    tx_latencies = []

    amount_of_added_txs = 0
    start = time.time()
    old_amount_of_blocks = len(node.blockchain.blocks)

    while len(node.blockchain.blocks) - amount_of_blocks_before != amount_of_generated_blocks:
        if len(node.blockchain.blocks) - old_amount_of_blocks == 1:
            old_amount_of_blocks = len(node.blockchain.blocks)

            for tx in node.blockchain.blocks[-1].transactions:
                tx_id = tx.hash()
                if tx_id in tx_submit_time:
                    latency = time.time() - tx_submit_time[tx_id]
                    tx_latencies.append(latency)

        if node.get_stage() != Stage.TX:
            continue

        tx = create_transfer_tx(node, random.choice(addresses), coins_to_send)
        if node.add_and_broadcast_tx(tx):
            amount_of_added_txs += 1
            tx_submit_time[tx.hash()] = time.time()

    time_of_work = time.time() - start
    tps = amount_of_added_txs / time_of_work

    print("Amount of transactions: ", amount_of_added_txs)
    print("Time spent: ", time_of_work / 60.0, " minutes")
    print("TPS: ", tps)

    print("📊 Transaction Latency (ms):")
    print(f"  avg: {np.mean(tx_latencies)  * 1000:.2}")
    print(f"  min: {np.min(tx_latencies) * 1000:.2}")
    print(f"  max: {np.max(tx_latencies) * 1000:.2}")
    print(f"  std: {np.std(tx_latencies) * 1000:.2}")

    # read_latency

    latencies = []
    addresses.append(node.address)

    for i in range(1000):
        addr = addresses[i % len(addresses)]
        t1 = time.perf_counter()
        node.blockchain.get_balance(addr)
        t2 = time.perf_counter()
        latencies.append(t2 - t1)

    print("Read Latency (ns):")
    print(f"  avg: {statistics.mean(latencies) * 1_000_000_000:.2f}")
    print(f"  min: {min(latencies) * 1_000_000_000:.2f}")
    print(f"  max: {max(latencies) * 1_000_000_000:.2f}")
    print(f"  std: {statistics.stdev(latencies) * 1_000_000_000:.2f}")

    # read_throughput

    NUM_THREADS = 10
    READS_PER_THREAD = 1000

    def read_task():
        count = 0
        for i in range(READS_PER_THREAD):
            node.blockchain.get_balance(addresses[i % len(addresses)])
            count += 1
        return count

    start = time.time()
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = [executor.submit(read_task) for _ in range(NUM_THREADS)]
        results = [f.result() for f in futures]
    end = time.time()

    total_reads = sum(results)
    throughput = total_reads / (end - start)
    print(f"Read Throughput: {throughput:.2f} reads/sec")






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
            start_research(node, addresses)
            print("Research finished")

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