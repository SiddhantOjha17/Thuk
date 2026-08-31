import SwiftUI
import Charts

struct InsightsView: View {
    @State private var selectedDate = Date.now
    @State private var summary: AnalyticsSummary?
    @State private var daily: AnalyticsDaily?
    @State private var isLoading = true

    private let api = APIClient.shared

    var body: some View {
        NavigationStack {
            ZStack {
                Color.thukBG.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 20) {
                        monthPicker
                            .padding(.horizontal, 20)

                        if isLoading {
                            loadingPlaceholder
                        } else {
                            donutSection
                            dailySection
                            categoryList
                        }
                    }
                    .padding(.bottom, 24)
                }
                .refreshable { await load() }
            }
            .navigationTitle("Insights")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(Color.thukSurface, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .task { await load() }
        .onChange(of: selectedDate) { _, _ in Task { await load() } }
    }

    // MARK: - Month picker

    private var monthPicker: some View {
        HStack {
            Button {
                selectedDate = Calendar.current.date(byAdding: .month, value: -1, to: selectedDate)!
            } label: {
                Image(systemName: "chevron.left")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(.thukSecondary)
            }

            Spacer()

            Text(selectedDate.monthYearDisplay)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(.white)

            Spacer()

            Button {
                let next = Calendar.current.date(byAdding: .month, value: 1, to: selectedDate)!
                if next <= Date.now { selectedDate = next }
            } label: {
                Image(systemName: "chevron.right")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(
                        Calendar.current.date(byAdding: .month, value: 1, to: selectedDate)! > Date.now
                        ? Color.thukSurfaceHi : Color.thukSecondary
                    )
            }
            .disabled(Calendar.current.date(byAdding: .month, value: 1, to: selectedDate)! > Date.now)
        }
    }

    // MARK: - Donut chart

    private var donutSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .bottom) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Total spend")
                        .font(.system(size: 13))
                        .foregroundStyle(.thukSecondary)
                    Text((summary?.total ?? 0).currencyDisplay(summary?.currency ?? "INR"))
                        .font(.amountDisplay(32))
                        .foregroundStyle(.white)
                }
                Spacer()
                if let count = summary?.count {
                    Text("\(count) transactions")
                        .font(.system(size: 13))
                        .foregroundStyle(.thukSecondary)
                }
            }

            if let cats = summary?.byCategory, !cats.isEmpty {
                Chart(cats) { item in
                    SectorMark(
                        angle: .value("Amount", NSDecimalNumber(decimal: item.amount).doubleValue),
                        innerRadius: .ratio(0.58),
                        angularInset: 2
                    )
                    .foregroundStyle(Color(hex: item.color ?? "9CA3AF"))
                    }
                .frame(height: 200)
            } else {
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color.thukSurfaceHi)
                    .frame(height: 200)
                    .overlay(
                        Text("No data this month")
                            .font(.system(size: 14))
                            .foregroundStyle(.thukSecondary)
                    )
            }
        }
        .padding(20)
        .surfaceCard()
        .padding(.horizontal, 20)
    }

    // MARK: - Daily area chart

    private var dailySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Daily spend")
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(.white)

            if let days = daily?.days, !days.isEmpty {
                Chart(days) { day in
                    AreaMark(
                        x: .value("Date", day.date),
                        y: .value("Amount", NSDecimalNumber(decimal: day.amount).doubleValue)
                    )
                    .foregroundStyle(
                        LinearGradient(
                            colors: [Color.thukAccent.opacity(0.5), Color.thukAccent.opacity(0)],
                            startPoint: .top, endPoint: .bottom
                        )
                    )
                    LineMark(
                        x: .value("Date", day.date),
                        y: .value("Amount", NSDecimalNumber(decimal: day.amount).doubleValue)
                    )
                    .foregroundStyle(Color.thukAccent)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                }
                .chartXAxis {
                    AxisMarks(values: .stride(by: .day, count: 7)) { _ in
                        AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5)).foregroundStyle(Color.thukSurfaceHi)
                        AxisTick().foregroundStyle(Color.thukSurfaceHi)
                        AxisValueLabel().foregroundStyle(Color.thukSecondary)
                    }
                }
                .chartYAxis {
                    AxisMarks { _ in
                        AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5)).foregroundStyle(Color.thukSurfaceHi)
                        AxisValueLabel().foregroundStyle(Color.thukSecondary)
                    }
                }
                .frame(height: 160)
            } else {
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color.thukSurfaceHi)
                    .frame(height: 160)
            }
        }
        .padding(20)
        .surfaceCard()
        .padding(.horizontal, 20)
    }

    // MARK: - Category ranking list

    private var categoryList: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("By category")
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(.white)

            let cats = summary?.byCategory ?? []
            let max  = cats.map { NSDecimalNumber(decimal: $0.amount).doubleValue }.max() ?? 1

            ForEach(cats) { item in
                VStack(spacing: 6) {
                    HStack {
                        CategoryIcon(name: item.categoryName, hexColor: item.color, size: 28)
                        Text(item.categoryName)
                            .font(.system(size: 14, weight: .medium))
                            .foregroundStyle(.white)
                        Spacer()
                        Text(item.amount.currencyDisplay(summary?.currency ?? "INR"))
                            .font(.amountLabel(14))
                            .foregroundStyle(.white)
                    }
                    GeometryReader { geo in
                        let pct = NSDecimalNumber(decimal: item.amount).doubleValue / max
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 3).fill(Color.thukSurfaceHi).frame(height: 4)
                            RoundedRectangle(cornerRadius: 3)
                                .fill(Color(hex: item.color ?? "9CA3AF"))
                                .frame(width: geo.size.width * pct, height: 4)
                        }
                    }
                    .frame(height: 4)
                }
            }
        }
        .padding(20)
        .surfaceCard()
        .padding(.horizontal, 20)
    }

    // MARK: - Loading

    private var loadingPlaceholder: some View {
        VStack(spacing: 20) {
            ForEach(0..<2, id: \.self) { _ in
                RoundedRectangle(cornerRadius: 16)
                    .fill(Color.thukSurface)
                    .frame(height: 220)
                    .shimmering()
                    .padding(.horizontal, 20)
            }
        }
    }

    // MARK: - Data

    private func load() async {
        isLoading = true
        let start = selectedDate.startOfMonth.isoDate
        let end   = selectedDate.endOfMonth.isoDate
        async let s = fetchSummary(start: start, end: end)
        async let d = fetchDaily(start: start, end: end)
        summary = await s
        daily   = await d
        isLoading = false
    }

    private func fetchSummary(start: String, end: String) async -> AnalyticsSummary? {
        try? await api.request("/api/analytics/summary?start=\(start)&end=\(end)")
    }

    private func fetchDaily(start: String, end: String) async -> AnalyticsDaily? {
        try? await api.request("/api/analytics/daily?start=\(start)&end=\(end)")
    }
}
