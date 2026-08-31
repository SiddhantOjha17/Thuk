import SwiftUI

struct ExpenseListView: View {
    @State private var viewModel = ExpensesViewModel()
    @State private var showAdd = false
    @State private var editingExpense: ExpenseResponse?
    @State private var deleteTarget: ExpenseResponse?
    @State private var showDeleteConfirm = false

    var body: some View {
        NavigationStack {
            ZStack {
                Color.thukBG.ignoresSafeArea()

                VStack(spacing: 0) {
                    // Filter pills
                    filterBar

                    // Search
                    searchBar

                    // List
                    if viewModel.isLoading {
                        loadingState
                    } else if viewModel.filtered.isEmpty {
                        emptyState
                    } else {
                        expenseList
                    }
                }
            }
            .navigationTitle("Expenses")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showAdd = true
                    } label: {
                        Image(systemName: "plus")
                            .font(.system(size: 16, weight: .semibold))
                    }
                    .tint(Color.thukAccent)
                }
            }
            .toolbarBackground(Color.thukSurface, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .task { await viewModel.load() }
        .onChange(of: viewModel.filter) { _, _ in Task { await viewModel.load() } }
        .sheet(isPresented: $showAdd) {
            AddExpenseView(viewModel: viewModel)
        }
        .sheet(item: $editingExpense) { expense in
            AddExpenseView(viewModel: viewModel, editingExpense: expense)
        }
        .alert("Delete expense?", isPresented: $showDeleteConfirm) {
            Button("Delete", role: .destructive) {
                if let target = deleteTarget {
                    Task { await viewModel.delete(target) }
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            if let target = deleteTarget {
                Text(target.amount.currencyDisplay(target.currency) + (target.description.map { " · \($0)" } ?? ""))
            }
        }
    }

    // MARK: - Subviews

    private var filterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(ExpenseFilter.allCases) { f in
                    Button {
                        viewModel.filter = f
                    } label: {
                        Text(f.rawValue)
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(viewModel.filter == f ? .white : Color.thukSecondary)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 8)
                            .background(viewModel.filter == f ? Color.thukAccent : Color.thukSurface)
                            .clipShape(Capsule())
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
        }
    }

    private var searchBar: some View {
        HStack(spacing: 10) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 14, weight: .medium))
                .foregroundStyle(Color.thukSecondary)
            TextField("Search", text: $viewModel.searchText)
                .font(.system(size: 15))
                .foregroundStyle(.white)
                .autocorrectionDisabled()
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(Color.thukSurface)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .padding(.horizontal, 20)
        .padding(.bottom, 8)
    }

    private var expenseList: some View {
        List {
            ForEach(viewModel.grouped, id: \.key) { group in
                Section {
                    ForEach(group.expenses) { expense in
                        TransactionRow(expense: expense)
                            .listRowBackground(Color.thukSurface)
                            .listRowInsets(.init(top: 10, leading: 16, bottom: 10, trailing: 16))
                            .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                Button(role: .destructive) {
                                    deleteTarget = expense
                                    showDeleteConfirm = true
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                            }
                            .swipeActions(edge: .leading) {
                                Button {
                                    editingExpense = expense
                                } label: {
                                    Label("Edit", systemImage: "pencil")
                                }
                                .tint(Color.thukAccent)
                            }
                    }
                } header: {
                    Text(group.key)
                        .font(.sectionHeader)
                        .foregroundStyle(Color.thukSecondary)
                        .listRowInsets(.init(top: 16, leading: 20, bottom: 4, trailing: 20))
                }
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .background(Color.thukBG)
    }

    private var loadingState: some View {
        VStack(spacing: 16) {
            ForEach(0..<5, id: \.self) { _ in
                HStack(spacing: 12) {
                    RoundedRectangle(cornerRadius: 10).fill(Color.thukSurface).frame(width: 36, height: 36).shimmering()
                    VStack(alignment: .leading, spacing: 6) {
                        RoundedRectangle(cornerRadius: 4).fill(Color.thukSurface).frame(width: 120, height: 12).shimmering()
                        RoundedRectangle(cornerRadius: 4).fill(Color.thukSurface).frame(width: 72, height: 10).shimmering()
                    }
                    Spacer()
                    RoundedRectangle(cornerRadius: 4).fill(Color.thukSurface).frame(width: 56, height: 14).shimmering()
                }
                .padding(.horizontal, 20)
            }
            Spacer()
        }
        .padding(.top, 20)
    }

    private var emptyState: some View {
        VStack(spacing: 10) {
            Spacer()
            Text("No expenses found")
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(.white)
            Text(viewModel.searchText.isEmpty
                 ? "Add your first expense using the + button"
                 : "Try a different search term")
                .font(.system(size: 14))
                .foregroundStyle(Color.thukSecondary)
                .multilineTextAlignment(.center)
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }
}
