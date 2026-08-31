import SwiftUI

// MARK: - Decimal formatting

extension Decimal {
    /// "₹1,500" or "$20.00"
    func currencyDisplay(_ currency: String = "INR") -> String {
        let fmt = NumberFormatter()
        fmt.numberStyle = .currency
        fmt.currencyCode = currency
        if currency == "INR" {
            fmt.currencySymbol = "₹"
            fmt.groupingSeparator = ","
            fmt.groupingSize = 3
            fmt.secondaryGroupingSize = 2
            fmt.maximumFractionDigits = 0
        } else {
            fmt.maximumFractionDigits = 2
        }
        return fmt.string(from: self as NSDecimalNumber) ?? "\(currency) \(self)"
    }
}

// MARK: - Date formatting

extension Date {
    /// "Aug 31"
    var shortDisplay: String {
        let fmt = DateFormatter()
        fmt.dateFormat = "MMM d"
        return fmt.string(from: self)
    }

    /// "Today", "Yesterday", or "Mon, Aug 28"
    var sectionHeader: String {
        let cal = Calendar.current
        if cal.isDateInToday(self)     { return "Today" }
        if cal.isDateInYesterday(self) { return "Yesterday" }
        let fmt = DateFormatter()
        fmt.dateFormat = "EEE, MMM d"
        return fmt.string(from: self)
    }

    /// ISO8601 date-only string "2025-08-31"
    var isoDate: String {
        let fmt = DateFormatter()
        fmt.dateFormat = "yyyy-MM-dd"
        return fmt.string(from: self)
    }

    /// "August 2025"
    var monthYearDisplay: String {
        let fmt = DateFormatter()
        fmt.dateFormat = "MMMM yyyy"
        return fmt.string(from: self)
    }

    /// First day of this month
    var startOfMonth: Date {
        Calendar.current.date(from: Calendar.current.dateComponents([.year, .month], from: self))!
    }

    /// Last day of this month
    var endOfMonth: Date {
        var comps = DateComponents(); comps.month = 1; comps.day = -1
        return Calendar.current.date(byAdding: comps, to: startOfMonth)!
    }
}

// MARK: - Data refresh notification

extension Notification.Name {
    /// Posted whenever expenses, budget, or debts change so all tabs reload.
    static let dataDidChange = Notification.Name("thuk.dataDidChange")
}

func notifyDataChanged() {
    NotificationCenter.default.post(name: .dataDidChange, object: nil)
}

// MARK: - Time-aware greeting

func timeGreeting() -> String {
    let hour = Calendar.current.component(.hour, from: .now)
    switch hour {
    case 0..<12:  return "Good morning"
    case 12..<17: return "Good afternoon"
    default:      return "Good evening"
    }
}

// MARK: - View helpers

extension View {
    /// Applies a consistent surface card style.
    func surfaceCard() -> some View {
        self
            .background(Color.thukSurface)
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    /// Hides the view but keeps layout space.
    @ViewBuilder
    func hidden(_ hide: Bool) -> some View {
        if hide { self.hidden() } else { self }
    }

    /// Skeleton shimmer animation for loading states.
    func shimmering() -> some View {
        modifier(ShimmerModifier())
    }
}

struct ShimmerModifier: ViewModifier {
    @State private var phase: CGFloat = 0

    func body(content: Content) -> some View {
        content
            .overlay(
                LinearGradient(
                    gradient: Gradient(stops: [
                        .init(color: .clear,                  location: phase - 0.3),
                        .init(color: .white.opacity(0.07),    location: phase),
                        .init(color: .clear,                  location: phase + 0.3),
                    ]),
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .onAppear {
                withAnimation(.linear(duration: 1.4).repeatForever(autoreverses: false)) {
                    phase = 1.3
                }
            }
    }
}
