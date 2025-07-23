class TransactionProcessingError(Exception):
    pass


class BusinessLogicError(TransactionProcessingError):
    pass


class TransactionSystemError(TransactionProcessingError):
    pass
