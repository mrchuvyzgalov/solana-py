import random
import socket
import threading
import json
import time
import queue
from typing import Optional

from blockchain import Blockchain, Block
from transaction import Transaction
from constants import MessageType, MessageField, Role, Stage, RebroadcastField, DisconnectField, Constants, \
    ShareBlockField, SignatureField
from wallet import load_wallet, pubkey_to_address, get_public_key
from deserialize_service import DeserializeService

def _get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

class SolanaNode:
    def __init__(self, host: str, port: int, role: Role, wallet_file="my_wallet.txt"):
        self._host = host
        self._port = port
        self.peers = set()
        self.blockchain = Blockchain()
        self.private_key = load_wallet(wallet_file)
        self.public_key = get_public_key(self.private_key)
        self.address = pubkey_to_address(self.public_key)
        self._discovery_port = 9000
        self._external_ip = _get_local_ip()
        self.role = role

        self.validators_nodes: set = set()
        self.stage: Stage = Stage.TX
        self._stage_lock = threading.Lock()

        self._temp_block: Optional[Block] = None

        self.message_queue = queue.Queue()

        self._mining_thread = None

        print(f"🟢 Node launched at {self._external_ip}:{self._port}")
        print(f"🏠 Wallet address: {self.address[:8]}...")

    def _set_stage(self, stage: Stage):
        with self._stage_lock:
            self.stage = stage

    def get_stage(self) -> Stage:
        with self._stage_lock:
            return self.stage

    def start(self):
        threading.Thread(target=self._listen_tcp, daemon=True).start()
        threading.Thread(target=self._listen_discovery, daemon=True).start()
        threading.Thread(target=self._broadcast_presence, daemon=True).start()
        threading.Thread(target=self._process_message_queue, daemon=True).start()

        self._mining_thread = threading.Thread(target=self._broadcast_mining, daemon=True)
        self._mining_thread.start()

    def _process_message_queue(self):
        while True:
            time.sleep(0.0000001)
            message = self.message_queue.get()
            try:
                self._handle_message(message)
            except Exception as e:
                print(f"❌ Error handling message: {e}")

    def disconnect(self):
        self._broadcast_disconnect()

    def verify_and_add_block(self, block):
        if self.blockchain.add_external_block(block):
            return True
        return False

    def _listen_tcp(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((self._host, self._port))
        sock.listen()
        print("📥 Waiting for TCP connections...")
        while True:
            conn, _ = sock.accept()
            threading.Thread(target=self._handle_tcp_connection, args=(conn,), daemon=True).start()

    def _handle_tcp_connection(self, conn):
        try:
            buffer = b""
            while True:
                chunk = conn.recv(10000)
                if not chunk:
                    break
                buffer += chunk
            data = buffer.decode()
            message = json.loads(data)
            self.message_queue.put(message)
        except Exception as e:
            print("❌ TCP error:", e)
        finally:
            conn.close()

    def _handle_message(self, message: dict):
        msg_type = message.get(MessageField.TYPE)
        data = message.get(MessageField.DATA)

        if msg_type == MessageType.TX:
            tx = DeserializeService.deserialize_tx(data)
            self.blockchain.add_transaction(tx)

        elif msg_type == MessageType.FINALISE_BLOCK:
            self._temp_block = None
            block = DeserializeService.deserialize_block(data)
            if self.verify_and_add_block(block):
                self._set_stage(Stage.TX)

            self._mining_thread = threading.Thread(target=self._broadcast_mining, daemon=True)
            self._mining_thread.start()

        elif msg_type == MessageType.SIGNATURE:
            signature, address = DeserializeService.deserialize_signature(data)
            self._temp_block.add_signature(address, signature=signature)

            self._try_finalize_block()

        elif msg_type == MessageType.SHARE_BLOCK:
            self._set_stage(Stage.MINING)
            block, ip, port = DeserializeService.deserialize_share_block(data)

            if self.role == Role.LEADER and self.blockchain.validate_block(block):
                signature = block.sign_block(self.private_key)

                if ip == self._external_ip and port == self._port:
                    message = {
                        MessageField.TYPE: MessageType.SIGNATURE,
                        MessageField.DATA: {
                            SignatureField.SIGNATURE: signature,
                            SignatureField.ADDRESS: self.address
                        }
                    }
                    self.message_queue.put(message)
                else:
                    self._broadcast_signature(f"{ip}:{port}", signature)

        elif msg_type == MessageType.REQUEST_CHAIN:
            self._broadcast_chain()

        elif msg_type == MessageType.CHAIN:
            blocks = DeserializeService.deserialize_chain(data)
            self.blockchain.try_to_update_chain(blocks)

        elif msg_type == MessageType.CREATOR:
            self._set_stage(Stage.MINING)
            if self.role == Role.LEADER:
                self._temp_block = self.blockchain.produce_block(self.address)

                self._broadcast_block(self._temp_block)
                self.message_queue.put({
                    MessageField.TYPE: MessageType.SHARE_BLOCK,
                    MessageField.DATA: {
                        ShareBlockField.BLOCK: self._temp_block.to_dict(),
                        ShareBlockField.HOST: self._external_ip,
                        ShareBlockField.PORT: self._port
                    }
                })

        elif msg_type == MessageType.CHOOSE_CREATOR:
            self._set_stage(Stage.MINING)

            if self._is_leader():
                creator = self._choose_creator()
                ip, port = creator.split(":")
                port = int(port)

                message = { MessageField.TYPE: MessageType.CREATOR }

                if ip == self._external_ip and port == self._port:
                    self.message_queue.put(message)
                else:
                    self._broadcast_to_user(message, creator)

        elif msg_type == MessageType.DISCONNECT:
            peer_to_remove = DeserializeService.deserialize_disconnect(data)
            self.peers.remove(peer_to_remove)

        else:
            print("⚠️ Unknown message type:", msg_type)

    def _try_finalize_block(self):
        if 3 * len(self._temp_block.validator_signatures) >= 2 * (len(self.validators_nodes) + 1):
            self._finalize_block(self._temp_block)
            self.message_queue.put({
                MessageField.TYPE: MessageType.FINALISE_BLOCK,
                MessageField.DATA: self._temp_block.to_dict()
            })

    def _choose_creator(self) -> str:
        if self.role == Role.LEADER:
            return random.choice(list(self.validators_nodes) + [f"{self._external_ip}:{self._port}"])
        else:
            return random.choice(list(self.validators_nodes))

    def _finalize_block(self, block: Block):
        self._broadcast({
            MessageField.TYPE: MessageType.FINALISE_BLOCK,
            MessageField.DATA: block.to_dict()
        })

    def _broadcast_signature(self, peer: str, signature: str):
        message = {
            MessageField.TYPE: MessageType.SIGNATURE,
            MessageField.DATA: {
                SignatureField.SIGNATURE: signature,
                SignatureField.ADDRESS: self.address
            }
        }
        self._broadcast_to_user(message, peer)

    def _broadcast_to_user(self, message: dict, peer: str):
        raw = json.dumps(message).encode()
        ip, port = peer.split(":")
        try:
            with socket.socket() as s:
                s.connect((ip, int(port)))
                s.send(raw)
        except Exception as e:
            print(f"❌ Failed to send {message['type']} → {peer}: {e}")

    def _rebroadcast_block(self, block: Block):
        self._broadcast({
            MessageField.TYPE: MessageType.REBROADCAST,
            MessageField.DATA: {
                RebroadcastField.HOST: self._external_ip,
                RebroadcastField.PORT: self._port,
                RebroadcastField.BLOCK: block.to_dict()
            },
        })

    def _broadcast_request_chain(self):
        self._broadcast({
            MessageField.TYPE: MessageType.REQUEST_CHAIN
        })

    def _broadcast_disconnect(self):
        self._broadcast({
            MessageField.TYPE: MessageType.DISCONNECT,
            MessageField.DATA: {
                DisconnectField.HOST: self._external_ip,
                DisconnectField.PORT: self._port
            }
        })

    def _broadcast(self, message: dict):
        raw = json.dumps(message).encode()
        for peer in self.peers.copy():
            try:
                with socket.socket() as s:
                    s.connect(peer)
                    s.send(raw)
            except Exception as e:
                print(f"❌ Failed to send {message['type']} → {peer}: {e}")

    def _broadcast_chain(self):
        self._broadcast({
            MessageField.TYPE: MessageType.CHAIN,
            MessageField.DATA: self.blockchain.to_dict()})

    def broadcast_transaction(self, tx: Transaction):
        self._broadcast({
            MessageField.TYPE: MessageType.TX,
            MessageField.DATA: tx.to_dict()
        })

    def _broadcast_block(self, block):
        self._broadcast({
            MessageField.TYPE: MessageType.SHARE_BLOCK,
            MessageField.DATA: {
                ShareBlockField.BLOCK: block.to_dict(),
                ShareBlockField.HOST: self._external_ip,
                ShareBlockField.PORT: self._port
            }
        })

    def add_and_broadcast_tx(self, tx: Transaction) -> bool:
        if self.get_stage() == Stage.TX and self.blockchain.add_transaction(tx):
            self.broadcast_transaction(tx)
            return True
        return False

    def _listen_discovery(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('', self._discovery_port))
        while True:
            data, addr = sock.recvfrom(1024)
            if data == b"DISCOVER":
                response = f"{self._external_ip}:{self._port}:{self.role == Role.LEADER}"
                sock.sendto(response.encode(), addr)

    def _broadcast_mining(self):
        time.sleep(Constants.TIME_TO_SLEEP)
        if self._is_leader():
            message = {MessageField.TYPE: MessageType.CHOOSE_CREATOR}
            self._broadcast(message)
            if self.role == Role.LEADER:
                self.message_queue.put(message)

    def _broadcast_presence(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            try:
                sock.sendto(b"DISCOVER", ('<broadcast>', self._discovery_port))
                sock.settimeout(0.0000001)
                while True:
                    try:
                        data, addr = sock.recvfrom(1024)
                        peer_host, peer_port, is_leader = data.decode().split(":")
                        if peer_host == self._external_ip and int(peer_port) == self._port:
                            continue
                        peer = (peer_host, int(peer_port))
                        self.peers.add(peer)

                        full_ip = f"{peer_host}:{peer_port}"

                        if is_leader == "True":
                            if full_ip not in self.validators_nodes:
                                self.validators_nodes.add(full_ip)
                        else:
                            self.validators_nodes.discard(full_ip)

                        if len(self.blockchain.blocks) == 1:
                            self._broadcast_request_chain()
                    except socket.timeout:
                        break
            except Exception as e:
                print("Error during UDP discovery:", e)
            time.sleep(5)

    def _is_leader(self) -> bool:
        my_id = f"{self._external_ip}:{self._port}"
        peer_ids = [f"{host}:{port}" for (host, port) in self.peers]
        return my_id == min([my_id] + peer_ids)
