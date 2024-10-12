from user.dtos import UserInfo, TransactionInfo


class BuildTransactionInfo:
    def __init__(self, transaction):
        self.transaction = transaction

    def call(self):
        return TransactionInfo(
            id=self.transaction.id,
            debtor=UserInfo(id=self.transaction.debtor.id, username=self.transaction.debtor.username,
                              name=self.transaction.debtor.fullname,
                              photo_url=self.transaction.debtor.photo_url),
            borrower=UserInfo(id=self.transaction.borrower.id, username=self.transaction.borrower.username,
                            name=self.transaction.borrower.fullname,
                            photo_url=self.transaction.borrower.photo_url),
            amount=self.transaction.amount,
        )
