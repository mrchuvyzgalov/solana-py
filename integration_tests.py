import copy
import tempfile
import time

import pytest

from constants import Constants, Role
from main import create_transfer_tx
from node import SolanaNode
from wallet import generate_keypair

Constants.TIME_TO_SLEEP = 10

@pytest.fixture
def temp_wallet_file1():
    privkey, _ = generate_keypair()
    path = tempfile.mktemp()
    with open(path, "w") as f:
        f.write(privkey)
    return path

@pytest.fixture
def temp_wallet_file2():
    privkey, _ = generate_keypair()
    path = tempfile.mktemp()
    with open(path, "w") as f:
        f.write(privkey)
    return path

def test_leader_node_creates_block_and_updates_balance(temp_wallet_file1):
    host = "127.0.0.1"
    port = 1111

    node = SolanaNode(host=host, port=port, role=Role.LEADER, wallet_file=temp_wallet_file1)
    node.start()

    time.sleep(Constants.TIME_TO_SLEEP * 1.5)

    chain = node.blockchain.blocks
    assert len(chain) == 2, "Expected 2 blocks (including genesis)"

    last_block = chain[-1]
    assert len(last_block.transactions) == 0, "The last block must contain 0 transactions"

    balance = node.blockchain.get_balance(node.address)
    assert balance == Constants.BLOCK_REWARD, f"The balance should be {Constants.BLOCK_REWARD}, but it is {balance}"

def test_node_can_synchronize_chain(temp_wallet_file1, temp_wallet_file2):
    host = "127.0.0.1"
    leader_port = 1111
    user_port = 2222

    leader_node = SolanaNode(host=host, port=leader_port, role=Role.LEADER, wallet_file=temp_wallet_file1)
    user_node = SolanaNode(host=host, port=user_port, role=Role.USER, wallet_file=temp_wallet_file2)

    # mocks
    leader_node._external_ip = host
    user_node._external_ip = host

    leader_node._listen_tcp = None
    user_node._listen_tcp = None

    leader_node._handle_tcp_connection = None
    user_node._handle_tcp_connection = None

    leader_node._listen_discovery = None
    user_node._listen_discovery = None

    leader_node._broadcast_presence = None
    user_node._broadcast_presence = None

    def broadcast_to_user(message: dict):
        if len(leader_node.peers) > 0:
            user_node.message_queue.put(message)

    def broadcast_to_leader(message: dict):
        if len(user_node.peers) > 0:
            leader_node.message_queue.put(message)

    leader_node._broadcast = broadcast_to_user
    user_node._broadcast = broadcast_to_leader

    # start miner node
    leader_node.start()

    time.sleep(Constants.TIME_TO_SLEEP * 1.5)

    # start user node
    user_node.start()

    leader_node.peers.add((host, user_port))
    user_node.peers.add((host, leader_port))
    user_node.validators_nodes.add(f"{host}:{leader_port}")

    user_node._broadcast_request_chain()

    time.sleep(5)

    miner_chain = copy.deepcopy(leader_node.blockchain.blocks)
    user_chain = copy.deepcopy(user_node.blockchain.blocks)

    miner_balance = leader_node.blockchain.get_balance(leader_node.address)
    user_balance = user_node.blockchain.get_balance(user_node.address)

    assert len(miner_chain) == 2, "Expected 2 miner blocks (including genesis)"
    assert len(user_chain) == 2, "Expected 2 user blocks (including genesis)"

    assert [b.to_dict() for b in miner_chain] == [b.to_dict() for b in user_chain], "Expected that the chains are identical"

    assert miner_balance == Constants.BLOCK_REWARD, f"The miner balance should be {Constants.BLOCK_REWARD}, but it is {miner_balance}"
    assert user_balance == 0, f"The user balance should be 0, but it is {user_balance}"

def test_transaction_propagates_between_nodes(temp_wallet_file1, temp_wallet_file2):
    host = "127.0.0.1"
    leader_port = 1111
    user_port = 2222

    leader_node = SolanaNode(host=host, port=leader_port, role=Role.LEADER, wallet_file=temp_wallet_file1)
    user_node = SolanaNode(host=host, port=user_port, role=Role.USER, wallet_file=temp_wallet_file2)

    # mocks
    leader_node._external_ip = host
    user_node._external_ip = host

    leader_node._listen_tcp = None
    user_node._listen_tcp = None

    leader_node._handle_tcp_connection = None
    user_node._handle_tcp_connection = None

    leader_node._listen_discovery = None
    user_node._listen_discovery = None

    leader_node._broadcast_presence = None
    user_node._broadcast_presence = None

    def broadcast_to_user(message: dict):
        if len(leader_node.peers) > 0:
            user_node.message_queue.put(message)

    def broadcast_to_leader(message: dict):
        if len(user_node.peers) > 0:
            leader_node.message_queue.put(message)

    leader_node._broadcast = broadcast_to_user
    user_node._broadcast = broadcast_to_leader

    user_node.validators_nodes.add(f"{host}:{leader_port}")

    # start miner node
    leader_node.start()

    time.sleep(Constants.TIME_TO_SLEEP * 1.5)

    # start user node
    user_node.start()

    leader_node.peers.add((host, user_port))
    user_node.peers.add((host, leader_port))

    user_node._broadcast_request_chain()

    time.sleep(5)

    coins_to_send = 1
    tx = create_transfer_tx(leader_node, to_address=user_node.address, amount=coins_to_send)
    leader_node.add_and_broadcast_tx(tx)

    time.sleep(Constants.TIME_TO_SLEEP)

    leader_chain = copy.deepcopy(leader_node.blockchain.blocks)
    user_chain = copy.deepcopy(user_node.blockchain.blocks)

    leader_balance = leader_node.blockchain.get_balance(leader_node.address)
    user_balance = user_node.blockchain.get_balance(user_node.address)

    expected_leader_balance = Constants.BLOCK_REWARD * 2 - coins_to_send
    expected_user_balance = coins_to_send

    assert len(leader_chain) == 3, "Expected 3 miner blocks (including genesis)"
    assert len(user_chain) == 3, "Expected 3 user blocks (including genesis)"

    assert leader_balance == expected_leader_balance, \
        f"The miner balance should be {expected_leader_balance}, but it is {leader_balance}"
    assert user_balance == expected_user_balance, \
        f"The user balance should be {expected_user_balance}, but it is {user_balance}"
