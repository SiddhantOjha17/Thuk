import SwiftUI

struct HomeView: View {
    var switchToChat: (() -> Void)? = nil
    @Environment(APIClient.self) private var api
    @State private var summary: AnalyticsSummary?
    @State private var recentExpenses: [ExpenseResponse] = []
    @State private var budget: BudgetResponse?
    @State private var isLoading = true
    @State private var showAddExpense = false

    private var monthRange: (start: String, end: String) {
        let now = Date.now
        return (now.startOfMonth.isoDate, now.endOfMonth.isoDate)
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Color.thukBG.ignoresSafeArea()

                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        // Header
                        headerSection
                            .padding(.horizontal, 20)
                            .padding(.top, 16)

                        // Monthly spend hero
                        spendHero
                            .padding(.horizontal, 20)
                            .padding(.top, 28)

                        // Budget bar (if set)
                        if let budget, budget.amount != nil {
                            budgetBar(budget)
                                .padding(.horizontal, 20)
                                .padding(.top, 20)
                        }

                        // Quick actions
                        quickActions
                            .padding(.horizontal, 20)
                            .padding(.top, 24)

                        // Recent transactions
                        recentSection
                            .padding(.top, 28)
                    }
                    .padding(.bottom, 24)
                }
                .refreshable { await loadAll() }
            }
            .navigationBarHidden(true)
        }
        .task { await loadAll() }
        .sheet(isPresented: $showAddExpense) {
            AddExpenseView()
        }
    }

    // MARK: - Sub-views

    private var headerSection: some View {
        HStack {
            VStack(alignment: .leading, spacing: 3) {
                Text(timeGreeting())
                    .font(.system(size: 13, weight: .regular))
                    .foregroundStyle(Color.thukSecondary)
                Text(api.currentUserName)
                    .font(.system(size: 22, weight: .bold))
                    .foregroundStyle(.white)
            }
            Spacer()
            Text(Date.now.monthYearDisplay)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(Color.thukSecondary)
        }
    }

    private var spendHero: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Spent this month")
                .font(.system(size: 13, weight: .regular))
                .foregroundStyle(Color.thukSecondary)

            if isLoading {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(Color.thukSurface)
                    .frame(width: 180, height: 56)
                    .shimmering()
            } else {
                Text((summary?.total ?? 0).currencyDisplay(summary?.currency ?? "INR"))
                    .font(.amountDisplay(48))
                    .foregroundStyle(.white)
                    .contentTransition(.numericText())
            }

            if let count = summary?.count, count > 0 {
                Text("\(count) transaction\(count == 1 ? "" : "s")")
                    .font(.system(size: 13))
                    .foregroundStyle(Color.thukSecondary)
            }
        }
    }

    private func budgetBar(_ b: BudgetResponse) -> some View {
        let pct = min((b.percentUsed ?? 0) / 100.0, 1.0)
        let isOver = (b.percentUsed ?? 0) > 100
        let barColor: Color = isOver ? Color.thukDanger : (pct > 0.8 ? Color.thukWarning : Color.thukAccent)

        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Budget")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(Color.thukSecondary)
                Spacer()
                if isOver {
                    Text("Over by \((b.spent - (b.amount ?? 0)).currencyDisplay(b.currency))")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(Color.thukDanger)
                } else if let rem = b.remaining {
                    Text("\(rem.currencyDisplay(b.currency)) left")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(Color.thukSecondary)
                }
            }

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4, style: .continuous)
                        .fill(Color.thukSurfaceHi)
                        .frame(height: 6)
                    RoundedRectangle(cornerRadius: 4, style: .continuous)
                        .fill(barColor)
                        .frame(width: geo.size.width * pct, height: 6)
                }
            }
            .frame(height: 6)
        }
        .padding(16)
        .surfaceCard()
    }

    private var quickActions: some View {
        HStack(spacing: 10) {
            QuickActionButton(title: "Add", icon: "plus") {
                showAddExpense = true
            }
            QuickActionButton(title: "Chat", icon: "bubble.left") {
                switchToChat?()
            }
        }
    }

    private var recentSection: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Recent")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(.white)
                Spacer()
                NavigationLink("See all") {
                    ExpenseListView()
                }
                .font(.system(size: 14))
                .foregroundStyle(Color.thukAccent)
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 12)

            if isLoading {
                ForEach(0..<4, id: \.self) { _ in
                    SkeletonRow()
                        .padding(.horizontal, 20)
                        .padding(.vertical, 6)
                }
            } else if recentExpenses.isEmpty {
                Text("No transactions yet. Add your first expense.")
                    .font(.system(size: 14))
                    .foregroundStyle(Color.thukSecondary)
                    .padding(.horizontal, 20)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(recentExpenses.prefix(5).enumerated()), id: \.element.id) { idx, exp in
                        TransactionRow(expense: exp)
                            .padding(.horizontal, 20)
                            .padding(.vertical, 10)
                        if idx < min(4, recentExpenses.count - 1) {
                            Divider()
                                .background(Color.thukSurfaceHi)
                                .padding(.leading, 68)
                        }
                    }
                }
                .surfaceCard()
                .padding(.horizontal, 20)
            }
        }
    }

    // MARK: - Data loading

    private func loadAll() async {
        isLoading = true
        async let summaryResult = fetchSummary()
        async let recentResult  = fetchRecent()
        async let budgetResult  = fetchBudget()
        summary         = await summaryResult
        recentExpenses  = await recentResult
        budget          = await budgetResult
        isLoading = false
    }

    private func fetchSummary() async -> AnalyticsSummary? {
        let r = monthRange
        return try? await api.request("/api/analytics/summary?start=\(r.start)&end=\(r.end)")
    }

    private func fetchRecent() async -> [ExpenseResponse] {
        (try? await api.request("/api/expenses?limit=5")) ?? []
    }

    private func fetchBudget() async -> BudgetResponse? {
        try? await api.request("/api/budget")
    }
}

// MARK: - Helper subviews

private struct QuickActionButton: View {
    let title: String
    let icon: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 15, weight: .medium))
                Text(title)
                    .font(.system(size: 14, weight: .medium))
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(Color.thukSurface)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

private struct SkeletonRow: View {
    var body: some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(Color.thukSurface)
                .frame(width: 36, height: 36)
                .shimmering()
            VStack(alignment: .leading, spacing: 6) {
                RoundedRectangle(cornerRadius: 4).fill(Color.thukSurface).frame(width: 120, height: 12).shimmering()
                RoundedRectangle(cornerRadius: 4).fill(Color.thukSurface).frame(width: 72, height: 10).shimmering()
            }
            Spacer()
            RoundedRectangle(cornerRadius: 4).fill(Color.thukSurface).frame(width: 56, height: 14).shimmering()
        }
    }
}


