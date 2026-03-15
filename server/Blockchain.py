from Block import Block


class Blockchain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.createGenesisBlock()

    def createGenesisBlock(self):
        if self.chain:
            return self.chain[0]
        genesis_block = Block("0", []).constructor(previous_hash="0")
        self.chain.append(genesis_block)
        return genesis_block

    def getLatestBlock(self):
        if self.chain:
            return self.chain[-1]
        return None

    def addPendingTransaction(self, transaction):
        if not transaction.validate():
            transaction.markFailed("Transaction validation failed")
            return False
        transaction.markPending()
        self.pending_transactions.append(transaction)
        return True

    def propposeBlock(self):
        latest_block = self.getLatestBlock()
        previous_hash = latest_block.hash if latest_block else "0"
        block = Block(str(len(self.chain)), list(self.pending_transactions))
        block.sealBlock(previous_hash)
        return block

    def validateBlock(self, block):
        previous_hash = "0"
        if block in self.chain:
            block_index = self.chain.index(block)
            if block_index > 0:
                previous_hash = self.chain[block_index - 1].hash
        else:
            latest_block = self.getLatestBlock()
            previous_hash = latest_block.hash if latest_block else "0"
        return block.isValid(previous_hash)

    def addBlock(self, block):
        if not self.validateBlock(block):
            return False
        self.chain.append(block)
        for transaction in block.transactions:
            transaction.markConfirmed(block.hash)
        confirmed_ids = {transaction.transaction_id for transaction in block.transactions}
        self.pending_transactions = [
            transaction
            for transaction in self.pending_transactions
            if transaction.transaction_id not in confirmed_ids
        ]
        return True

    def minePendingTransactions(self):
        if not self.pending_transactions:
            return None
        block = self.propposeBlock()
        self.addBlock(block)
        return block

    def getTransactionHistory(self, address):
        history = []
        for block in self.chain:
            for transaction in block.transactions:
                if transaction.sender == address or transaction.receiver == address:
                    history.append(transaction)
        for transaction in self.pending_transactions:
            if transaction.sender == address or transaction.receiver == address:
                history.append(transaction)
        return history

    def getWalletBalance(self, address):
        balance = 0.0
        for transaction in self.getTransactionHistory(address):
            if transaction.receiver == address:
                balance += transaction.amount
            if transaction.sender == address:
                balance -= transaction.amount
        return balance