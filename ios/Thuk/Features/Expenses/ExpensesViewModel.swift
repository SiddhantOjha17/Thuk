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
    var isLoadingMore = false
    var errorMessage: String?

    private let api = APIClient.shared
    private let pageSize = 50
    private var offset = 0
    private var hasMore = true

    /// Group expenses by date for sectioned list display.
    /// Search is applied server-side (see `fetchExpenses`) since the list is
    /// paginated — filtering only what's loaded so far would silently miss
    /// older matches the same way unbounded local loading used to.
    var grouped: [(key: String, expenses: [ExpenseResponse])] {
        let dict = Dictionary(grouping: expenses) { $0.expenseDate.sectionHeader }
        return dict.map { ($0.key, $0.value) }
            .sorted { lhs, rhs in
                let lDate = expenses.first { $0.expenseDate.sectionHeader == lhs.key }?.expenseDate ?? .now
                let rDate = expenses.first { $0.expenseDate.sectionHeader == rhs.key }?.expenseDate ?? .now
                return lDate > rDate
            }
    }

    func load() async {
        isLoading = true
        errorMessage = nil
        offset = 0
        hasMore = true
        async let expResult  = fetchExpenses(offset: 0)
        async let catResult  = fetchCategories()
        let fetched = await expResult
        expenses   = fetched
        categories = await catResult
        offset     = fetched.count
        hasMore    = fetched.count == pageSize
        isLoading  = false
    }

    /// Call from a row's `.onAppear` — fetches the next page once the user
    /// scrolls near the end of what's currently loaded.
    func loadMoreIfNeeded(currentItem: ExpenseResponse) {
        guard hasMore, !isLoadingMore else { return }
        guard let index = expenses.firstIndex(where: { $0.id == currentItem.id }) else { return }
        guard index >= expenses.count - 5 else { return }
        Task { await loadMore() }
    }

    private func loadMore() async {
        guard hasMore, !isLoadingMore else { return }
        isLoadingMore = true
        let next = await fetchExpenses(offset: offset)
        expenses.append(contentsOf: next)
        offset  += next.count
        hasMore  = next.count == pageSize
        isLoadingMore = false
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

    func add(amount: Decimal, currency: String, description: String?, categoryId: UUID?, date: Date, paymentMethod: PaymentMethod? = nil, tags: [String] = [], splitPeople: [String]? = nil) async -> Bool {
        do {
            let body = ExpenseCreate(
                amount: amount, currency: currency,
                description: description?.isEmpty == true ? nil : description,
                categoryId: categoryId, expenseDate: date.isoDate,
                paymentMethod: paymentMethod, tags: tags.isEmpty ? nil : tags,
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

    func update(_ expense: ExpenseResponse, amount: Decimal, description: String?, categoryId: UUID?, date: Date, paymentMethod: PaymentMethod? = nil, tags: [String] = []) async -> Bool {
        do {
            let body = ExpenseUpdate(
                amount: amount,
                description: description,
                categoryId: categoryId,
                expenseDate: date.isoDate,
                paymentMethod: paymentMethod,
                tags: tags
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

    private func fetchExpenses(offset: Int) async -> [ExpenseResponse] {
        var path = "/api/expenses?limit=\(pageSize)&offset=\(offset)"
        if let range = filter.dateRange {
            path += "&start=\(range.start)&end=\(range.end)"
        }
        if !searchText.isEmpty {
            let encoded = searchText.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? searchText
            path += "&q=\(encoded)"
        }
        return (try? await api.request(path)) ?? []
    }

    private func fetchCategories() async -> [CategoryResponse] {
        (try? await api.request("/api/categories")) ?? []
    }
}
