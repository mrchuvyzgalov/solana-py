from typing import List, Tuple

from blockchain import Block
from transaction import Transaction, Instruction, AccountMeta
from constants import BlockField, BlockchainField, DisconnectField, RebroadcastField, TxField, ShareBlockField, \
    SignatureField


class DeserializeService:
    @staticmethod
    def deserialize_tx(data: dict) -> Transaction:
        instructions = []
        for instr_data in data[TxField.INSTRUCTIONS]:
            accounts = [
                AccountMeta(
                    pubkey=acc["pubkey"],
                    is_signer=acc["is_signer"],
                    is_writable=acc["is_writable"]
                )
                for acc in instr_data["accounts"]
            ]
            instruction = Instruction(
                program_id=instr_data["program_id"],
                accounts=accounts,
                data=instr_data["data"]
            )
            instructions.append(instruction)

        recent_blockhash = data["recent_blockhash"]
        tx = Transaction(instructions=instructions, recent_blockhash=recent_blockhash)
        tx.signatures = data.get("signatures", {})
        return tx

    @staticmethod
    def deserialize_block(data: dict) -> Block:
        txs = [DeserializeService.deserialize_tx(tx) for tx in data[BlockField.TRANSACTIONS]]
        return Block(
            index=data[BlockField.INDEX],
            previous_hash=data[BlockField.PREVIOUS_HASH],
            transactions=txs,
            leader_id=data[BlockField.LEADER_ID],
            poh=data[BlockField.POH],
            validator_signatures=data[BlockField.VALIDATOR_SIGNATURES]
        )

    @staticmethod
    def deserialize_share_block(data: dict) -> (Block, str, int):
        block = DeserializeService.deserialize_block(data[ShareBlockField.BLOCK])
        host = data[ShareBlockField.HOST]
        port = int(data[ShareBlockField.PORT])
        return block, host, port

    @staticmethod
    def deserialize_signature(data: dict) -> (str, str):
        signature = data[SignatureField.SIGNATURE]
        address = data[SignatureField.SIGNATURE]
        return signature, address

    @staticmethod
    def deserialize_chain(data: dict) -> List[Block]:
        return [DeserializeService.deserialize_block(b) for b in data[BlockchainField.BLOCKS]]

    @staticmethod
    def deserialize_rebroadcast(data: dict) -> Tuple[str, int, Block]:
        block = DeserializeService.deserialize_block(data[RebroadcastField.BLOCK])
        return data[RebroadcastField.HOST], int(data[RebroadcastField.PORT]), block

    @staticmethod
    def deserialize_disconnect(data: dict) -> Tuple[str, int]:
        return data[DisconnectField.HOST], int(data[DisconnectField.PORT])
