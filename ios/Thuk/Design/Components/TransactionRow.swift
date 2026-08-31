import SwiftUI

struct TransactionRow: View {
    let expense: ExpenseResponse

    var body: some View {
        HStack(spacing: 12) {
            CategoryIcon(
                name: expense.category?.name ?? "Other",
                hexColor: expense.category?.color
            )

            VStack(alignment: .leading, spacing: 3) {
                Text(expense.description ?? expense.category?.name ?? "Expense")
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(.white)
                    .lineLimit(1)

                Text(expense.expenseDate.shortDisplay)
                    .font(.caption)
                    .foregroundStyle(Color.thukSecondary)
            }

            Spacer()

            Text(expense.amount.currencyDisplay(expense.currency))
                .font(.amountLabel(15))
                .foregroundStyle(.white)
        }
        .padding(.vertical, 4)
    }
}
