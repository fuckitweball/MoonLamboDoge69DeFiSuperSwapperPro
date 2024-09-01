from solana.rpc.api import Client

rpc = "yo_rpc_url_here"
client = Client(rpc)

wallets_map = {
    "Wallet 1": {
        "private_key": "pk1_here"
    },
    "Wallet 2":{
        "private_key": "pk2_here"
    },
    "Wallet 3":{
        "private_key": "pk3_here"
    }
}