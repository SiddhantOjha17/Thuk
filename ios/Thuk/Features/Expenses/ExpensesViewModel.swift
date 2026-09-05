import Foundation

enum ExpenseFilter: String, CaseIterable, Identifiable {
    case week = "Week", month = "Month", all = "All"
    var id: String { rawValue }

    var dateRange: (start: String, end: String)? {
        let cal = Calendar.current
        let now = Date.now
        switch self {
        case .week:
            let start = cal.date(byAdding: .day, value: -6, to: now)!
            return (start.isoDate, now.isoDate)
        case .month:
            return (now.startOfMonth.isoDate, now.endOfMonth.isoDate)
        case .all:
            return nil
        }
    }
}

@Observable
final class ExpensesViewModel {
    var expenses: [ExpenseResponse] = []
    var categories: [CategoryResponse] = []
    var filter: ExpenseFilter = .month
    var searchText: String = ""
    var isLoading = false
    var errorMessage: String?

    private let api = APIClient.shared

    var filtered: [ExpenseResponse] {
        guard searchText.isEmpty else {
            return expenses.filter {
                ($0.description ?? "").localizedCaseInsensitiveContains(searchText)
                || ($0.category?.name ?? "").localizedCaseInsensitiveContains(searchText)
            }
        }
        return expenses
    }

    /// Group expenses by date for sectioned list display
    var grouped: [(key: String, expenses: [ExpenseResponse])] {
        let dict = Dictionary(grouping: filtered) { $0.expenseDate.sectionHeader }
        return dict.map { ($0.key, $0.value) }
            .sorted { lhs, rhs in
                let lDate = filtered.first { $0.expenseDate.sectionHeader == lhs.key }?.expenseDate ?? .now
                let rDate = filtered.first { $0.expenseDate.sectionHeader == rhs.key }?.expenseDate ?? .now
                return lDate > rDate
            }
    }

    func load() async {
        isLoading = true
        errorMessage = nil
        async let expResult  = fetchExpenses()
        async let catResult  = fetchCategories()
        expenses   = await expResult
        categories = await catResult
        isLoading  = false
    }

    func delete(_ expense: ExpenseResponse) async {
        do {
            try await api.requestNoBody("/api/expenses/\(expense.id)", method: "DELETE")
            expenses.removeAll { $0.id == expense.id }
            notifyDataChanged()
        } catch {
            errorMessage = "Could not delete expense."
        }
    }

    func add(amount: Decimal, currency: String, description: String?, categoryId: UUID?, date: Date, splitPeople: [String]? = nil) async -> Bool {
        do {
            let body = ExpenseCreate(
                amount: amount, currency: currency,
                description: description?.isEmpty == true ? nil : description,
                categoryId: categoryId, expenseDate: date.isoDate,
                splitPeople: (splitPeople?.isEmpty == false) ? splitPeople : nil
            )
            let created: ExpenseResponse = try await api.request("/api/expenses", method: "POST", body: body)
            expenses.insert(created, at: 0)
            return true
        } catch {
            errorMessage = "Could not add expense."
            return false
        }
    }

    func update(_ expense: ExpenseResponse, amount: Decimal, description: String?, categoryId: UUID?, date: Date) async -> Bool {
        do {
            let body = ExpenseUpdate(
                amount: amount,
                description: description,
                categoryId: categoryId,
                expenseDate: date.isoDate
            )
            let updated: ExpenseResponse = try await api.request("/api/expenses/\(expense.id)", method: "PUT", body: body)
            if let idx = expenses.firstIndex(where: { $0.id == expense.id }) {
                expenses[idx] = updated
            }
            return true
        } catch {
            errorMessage = "Could not update expense."
            return false
        }
    }

    private func fetchExpenses() async -> [ExpenseResponse] {
        var path = "/api/expenses?limit=200"
        if let range = filter.dateRange {
            path += "&start=\(range.start)&end=\(range.end)"
        }
        return (try? await api.request(path)) ?? []
    }

    private func fetchCategories() async -> [CategoryResponse] {
        (try? await api.request("/api/categories")) ?? []
    }
}
