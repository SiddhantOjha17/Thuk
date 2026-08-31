import Foundation

// MARK: - Auth

struct TokenResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String
}

struct UserResponse: Codable {
    let id: UUID
    let name: String
    let email: String
    let createdAt: Date
}

extension APIClient {
    func fetchAndStoreProfile() async {
        if let user: UserResponse = try? await request("/api/me") {
            currentUserName = user.name
            Keychain.set(user.name, key: "user_name")
        }
    }
}

// MARK: - Categories

struct CategoryResponse: Codable, Identifiable, Hashable {
    let id: UUID
    let name: String
    let color: String?
    let isDefault: Bool
}

// MARK: - Expenses

struct ExpenseResponse: Codable, Identifiable {
    let id: UUID
    let amount: Decimal
    let currency: String
    let description: String?
    let categoryId: UUID?
    let sourceType: String
    let expenseDate: Date
    let createdAt: Date
    var category: CategoryResponse?
}

struct ExpenseCreate: Encodable {
    let amount: Decimal
    let currency: String
    let description: String?
    let categoryId: UUID?
    let expenseDate: String  // ISO8601 date string "YYYY-MM-DD"
}

struct ExpenseUpdate: Encodable {
    var amount: Decimal?
    var currency: String?
    var description: String?
    var categoryId: UUID?
    var expenseDate: String?
}

// MARK: - Budget

struct BudgetResponse: Codable {
    let amount: Decimal?
    let currency: String
    let spent: Decimal
    let remaining: Decimal?
    let percentUsed: Double?
}

struct BudgetUpdate: Encodable {
    let amount: Decimal
    let currency: String
}

// MARK: - Debts

struct DebtEntry: Codable, Identifiable {
    let id: UUID
    let personName: String
    let total: Decimal
    let currency: String
    let direction: String   // "owes_me" | "i_owe"
    let count: Int
}

struct DebtSummary: Codable {
    let totalOwedToMe: Decimal
    let totalIOwe: Decimal
    let debts: [DebtEntry]
}

// MARK: - Analytics

struct CategoryAmount: Codable, Identifiable {
    var id: String { categoryName }
    let categoryName: String
    let amount: Decimal
    let color: String?
}

struct AnalyticsSummary: Codable {
    let total: Decimal
    let currency: String
    let count: Int
    let byCategory: [CategoryAmount]
    let startDate: Date
    let endDate: Date
}

struct DailyAmount: Codable, Identifiable {
    var id: Date { date }
    let date: Date
    let amount: Decimal
}

struct AnalyticsDaily: Codable {
    let currency: String
    let days: [DailyAmount]
    let startDate: Date
    let endDate: Date
}

// MARK: - Chat

struct ChatResponse: Codable {
    let response: String
    let expenseId: UUID?
}

// MARK: - API Error

enum APIError: LocalizedError {
    case unauthorized
    case conflict(String)
    case notFound
    case serverError(Int)
    case decodingFailed(Error)
    case network(Error)
    case noData

    var errorDescription: String? {
        switch self {
        case .unauthorized:       return "Session expired. Please log in again."
        case .conflict(let msg):  return msg
        case .notFound:           return "Not found."
        case .serverError(let c): return "Server error (\(c))."
        case .decodingFailed:     return "Unexpected server response."
        case .network:            return "Network unavailable."
        case .noData:             return "No data received."
        }
    }
}
