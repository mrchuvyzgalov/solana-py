import hashlib

from blockchain import Block, Blockchain
from constants import Constants
from transaction import Instruction, AccountMeta, Transaction
from wallet import generate_keypair


def create_transaction(amount=10):
    priv, pub = generate_keypair()
    receiver_priv, receiver_pub = generate_keypair()
    instr = Instruction(
        "SystemProgram",
        [AccountMeta(pub, True, True), AccountMeta(receiver_pub, False, True)],
        data=str({"amount": amount})
    )
    tx = Transaction([instr])
    return tx, pub, priv, receiver_pub

def test_block_creation_and_hash():
    tx, pub, priv, _ = create_transaction()
    poh = hashlib.sha256(b"genesis").hexdigest()
    block = Block(0, "0" * 64, [tx], leader_id=pub, poh=poh, validator_signatures={})
    assert isinstance(block.hash(), str)
    assert len(block.hash()) == 64


def test_block_sign_and_add_signature():
    tx, pub, priv, _ = create_transaction()
    poh = hashlib.sha256(b"genesis").hexdigest()
    block = Block(0, "0" * 64, [tx], leader_id=pub, poh=poh, validator_signatures={})
    signature = block.sign_block(priv)
    block.add_signature(pub, signature)
    assert pub in block.validator_signatures
    assert isinstance(signature, str)

def test_blockchain_add_transaction_and_balance_update():
    blockchain = Blockchain()
    tx, sender, priv, receiver = create_transaction(amount=25)
    blockchain.accounts[sender] = {"balance": 50}
    blockchain.accounts[receiver] = {"balance": 10}
    blockchain.add_transaction(tx)

    block = blockchain.produce_block(sender)
    sig = block.sign_block(priv)
    block.add_signature(sender, sig)
    added = blockchain.add_external_block(block)

    assert added
    assert blockchain.get_balance(sender) == 25 + Constants.BLOCK_REWARD
    assert blockchain.get_balance(receiver) == 35

def test_blockchain_rejects_invalid_poh():
    blockchain = Blockchain()
    tx, sender, priv, _ = create_transaction()
    blockchain.accounts[sender] = {"balance": 50}
    blockchain.add_transaction(tx)

    block = blockchain.produce_block(sender)
    block.poh = "invalid_poh"

    assert not blockchain.add_external_block(block)

def test_blockchain_chain_length_increases():
    blockchain = Blockchain()
    tx, sender, priv, _ = create_transaction()
    blockchain.accounts[sender] = {"balance": 100}
    blockchain.add_transaction(tx)

    old_len = len(blockchain.blocks)
    block = blockchain.produce_block(sender)
    sig = block.sign_block(priv)
    block.add_signature(sender, sig)

    blockchain.add_external_block(block)
    new_len = len(blockchain.blocks)
    assert new_len == old_len + 1

def test_blockchain_to_dict_structure():
    blockchain = Blockchain()
    result = blockchain.to_dict()
    assert isinstance(result, dict)
    assert "blocks" in result
    assert isinstance(result["blocks"], list)