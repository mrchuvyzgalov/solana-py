import base64
import hashlib
from typing import List

from ecdsa import SigningKey, SECP256k1

from constants import Constants
from transaction import Transaction


class Block:
    def __init__(self, index, previous_hash, transactions, leader_id, poh, validator_signatures: dict):
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.leader_id = leader_id
        self.poh = poh
        self.validator_signatures = validator_signatures

        self._txs_hash = hashlib.sha256("".join(tx.hash() for tx in self.transactions).encode()).hexdigest()

    def hash(self):
        raw = f"{self.index}{self.previous_hash}{self.leader_id}{self.poh}{self._txs_hash}"
        raw += "".join(self.validator_signatures)
        return hashlib.sha256(raw.encode()).hexdigest()

    def hash_content(self):
        raw = f"{self.index}{self.previous_hash}{self.leader_id}{self.poh}{self._txs_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def sign_block(self, privkey_wif: str) -> str:
        sk = SigningKey.from_string(base64.b64decode(privkey_wif), curve=SECP256k1)
        message_hash = self.hash_content().encode()
        return base64.b64encode(sk.sign(message_hash)).decode()

    def add_signature(self, validator: str, signature: str):
        self.validator_signatures[validator] = signature

    def to_dict(self):
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "leader_id": self.leader_id,
            "poh": self.poh,
            "validator_signatures": self.validator_signatures
        }


def _initial_poh() -> str:
    return hashlib.sha256(b"genesis").hexdigest()


class Blockchain:
    def __init__(self):
        self.blocks: List[Block] = []
        self.accounts: dict[str, dict] = {}
        self.pending_txs: List[Transaction] = []
        self.last_poh = _initial_poh()
        self._create_genesis_block()

    def _generate_next_poh(self) -> str:
        next_poh = hashlib.sha256(self.last_poh.encode()).hexdigest()
        self.last_poh = next_poh
        return next_poh

    def validate_block(self, block) -> bool:
        if block.previous_hash != self.get_last_block().hash():
            return False

        expected_poh = self._peek_next_poh()
        if block.poh != expected_poh:
            print("❌ Block rejected: invalid PoH")
            return False
        return True

    def _peek_next_poh(self) -> str:
        return hashlib.sha256(self.last_poh.encode()).hexdigest()

    def _create_genesis_block(self):
        genesis = Block(0, "0" * 64, [], leader_id="genesis", poh=self._generate_next_poh(), validator_signatures={})
        self.blocks.append(genesis)

    def get_last_block(self) -> Block:
        return self.blocks[-1]

    def add_transaction(self, tx: Transaction) -> bool:
        self.pending_txs.append(tx)
        return True

    def apply_transaction(self, tx: Transaction):
        for instr in tx.instructions:
            if instr.program_id == "SystemProgram":
                self._execute_system_program(instr)

    def _execute_system_program(self, instr):
        sender = instr.accounts[0].pubkey
        receiver = instr.accounts[1].pubkey
        data = eval(instr.data)
        amount = data.get("amount")

        if self.accounts.get(sender, {}).get("balance", 0) >= amount:
            self.accounts[sender]["balance"] -= amount
            self.accounts.setdefault(receiver, {"balance": 0})
            self.accounts[receiver]["balance"] += amount

    def produce_block(self, leader_id: str) -> Block:
        poh = self._peek_next_poh()
        block = Block(
            index=len(self.blocks),
            previous_hash=self.get_last_block().hash(),
            transactions=self.pending_txs,
            leader_id=leader_id,
            poh=poh,
            validator_signatures={}
        )

        return block

    def add_external_block(self, block: Block) -> bool:
        if not self.validate_block(block):
            return False

        self.last_poh = block.poh

        for tx in block.transactions:
            self.apply_transaction(tx)
        self.blocks.append(block)
        self.pending_txs = []

        self.accounts.setdefault(block.leader_id, {"balance": 0})
        self.accounts[block.leader_id]["balance"] += Constants.BLOCK_REWARD

        return True

    def print_chain(self):
        for block in self.blocks:
            print(f"Block {block.index} | Hash: {block.hash()[:8]} | TXs: {len(block.transactions)} | Leader: {block.leader_id[:6]} | PoH: {block.poh[:6]}")

    def get_balance(self, address: str) -> float:
        return self.accounts.get(address, {}).get("balance", 0.0)

    def try_to_update_chain(self, blocks: List[Block]):
        if len(blocks) > len(self.blocks):
            self.blocks = blocks
            self.accounts = {}
            self.last_poh = _initial_poh()
            for block in self.blocks:
                self.last_poh = block.poh
                for tx in block.transactions:
                    self.apply_transaction(tx)
                self.accounts.setdefault(block.leader_id, {"balance": 0})
                self.accounts[block.leader_id]["balance"] += Constants.BLOCK_REWARD

    def to_dict(self):
        return {
            "blocks": [b.to_dict() for b in self.blocks]
        }