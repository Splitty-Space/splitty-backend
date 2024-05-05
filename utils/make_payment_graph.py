import heapq
from utils.entities.PaymentNode import PaymentNode

def make_payment_graph(balances):
    debtors_heap = []
    creditors_heap = []
    graph = []

    for user_balance in balances:
        if user_balance.final_balance > 0:
            heapq.heappush(creditors_heap, user_balance)
        if user_balance.final_balance < 0:
            heapq.heappush(debtors_heap, user_balance)

    while debtors_heap and creditors_heap:
        debtor = heapq.heappop(debtors_heap)
        creditor = heapq.heappop(creditors_heap)

        amount_transferred = min(-debtor.final_balance, creditor.final_balance)

        graph.append(PaymentNode(debtor.user_id, creditor.user_id, amount_transferred))

        debtor.final_balance += amount_transferred
        creditor.final_balance -= amount_transferred

        if debtor.final_balance != 0:
            heapq.heappush(debtors_heap, debtor)
        if creditor.final_balance != 0:
            heapq.heappush(creditors_heap, creditor)

    return graph

# node1 = Node("user1", -5)
# node2 = Node("user2", 5)
# node3 = Node("user3", 5)

# payment_graph = make_payment_graph([node1, node2, node3])
# for payment in payment_graph:
#   print(f"From: {payment.from_user}, To: {payment.to_user}, Amount: {payment.amount}")
