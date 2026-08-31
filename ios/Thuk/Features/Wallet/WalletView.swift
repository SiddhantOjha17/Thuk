import SwiftUI

struct WalletView: View {
    @Environment(APIClient.self) private var api
    @State private var budget: BudgetResponse?
    @State private var debtSummary: DebtSummary?
    @State private var categories: [CategoryResponse] = []
    @State private var isLoading = true
    @State private var showBudgetEditor = false
    @State private var showAddCategory = false
    @State private var errorMessage: String?
    @State private var exportURL: URL?
    @State private var showShareSheet = false
    @State private var isExporting = false

    var body: some View {
        NavigationStack {
            ZStack {
                Color.thukBG.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 20) {
                        budgetSection
                        debtsSection
                        categoriesSection
                        exportSection
                    }
                    .padding(.bottom, 32)
                }
                .refreshable { await load() }
            }
            .navigationTitle("Wallet")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(Color.thukSurface, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .task { await load() }
        .sheet(isPresented: $showBudgetEditor) {
            BudgetEditorView(current: budget) { await load() }
        }
        .sheet(isPresented: $showAddCategory) {
            AddCategoryView { await load() }
        }
    }

    // MARK: - Budget

    private var budgetSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Monthly Budget")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(.white)
                Spacer()
                Button("Edit") { showBudgetEditor = true }
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(.thukAccent)
            }

            if isLoading {
                RoundedRectangle(cornerRadius: 8).fill(Color.thukSurfaceHi).frame(height: 80).shimmering()
            } else if let b = budget, let amount = b.amount {
                let pct    = min((b.percentUsed ?? 0) / 100.0, 1.0)
                let isOver = (b.percentUsed ?? 0) > 100
                let color: Color = isOver ? .thukDanger : (pct > 0.8 ? .thukWarning : .thukSuccess)

                VStack(spacing: 12) {
                    HStack(alignment: .bottom) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(b.spent.currencyDisplay(b.currency))
                                .font(.amountDisplay(28))
                                .foregroundStyle(.white)
                            Text("of \(amount.currencyDisplay(b.currency))")
                                .font(.system(size: 13))
                                .foregroundStyle(.thukSecondary)
                        }
                        Spacer()
                        VStack(alignment: .trailing, spacing: 4) {
                            Text(isOver ? "Over budget" : "\(Int((b.percentUsed ?? 0).rounded()))%")
                                .font(.system(size: 15, weight: .semibold))
                                .foregroundStyle(color)
                            if let rem = b.remaining, !isOver {
                                Text("\(rem.currencyDisplay(b.currency)) left")
                                    .font(.system(size: 13))
                                    .foregroundStyle(.thukSecondary)
                            }
                        }
                    }

                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 4).fill(Color.thukSurfaceHi).frame(height: 8)
                            RoundedRectangle(cornerRadius: 4)
                                .fill(color)
                                .frame(width: geo.size.width * pct, height: 8)
                                .animation(.easeOut(duration: 0.6), value: pct)
                        }
                    }
                    .frame(height: 8)
                }
            } else {
                Button { showBudgetEditor = true } label: {
                    HStack {
                        Text("Set a monthly budget")
                            .font(.system(size: 15))
                            .foregroundStyle(.thukSecondary)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.system(size: 13))
                            .foregroundStyle(.thukSecondary)
                    }
                    .padding(16)
                    .background(Color.thukSurfaceHi)
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(20)
        .surfaceCard()
        .padding(.horizontal, 20)
        .padding(.top, 8)
    }

    // MARK: - Debts

    private var debtsSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Splits & Debts")
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(.white)

            if isLoading {
                ForEach(0..<2, id: \.self) { _ in
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.thukSurfaceHi)
                        .frame(height: 60)
                        .shimmering()
                }
            } else if let debts = debtSummary?.debts, !debts.isEmpty {
                ForEach(debts) { debt in
                    DebtRow(debt: debt) {
                        await settleDebt(debt)
                    }
                }
            } else {
                Text("No pending debts.")
                    .font(.system(size: 14))
                    .foregroundStyle(.thukSecondary)
                    .padding(.vertical, 8)
            }
        }
        .padding(20)
        .surfaceCard()
        .padding(.horizontal, 20)
    }

    // MARK: - Categories

    private var categoriesSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("Categories")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(.white)
                Spacer()
                Button {
                    showAddCategory = true
                } label: {
                    Image(systemName: "plus")
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(.thukAccent)
                }
            }

            let columns = [GridItem(.adaptive(minimum: 80), spacing: 12)]
            LazyVGrid(columns: columns, spacing: 12) {
                ForEach(categories) { cat in
                    CategoryPill(category: cat) {
                        await deleteCategory(cat)
                    }
                }
            }
        }
        .padding(20)
        .surfaceCard()
        .padding(.horizontal, 20)
    }

    // MARK: - Export

    private var exportSection: some View {
        Button { exportCSV() } label: {
            HStack(spacing: 10) {
                if isExporting {
                    ProgressView().tint(.white).scaleEffect(0.8)
                } else {
                    Image(systemName: "arrow.down.doc")
                        .font(.system(size: 15, weight: .medium))
                }
                Text(isExporting ? "Exporting..." : "Export to CSV")
                    .font(.system(size: 15, weight: .medium))
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.thukSurface)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
        .buttonStyle(.plain)
        .disabled(isExporting)
        .padding(.horizontal, 20)
        .sheet(isPresented: $showShareSheet) {
            if let url = exportURL {
                ShareSheet(url: url)
            }
        }
    }

    // MARK: - Actions

    private func load() async {
        isLoading = true
        async let b  = fetchBudget()
        async let d  = fetchDebts()
        async let c  = fetchCategories()
        budget      = await b
        debtSummary = await d
        categories  = await c
        isLoading   = false
    }

    private func settleDebt(_ debt: DebtEntry) async {
        do {
            try await api.requestNoBody("/api/debts/\(debt.personName)/settle", method: "POST")
            await load()
        } catch {
            errorMessage = "Could not settle debt."
        }
    }

    private func deleteCategory(_ cat: CategoryResponse) async {
        guard !cat.isDefault else { return }
        do {
            try await api.requestNoBody("/api/categories/\(cat.id)", method: "DELETE")
            categories.removeAll { $0.id == cat.id }
        } catch {
            errorMessage = "Could not delete category."
        }
    }

    private func exportCSV() {
        isExporting = true
        Task {
            do {
                // Download CSV via authenticated request
                let data: Data = try await api.requestRawData("/api/export/csv")
                let tmp = FileManager.default.temporaryDirectory
                    .appendingPathComponent("thuk_expenses.csv")
                try data.write(to: tmp)
                exportURL = tmp
                showShareSheet = true
            } catch {
                errorMessage = "Export failed. Try again."
            }
            isExporting = false
        }
    }

    private func fetchBudget() async -> BudgetResponse? {
        try? await api.request("/api/budget")
    }
    private func fetchDebts() async -> DebtSummary? {
        try? await api.request("/api/debts")
    }
    private func fetchCategories() async -> [CategoryResponse] {
        (try? await api.request("/api/categories")) ?? []
    }
}

// MARK: - Debt row

private struct DebtRow: View {
    let debt: DebtEntry
    let onSettle: () async -> Void

    private var owesMe: Bool { debt.direction == "owes_me" }

    var body: some View {
        HStack(spacing: 12) {
            Rectangle()
                .fill(owesMe ? Color.thukSuccess : Color.thukDanger)
                .frame(width: 3)
                .clipShape(Capsule())

            VStack(alignment: .leading, spacing: 3) {
                Text(debt.personName)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(.white)
                Text(owesMe ? "Owes you" : "You owe")
                    .font(.system(size: 12))
                    .foregroundStyle(.thukSecondary)
                + Text(debt.count > 1 ? " · \(debt.count) debts" : "")
                    .font(.system(size: 12))
                    .foregroundStyle(.thukSecondary)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 6) {
                Text(debt.total.currencyDisplay(debt.currency))
                    .font(.amountLabel(15))
                    .foregroundStyle(owesMe ? Color.thukSuccess : Color.thukDanger)

                Button {
                    Task { await onSettle() }
                } label: {
                    Text("Settle")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 4)
                        .background(Color.thukAccent)
                        .clipShape(Capsule())
                }
                .buttonStyle(.plain)
            }
        }
        .padding(14)
        .background(Color.thukSurfaceHi)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

// MARK: - Category pill

private struct CategoryPill: View {
    let category: CategoryResponse
    let onDelete: () async -> Void
    @State private var showDeleteConfirm = false

    var body: some View {
        VStack(spacing: 6) {
            CategoryIcon(name: category.name, hexColor: category.color, size: 32)
            Text(category.name)
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(.thukSecondary)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(Color.thukSurfaceHi)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        .contextMenu {
            if !category.isDefault {
                Button(role: .destructive) {
                    showDeleteConfirm = true
                } label: {
                    Label("Delete", systemImage: "trash")
                }
            }
        }
        .confirmationDialog("Delete \(category.name)?", isPresented: $showDeleteConfirm) {
            Button("Delete", role: .destructive) { Task { await onDelete() } }
        }
    }
}

// MARK: - Budget editor sheet

private struct BudgetEditorView: View {
    let current: BudgetResponse?
    let onSave: () async -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var amountString: String = ""
    @State private var isLoading = false
    private let api = APIClient.shared

    var body: some View {
        NavigationStack {
            ZStack {
                Color.thukBG.ignoresSafeArea()
                VStack(spacing: 24) {
                    VStack(spacing: 6) {
                        Text(amountString.isEmpty ? "0" : amountString)
                            .font(.amountDisplay(52))
                            .foregroundStyle(amountString.isEmpty ? .thukSecondary : .white)
                            .contentTransition(.numericText())
                        Text("INR / month")
                            .font(.system(size: 13))
                            .foregroundStyle(.thukSecondary)
                    }
                    .padding(.top, 24)

                    AmountPad(amountString: $amountString)
                        .padding(.horizontal, 20)

                    PrimaryButton(title: "Set Budget", isLoading: isLoading) { save() }
                        .padding(.horizontal, 20)
                        .padding(.bottom, 24)
                }
            }
            .navigationTitle("Set Budget")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }.foregroundStyle(.thukSecondary)
                }
            }
            .toolbarBackground(Color.thukSurface, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .onAppear {
            if let amt = current?.amount { amountString = "\(amt)" }
        }
    }

    private func save() {
        guard let amount = Decimal(string: amountString), amount > 0 else { return }
        isLoading = true
        Task {
            let body = BudgetUpdate(amount: amount, currency: "INR")
            let _: BudgetResponse? = try? await api.request("/api/budget", method: "PUT", body: body)
            await onSave()
            isLoading = false
            dismiss()
        }
    }
}

// MARK: - Share sheet

private struct ShareSheet: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: [url], applicationActivities: nil)
    }
    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}

// MARK: - Add category sheet

private struct AddCategoryView: View {
    let onSave: () async -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var selectedColor = "6366F1"
    @State private var isLoading = false
    @State private var errorMessage: String?
    private let api = APIClient.shared

    private let palette = [
        "F97316", "38BDF8", "A78BFA", "FBBF24",
        "F472B6", "34D399", "9CA3AF", "6366F1",
        "EF4444", "14B8A6",
    ]

    var body: some View {
        NavigationStack {
            ZStack {
                Color.thukBG.ignoresSafeArea()
                VStack(spacing: 20) {
                    // Preview
                    CategoryIcon(name: name.isEmpty ? "Tag" : name, hexColor: selectedColor, size: 52)
                        .padding(.top, 24)

                    // Name
                    HStack(spacing: 12) {
                        Image(systemName: "tag")
                            .font(.system(size: 15, weight: .medium))
                            .foregroundStyle(.thukSecondary)
                        TextField("Category name", text: $name)
                            .font(.system(size: 16))
                            .foregroundStyle(.white)
                            .autocorrectionDisabled()
                    }
                    .padding(16)
                    .background(Color.thukSurface)
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                    .padding(.horizontal, 20)

                    // Color picker
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Color")
                            .font(.system(size: 13, weight: .medium))
                            .foregroundStyle(.thukSecondary)
                            .padding(.horizontal, 20)

                        LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 5), spacing: 12) {
                            ForEach(palette, id: \.self) { hex in
                                Circle()
                                    .fill(Color(hex: hex))
                                    .frame(width: 40, height: 40)
                                    .overlay(
                                        Circle()
                                            .strokeBorder(.white, lineWidth: selectedColor == hex ? 2 : 0)
                                    )
                                    .scaleEffect(selectedColor == hex ? 1.1 : 1)
                                    .onTapGesture {
                                        withAnimation(.spring(duration: 0.2)) {
                                            selectedColor = hex
                                        }
                                    }
                            }
                        }
                        .padding(.horizontal, 20)
                    }

                    if let err = errorMessage {
                        Text(err)
                            .font(.system(size: 13))
                            .foregroundStyle(.thukDanger)
                    }

                    Spacer()

                    PrimaryButton(title: "Add Category", isLoading: isLoading) { save() }
                        .padding(.horizontal, 20)
                        .padding(.bottom, 24)
                }
            }
            .navigationTitle("New Category")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }.foregroundStyle(.thukSecondary)
                }
            }
            .toolbarBackground(Color.thukSurface, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
    }

    private func save() {
        let trimmed = name.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { errorMessage = "Please enter a name."; return }
        isLoading = true
        errorMessage = nil
        Task {
            struct Body: Encodable { let name: String; let color: String }
            let _: CategoryResponse? = try? await api.request(
                "/api/categories", method: "POST",
                body: Body(name: trimmed, color: "#\(selectedColor)")
            )
            await onSave()
            isLoading = false
            dismiss()
        }
    }
}
