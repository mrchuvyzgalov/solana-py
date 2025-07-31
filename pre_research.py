import json

from constants import Role
from node import SolanaNode


def prepare_leader(node: SolanaNode, amount_of_blocks: int, amount_of_tx_in_block: int):
    for i in range(amount_of_blocks):
        new_block = node.blockchain.produce_block(node.address)
        node.verify_and_add_block(new_block)
        print(f"Block #{i} added")

    with open(f"research_files/blockchain.json", "w") as f:
        json.dump(node.blockchain.to_dict(), f, indent=2)

if __name__ == "__main__":
    role = Role.LEADER
    AMOUNT_OF_BLOCKS = 3000
    AMOUNT_OF_TX_IN_BLOCK = 1000

    node = SolanaNode("0.0.0.0", 1111, role=role, wallet_file="research_files/leader_wallet.txt")
    prepare_leader(node, AMOUNT_OF_BLOCKS, AMOUNT_OF_TX_IN_BLOCK)

