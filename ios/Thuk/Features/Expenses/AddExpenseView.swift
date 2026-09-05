import SwiftUI

struct AddExpenseView: View {
    @Environment(\.dismiss) private var dismiss
    var viewModel: ExpensesViewModel? = nil
    var onSave: (() -> Void)? = nil
    var editingExpense: ExpenseResponse? = nil

    @State private var amountString: String = ""
    @State private var description: String = ""
    @State private var selectedCategoryId: UUID? = nil
    @State private var expenseDate: Date = .now
    @State private var categories: [CategoryResponse] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var isSplitting = false
    @State private var splitPeople: [String] = [""]

    private let api = APIClient.shared

    private var amountDecimal: Decimal? {
        amountString.isEmpty ? nil : Decimal(string: amountString)
    }

    private var splitParticipants: [String] {
        splitPeople.map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
    }

    private var perPersonShare: Decimal? {
        guard let amount = amountDecimal, amount > 0 else { return nil }
        let count = Decimal(splitParticipants.count + 1)
        return amount / count
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Color.thukBG.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 24) {
                        // Amount display
                        amountDisplay

                        // Numpad
                        AmountPad(amountString: $amountString)
                            .padding(.horizontal, 20)

                        Divider()
                            .background(Color.thukSurfaceHi)
                            .padding(.horizontal, 20)

                        // Details
                        details

                        if let err = errorMessage {
                            Text(err)
                                .font(.system(size: 13))
                                .foregroundStyle(Color.thukDanger)
                                .padding(.horizontal, 20)
                        }

                        // Save
                        PrimaryButton(title: editingExpense == nil ? "Add Expense" : "Save Changes",
                                      isLoading: isLoading) {
                            save()
                        }
                        .padding(.horizontal, 20)
                        .padding(.bottom, 24)
                    }
                }
            }
            .navigationTitle(editingExpense == nil ? "New Expense" : "Edit Expense")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .foregroundStyle(Color.thukSecondary)
                }
            }
        }
        .task {
            categories = (try? await api.request("/api/categories")) ?? []
            if let exp = editingExpense {
                amountString = "\(exp.amount)"
                description  = exp.description ?? ""
                selectedCategoryId = exp.categoryId
                expenseDate  = exp.expenseDate
            }
        }
    }

    // MARK: - Amount display

    private var amountDisplay: some View {
        VStack(spacing: 4) {
            Text(amountString.isEmpty ? "0" : amountString)
                .font(.amountDisplay(56))
                .foregroundStyle(amountString.isEmpty ? Color.thukSecondary : .white)
                .contentTransition(.numericText())
                .animation(.easeInOut(duration: 0.1), value: amountString)
            Text("INR")
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(Color.thukSecondary)
        }
        .padding(.top, 20)
    }

    // MARK: - Details section

    private var details: some View {
        VStack(spacing: 12) {
            // Description
            HStack(spacing: 12) {
                Image(systemName: "text.alignleft")
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(Color.thukSecondary)
                    .frame(width: 20)
                TextField("Description (optional)", text: $description)
                    .font(.system(size: 16))
                    .foregroundStyle(.white)
            }
            .padding(16)
            .background(Color.thukSurface)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

            // Category
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    categoryChip(nil, name: "None")
                    ForEach(categories) { cat in
                        categoryChip(cat.id, name: cat.name, hexColor: cat.color)
                    }
                }
                .padding(.horizontal, 20)
            }

            // Date
            HStack(spacing: 12) {
                Image(systemName: "calendar")
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(Color.thukSecondary)
                    .frame(width: 20)
                DatePicker("Date", selection: $expenseDate, in: ...Date.now, displayedComponents: .date)
                    .labelsHidden()
                    .colorScheme(.dark)
                    .tint(Color.thukAccent)
                Spacer()
                Text(expenseDate.shortDisplay)
                    .font(.system(size: 15))
                    .foregroundStyle(Color.thukSecondary)
            }
            .padding(16)
            .background(Color.thukSurface)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

            if editingExpense == nil {
                splitSection
            }
        }
        .padding(.horizontal, 20)
    }

    // MARK: - Split section

    private var splitSection: some View {
        VStack(spacing: 12) {
            Toggle(isOn: $isSplitting.animation()) {
                HStack(spacing: 12) {
                    Image(systemName: "person.2")
                        .font(.system(size: 15, weight: .medium))
                        .foregroundStyle(Color.thukSecondary)
                        .frame(width: 20)
                    Text("Split with others")
                        .font(.system(size: 16))
                        .foregroundStyle(.white)
                }
            }
            .tint(Color.thukAccent)
            .padding(16)
            .background(Color.thukSurface)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

            if isSplitting {
                VStack(spacing: 8) {
                    ForEach(splitPeople.indices, id: \.self) { i in
                        HStack(spacing: 8) {
                            TextField("Person's name", text: $splitPeople[i])
                                .font(.system(size: 15))
                                .foregroundStyle(.white)
                            if splitPeople.count > 1 {
                                Button {
                                    splitPeople.remove(at: i)
                                } label: {
                                    Image(systemName: "minus.circle.fill")
                                        .foregroundStyle(Color.thukSecondary)
                                }
                            }
                        }
                        .padding(12)
                        .background(Color.thukSurface)
                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                    }

                    Button {
                        splitPeople.append("")
                    } label: {
                        Label("Add person", systemImage: "plus")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundStyle(Color.thukAccent)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 4)

                    if let share = perPersonShare, !splitParticipants.isEmpty {
                        Text("Your share: \(share.currencyDisplay()) · \(splitParticipants.count) \(splitParticipants.count == 1 ? "person" : "people") owe you")
                            .font(.system(size: 13))
                            .foregroundStyle(Color.thukSecondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 4)
                    }
                }
            }
        }
    }

    private func categoryChip(_ id: UUID?, name: String, hexColor: String? = nil) -> some View {
        let selected = selectedCategoryId == id
        return Button {
            selectedCategoryId = selected ? nil : id
        } label: {
            HStack(spacing: 6) {
                if let id {
                    CategoryIcon(name: name, hexColor: hexColor, size: 18)
                }
                Text(name)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(selected ? .white : Color.thukSecondary)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(selected ? Color.thukAccent : Color.thukSurface)
            .clipShape(Capsule())
        }
        .buttonStyle(.plain)
    }

    // MARK: - Save

    private func save() {
        guard let amount = amountDecimal, amount > 0 else {
            errorMessage = "Please enter an amount."
            return
        }
        isLoading = true
        errorMessage = nil
        let people = (isSplitting && !splitParticipants.isEmpty) ? splitParticipants : nil
        Task {
            let success: Bool
            if let editing = editingExpense, let vm = viewModel {
                success = await vm.update(editing, amount: amount, description: description.isEmpty ? nil : description, categoryId: selectedCategoryId, date: expenseDate)
            } else if let vm = viewModel {
                success = await vm.add(amount: amount, currency: "INR", description: description.isEmpty ? nil : description, categoryId: selectedCategoryId, date: expenseDate, splitPeople: people)
            } else {
                // Standalone (from HomeView)
                do {
                    let body = ExpenseCreate(amount: amount, currency: "INR", description: description.isEmpty ? nil : description, categoryId: selectedCategoryId, expenseDate: expenseDate.isoDate, splitPeople: people)
                    let _: ExpenseResponse = try await api.request("/api/expenses", method: "POST", body: body)
                    success = true
                } catch {
                    errorMessage = "Could not save expense."
                    success = false
                }
            }
            isLoading = false
            if success {
                UINotificationFeedbackGenerator().notificationOccurred(.success)
                notifyDataChanged()
                onSave?()
                dismiss()
            } else {
                errorMessage = viewModel?.errorMessage ?? "Could not save expense."
            }
        }
    }
}
