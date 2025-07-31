import hashlib
import json
import base64
import ecdsa
from typing import List

class AccountMeta:
    def __init__(self, pubkey: str, is_signer: bool, is_writable: bool):
        self.pubkey = pubkey
        self.is_signer = is_signer
        self.is_writable = is_writable

    def to_dict(self):
        return {
            "pubkey": self.pubkey,
            "is_signer": self.is_signer,
            "is_writable": self.is_writable
        }

class Instruction:
    def __init__(self, program_id: str, accounts: List[AccountMeta], data: str):
        self.program_id = program_id
        self.accounts = accounts
        self.data = data

    def to_dict(self):
        return {
            "program_id": self.program_id,
            "accounts": [acc.to_dict() for acc in self.accounts],
            "data": self.data
        }

class Transaction:
    def __init__(self, instructions: List[Instruction], recent_blockhash: str = None):
        self.instructions = instructions
        self.recent_blockhash = recent_blockhash
        self.signatures = {}

    def to_dict(self, include_signatures=True):
        return {
            "recent_blockhash": self.recent_blockhash,
            "instructions": [instr.to_dict() for instr in self.instructions],
            "signatures": self.signatures if include_signatures else {}
        }

    def to_json(self, include_signatures=True):
        return json.dumps(self.to_dict(include_signatures), sort_keys=True)

    def hash(self) -> str:
        return hashlib.sha256(self.to_json(include_signatures=False).encode()).hexdigest()

    def sign(self, privkey_base64: str):
        sk = ecdsa.SigningKey.from_string(base64.b64decode(privkey_base64), curve=ecdsa.SECP256k1)
        pubkey = base64.b64encode(sk.get_verifying_key().to_string()).decode()
        signature = sk.sign(self.hash().encode())
        self.signatures[pubkey] = base64.b64encode(signature).decode()

    def verify(self) -> bool:
        for pubkey, signature in self.signatures.items():
            try:
                vk = ecdsa.VerifyingKey.from_string(base64.b64decode(pubkey), curve=ecdsa.SECP256k1)
                vk.verify(base64.b64decode(signature), self.hash().encode())
            except ecdsa.BadSignatureError:
                return False
        return True
