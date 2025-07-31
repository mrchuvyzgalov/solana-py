from enum import Enum


class MessageType:
    TX = "tx"
    SHARE_BLOCK = "share_block"
    REQUEST_CHAIN = "request_chain"
    CHAIN = "chain"
    CHOOSE_CREATOR = "choose_creator"
    REBROADCAST = "rebroadcast"
    FINALISE_BLOCK = "finalize_block"
    DISCONNECT = "disconnect"
    CREATOR = "creator"
    SIGNATURE = "signature"


class CreatorField:
    HOST = "host"
    PORT = "port"


class SignatureField:
    ADDRESS = "address"
    SIGNATURE = "signature"


class MessageField:
    TYPE = "type"
    DATA = "data"


class TxField:
    INSTRUCTIONS = "instructions"
    RECENT_BLOCKHASH = "recent_blockhash"
    SIGNATURES = "signatures"


class InstructionField:
    PROGRAM_ID = "program_id"
    ACCOUNTS = "accounts"
    DATA = "data"


class AccountMetaField:
    PUBKEY = "pubkey"
    IS_SIGNER = "is_signer"
    IS_WRITABLE = "is_writable"


class BlockField:
    INDEX = "index"
    PREVIOUS_HASH = "previous_hash"
    TRANSACTIONS = "transactions"
    LEADER_ID = "leader_id"
    TIMESTAMP = "timestamp"
    POH = "poh"
    VALIDATOR_SIGNATURES = "validator_signatures"


class ShareBlockField:
    BLOCK = "block"
    HOST = "host"
    PORT = "port"


class BlockchainField:
    BLOCKS = "blocks"


class DisconnectField:
    HOST = "host"
    PORT = "port"


class RebroadcastField:
    HOST = "host"
    PORT = "port"
    BLOCK = "block"


class Role(Enum):
    LEADER = "leader"
    USER = "user"


class Stage(Enum):
    TX = "tx"
    BLOCK = "block"
    MINING = "mining"


class Constants:
    TIME_TO_SLEEP = 10
    BLOCK_REWARD = 10