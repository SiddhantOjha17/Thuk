import SwiftUI

// MARK: - Color palette

extension Color {
    static let thukBG         = Color(hex: "0C0C0E")
    static let thukSurface    = Color(hex: "1C1C1E")
    static let thukSurfaceHi  = Color(hex: "2C2C2E")
    static let thukAccent     = Color(hex: "6366F1")
    static let thukSecondary  = Color(hex: "8E8E93")
    static let thukSuccess    = Color(hex: "10B981")
    static let thukDanger     = Color(hex: "F43F5E")
    static let thukWarning    = Color(hex: "F59E0B")

    init(hex: String) {
        var s = hex.trimmingCharacters(in: .init(charactersIn: "#"))
        if s.count == 3 { s = s.flatMap { [$0, $0] }.map(String.init).joined() }
        var n: UInt64 = 0
        Scanner(string: s).scanHexInt64(&n)
        self.init(
            .sRGB,
            red:     Double((n >> 16) & 0xFF) / 255,
            green:   Double((n >>  8) & 0xFF) / 255,
            blue:    Double( n        & 0xFF) / 255,
            opacity: 1
        )
    }
}

// MARK: - Typography

extension Font {
    /// Large amount display — SF Pro Rounded Heavy
    static func amountDisplay(_ size: CGFloat = 52) -> Font {
        .system(size: size, weight: .heavy, design: .rounded)
    }
    /// Smaller amount in lists — SF Pro Rounded Semibold
    static func amountLabel(_ size: CGFloat = 17) -> Font {
        .system(size: size, weight: .semibold, design: .rounded)
    }
    static let sectionHeader = Font.system(size: 13, weight: .semibold)
    static let caption        = Font.system(size: 12, weight: .regular)
}

// MARK: - Category metadata

struct CategoryMeta: Identifiable {
    let id = UUID()
    let name: String
    let color: Color
    let hexColor: String
    let symbol: String

    static let all: [CategoryMeta] = [
        .init(name: "Food",          color: .init(hex: "F97316"), hexColor: "F97316", symbol: "fork.knife"),
        .init(name: "Transport",     color: .init(hex: "38BDF8"), hexColor: "38BDF8", symbol: "car.fill"),
        .init(name: "Shopping",      color: .init(hex: "A78BFA"), hexColor: "A78BFA", symbol: "bag.fill"),
        .init(name: "Bills",         color: .init(hex: "FBBF24"), hexColor: "FBBF24", symbol: "bolt.fill"),
        .init(name: "Entertainment", color: .init(hex: "F472B6"), hexColor: "F472B6", symbol: "play.fill"),
        .init(name: "Health",        color: .init(hex: "34D399"), hexColor: "34D399", symbol: "heart.fill"),
        .init(name: "Other",         color: .init(hex: "9CA3AF"), hexColor: "9CA3AF", symbol: "ellipsis"),
    ]

    static func find(name: String) -> CategoryMeta {
        all.first { $0.name.lowercased() == name.lowercased() }
            ?? .init(name: name, color: .init(hex: "9CA3AF"), hexColor: "9CA3AF", symbol: "tag.fill")
    }

    static func color(hex: String?) -> Color {
        guard let hex else { return .init(hex: "9CA3AF") }
        return .init(hex: hex)
    }
}
